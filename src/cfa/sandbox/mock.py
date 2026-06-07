"""Mock sandbox backend — deterministic simulation for testing."""

from __future__ import annotations

from typing import Any

from cfa.core.planner import ExecutionStep
from cfa.types import Fault, FaultFamily, FaultSeverity, PolicyAction

from . import (
    ExecutionMetrics,
    SandboxBackend,
    SandboxCapabilities,
    StepOutcome,
    StepResult,
)


class MockSandboxBackend(SandboxBackend):
    """Deterministic sandbox for testing and local simulation.

    Configurable outcomes allow testing failure scenarios without
    a real execution environment.
    """

    def __init__(
        self,
        default_rows: int = 100_000,
        default_shuffle_mb: float = 50.0,
        default_cost_dbu: float = 5.0,
        fail_steps: set[str] | None = None,
        null_ratio: float = 0.01,
        output_schema: list[str] | None = None,
    ) -> None:
        self.default_rows = default_rows
        self.default_shuffle_mb = default_shuffle_mb
        self.default_cost_dbu = default_cost_dbu
        self.fail_steps = fail_steps or set()
        self.null_ratio = null_ratio
        self.output_schema = output_schema or ["nfe_id", "cpf_hash", "processing_date"]

    def get_capabilities(self) -> SandboxCapabilities:
        return SandboxCapabilities(
            backend_name="mock",
            backend_version="sim-1.0",
            execution_mode="simulation",
            supports_rollback=False,
            supports_metrics=True,
            supports_environment_check=False,
        )

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
