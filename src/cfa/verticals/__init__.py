"""CFA verticals — domains that CFA governs.

Each vertical is a self-contained package implementing the
:class:`cfa.core.vertical.Vertical` protocol. The first-party
``cfa.verticals.data`` vertical ships inside ``cfa-kernel`` and
demonstrates the contract end-to-end. Third-party verticals live in
separate distributions and register via Python entry points.

See ``docs/adr/0007-layered-architecture.md`` and
``docs/extending.md`` for the full reasoning.
"""

__all__: list[str] = []
