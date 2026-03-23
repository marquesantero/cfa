"""Tests for CFA Sandbox Executor."""

from cfa.codegen import PySparkGenerator
from cfa.planner import ExecutionPlanner
from cfa.sandbox import (
    ExecutionMetrics,
    MockSandboxBackend,
    PanicSandboxBackend,
    SandboxExecutor,
    SandboxOutcome,
    StepOutcome,
)
from conftest import make_signature


def _make_plan_and_code(**kwargs):
    planner = ExecutionPlanner()
    gen = PySparkGenerator()
    sig = make_signature(**kwargs)
    plan = planner.plan(sig)
    code = gen.generate(plan)
    return plan, code, sig


class TestExecutionMetrics:
    def test_shuffle_mb_conversion(self):
        m = ExecutionMetrics(shuffle_bytes=1024 * 1024 * 100)
        assert m.shuffle_mb == 100.0

    def test_null_ratio(self):
        m = ExecutionMetrics(rows_output=1000, null_counts={"cpf": 50})
        assert m.null_ratio("cpf") == 0.05
        assert m.null_ratio("nonexistent") == 0.0

    def test_null_ratio_zero_rows(self):
        m = ExecutionMetrics(rows_output=0, null_counts={"cpf": 0})
        assert m.null_ratio("cpf") == 0.0


class TestMockSandboxBackend:
    def test_default_execution_succeeds(self):
        plan, code, sig = _make_plan_and_code()
        executor = SandboxExecutor(backend=MockSandboxBackend())
        result = executor.execute(plan, code, sig)
        assert result.outcome == SandboxOutcome.COMPLETED
        assert result.all_succeeded

    def test_configurable_failure(self):
        plan, code, sig = _make_plan_and_code()
        step_ids = {s.id for s in plan.steps}
        fail_id = next(iter(step_ids))  # fail the first step
        executor = SandboxExecutor(backend=MockSandboxBackend(fail_steps={fail_id}))
        result = executor.execute(plan, code, sig)
        assert result.outcome in (SandboxOutcome.PARTIAL, SandboxOutcome.FAILED)
        assert len(result.failed_steps) >= 1

    def test_metrics_accumulated(self):
        plan, code, sig = _make_plan_and_code()
        executor = SandboxExecutor(backend=MockSandboxBackend())
        result = executor.execute(plan, code, sig)
        assert result.aggregate_metrics.rows_output > 0
        assert result.aggregate_metrics.shuffle_bytes > 0
        assert result.aggregate_metrics.cost_dbu > 0


class TestPanicSandboxBackend:
    def test_panic_on_specific_step(self):
        plan, code, sig = _make_plan_and_code()
        ordered = plan.execution_order()
        panic_id = ordered[0].id
        executor = SandboxExecutor(
            backend=PanicSandboxBackend(panic_on_step=panic_id)
        )
        result = executor.execute(plan, code, sig)
        assert result.outcome == SandboxOutcome.PANIC
        assert result.panic_reason != ""

    def test_panic_includes_faults(self):
        plan, code, sig = _make_plan_and_code()
        ordered = plan.execution_order()
        panic_id = ordered[0].id
        executor = SandboxExecutor(
            backend=PanicSandboxBackend(panic_on_step=panic_id, panic_reason="disk_full")
        )
        result = executor.execute(plan, code, sig)
        env_faults = [f for f in result.faults if f.family.value == "environmental_faults"]
        assert len(env_faults) > 0


class TestSandboxExecutor:
    def test_env_check_failure_returns_panic(self):
        """If backend.check_environment returns faults, executor returns PANIC immediately."""
        from cfa.sandbox import SandboxBackend, StepResult
        from cfa.planner import ExecutionStep
        from cfa.types import Fault, FaultFamily, FaultSeverity, PolicyAction

        class FailEnvBackend(SandboxBackend):
            def execute_step(self, step, code, context):
                return StepResult(step_id=step.id, outcome=StepOutcome.SUCCESS)

            def check_environment(self):
                return [Fault(
                    code="ENV_CHECK_FAILED",
                    family=FaultFamily.ENVIRONMENT,
                    severity=FaultSeverity.CRITICAL,
                    stage="sandbox",
                    message="Cluster unavailable.",
                    mandatory_action=PolicyAction.BLOCK,
                    detected_before_execution=False,
                )]

        plan, code, sig = _make_plan_and_code()
        executor = SandboxExecutor(backend=FailEnvBackend())
        result = executor.execute(plan, code, sig)
        assert result.outcome == SandboxOutcome.PANIC
        assert len(result.step_results) == 0
