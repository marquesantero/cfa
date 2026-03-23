"""Tests for CFA Partial Execution State."""

from cfa.codegen import PySparkGenerator
from cfa.partial_execution import (
    FailurePolicy,
    PartialExecutionManager,
    PublishState,
    RetryPolicy,
)
from cfa.planner import ExecutionPlanner
from cfa.runtime_validation import RuntimeThresholds, RuntimeValidator
from cfa.sandbox import (
    MockSandboxBackend,
    PanicSandboxBackend,
    StepOutcome,
    StepResult,
    SandboxExecutor,
    SandboxOutcome,
)
from cfa.types import Fault, FaultFamily, FaultSeverity, PolicyAction
from conftest import make_signature


def _make_plan_code_sig(**kwargs):
    planner = ExecutionPlanner()
    gen = PySparkGenerator()
    sig = make_signature(**kwargs)
    plan = planner.plan(sig)
    code = gen.generate(plan)
    return plan, code, sig


class FailOnceBackend(MockSandboxBackend):
    def __init__(self, fail_once_steps: set[str], **kwargs):
        super().__init__(**kwargs)
        self.fail_once_steps = set(fail_once_steps)

    def execute_step(self, step, code, context):
        if step.id in self.fail_once_steps:
            self.fail_once_steps.remove(step.id)
            return StepResult(
                step_id=step.id,
                outcome=StepOutcome.FAILED,
                error=f"Transient failure on step {step.id}",
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
        return super().execute_step(step, code, context)


class TestHappyPath:
    def test_full_success_publishes(self):
        plan, code, sig = _make_plan_code_sig()
        manager = PartialExecutionManager(
            sandbox=SandboxExecutor(backend=MockSandboxBackend()),
        )
        state = manager.execute(plan, code, sig)
        assert state.publish_state == PublishState.PUBLISHED
        assert len(state.committed_steps) > 0
        assert len(state.quarantined_steps) == 0

    def test_runtime_validation_runs(self):
        plan, code, sig = _make_plan_code_sig()
        manager = PartialExecutionManager(
            sandbox=SandboxExecutor(backend=MockSandboxBackend()),
        )
        state = manager.execute(plan, code, sig)
        assert state.runtime_validation is not None
        assert state.runtime_validation.passed


class TestPanicRollback:
    def test_panic_rolls_back(self):
        plan, code, sig = _make_plan_code_sig()
        ordered = plan.execution_order()
        backend = PanicSandboxBackend(panic_on_step=ordered[0].id)
        manager = PartialExecutionManager(
            sandbox=SandboxExecutor(backend=backend),
        )
        state = manager.execute(plan, code, sig)
        assert state.publish_state == PublishState.ROLLED_BACK
        assert state.failure_policy_applied == FailurePolicy.FULL_ROLLBACK


class TestFailurePolicies:
    def test_full_rollback_on_partial_failure(self):
        plan, code, sig = _make_plan_code_sig()
        step_ids = {s.id for s in plan.steps}
        fail_id = next(iter(step_ids))
        manager = PartialExecutionManager(
            sandbox=SandboxExecutor(backend=MockSandboxBackend(fail_steps={fail_id})),
            failure_policy=FailurePolicy.FULL_ROLLBACK,
        )
        state = manager.execute(plan, code, sig)
        assert state.publish_state == PublishState.ROLLED_BACK

    def test_selective_quarantine_on_partial_failure(self):
        plan, code, sig = _make_plan_code_sig()
        step_ids = {s.id for s in plan.steps}
        fail_id = next(iter(step_ids))
        manager = PartialExecutionManager(
            sandbox=SandboxExecutor(backend=MockSandboxBackend(fail_steps={fail_id})),
            failure_policy=FailurePolicy.SELECTIVE_QUARANTINE,
        )
        state = manager.execute(plan, code, sig)
        assert state.publish_state in (PublishState.QUARANTINED, PublishState.ROLLED_BACK)
        assert fail_id in state.quarantined_steps

    def test_partial_commit_no_publish(self):
        plan, code, sig = _make_plan_code_sig()
        step_ids = {s.id for s in plan.steps}
        fail_id = next(iter(step_ids))
        manager = PartialExecutionManager(
            sandbox=SandboxExecutor(backend=MockSandboxBackend(fail_steps={fail_id})),
            failure_policy=FailurePolicy.PARTIAL_COMMIT_NO_PUBLISH,
        )
        state = manager.execute(plan, code, sig)
        assert state.publish_state == PublishState.COMMITTED_NOT_PUBLISHED

    def test_degraded_publish_on_partial_failure(self):
        plan, code, sig = _make_plan_code_sig(include_pii=True)  # more steps
        ordered = plan.execution_order()
        # Fail only the last step to ensure some succeed
        fail_id = ordered[-1].id
        manager = PartialExecutionManager(
            sandbox=SandboxExecutor(backend=MockSandboxBackend(fail_steps={fail_id})),
            failure_policy=FailurePolicy.DEGRADED_PUBLISH,
        )
        state = manager.execute(plan, code, sig)
        # If at least one step succeeded, should be DEGRADED
        if len(state.committed_steps) > 0:
            assert state.publish_state == PublishState.DEGRADED
            degraded_faults = [f for f in state.faults if f.code == "PARTIAL_DEGRADED_PUBLISH"]
            assert len(degraded_faults) == 1


class TestRetries:
    def test_retry_failed_steps_only_can_recover(self):
        plan, code, sig = _make_plan_code_sig()
        fail_id = plan.execution_order()[0].id
        manager = PartialExecutionManager(
            sandbox=SandboxExecutor(backend=FailOnceBackend(fail_once_steps={fail_id})),
            retry_policy=RetryPolicy(max_attempts=3, retry_failed_only=True),
        )
        state = manager.execute(plan, code, sig)
        assert state.retry_count == 1
        assert state.publish_state == PublishState.PUBLISHED
        assert fail_id in state.committed_steps


class TestRuntimeValidationFailure:
    def test_cost_ceiling_triggers_failure_policy(self):
        plan, code, sig = _make_plan_code_sig(max_cost_dbu=0.01)  # very low ceiling
        manager = PartialExecutionManager(
            sandbox=SandboxExecutor(backend=MockSandboxBackend()),
            failure_policy=FailurePolicy.FULL_ROLLBACK,
        )
        state = manager.execute(plan, code, sig)
        # Execution completes but runtime validation fails -> rolled back
        assert state.publish_state == PublishState.ROLLED_BACK

    def test_quarantine_on_runtime_validation_failure(self):
        plan, code, sig = _make_plan_code_sig(max_cost_dbu=0.01)
        manager = PartialExecutionManager(
            sandbox=SandboxExecutor(backend=MockSandboxBackend()),
            failure_policy=FailurePolicy.SELECTIVE_QUARANTINE,
        )
        state = manager.execute(plan, code, sig)
        assert state.publish_state == PublishState.QUARANTINED


class TestIntegrationWithKernel:
    def test_kernel_full_pipeline_with_sandbox(self):
        """End-to-end: kernel processes intent through sandbox."""
        from cfa.kernel import KernelConfig, KernelOrchestrator
        from cfa.types import DecisionState

        kernel = KernelOrchestrator(
            config=KernelConfig(enable_sandbox=True),
        )
        result = kernel.process("Join NFe with Clientes and persist to Silver")
        # Should reach sandbox phase and complete
        assert result.execution_state is not None
        assert result.sandbox_result is not None

    def test_kernel_sandbox_disabled(self):
        from cfa.kernel import KernelConfig, KernelOrchestrator

        kernel = KernelOrchestrator(
            config=KernelConfig(enable_sandbox=False),
        )
        result = kernel.process("Join NFe with Clientes and persist to Silver")
        assert result.execution_state is None
        assert result.sandbox_result is None
