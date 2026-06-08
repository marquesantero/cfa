"""Integration and DecisionSink protocols.

An *integration* is the bridge between CFA and an external toolchain:
dbt manifests, Airflow DAGs, GitHub PR diffs, Terraform plans, LangGraph
states, Databricks Jobs, Kubernetes admission events. An integration
translates a tool-native input into one or more :class:`StateSignature`
instances for a known vertical, runs them through the kernel, and
(optionally) surfaces the decisions back to the tool's natural channel.

A *decision sink* is the symmetric idea on the output side: it receives
:class:`KernelResult` events and emits them somewhere — stdout, OTel
span exporter, Slack webhook, GitHub PR comment, JIRA ticket creator,
audit log writer.

The two contracts compose: one integration may produce signatures that
flow through the kernel, and many sinks may emit the decisions. Neither
contract depends on kernel internals; both depend on the public types
from :mod:`cfa.types`.

See ADR-0010 for the full design rationale.

Example minimal integration::

    from cfa.core.integration import Integration, IntegrationRegistry
    from cfa.types import KernelResult, StateSignature

    class MyIntegration:
        name = "my-tool"
        consumes = ["my-tool-output"]
        produces = "data"

        def build_signatures(self, raw):
            return [StateSignature.from_dict(raw)]

        def emit_decisions(self, results):
            for r in results:
                print(r.summary())

    IntegrationRegistry.singleton().register(MyIntegration())

Example minimal decision sink::

    from cfa.core.integration import DecisionSink

    class StdoutJsonSink:
        name = "stdout-json"

        def emit(self, result):
            print(result.to_json())

        def flush(self):
            pass
"""

from __future__ import annotations

import warnings
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from cfa.types import KernelResult, StateSignature


# ── Errors ───────────────────────────────────────────────────────────────────


class IntegrationInputError(ValueError):
    """Raised by an integration when its input is malformed.

    Carries the offending location (a free-form string — usually a JSON
    Pointer or a file:line reference) so the CLI can surface it next to
    the user-supplied input.
    """

    def __init__(self, location: str, message: str) -> None:
        super().__init__(f"{location}: {message}")
        self.location = location
        self.message = message


# ── Protocols ────────────────────────────────────────────────────────────────


@runtime_checkable
class Integration(Protocol):
    """Structural contract for every CFA integration.

    Implementations may inherit or simply provide the same attributes and
    methods (Protocol structural typing). Integrations are expected to be
    cheap to construct — heavy I/O should happen inside
    :meth:`build_signatures`, not in ``__init__``.
    """

    #: Globally unique, machine-readable slug. Examples:
    #: ``"dbt-check"``, ``"terraform-check"``, ``"github-pr"``.
    name: str

    #: Input format identifiers the integration knows how to consume.
    #: Examples: ``["dbt-manifest"]``, ``["tfplan-json"]``,
    #: ``["github-pr-diff", "github-pr-files"]``.
    consumes: list[str]

    #: Name of the vertical the produced signatures target.
    #: Examples: ``"data"``, ``"infra"``, ``"agent"``.
    produces: str

    def build_signatures(self, raw: Any) -> list[StateSignature]:
        """Translate a tool-native input into one or more StateSignatures.

        Raises:
            IntegrationInputError: when ``raw`` is malformed. The error
                carries the offending location so the CLI can surface it
                clearly.
        """
        ...

    def emit_decisions(self, results: list[KernelResult]) -> None:
        """Surface decisions back to the integration's natural channel.

        Optional behavior: integrations that only translate input may
        provide a no-op implementation. The kernel never asserts that
        this method does anything observable.
        """
        ...


@runtime_checkable
class DecisionSink(Protocol):
    """Structural contract for a decision sink.

    Sinks are wired separately from integrations. The same decision can
    flow into multiple sinks simultaneously (stdout + OTel + Slack) with
    no coordination between them.

    Sink failures are *logged*, not propagated. Decision processing must
    remain authoritative even if a downstream sink is unavailable; sinks
    that require reliability should implement retries internally.
    """

    #: Globally unique slug. Examples: ``"stdout-json"``, ``"otel-span"``,
    #: ``"slack-webhook"``, ``"github-pr-comment"``.
    name: str

    def emit(self, result: KernelResult) -> None:
        """Emit a decision to this sink."""
        ...

    def flush(self) -> None:
        """Block until any buffered decisions are delivered. Optional."""
        ...


# ── Registries ───────────────────────────────────────────────────────────────


_INTEGRATION_GROUP = "cfa.integrations"
_SINK_GROUP = "cfa.decision_sinks"


