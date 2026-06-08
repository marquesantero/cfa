"""Vertical protocol and registry.

A *vertical* is a domain that CFA governs — data writes, agent tool calls,
infrastructure plans, financial transactions, schema migrations, ML model
deploys, anything that follows the *declare intent → decide → execute →
audit* pattern.

This module defines:

- :class:`Vertical` — the structural contract every vertical implements.
- :class:`VerticalRegistry` — a process-wide singleton that holds the
  active verticals and lazily discovers third-party verticals via
  :mod:`importlib.metadata` entry points.

The kernel itself never depends on any specific vertical. It queries the
registry by name. See ADR-0007 (layered architecture) and ADR-0009
(Vertical protocol).

Third-party verticals are pip-installable packages that declare an entry
point in their ``pyproject.toml``::

    [project.entry-points."cfa.verticals"]
    finance = "cfa_finance.vertical:FinanceVertical"

CFA discovers them the first time :meth:`VerticalRegistry.get` or
:meth:`VerticalRegistry.list` is called and instantiates them on demand.

Example minimal vertical::

    from cfa.core.vertical import Vertical, VerticalRegistry

    class MyVertical:
        name = "my-domain"

        def payload_schema(self):
            return {"type": "object", "required": ["target"]}

        def constraints_schema(self):
            return {"type": "object"}

        def conditions(self):
            return {"is_safe": lambda **_: lambda sig: True}

        def default_rules(self):
            return []

        def catalog_schema(self):
            return None

        def backends(self):
            return {}

    VerticalRegistry.singleton().register(MyVertical())
"""

from __future__ import annotations

import warnings
from collections.abc import Callable, Iterator
from typing import Any, Protocol, runtime_checkable

# A condition factory accepts parameter kwargs (parsed from YAML) and
# returns the actual predicate callable. The predicate takes a
# StateSignature and returns True when the condition fires.
ConditionFactory = Callable[..., Callable[..., bool]]

# A backend factory takes no arguments and returns a backend instance
# implementing the codegen contract for its vertical. See ADR-0012.
BackendFactory = Callable[[], Any]


# ── The Vertical protocol ────────────────────────────────────────────────────


@runtime_checkable
class Vertical(Protocol):
    """Structural contract that every CFA vertical implements.

    Implementations may inherit from this class or simply provide the
    same attributes and methods (Protocol's structural typing).
    Each method is queried lazily by the kernel — verticals should
    therefore avoid heavy work in ``__init__``.
    """

    #: Globally unique, machine-readable identifier for this vertical.
    #: Examples: ``"data"``, ``"agent"``, ``"infra"``, ``"finance"``.
    name: str

    def payload_schema(self) -> dict[str, Any]:
        """JSON Schema for ``StateSignature.payload`` in this vertical."""
        ...

    def constraints_schema(self) -> dict[str, Any]:
        """JSON Schema for ``StateSignature.constraints`` in this vertical."""
        ...

    def conditions(self) -> dict[str, ConditionFactory]:
        """Named condition factories this vertical contributes.

        Returned dict maps short name → factory. The registry auto-prefixes
        names with ``{vertical.name}.`` so two verticals can independently
        register ``pii_in_protected_layer`` without collision.
        """
        ...

    def default_rules(self) -> list[Any]:
        """Default ruleset shipped with the vertical. May be empty."""
        ...

    def catalog_schema(self) -> dict[str, Any] | None:
        """JSON Schema for ground-truth catalog entries, or ``None``."""
        ...

    def backends(self) -> dict[str, BackendFactory]:
        """Codegen / execution backends valid in this vertical.

        Returns a mapping from short name (``"pyspark"``, ``"sql"``,
        ``"terraform"``) to a zero-argument factory. May be empty for
        verticals that do not generate code (e.g., the agent vertical).
        See ADR-0012.
        """
        ...


# ── The registry ─────────────────────────────────────────────────────────────


_ENTRY_POINT_GROUP = "cfa.verticals"


