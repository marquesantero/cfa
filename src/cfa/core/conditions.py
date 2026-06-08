"""CFA Condition Registry — the canonical way to attach policy rules.

Every governance condition CFA knows about lives in a single registry,
identified by a fully-qualified name (typically ``{vertical}.{short_name}``,
e.g. ``data.pii_in_protected_layer``). YAML policy bundles reference
conditions by name; verticals contribute conditions via
:meth:`cfa.core.vertical.Vertical.conditions`.

See ADR-0011 for the full design rationale.

Public API
----------

Module-level functions (kept for backwards compatibility):

- :func:`register_condition` — register a condition factory.
- :func:`build_condition` — resolve a name + parameters into a callable.
- :func:`list_conditions` — introspect the registry.

Object-oriented form (preferred for new code):

- :class:`ConditionRegistry` — singleton with the same surface, plus
  :meth:`ConditionRegistry.describe` for introspection that also returns
  each condition's docstring and registered metadata.

Both forms operate on the same underlying registry — they are not
independent.

Built-in conditions
-------------------

The data-shaped conditions shipped today (``pii_in_protected_layer``,
``missing_partition``, ``cost_budget_exceeded``, etc.) are registered at
module import time for backward compatibility. They will move to
``cfa.verticals.data`` in 1.2 as part of the vertical extraction
(ADR-0008). When that happens, they will be re-registered under
``data.<short_name>``; the legacy unprefixed names remain as aliases for
the 1.x line.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

from cfa.types import DatasetClassification, StateSignature

#: A condition is a predicate over a :class:`StateSignature`.
ConditionFn = Callable[[StateSignature], bool]

#: A condition factory takes a metadata dict (parsed from YAML) and
#: returns a bound predicate. The metadata dict is the place where YAML
#: parameters arrive — e.g., ``max_dbu`` for ``cost_budget_exceeded``.
ConditionFactory = Callable[[dict[str, Any]], ConditionFn]


# ── ConditionSpec — the registered entry ─────────────────────────────────────


@dataclass(frozen=True)
class ConditionSpec:
    """Everything the registry knows about one condition."""

    name: str
    factory: ConditionFactory
    doc: str = ""
    expected_params: dict[str, str] = field(default_factory=dict)


# ── The registry ─────────────────────────────────────────────────────────────


class ConditionRegistry:
    """Process-wide singleton mapping condition names to factories.

    Names are case-sensitive strings. By convention, names contributed by
    a vertical are auto-prefixed with the vertical's name at registration
    time (e.g., ``data.pii_in_protected_layer``); top-level names without a
    prefix are reserved for cross-vertical or legacy entries.
    """

    _instance: ConditionRegistry | None = None

    def __init__(self) -> None:
        self._specs: dict[str, ConditionSpec] = {}

    # ---- singleton plumbing -------------------------------------------------

    @classmethod
    def singleton(cls) -> ConditionRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_singleton(cls) -> None:
        """For tests only."""
        cls._instance = None

    # ---- public API ---------------------------------------------------------

    def register(
        self,
        name: str,
        factory: ConditionFactory,
        *,
        doc: str = "",
        expected_params: dict[str, str] | None = None,
        overwrite: bool = False,
    ) -> None:
        """Register a condition.

        Args:
            name: Fully-qualified identifier (e.g., ``data.pii_in_protected_layer``).
            factory: Callable returning the actual predicate when invoked
                with a metadata dict.
            doc: Human-readable description shown by ``cfa rules list
                --available-conditions``.
            expected_params: Mapping of parameter name to a short
                description; used by introspection and validation
                tooling.
            overwrite: When ``True``, an existing registration with the
                same name is replaced. Default ``False`` raises to
                surface accidental collisions.
        """
        if not name:
            raise ValueError("condition name must be a non-empty string")
        if not overwrite and name in self._specs:
            raise ValueError(
                f"condition {name!r} is already registered; pass "
                "overwrite=True to replace"
            )
        self._specs[name] = ConditionSpec(
            name=name,
            factory=factory,
            doc=doc,
            expected_params=expected_params or {},
        )

    def build(self, name: str, metadata: dict[str, Any] | None = None) -> ConditionFn:
        """Build a bound predicate from a registered name + parameters."""
        try:
            spec = self._specs[name]
        except KeyError as exc:
            available = ", ".join(sorted(self._specs)) or "<none>"
            raise KeyError(
                f"unknown condition {name!r}. Registered conditions: {available}"
            ) from exc
        return spec.factory(metadata or {})

    def list(self) -> list[str]:
        """Return registered condition names, sorted."""
        return sorted(self._specs)

    def describe(self, name: str) -> ConditionSpec:
        """Return the :class:`ConditionSpec` for a registered name."""
        try:
            return self._specs[name]
        except KeyError as exc:
            available = ", ".join(sorted(self._specs)) or "<none>"
            raise KeyError(
                f"unknown condition {name!r}. Registered conditions: {available}"
            ) from exc

    def describe_all(self) -> list[ConditionSpec]:
        """Return every :class:`ConditionSpec`, sorted by name."""
        return [self._specs[name] for name in sorted(self._specs)]

    def __contains__(self, name: object) -> bool:
        return name in self._specs

    def __iter__(self) -> Iterator[str]:
        yield from sorted(self._specs)


# ── Backwards-compatible module-level surface ─────────────────────────────────
# These functions are the legacy API; they delegate to the singleton and
# remain supported through the 1.x line.


def register_condition(
    name: str,
    builder: ConditionFactory,
    *,
    doc: str = "",
    expected_params: dict[str, str] | None = None,
) -> None:
    """Register a condition factory under ``name``.

    Equivalent to ``ConditionRegistry.singleton().register(...)``. Kept as
    a module-level function for parity with the 1.0/1.1 surface.
    Re-registering an existing name silently overwrites (legacy behavior)
    and emits a :class:`DeprecationWarning`; new code should pass
    ``overwrite=True`` to :meth:`ConditionRegistry.register` explicitly.
    """
    registry = ConditionRegistry.singleton()
    if name in registry:
        warnings.warn(
            f"condition {name!r} is being silently re-registered. In 2.0 "
            "this will raise; pass overwrite=True to ConditionRegistry.register "
            "to keep the override.",
            DeprecationWarning,
            stacklevel=2,
        )
        registry.register(
            name, builder, doc=doc, expected_params=expected_params, overwrite=True
        )
    else:
        registry.register(
            name, builder, doc=doc, expected_params=expected_params
        )


def build_condition(name: str, metadata: dict[str, Any] | None = None) -> ConditionFn:
    """Resolve a condition by name. See :meth:`ConditionRegistry.build`."""
    return ConditionRegistry.singleton().build(name, metadata)


def list_conditions() -> list[str]:
    """Return all registered condition names, sorted."""
    return ConditionRegistry.singleton().list()


# Backwards-compatible alias for the underlying dict shape.
# Pre-1.1.2 code may have read CONDITION_REGISTRY directly. The mapping
# is now derived from the singleton on each access so it always reflects
# the live state. Direct mutation is no longer supported — use
# register_condition().


class _LegacyDictView:
    """Mapping view over the singleton's specs (factories only)."""

    def __getitem__(self, name: str) -> ConditionFactory:
        return ConditionRegistry.singleton().describe(name).factory

    def __contains__(self, name: object) -> bool:
        return name in ConditionRegistry.singleton()

    def __iter__(self) -> Iterator[str]:
        return iter(ConditionRegistry.singleton())

    def __len__(self) -> int:
        return len(ConditionRegistry.singleton().list())

    def get(
        self, name: str, default: ConditionFactory | None = None
    ) -> ConditionFactory | None:
        try:
            return self[name]
        except KeyError:
            return default

    def keys(self) -> list[str]:
        return list(ConditionRegistry.singleton())


