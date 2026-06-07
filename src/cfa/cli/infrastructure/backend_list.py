"""cfa backend list — list registered backends."""

from __future__ import annotations

from typing import Any


def cmd_backend_list(args) -> int:
    from cfa.backends import BackendRegistry
    from cfa.cli.formatters import format_backends_list, format_json

    registry = BackendRegistry.singleton()
    names = registry.list()
    backends: list[dict[str, Any]] = []
    for name in names:
        factory = registry.get(name)
        backend = factory()
        caps = backend.get_capabilities() if hasattr(backend, "get_capabilities") else None
        backends.append({"name": name, "supports_merge": caps.supports_merge if caps else False, "supports_anonymization": caps.supports_anonymization if caps else False, "supports_partition_overwrite": caps.supports_partition_overwrite if caps else False, "cost_model_available": caps.cost_model_available if caps else False})

    fmt = args.format or "table"
    if fmt == "json": print(format_json(backends))
    else: print(format_backends_list(backends))
    return 0
