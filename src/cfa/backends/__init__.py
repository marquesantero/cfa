"""
CFA Backend Registry
====================
Pluggable backends for code generation and execution.

A BackendAdapter extends CodeGenBackend with capability introspection,
enabling the Policy Engine to validate whether a backend can satisfy
a given intent's constraints before attempting code generation.

Usage:
    from cfa.backends import BackendRegistry, BackendAdapter, BackendCapabilities

    registry = BackendRegistry()
    registry.register("pyspark", PySparkBackend)
    registry.register("duckdb", DuckDBBackend)

    backend = registry.get("pyspark")()
    caps = backend.get_capabilities()
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from cfa.core.codegen import CodeGenBackend
from cfa.validation.static import ForbiddenToken


@dataclass
class BackendCapabilities:
    """Capabilities exposed by a backend for policy validation.

    The PolicyEngine queries these before approving an intent —
    if a backend cannot satisfy a required constraint (e.g., merge_key
    on a Silver write), the intent is blocked before code generation.
    """

    backend_name: str = ""
    backend_version: str = ""

    supports_merge: bool = False
    supports_partition_overwrite: bool = False
    supports_anonymization: bool = False
    supports_schema_enforcement: bool = False

    pii_anonymization_methods: list[str] = field(default_factory=lambda: ["sha256", "drop"])
    cost_model_available: bool = False
    max_recommended_rows: int = 10_000_000
    supported_languages: list[str] = field(default_factory=lambda: ["python"])

    forbidden_tokens: list[ForbiddenToken] = field(default_factory=list)

    custom: dict[str, Any] = field(default_factory=dict)


class BackendAdapter(CodeGenBackend):
    """Extension of CodeGenBackend with capability introspection.

    Implement this to create a pluggable backend for any target:
    PySpark, DuckDB, BigQuery, REST API, LLM chain, etc.
    """

    @abstractmethod
    def get_capabilities(self) -> BackendCapabilities: ...


BackendFactory = Callable[[], BackendAdapter]


class BackendRegistry:
    """Global registry of available backend factories.

    Supports:
    - register(name, factory) — add a backend
    - get(name) -> factory — retrieve by name
    - list() -> list of registered names
    - remove(name) — unregister a backend
    """

    _instance: BackendRegistry | None = None
    _lock: Any = None

    def __init__(self) -> None:
        self._backends: dict[str, BackendFactory] = {}

    @classmethod
    def singleton(cls) -> BackendRegistry:
        if cls._lock is None:
            import threading
            cls._lock = threading.Lock()
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
                cls._instance._bootstrap()
            return cls._instance

    def _bootstrap(self) -> None:
        if self._backends:
            return
        from .dbt import DbtBackend  # noqa: F811
        from .pyspark import PySparkBackend  # noqa: F811
        from .sql import SqlBackend  # noqa: F811

        self.register("dbt", lambda: DbtBackend())
        self.register("pyspark", lambda: PySparkBackend())
        self.register("sql", lambda: SqlBackend())

    def register(self, name: str, factory: BackendFactory) -> None:
        self._backends[name] = factory

    def get(self, name: str) -> BackendFactory:
        if name not in self._backends:
            available = ", ".join(sorted(self._backends))
            raise KeyError(
                f"Unknown backend '{name}'. Registered backends: {available or '(none)'}"
            )
        return self._backends[name]

    def list(self) -> list[str]:
        return sorted(self._backends)

    def remove(self, name: str) -> None:
        self._backends.pop(name, None)

    def clear(self) -> None:
        self._backends.clear()

    def __contains__(self, name: str) -> bool:
        return name in self._backends
