"""Reusable lazy import helper for package __init__.py files.

Usage::

    from cfa._lazy import LazyLoader

    __getattr__ = LazyLoader({
        "KernelOrchestrator": ("cfa.core.kernel", "KernelOrchestrator"),
        "KernelConfig": ("cfa.core.kernel", "KernelConfig"),
    })
"""

from __future__ import annotations

import importlib
from typing import Any


class LazyLoader:
    """Callable that resolves symbols lazily from a mapping.

    Replace ``__getattr__`` in any package ``__init__.py``::

        from cfa._lazy import LazyLoader
        __getattr__ = LazyLoader({"Symbol": ("package.module", "Symbol")})
    """

    __slots__ = ("_map",)

    def __init__(self, mapping: dict[str, tuple[str, str]]) -> None:
        self._map = mapping

    def __call__(self, name: str) -> Any:
        entry = self._map.get(name)
        if entry is None:
            raise AttributeError(f"module has no attribute {name!r}")
        module_path, attr = entry
        module = importlib.import_module(module_path)
        return getattr(module, attr)