class VerticalRegistry:
    """Process-wide singleton of registered verticals.

    Verticals are registered either explicitly (the data vertical shipped
    inside ``cfa-kernel`` registers itself when imported) or implicitly
    via Python entry points declared in third-party packages.

    Entry-point discovery is performed lazily on first ``get``/``list``
    call so importing :mod:`cfa.core.vertical` does not pay the cost.
    """

    _instance: VerticalRegistry | None = None

    def __init__(self) -> None:
        self._verticals: dict[str, Vertical] = {}
        self._discovered: bool = False

    # ---- singleton plumbing -------------------------------------------------

    @classmethod
    def singleton(cls) -> VerticalRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_singleton(cls) -> None:
        """For tests only — wipe the registry between cases."""
        cls._instance = None

    # ---- public API ---------------------------------------------------------

    def register(self, vertical: Vertical) -> None:
        """Register a vertical.

        Raises:
            TypeError: if ``vertical`` does not satisfy the
                :class:`Vertical` protocol structurally.
            ValueError: if a vertical with the same ``name`` is already
                registered.
        """
        if not isinstance(vertical, Vertical):
            raise TypeError(
                f"object of type {type(vertical).__name__!r} does not "
                "implement the cfa.core.vertical.Vertical protocol"
            )
        if not getattr(vertical, "name", None):
            raise ValueError("vertical must have a non-empty 'name' attribute")
        if vertical.name in self._verticals:
            raise ValueError(
                f"vertical {vertical.name!r} is already registered"
            )
        self._verticals[vertical.name] = vertical
        self._register_conditions(vertical)

    def get(self, name: str) -> Vertical:
        """Return the vertical with the given name.

        Raises:
            KeyError: if no vertical with that name is registered (after
                entry-point discovery).
        """
        self._ensure_discovered()
        try:
            return self._verticals[name]
        except KeyError as exc:
            available = ", ".join(sorted(self._verticals)) or "<none>"
            raise KeyError(
                f"unknown vertical {name!r}. Registered verticals: {available}"
            ) from exc

    def list(self) -> list[str]:
        """Return the names of all registered verticals (sorted)."""
        self._ensure_discovered()
        return sorted(self._verticals)

    def __iter__(self) -> Iterator[Vertical]:
        self._ensure_discovered()
        yield from self._verticals.values()

    def __contains__(self, name: object) -> bool:
        self._ensure_discovered()
        return name in self._verticals

    # ---- internal -----------------------------------------------------------

    def _register_conditions(self, vertical: Vertical) -> None:
        """Auto-prefix and register the vertical's conditions."""
        try:
            from cfa.core.conditions import register_condition
        except ImportError:  # pragma: no cover — defensive
            return
        try:
            conditions = vertical.conditions()
        except Exception as exc:  # pragma: no cover — defensive
            warnings.warn(
                f"vertical {vertical.name!r} raised while listing conditions: {exc}",
                RuntimeWarning,
                stacklevel=2,
            )
            return
        for short_name, factory in conditions.items():
            qualified = f"{vertical.name}.{short_name}"
            register_condition(qualified, factory)

    def _ensure_discovered(self) -> None:
        if self._discovered:
            return
        self._discovered = True
        try:
            from importlib.metadata import entry_points
        except ImportError:  # pragma: no cover — Python < 3.8 (unsupported)
            return
        try:
            eps = entry_points(group=_ENTRY_POINT_GROUP)
        except TypeError:  # Python 3.9 compat
            eps = entry_points().get(_ENTRY_POINT_GROUP, [])  # type: ignore[attr-defined]
        for ep in eps:
            self._load_entry_point(ep)

    def _load_entry_point(self, ep: Any) -> None:
        try:
            loaded = ep.load()
        except Exception as exc:
            warnings.warn(
                f"failed to load vertical entry point {ep.name!r}: {exc}",
                RuntimeWarning,
                stacklevel=2,
            )
            return
        try:
            instance = loaded() if callable(loaded) else loaded
        except Exception as exc:
            warnings.warn(
                f"failed to instantiate vertical entry point {ep.name!r}: {exc}",
                RuntimeWarning,
                stacklevel=2,
            )
            return
        name = getattr(instance, "name", None)
        if not name:
            warnings.warn(
                f"vertical entry point {ep.name!r} produced an instance "
                "without a 'name' attribute; skipping",
                RuntimeWarning,
                stacklevel=2,
            )
            return
        if name in self._verticals:
            # Already registered — explicit registrations take precedence.
            return
        try:
            self.register(instance)
        except Exception as exc:
            warnings.warn(
                f"failed to register vertical {name!r} from entry point "
                f"{ep.name!r}: {exc}",
                RuntimeWarning,
                stacklevel=2,
            )


__all__ = [
    "BackendFactory",
    "ConditionFactory",
    "Vertical",
    "VerticalRegistry",
]