CONDITION_REGISTRY: _LegacyDictView = _LegacyDictView()


# ── Shipped data-vertical conditions ─────────────────────────────────────────
# Registered at import time for backward compatibility. They will move
# into cfa.verticals.data during the 1.2 vertical extraction (ADR-0008);
# the unprefixed names remain as aliases for the 1.x line.


def _pii_in_protected_layer(meta: dict[str, Any]) -> ConditionFn:
    target_layer = meta.get("target_layer", "")

    def check(sig: StateSignature) -> bool:
        protected = (target_layer in ("silver", "gold")) or sig.writes_to_protected_layer
        return protected and sig.contains_pii and not sig.constraints.no_pii_raw

    return check


def _missing_merge_key(meta: dict[str, Any]) -> ConditionFn:
    def check(sig: StateSignature) -> bool:
        return sig.writes_to_protected_layer and not sig.constraints.merge_key_required

    return check


def _missing_partition(meta: dict[str, Any]) -> ConditionFn:
    min_size_gb = meta.get("min_size_gb", 1.0)

    def check(sig: StateSignature) -> bool:
        has_large = any(
            d.classification in (DatasetClassification.HIGH_VOLUME, DatasetClassification.SENSITIVE)
            or d.size_gb >= min_size_gb
            for d in sig.datasets
        )
        return has_large and len(sig.constraints.partition_by) == 0

    return check


