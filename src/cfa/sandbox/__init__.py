"""
CFA Sandbox Registry
====================
Pluggable execution backends for governed code.

Each sandbox backend declares its capabilities (execution mode,
rollback support, metrics accuracy) via ``SandboxCapabilities``.

The registry follows the same pattern as ``BackendRegistry``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from cfa.core.codegen import GeneratedCode  # noqa: F401
from cfa.core.planner import ExecutionStep
from cfa.types import Fault

# ── Execution Metrics ────────────────────────────────────────────────────────


@dataclass
class ExecutionMetrics:
    rows_output: int = 0
    shuffle_bytes: int = 0
    duration_seconds: float = 0.0
    cost_dbu: float = 0.0
    null_counts: dict[str, int] = field(default_factory=dict)
    output_schema: list[str] = field(default_factory=list)
    peak_memory_mb: float = 0.0

    @property
    def shuffle_mb(self) -> float:
        return self.shuffle_bytes / (1024 * 1024)

    def null_ratio(self, column: str, total_rows: int | None = None) -> float:
        rows = total_rows or self.rows_output
        if rows == 0:
            return 0.0
        return self.null_counts.get(column, 0) / rows


# ── Step Result ──────────────────────────────────────────────────────────────


class StepOutcome(str):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    INTERRUPTED = "interrupted"


@dataclass
class StepResult:
    step_id: str
    outcome: str  # StepOutcome value
    metrics: ExecutionMetrics = field(default_factory=ExecutionMetrics)
    error: str = ""
    faults: list[Fault] = field(default_factory=list)
    retry_count: int = 0


# ── Sandbox Result ───────────────────────────────────────────────────────────


class SandboxOutcome(str):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    PANIC = "panic"


@dataclass
class SandboxResult:
    outcome: str  # SandboxOutcome value
    step_results: list[StepResult] = field(default_factory=list)
    aggregate_metrics: ExecutionMetrics = field(default_factory=ExecutionMetrics)
    faults: list[Fault] = field(default_factory=list)
    panic_reason: str = ""

    @property
    def successful_steps(self) -> list[StepResult]:
        return [r for r in self.step_results if r.outcome == StepOutcome.SUCCESS]

    @property
    def failed_steps(self) -> list[StepResult]:
        return [r for r in self.step_results if r.outcome == StepOutcome.FAILED]

    @property
    def all_succeeded(self) -> bool:
        return all(r.outcome == StepOutcome.SUCCESS for r in self.step_results)


# ── Capabilities ─────────────────────────────────────────────────────────────


@dataclass
class SandboxCapabilities:
    backend_name: str = ""
    backend_version: str = ""

    execution_mode: str = "simulation"  # "simulation" | "local" | "cluster"
    supports_rollback: bool = False
    supports_metrics: bool = True
    supports_environment_check: bool = False
    max_parallel_steps: int = 1

    custom: dict[str, Any] = field(default_factory=dict)


# ── Sandbox Backend ──────────────────────────────────────────────────────────


class SandboxBackend(ABC):
    """Extension point: pluggable execution backend."""

    @abstractmethod
    def execute_step(
        self, step: ExecutionStep, code: str, context: dict[str, Any]
    ) -> StepResult: ...

    @abstractmethod
    def check_environment(self) -> list[Fault]: ...

    def get_capabilities(self) -> SandboxCapabilities:
        return SandboxCapabilities()


# ── Sandbox Registry ─────────────────────────────────────────────────────────


SandboxFactory = Any  # Callable[[], SandboxBackend]


class SandboxRegistry:
    """Global registry of available sandbox backend factories."""

    _instance: SandboxRegistry | None = None
    _lock: Any = None

    def __init__(self) -> None:
        self._backends: dict[str, SandboxFactory] = {}

    @classmethod
    def singleton(cls) -> SandboxRegistry:
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
        from .mock import MockSandboxBackend  # noqa: F811
        from .panic import PanicSandboxBackend  # noqa: F811

        self.register("mock", lambda: MockSandboxBackend())
        self.register("panic", lambda: PanicSandboxBackend(panic_on_step="extract_nfe"))

    def register(self, name: str, factory: SandboxFactory) -> None:
        self._backends[name] = factory

    def get(self, name: str) -> SandboxFactory:
        if name not in self._backends:
            available = ", ".join(sorted(self._backends))
            raise KeyError(f"Unknown sandbox '{name}'. Registered: {available or '(none)'}")
        return self._backends[name]

    def list(self) -> list[str]:
        return sorted(self._backends)

    def __contains__(self, name: str) -> bool:
        return name in self._backends


# ── Backward-compatible re-exports ──────────────────────────────────────────

__all__ = ["SandboxExecutor", "MockSandboxBackend", "PanicSandboxBackend"]

from .executor import SandboxExecutor  # noqa: E402
from .mock import MockSandboxBackend  # noqa: E402
from .panic import PanicSandboxBackend  # noqa: E402
