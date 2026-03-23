"""
CFA Partial Execution State
============================
Manages partial failures, retry policies, and publish semantics.

When a plan partially fails, CFA does NOT silently succeed or blindly fail.
Instead, it applies a FailurePolicy to determine next action:
- FULL_ROLLBACK: discard everything, mark as rolled_back
- SELECTIVE_QUARANTINE: quarantine failed consistency units, commit the rest
- PARTIAL_COMMIT_NO_PUBLISH: commit all succeeded, but do not publish
- DEGRADED_PUBLISH: commit and publish with degradation flag

Retry policy: max 3 attempts, failed consistency units only.
Publish semantics: committed_not_published -> published | degraded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .sandbox import (
    ExecutionMetrics,
    SandboxExecutor,
    SandboxResult,
    SandboxOutcome,
    StepOutcome,
    StepResult,
)
from .codegen import GeneratedCode
from .planner import ExecutionPlan
from .runtime_validation import RuntimeValidationResult, RuntimeValidator
from .types import (
    Fault,
    FaultFamily,
    FaultSeverity,
    PolicyAction,
    StateSignature,
    _utcnow,
)


# ── Enums ───────────────────────────────────────────────────────────────────


class FailurePolicy(str, Enum):
    FULL_ROLLBACK = "full_rollback"
    SELECTIVE_QUARANTINE = "selective_quarantine"
    PARTIAL_COMMIT_NO_PUBLISH = "partial_commit_no_publish"
    DEGRADED_PUBLISH = "degraded_publish"


class PublishState(str, Enum):
    NOT_STARTED = "not_started"
    COMMITTED_NOT_PUBLISHED = "committed_not_published"
    PUBLISHED = "published"
    DEGRADED = "degraded"
    ROLLED_BACK = "rolled_back"
    QUARANTINED = "quarantined"


# ── Retry Policy ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RetryPolicy:
    """Controls retry behavior for failed steps."""

    max_attempts: int = 3
    retry_failed_only: bool = True  # only retry failed consistency units


# ── Execution State ─────────────────────────────────────────────────────────


@dataclass
class PartialExecutionState:
    """
    Tracks the state of a partially executed plan.
    Supports retry, quarantine, and publish semantics.
    """

    plan_signature_hash: str
    publish_state: PublishState = PublishState.NOT_STARTED
    sandbox_result: SandboxResult | None = None
    runtime_validation: RuntimeValidationResult | None = None
    retry_count: int = 0
    quarantined_steps: list[str] = field(default_factory=list)
    committed_steps: list[str] = field(default_factory=list)
    faults: list[Fault] = field(default_factory=list)
    failure_policy_applied: FailurePolicy | None = None

    @property
    def is_fully_committed(self) -> bool:
        return (
            self.sandbox_result is not None
            and self.sandbox_result.all_succeeded
            and self.publish_state in (PublishState.COMMITTED_NOT_PUBLISHED, PublishState.PUBLISHED)
        )

    @property
    def has_quarantined(self) -> bool:
        return len(self.quarantined_steps) > 0


# ── Partial Execution Manager ───────────────────────────────────────────────


class PartialExecutionManager:
    """
    Orchestrates sandbox execution with failure policy, retry, and publish semantics.

    Flow:
    1. Execute plan in sandbox
    2. Validate runtime metrics
    3. On partial failure, apply failure policy
    4. Retry if policy allows
    5. Determine publish state
    """

    def __init__(
        self,
        sandbox: SandboxExecutor,
        runtime_validator: RuntimeValidator | None = None,
        failure_policy: FailurePolicy = FailurePolicy.SELECTIVE_QUARANTINE,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self.sandbox = sandbox
        self.runtime_validator = runtime_validator or RuntimeValidator()
        self.failure_policy = failure_policy
        self.retry_policy = retry_policy or RetryPolicy()

    def execute(
        self,
        plan: ExecutionPlan,
        code: GeneratedCode,
        signature: StateSignature,
        schema_contract: dict[str, Any] | None = None,
    ) -> PartialExecutionState:
        state = PartialExecutionState(plan_signature_hash=plan.signature_hash)

        # ── Execute in sandbox ──────────────────────────────────────────
        sandbox_result = self.sandbox.execute(plan, code, signature)
        state.sandbox_result = sandbox_result
        state.faults.extend(sandbox_result.faults)

        # ── Handle panic (environmental fault) ──────────────────────────
        if sandbox_result.outcome == SandboxOutcome.PANIC:
            state.publish_state = PublishState.ROLLED_BACK
            state.failure_policy_applied = FailurePolicy.FULL_ROLLBACK
            return state

        # ── Runtime validation ──────────────────────────────────────────
        rv_result = self.runtime_validator.validate(sandbox_result, signature, schema_contract)
        state.runtime_validation = rv_result
        state.faults.extend(rv_result.faults)

        # ── All succeeded + validation passed ───────────────────────────
        if sandbox_result.outcome == SandboxOutcome.COMPLETED and rv_result.passed:
            state.publish_state = PublishState.PUBLISHED
            state.committed_steps = [r.step_id for r in sandbox_result.step_results]
            return state

        # ── Runtime validation failed on complete execution ─────────────
        if sandbox_result.outcome == SandboxOutcome.COMPLETED and not rv_result.passed:
            return self._apply_failure_policy_for_validation(state)

        # ── Partial failure: some steps failed ──────────────────────────
        if sandbox_result.outcome in (SandboxOutcome.PARTIAL, SandboxOutcome.FAILED):
            retried = self._retry_failed_steps(state, plan, code, signature, schema_contract)
            if retried is not None:
                return retried
            return self._apply_failure_policy(state)

        return state

    def _retry_failed_steps(
        self,
        state: PartialExecutionState,
        plan: ExecutionPlan,
        code: GeneratedCode,
        signature: StateSignature,
        schema_contract: dict[str, Any] | None,
    ) -> PartialExecutionState | None:
        """Retry failed consistency units before terminal policy application."""
        assert state.sandbox_result is not None
        failed_step_ids = [r.step_id for r in state.sandbox_result.failed_steps]
        if not failed_step_ids or self.retry_policy.max_attempts <= 1:
            return None

        latest_result = state.sandbox_result
        retryable_ids = list(failed_step_ids)

        for attempt in range(1, self.retry_policy.max_attempts):
            retry_result = self.sandbox.execute(plan, code, signature, step_ids=retryable_ids)
            state.retry_count = attempt
            state.faults.extend(retry_result.faults)

            latest_result = self._merge_retry_result(latest_result, retry_result)
            remaining_failed = [r.step_id for r in latest_result.failed_steps]

            if not remaining_failed:
                state.sandbox_result = latest_result
                rv_result = self.runtime_validator.validate(latest_result, signature, schema_contract)
                state.runtime_validation = rv_result
                state.faults.extend(rv_result.faults)
                if rv_result.passed:
                    state.publish_state = PublishState.PUBLISHED
                    state.committed_steps = [r.step_id for r in latest_result.step_results]
                    state.quarantined_steps = []
                    return state
                return self._apply_failure_policy_for_validation(state)

            if not self.retry_policy.retry_failed_only:
                retryable_ids = [s.id for s in plan.execution_order()]
            else:
                retryable_ids = remaining_failed

        state.sandbox_result = latest_result
        return None

    def _merge_retry_result(
        self,
        base: SandboxResult,
        retry: SandboxResult,
    ) -> SandboxResult:
        """Merge retry outcomes over the original attempt, keeping latest result per retried step."""
        replacement = {r.step_id: r for r in retry.step_results}
        merged_steps = [replacement.get(step.step_id, step) for step in base.step_results]

        aggregate = ExecutionMetrics()
        all_faults: list[Fault] = []
        for step in merged_steps:
            if step.faults:
                all_faults.extend(step.faults)
            if step.outcome == StepOutcome.SUCCESS:
                aggregate.rows_output = step.metrics.rows_output
                aggregate.shuffle_bytes += step.metrics.shuffle_bytes
                aggregate.duration_seconds += step.metrics.duration_seconds
                aggregate.cost_dbu += step.metrics.cost_dbu
                aggregate.output_schema = step.metrics.output_schema
                for col, cnt in step.metrics.null_counts.items():
                    aggregate.null_counts[col] = aggregate.null_counts.get(col, 0) + cnt

        failed = [r for r in merged_steps if r.outcome == StepOutcome.FAILED]
        if not failed:
            outcome = SandboxOutcome.COMPLETED
        elif len(failed) < len(merged_steps):
            outcome = SandboxOutcome.PARTIAL
        else:
            outcome = SandboxOutcome.FAILED

        return SandboxResult(
            outcome=outcome,
            step_results=merged_steps,
            aggregate_metrics=aggregate,
            faults=all_faults,
            panic_reason=retry.panic_reason or base.panic_reason,
        )

    def _apply_failure_policy(self, state: PartialExecutionState) -> PartialExecutionState:
        """Apply failure policy when sandbox has partial/full failure."""
        assert state.sandbox_result is not None

        state.failure_policy_applied = self.failure_policy
        succeeded = state.sandbox_result.successful_steps
        failed = state.sandbox_result.failed_steps

        match self.failure_policy:
            case FailurePolicy.FULL_ROLLBACK:
                state.publish_state = PublishState.ROLLED_BACK
                state.quarantined_steps = [r.step_id for r in state.sandbox_result.step_results]

            case FailurePolicy.SELECTIVE_QUARANTINE:
                state.committed_steps = [r.step_id for r in succeeded]
                state.quarantined_steps = [r.step_id for r in failed]
                if succeeded:
                    state.publish_state = PublishState.QUARANTINED
                else:
                    state.publish_state = PublishState.ROLLED_BACK

            case FailurePolicy.PARTIAL_COMMIT_NO_PUBLISH:
                state.committed_steps = [r.step_id for r in succeeded]
                state.quarantined_steps = [r.step_id for r in failed]
                state.publish_state = PublishState.COMMITTED_NOT_PUBLISHED

            case FailurePolicy.DEGRADED_PUBLISH:
                state.committed_steps = [r.step_id for r in succeeded]
                state.quarantined_steps = [r.step_id for r in failed]
                if succeeded:
                    state.publish_state = PublishState.DEGRADED
                    state.faults.append(Fault(
                        code="PARTIAL_DEGRADED_PUBLISH",
                        family=FaultFamily.RUNTIME,
                        severity=FaultSeverity.WARNING,
                        stage="partial_execution",
                        message=(
                            f"Degraded publish: {len(failed)} of "
                            f"{len(state.sandbox_result.step_results)} steps failed."
                        ),
                        mandatory_action=PolicyAction.APPROVE,
                        detected_before_execution=False,
                    ))
                else:
                    state.publish_state = PublishState.ROLLED_BACK

        return state

    def _apply_failure_policy_for_validation(
        self, state: PartialExecutionState
    ) -> PartialExecutionState:
        """Apply failure policy when runtime validation fails on complete execution."""
        state.failure_policy_applied = self.failure_policy

        match self.failure_policy:
            case FailurePolicy.FULL_ROLLBACK:
                state.publish_state = PublishState.ROLLED_BACK

            case FailurePolicy.SELECTIVE_QUARANTINE:
                # All steps succeeded but validation failed — quarantine the whole batch
                state.publish_state = PublishState.QUARANTINED
                if state.sandbox_result:
                    state.quarantined_steps = [
                        r.step_id for r in state.sandbox_result.step_results
                    ]

            case FailurePolicy.PARTIAL_COMMIT_NO_PUBLISH:
                state.publish_state = PublishState.COMMITTED_NOT_PUBLISHED
                if state.sandbox_result:
                    state.committed_steps = [
                        r.step_id for r in state.sandbox_result.step_results
                    ]

            case FailurePolicy.DEGRADED_PUBLISH:
                state.publish_state = PublishState.DEGRADED
                if state.sandbox_result:
                    state.committed_steps = [
                        r.step_id for r in state.sandbox_result.step_results
                    ]

        return state
