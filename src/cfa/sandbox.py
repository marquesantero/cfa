"""
CFA Sandbox Executor
====================
Isolated, monitored execution environment.

The Sandbox:
- Executes generated code in isolation
- Monitors for forbidden operations at runtime
- Collects execution metrics (rows, shuffle, cost, duration)
- Interrupts immediately on Environmental Fault or forbidden operation (Invariant I6)
- Supports Panic Rollback when external environment changes mid-execution

Phase 3: in-process simulation with pluggable backend.
Production: Spark cluster, Databricks job, etc.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .codegen import GeneratedCode
from .planner import ExecutionPlan, ExecutionStep
from .types import (
    Fault,
    FaultFamily,
    FaultSeverity,
    PolicyAction,
    StateSignature,
    _utcnow,
)


# ── Execution Metrics ────────────────────────────────────────────────────────


@dataclass
class ExecutionMetrics:
    """Runtime metrics collected during sandbox execution."""

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


class StepOutcome(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    INTERRUPTED = "interrupted"


@dataclass
class StepResult:
    """Result of executing a single step in the sandbox."""

    step_id: str
    outcome: StepOutcome
    metrics: ExecutionMetrics = field(default_factory=ExecutionMetrics)
    error: str = ""
    faults: list[Fault] = field(default_factory=list)
    retry_count: int = 0


# ── Sandbox Result ───────────────────────────────────────────────────────────


class SandboxOutcome(str, Enum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    PANIC = "panic"


@dataclass
class SandboxResult:
    """Complete result of sandbox execution."""

    outcome: SandboxOutcome
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


# ── Sandbox Backend ──────────────────────────────────────────────────────────


class SandboxBackend(ABC):
    """
    Extension point: pluggable execution backend.
    Production: SparkSandbox, DatabricksSandbox, etc.
    """

    @abstractmethod
    def execute_step(
        self, step: ExecutionStep, code: str, context: dict[str, Any]
    ) -> StepResult: ...

    @abstractmethod
    def check_environment(self) -> list[Fault]: ...


# ── Mock Sandbox Backend ─────────────────────────────────────────────────────


class MockSandboxBackend(SandboxBackend):
    """
    Deterministic sandbox for testing.
    Simulates execution with configurable outcomes.
    """

    def __init__(
        self,
        default_rows: int = 100_000,
        default_shuffle_mb: float = 50.0,
        default_cost_dbu: float = 5.0,
        fail_steps: set[str] | None = None,
        panic_on_step: str | None = None,
        null_ratio: float = 0.01,
        output_schema: list[str] | None = None,
    ) -> None:
        self.default_rows = default_rows
        self.default_shuffle_mb = default_shuffle_mb
        self.default_cost_dbu = default_cost_dbu
        self.fail_steps = fail_steps or set()
        self.panic_on_step = panic_on_step
        self.null_ratio = null_ratio
        self.output_schema = output_schema or ["nfe_id", "cpf_hash", "processing_date"]

    def execute_step(
        self, step: ExecutionStep, code: str, context: dict[str, Any]
    ) -> StepResult:
        if step.id in self.fail_steps:
            return StepResult(
                step_id=step.id,
                outcome=StepOutcome.FAILED,
                error=f"Simulated failure on step {step.id}",
                faults=[
                    Fault(
                        code="RUNTIME_STEP_FAILED",
                        family=FaultFamily.RUNTIME,
                        severity=FaultSeverity.HIGH,
                        stage="sandbox",
                        message=f"Step {step.id} failed during execution.",
                        mandatory_action=PolicyAction.BLOCK,
                        detected_before_execution=False,
                    )
                ],
            )

        null_counts = {col: int(self.default_rows * self.null_ratio) for col in self.output_schema}

        return StepResult(
            step_id=step.id,
            outcome=StepOutcome.SUCCESS,
            metrics=ExecutionMetrics(
                rows_output=self.default_rows,
                shuffle_bytes=int(self.default_shuffle_mb * 1024 * 1024),
                duration_seconds=2.5,
                cost_dbu=self.default_cost_dbu / max(len(context.get("steps", [1])), 1),
                null_counts=null_counts,
                output_schema=list(self.output_schema),
            ),
        )

    def check_environment(self) -> list[Fault]:
        return []


class PanicSandboxBackend(MockSandboxBackend):
    """Backend that simulates an environmental fault mid-execution."""

    def __init__(self, panic_on_step: str, panic_reason: str = "cluster_node_lost", **kwargs: Any):
        super().__init__(**kwargs)
        self._panic_step = panic_on_step
        self._panic_reason = panic_reason

    def execute_step(
        self, step: ExecutionStep, code: str, context: dict[str, Any]
    ) -> StepResult:
        if step.id == self._panic_step:
            return StepResult(
                step_id=step.id,
                outcome=StepOutcome.INTERRUPTED,
                error=f"Environmental fault: {self._panic_reason}",
                faults=[
                    Fault(
                        code="ENVIRONMENTAL_PANIC",
                        family=FaultFamily.ENVIRONMENT,
                        severity=FaultSeverity.CRITICAL,
                        stage="sandbox",
                        message=f"Environmental fault during {step.id}: {self._panic_reason}",
                        mandatory_action=PolicyAction.BLOCK,
                        detected_before_execution=False,
                    )
                ],
            )
        return super().execute_step(step, code, context)


# ── Sandbox Executor ─────────────────────────────────────────────────────────


class SandboxExecutor:
    """
    Orchestrates isolated execution of a plan in the sandbox.

    Flow:
    1. Check environment health
    2. Execute steps in topological order
    3. Collect metrics per step
    4. Interrupt on forbidden operation or environmental fault
    5. Produce SandboxResult
    """

    def __init__(self, backend: SandboxBackend | None = None) -> None:
        self.backend = backend or MockSandboxBackend()

    def execute(
        self,
        plan: ExecutionPlan,
        code: GeneratedCode,
        signature: StateSignature,
        step_ids: list[str] | None = None,
    ) -> SandboxResult:
        # Pre-check environment
        env_faults = self.backend.check_environment()
        if env_faults:
            return SandboxResult(
                outcome=SandboxOutcome.PANIC,
                faults=env_faults,
                panic_reason="Pre-execution environment check failed.",
            )

        ordered_steps = plan.execution_order()
        if step_ids is not None:
            allowed = set(step_ids)
            ordered_steps = [step for step in ordered_steps if step.id in allowed]
        step_results: list[StepResult] = []
        all_faults: list[Fault] = []
        total_metrics = ExecutionMetrics()

        context = {"signature": signature.signature_hash, "steps": [s.id for s in ordered_steps]}

        for step in ordered_steps:
            step_code = code.step_code_map.get(step.id, "")
            result = self.backend.execute_step(step, step_code, context)
            step_results.append(result)

            if result.faults:
                all_faults.extend(result.faults)

            # Panic Rollback on environmental fault
            if result.outcome == StepOutcome.INTERRUPTED:
                env_faults = [f for f in result.faults if f.family == FaultFamily.ENVIRONMENT]
                if env_faults:
                    return SandboxResult(
                        outcome=SandboxOutcome.PANIC,
                        step_results=step_results,
                        aggregate_metrics=total_metrics,
                        faults=all_faults,
                        panic_reason=result.error,
                    )

            # Accumulate metrics on success
            if result.outcome == StepOutcome.SUCCESS:
                total_metrics.rows_output = result.metrics.rows_output
                total_metrics.shuffle_bytes += result.metrics.shuffle_bytes
                total_metrics.duration_seconds += result.metrics.duration_seconds
                total_metrics.cost_dbu += result.metrics.cost_dbu
                total_metrics.output_schema = result.metrics.output_schema
                for col, cnt in result.metrics.null_counts.items():
                    total_metrics.null_counts[col] = total_metrics.null_counts.get(col, 0) + cnt

        # Determine outcome
        failed = [r for r in step_results if r.outcome == StepOutcome.FAILED]
        if not failed:
            outcome = SandboxOutcome.COMPLETED
        elif len(failed) < len(step_results):
            outcome = SandboxOutcome.PARTIAL
        else:
            outcome = SandboxOutcome.FAILED

        return SandboxResult(
            outcome=outcome,
            step_results=step_results,
            aggregate_metrics=total_metrics,
            faults=all_faults,
        )
