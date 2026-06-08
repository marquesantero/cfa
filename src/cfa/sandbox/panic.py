# NOTE: This module is internal to CFA — not part of the public API. Use at your own risk.
"""Panic sandbox backend — simulates environmental faults for resilience testing."""

from __future__ import annotations

from typing import Any

from cfa.core.planner import ExecutionStep
from cfa.types import Fault, FaultFamily, FaultSeverity, PolicyAction

from . import SandboxCapabilities, StepOutcome, StepResult
from .mock import MockSandboxBackend


class PanicSandboxBackend(MockSandboxBackend):
    """Backend that simulates an environmental fault mid-execution."""

    def __init__(self, panic_on_step: str, panic_reason: str = "cluster_node_lost", **kwargs: Any):
        super().__init__(**kwargs)
        self._panic_step = panic_on_step
        self._panic_reason = panic_reason

    def get_capabilities(self) -> SandboxCapabilities:
        return SandboxCapabilities(
            backend_name="panic",
            backend_version="panic-1.0",
            execution_mode="simulation",
            supports_rollback=True,
            supports_metrics=True,
            supports_environment_check=True,
        )

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
