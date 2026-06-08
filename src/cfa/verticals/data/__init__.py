"""The data vertical — first-party vertical shipped inside ``cfa-kernel``.

Importing this package registers :class:`DataVertical` in the global
:class:`cfa.core.vertical.VerticalRegistry` if it is not already
registered. The vertical can also be picked up via the
``cfa.verticals`` entry-point group declared in ``pyproject.toml`` —
that path is used by ``VerticalRegistry._ensure_discovered`` on first
query, so importing this module is not strictly required.

Use::

    from cfa.verticals.data import DataVertical
    from cfa.core.vertical import VerticalRegistry

    vertical = VerticalRegistry.singleton().get("data")
    assert isinstance(vertical, DataVertical)
"""

from __future__ import annotations

from cfa.verticals.data.vertical import (
    CATALOG_SCHEMA,
    CONSTRAINTS_SCHEMA,
    PAYLOAD_SCHEMA,
    DataVertical,
)


def _autoregister() -> None:
    """Register :class:`DataVertical` in the global registry if absent."""
    from cfa.core.vertical import VerticalRegistry

    registry = VerticalRegistry.singleton()
    if "data" not in registry._verticals:
        registry.register(DataVertical())


_autoregister()


__all__ = [
    "CATALOG_SCHEMA",
    "CONSTRAINTS_SCHEMA",
    "PAYLOAD_SCHEMA",
    "DataVertical",
]