class _BaseRegistry:
    """Shared lazy-discovery plumbing for integration and sink registries."""

    _entry_point_group: str = ""
    _kind: str = "object"

    def __init__(self) -> None:
        self._items: dict[str, Any] = {}
        self._discovered: bool = False

    # Public introspection -----------------------------------------------------

    def list(self) -> list[str]:
        self._ensure_discovered()
        return sorted(self._items)

    def __contains__(self, name: object) -> bool:
        self._ensure_discovered()
        return name in self._items

    def __iter__(self) -> Iterator[Any]:
        self._ensure_discovered()
        yield from self._items.values()

    # Internal -----------------------------------------------------------------

    def _ensure_discovered(self) -> None:
        if self._discovered:
            return
        self._discovered = True
        try:
            from importlib.metadata import entry_points
        except ImportError:  # pragma: no cover
            return
        try:
            eps = entry_points(group=self._entry_point_group)
        except TypeError:
            eps = entry_points().get(self._entry_point_group, [])  # type: ignore[attr-defined]
        for ep in eps:
            self._load_entry_point(ep)

    def _load_entry_point(self, ep: Any) -> None:
        try:
            loaded = ep.load()
        except Exception as exc:
            warnings.warn(
                f"failed to load {self._kind} entry point {ep.name!r}: {exc}",
                RuntimeWarning,
                stacklevel=2,
            )
            return
        try:
            instance = loaded() if callable(loaded) else loaded
        except Exception as exc:
            warnings.warn(
                f"failed to instantiate {self._kind} entry point {ep.name!r}: {exc}",
                RuntimeWarning,
                stacklevel=2,
            )
            return
        name = getattr(instance, "name", None)
        if not name:
            warnings.warn(
                f"{self._kind} entry point {ep.name!r} produced an instance "
                "without a 'name' attribute; skipping",
                RuntimeWarning,
                stacklevel=2,
            )
            return
        if name in self._items:
            return
        try:
            self._register(instance)
        except Exception as exc:
            warnings.warn(
                f"failed to register {self._kind} {name!r} from entry point "
                f"{ep.name!r}: {exc}",
                RuntimeWarning,
                stacklevel=2,
            )

    def _register(self, instance: Any) -> None:
        raise NotImplementedError


# ----------------------------------------------------------------------------


class IntegrationRegistry(_BaseRegistry):
    """Process-wide singleton of registered integrations.

    Entry-point discovery uses the ``cfa.integrations`` group. See
    ADR-0010 for the rationale and the integration contract.
    """

    _entry_point_group = _INTEGRATION_GROUP
    _kind = "integration"
    _instance: IntegrationRegistry | None = None

    @classmethod
    def singleton(cls) -> IntegrationRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_singleton(cls) -> None:
        """For tests only."""
        cls._instance = None

    def register(self, integration: Integration) -> None:
        if not isinstance(integration, Integration):
            raise TypeError(
                f"object of type {type(integration).__name__!r} does not "
                "implement the cfa.core.integration.Integration protocol"
            )
        if not getattr(integration, "name", None):
            raise ValueError("integration must have a non-empty 'name' attribute")
        if integration.name in self._items:
            raise ValueError(
                f"integration {integration.name!r} is already registered"
            )
        self._items[integration.name] = integration

    def get(self, name: str) -> Integration:
        self._ensure_discovered()
        try:
            return self._items[name]
        except KeyError as exc:
            available = ", ".join(sorted(self._items)) or "<none>"
            raise KeyError(
                f"unknown integration {name!r}. Registered integrations: {available}"
            ) from exc

    def _register(self, instance: Any) -> None:
        self.register(instance)


# ----------------------------------------------------------------------------


class DecisionSinkRegistry(_BaseRegistry):
    """Process-wide singleton of registered decision sinks.

    Entry-point discovery uses the ``cfa.decision_sinks`` group.
    """

    _entry_point_group = _SINK_GROUP
    _kind = "decision sink"
    _instance: DecisionSinkRegistry | None = None

    @classmethod
    def singleton(cls) -> DecisionSinkRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_singleton(cls) -> None:
        """For tests only."""
        cls._instance = None

    def register(self, sink: DecisionSink) -> None:
        if not isinstance(sink, DecisionSink):
            raise TypeError(
                f"object of type {type(sink).__name__!r} does not "
                "implement the cfa.core.integration.DecisionSink protocol"
            )
        if not getattr(sink, "name", None):
            raise ValueError("decision sink must have a non-empty 'name' attribute")
        if sink.name in self._items:
            raise ValueError(
                f"decision sink {sink.name!r} is already registered"
            )
        self._items[sink.name] = sink

    def get(self, name: str) -> DecisionSink:
        self._ensure_discovered()
        try:
            return self._items[name]
        except KeyError as exc:
            available = ", ".join(sorted(self._items)) or "<none>"
            raise KeyError(
                f"unknown decision sink {name!r}. Registered sinks: {available}"
            ) from exc

    def fanout(self, result: KernelResult) -> None:
        """Emit ``result`` to every registered sink.

        Failures in any single sink are logged via :mod:`warnings` and
        do not interrupt the fanout. See ADR-0010 for rationale.
        """
        self._ensure_discovered()
        for sink in self._items.values():
            try:
                sink.emit(result)
            except Exception as exc:
                warnings.warn(
                    f"decision sink {sink.name!r} raised during emit: {exc}",
                    RuntimeWarning,
                    stacklevel=2,
                )

    def _register(self, instance: Any) -> None:
        self.register(instance)


__all__ = [
    "DecisionSink",
    "DecisionSinkRegistry",
    "Integration",
    "IntegrationInputError",
    "IntegrationRegistry",
]
