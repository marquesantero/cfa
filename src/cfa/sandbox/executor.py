"""Sandbox executor — orchestrates plan execution through a sandbox backend."""

from __future__ import annotations

from typing import Any

from cfa.core.codegen import GeneratedCode
from cfa.core.planner import ExecutionPlan
from cfa.types import StateSignature

from . import (
    ExecutionMetrics,
    SandboxBackend,
    SandboxOutcome,
    SandboxResult,
    StepOutcome,
    StepResult,
)


class SandboxExecutor:
    """Orchestrates isolated execution of a plan in a sandbox."""

    def __init__(self, backend: SandboxBackend) -> None:
        self.backend = backend

    def execute(
        self,
        plan: ExecutionPlan,
        code: GeneratedCode,
        signature: StateSignature,
        schema_contract: dict[str, Any] | None = None,
        step_ids: list[str] | None = None,
    ) -> SandboxResult:
        step_results: list[StepResult] = []
        faults: list = []
        aggregate = None

        context: dict[str, Any] = {"steps": [s.id for s in plan.steps]}
        target_ids = set(step_ids) if step_ids else None

        for step in plan.execution_order():
            if target_ids is not None and step.id not in target_ids:
                continue
            env_faults = self.backend.check_environment()
            if env_faults:
                return SandboxResult(
                    outcome=SandboxOutcome.PANIC,
                    step_results=step_results,
                    faults=env_faults,
                    panic_reason="environment_check_failed",
                )

            step_code = code.step_code_map.get(step.id, code.code)
            result = self.backend.execute_step(step, step_code, context)

            if result.outcome == StepOutcome.INTERRUPTED:
                return SandboxResult(
                    outcome=SandboxOutcome.PANIC,
                    step_results=step_results + [result],
                    faults=result.faults,
                    panic_reason=result.error,
                )

            step_results.append(result)
            faults.extend(result.faults)

            if result.outcome == StepOutcome.FAILED:
                return SandboxResult(
                    outcome=SandboxOutcome.PARTIAL,
                    step_results=step_results,
                    faults=faults,
                )

        total_rows = sum(r.metrics.rows_output for r in step_results)
        total_shuffle = sum(r.metrics.shuffle_bytes for r in step_results)
        total_duration = sum(r.metrics.duration_seconds for r in step_results)
        total_cost = sum(r.metrics.cost_dbu for r in step_results)

        aggregate = ExecutionMetrics(
            rows_output=total_rows,
            shuffle_bytes=total_shuffle,
            duration_seconds=total_duration,
            cost_dbu=total_cost,
        )

        return SandboxResult(
            outcome=SandboxOutcome.COMPLETED,
            step_results=step_results,
            aggregate_metrics=aggregate,
            faults=faults,
        )