def _enforce_types_disabled(meta: dict[str, Any]) -> ConditionFn:
    def check(sig: StateSignature) -> bool:
        return sig.writes_to_protected_layer and not sig.constraints.enforce_types

    return check


def _pii_without_policy(meta: dict[str, Any]) -> ConditionFn:
    def check(sig: StateSignature) -> bool:
        return sig.contains_pii and not sig.constraints.no_pii_raw

    return check


def _sensitive_without_partition(meta: dict[str, Any]) -> ConditionFn:
    def check(sig: StateSignature) -> bool:
        return (
            any(d.classification == DatasetClassification.SENSITIVE for d in sig.datasets)
            and len(sig.constraints.partition_by) == 0
        )

    return check


def _cost_budget_exceeded(meta: dict[str, Any]) -> ConditionFn:
    max_dbu = meta.get("max_dbu", 0.0) or 0.0

    def check(sig: StateSignature) -> bool:
        limit = max_dbu or 0.0
        if limit > 0 and sig.constraints.max_cost_dbu is not None:
            return sig.constraints.max_cost_dbu > limit
        return sig.constraints.max_cost_dbu is not None and sig.constraints.max_cost_dbu <= 0

    return check


# Register the data-vertical conditions on import. In 1.2 the same
# factories will be re-registered under "data.<name>" by the data
# vertical; both forms coexist for one major release.
_registry = ConditionRegistry.singleton()
_registry.register(
    "pii_in_protected_layer",
    _pii_in_protected_layer,
    doc="Fires when PII columns appear in a write targeting Silver or Gold without anonymization.",
    expected_params={"target_layer": "Optional layer override ('silver'|'gold')."},
)
_registry.register(
    "missing_merge_key",
    _missing_merge_key,
    doc="Fires when a Silver/Gold write does not declare merge_key_required.",
)
_registry.register(
    "missing_partition",
    _missing_partition,
    doc="Fires when a high-volume or sensitive dataset is written without a partition_by.",
    expected_params={"min_size_gb": "Trigger threshold in GB (default 1.0)."},
)
_registry.register(
    "enforce_types_disabled",
    _enforce_types_disabled,
    doc="Fires when a Silver/Gold write disables type enforcement.",
)
_registry.register(
    "pii_without_policy",
    _pii_without_policy,
    doc="Fires when datasets carry PII without no_pii_raw=True.",
)
_registry.register(
    "sensitive_without_partition",
    _sensitive_without_partition,
    doc="Fires when sensitive datasets are written without partitioning.",
)
_registry.register(
    "cost_budget_exceeded",
    _cost_budget_exceeded,
    doc="Fires when max_cost_dbu exceeds a configured ceiling or is non-positive.",
    expected_params={"max_dbu": "Maximum DBU ceiling (>0)."},
)

# Aliases shipped pre-1.1.2 for behavior-spec compatibility.
_registry.register("schema_mismatch", _missing_partition, doc="Alias of missing_partition.")
_registry.register("shuffle_budget_exceeded", _missing_partition, doc="Alias of missing_partition.")
_registry.register("unauthorized_gold_write", _pii_in_protected_layer, doc="Alias of pii_in_protected_layer.")


__all__ = [
    "CONDITION_REGISTRY",
    "ConditionFactory",
    "ConditionFn",
    "ConditionRegistry",
    "ConditionSpec",
    "build_condition",
    "list_conditions",
    "register_condition",
]
