"""CFA Kernel Phases — the 5-phase governance pipeline executor.

Extracted from KernelOrchestrator to keep the orchestrator thin.
"""

from __future__ import annotations

import uuid
from typing import Any

from cfa.audit.context import ContextRegistry
from cfa.audit.trail import AuditTrail
from cfa.core.codegen import CodeGenBackend
from cfa.core.kernel import KernelConfig, PipelinePhase
from cfa.core.planner import ExecutionPlanner
from cfa.execution.partial import (
    PartialExecutionManager,
    PublishState,
)
from cfa.execution.state_projection import StateProjectionProtocol
from cfa.normalizer.base import (
    ConfirmationOrchestrator,
    IntentNormalizer,
)
from cfa.observability.indices import ExecutionRecord
from cfa.observability.promotion import PromotionEngine, SkillState
from cfa.policy.catalog import validate_catalog
from cfa.policy.engine import PolicyEngine
from cfa.sandbox.executor import SandboxExecutor
from cfa.types import (
    DecisionState,
    Fault,
    FaultFamily,
    FaultSeverity,
    KernelResult,
    PolicyAction,
    PolicyResult,
    SemanticResolution,
    StateSignature,
    _utcnow,
)
from cfa.validation.runtime import RuntimeValidator
from cfa.validation.static import StaticValidator


class KernelPhases:
    """Executes the 5-phase CFA governance pipeline.

    Created by KernelOrchestrator with all dependencies injected.
    """

    def __init__(
        self,
        config: KernelConfig,
        context_registry: ContextRegistry,
        audit_trail: AuditTrail,
        catalog: dict[str, Any],
        schema_contract: dict[str, Any] | None,
        normalizer: IntentNormalizer,
        confirmation: ConfirmationOrchestrator,
        policy: PolicyEngine,
        planner: ExecutionPlanner,
        codegen: CodeGenBackend,
        static_validator: StaticValidator,
        sandbox_executor: SandboxExecutor,
        runtime_validator: RuntimeValidator,
        partial_execution_manager: PartialExecutionManager,
        state_projection: StateProjectionProtocol,
        promotion_engine: PromotionEngine,
    ) -> None:
        self.config = config
        self.context_registry = context_registry
        self.audit_trail = audit_trail
        self.catalog = catalog
        self.schema_contract = schema_contract
        self.normalizer = normalizer
        self.confirmation = confirmation
        self.policy = policy
        self.planner = planner
        self.codegen = codegen
        self.static_validator = static_validator
        self.sandbox_executor = sandbox_executor
        self.runtime_validator = runtime_validator
        self.partial_execution_manager = partial_execution_manager
        self.state_projection = state_projection
        self.promotion_engine = promotion_engine

    # ── Public API ────────────────────────────────────────────────────────────

    def process(self, raw_intent: str) -> KernelResult:
        intent_id = str(uuid.uuid4())
        result = KernelResult(intent_id=intent_id, state=DecisionState.BLOCKED)

        if self.config.phase_formalize:
            signature, early = self._phase_formalize(intent_id, raw_intent, result)
            if early:
                return result
            result.signature = signature
        else:
            return result

        if self.config.phase_govern:
            signature, policy_ok, replan_count = self._phase_govern(intent_id, result)
            if not policy_ok:
                return result
        else:
            replan_count = 0

        if self.config.phase_generate and self.config.enable_planning:
            early = self._phase_generate(intent_id, signature, result)
            if early:
                return result
            if self.config.phase_execute and self.config.enable_sandbox:
                early = self._phase_execute(intent_id, signature, result, replan_count)
                if early:
                    return result

        self._phase_validate(intent_id, signature, result, replan_count)
        return result

    # ── Phase 1: Formalize ────────────────────────────────────────────────────

    def _phase_formalize(
        self, intent_id: str, raw_intent: str, result: KernelResult
    ) -> tuple[StateSignature | None, bool]:
        if self.config.strict_normalization:
            catalog_result = validate_catalog(self.catalog, require_datasets=True)
            if not catalog_result.valid:
                fault = catalog_result.to_fault()
                result.state = DecisionState.BLOCKED
                result.blocked_reason = fault.message
                result.policy_result = PolicyResult(
                    action=PolicyAction.BLOCK, faults=[fault],
                    reasoning="; ".join(catalog_result.messages),
                )
                self._audit(intent_id, PipelinePhase.FORMALIZE, "catalog_validation", "blocked",
                            issues=catalog_result.messages)
                result.add_event(PipelinePhase.FORMALIZE, "catalog_validation", "blocked",
                                 issues=catalog_result.messages)
                return None, True

        environment_state = self.context_registry.get_environment_state()
        self._audit(intent_id, PipelinePhase.FORMALIZE, "environment_state_consulted", "ok",
                    version_id=self.context_registry.version_id)
        result.add_event(PipelinePhase.FORMALIZE, "environment_state_consulted", "ok",
                         version_id=self.context_registry.version_id)

        try:
            resolution = self.normalizer.normalize(
                raw_intent=raw_intent, environment_state=environment_state,
                catalog=self.catalog,
                context_registry_version_id=self.context_registry.version_id,
            )
            result.resolution = resolution
            self._audit(intent_id, PipelinePhase.FORMALIZE, "semantic_resolution", "resolved",
                        confidence=resolution.confidence_score,
                        confirmation_mode=resolution.confirmation_mode.value)
            result.add_event(PipelinePhase.FORMALIZE, "semantic_resolution", "resolved",
                             confidence=resolution.confidence_score,
                             confirmation_mode=resolution.confirmation_mode.value)
        except (ValueError, TypeError, ImportError, RuntimeError, KeyError) as e:
            result.blocked_reason = f"Normalization failed: {e}"
            self._audit(intent_id, PipelinePhase.FORMALIZE, "normalization_error", "error", error=str(e))
            result.add_event(PipelinePhase.FORMALIZE, "normalization_error", "error", error=str(e))
            return None, True

        if self.config.strict_normalization:
            strict_fault = self._strict_normalization_fault(resolution)
            if strict_fault:
                result.state = DecisionState.BLOCKED
                result.blocked_reason = strict_fault.message
                result.policy_result = PolicyResult(
                    action=PolicyAction.BLOCK, faults=[strict_fault],
                    reasoning=strict_fault.message,
                )
                self._audit(intent_id, PipelinePhase.FORMALIZE, "strict_normalization", "blocked",
                            fault=strict_fault.code)
                result.add_event(PipelinePhase.FORMALIZE, "strict_normalization", "blocked",
                                 fault=strict_fault.code)
                return None, True

        approved, confirm_reason, confirm_fault = self.confirmation.process(resolution)
        self._audit(intent_id, PipelinePhase.FORMALIZE, "confirmation",
                    "approved" if approved else "rejected",
                    mode=resolution.confirmation_mode.value, reason=confirm_reason)
        result.add_event(PipelinePhase.FORMALIZE, "confirmation",
                         "approved" if approved else "rejected",
                         mode=resolution.confirmation_mode.value, reason=confirm_reason)

        if not approved:
            result.state = DecisionState.BLOCKED
            result.blocked_reason = confirm_reason
            if confirm_fault:
                result.policy_result = PolicyResult(
                    action=PolicyAction.BLOCK, faults=[confirm_fault],
                    reasoning=confirm_reason,
                )
            return None, True

        return resolution.signature, False

    # ── Phase 2: Govern ───────────────────────────────────────────────────────

    def _phase_govern(
        self, intent_id: str, result: KernelResult
    ) -> tuple[StateSignature, bool, int]:
        signature = result.resolution.signature  # type: ignore[union-attr]
        replan_count = 0

        while True:
            policy_result = self.policy.evaluate(signature, replan_count=replan_count)
            result.policy_result = policy_result
            self._audit(intent_id, PipelinePhase.GOVERN, "policy_evaluation",
                        policy_result.action.value, replan_count=replan_count,
                        faults=[f.code for f in policy_result.faults])
            result.add_event(PipelinePhase.GOVERN, "policy_evaluation",
                             policy_result.action.value, replan_count=replan_count,
                             faults=[f.code for f in policy_result.faults])

            if policy_result.action == PolicyAction.APPROVE:
                return signature, True, replan_count
            if policy_result.action == PolicyAction.BLOCK:
                result.state = DecisionState.BLOCKED
                result.blocked_reason = policy_result.reasoning
                return signature, False, replan_count

            result.replan_history.append(policy_result)
            replan_count += 1
            new_signature = _apply_interventions(signature, policy_result)
            if new_signature is None:
                result.state = DecisionState.BLOCKED
                result.blocked_reason = "Replan failed: interventions not applicable."
                return signature, False, replan_count

            signature = new_signature
            self._audit(intent_id, PipelinePhase.GOVERN, "replan_applied", "replanned",
                        replan_count=replan_count, interventions=policy_result.interventions)
            result.add_event(PipelinePhase.GOVERN, "replan_applied", "replanned",
                             replan_count=replan_count, interventions=policy_result.interventions)

    # ── Phase 3: Generate ─────────────────────────────────────────────────────

    def _phase_generate(
        self, intent_id: str, signature: StateSignature, result: KernelResult
    ) -> bool:
        plan = self.planner.plan(signature)
        result.execution_plan = plan
        self._audit(intent_id, PipelinePhase.GENERATE, "plan_generated", "ok",
                    step_count=plan.step_count, consistency_unit=plan.consistency_unit.value,
                    write_mode=plan.write_mode.value)
        result.add_event(PipelinePhase.GENERATE, "plan_generated", "ok",
                         step_count=plan.step_count, consistency_unit=plan.consistency_unit.value,
                         write_mode=plan.write_mode.value)

        if not self.config.enable_codegen:
            return False

        generated = self.codegen.generate(plan)
        result.generated_code = generated
        self._audit(intent_id, PipelinePhase.GENERATE, "code_generated", "ok",
                    language=generated.language, line_count=generated.line_count)
        result.add_event(PipelinePhase.GENERATE, "code_generated", "ok",
                         language=generated.language, line_count=generated.line_count)

        if not self.config.enable_static_validation:
            return False

        sv_result = self.static_validator.validate(
            generated, signature, self.schema_contract, backend=self.codegen)
        result.static_validation = sv_result
        sv_outcome = "passed" if sv_result.passed else "blocked"
        self._audit(intent_id, PipelinePhase.GENERATE, "static_validation", sv_outcome,
                    checks=sv_result.checks_performed, faults=[f.code for f in sv_result.faults])
        result.add_event(PipelinePhase.GENERATE, "static_validation", sv_outcome,
                         checks=sv_result.checks_performed, faults=[f.code for f in sv_result.faults])

        if not sv_result.passed:
            result.state = DecisionState.BLOCKED
            result.blocked_reason = f"Static validation failed: {', '.join(sv_result.fault_codes)}"
            result.signature = signature
            return True
        return False

    # ── Phase 4: Execute ──────────────────────────────────────────────────────

    def _phase_execute(
        self, intent_id: str, signature: StateSignature, result: KernelResult, replan_count: int,
    ) -> bool:
        plan = result.execution_plan
        generated = result.generated_code
        exec_state = self.partial_execution_manager.execute(
            plan, generated, signature, self.schema_contract)
        result.execution_state = exec_state
        result.sandbox_result = exec_state.sandbox_result
        result.runtime_validation = exec_state.runtime_validation

        self._audit(intent_id, PipelinePhase.EXECUTE, "execution_completed",
                    exec_state.publish_state.value, publish_state=exec_state.publish_state.value,
                    quarantined=exec_state.quarantined_steps,
                    committed=exec_state.committed_steps)
        result.add_event(PipelinePhase.EXECUTE, "execution_completed",
                         exec_state.publish_state.value, publish_state=exec_state.publish_state.value,
                         quarantined=exec_state.quarantined_steps,
                         committed=exec_state.committed_steps)

        projection = self.state_projection.project(signature, exec_state)
        self._audit(intent_id, PipelinePhase.EXECUTE, "state_projected",
                    projection.projection_type, snapshot_version=projection.snapshot_version,
                    datasets_updated=projection.dataset_states_updated,
                    projected=projection.projected, audit_only=projection.audit_only)
        result.add_event(PipelinePhase.EXECUTE, "state_projected",
                         projection.projection_type, snapshot_version=projection.snapshot_version,
                         datasets_updated=projection.dataset_states_updated,
                         projected=projection.projected, audit_only=projection.audit_only)

        if exec_state.publish_state in (PublishState.ROLLED_BACK, PublishState.QUARANTINED,
                                         PublishState.COMMITTED_NOT_PUBLISHED):
            state_map = {
                PublishState.ROLLED_BACK: (DecisionState.ROLLED_BACK, "Execution rolled back."),
                PublishState.QUARANTINED: (DecisionState.QUARANTINED,
                                            f"Steps quarantined: {exec_state.quarantined_steps}"),
                PublishState.COMMITTED_NOT_PUBLISHED: (DecisionState.PARTIALLY_COMMITTED, ""),
            }
            d_state, reason = state_map[exec_state.publish_state]
            result.state = d_state
            result.blocked_reason = reason
            result.signature = signature
            self._finalize_execution_result(result, signature, replan_count)
            return True
        return False

    # ── Phase 5: Validate ─────────────────────────────────────────────────────

    def _phase_validate(
        self, intent_id: str, signature: StateSignature, result: KernelResult, replan_count: int,
    ) -> None:
        if not self.config.phase_validate:
            return

        policy_result = result.policy_result
        has_warnings = (
            policy_result is not None
            and any(f.severity == FaultSeverity.WARNING for f in policy_result.faults)
        )

        if has_warnings and self.config.warnings_are_blocking:
            result.state = DecisionState.BLOCKED
            result.blocked_reason = "Warnings treated as blocking (config)."
        elif has_warnings or replan_count > 0:
            result.state = DecisionState.APPROVED_WITH_WARNINGS
        else:
            result.state = DecisionState.APPROVED

        result.signature = signature
        self._finalize_execution_result(result, signature, replan_count)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _strict_normalization_fault(self, resolution: SemanticResolution) -> Fault | None:
        sig = resolution.signature
        if not sig.datasets:
            return Fault(
                code="NORMALIZATION_NO_CATALOG_DATASET_MATCH", family=FaultFamily.SEMANTIC,
                severity=FaultSeverity.CRITICAL, stage="intent_normalizer",
                message="Strict normalization blocked the intent because no catalog dataset was matched.",
                mandatory_action=PolicyAction.BLOCK,
                remediation=("Reference datasets that exist in the catalog or update the catalog.",),
            )
        if resolution.confidence_score < self.config.min_normalizer_confidence:
            return Fault(
                code="NORMALIZATION_LOW_CONFIDENCE", family=FaultFamily.SEMANTIC,
                severity=FaultSeverity.HIGH, stage="intent_normalizer",
                message=(
                    f"Strict normalization blocked: confidence {resolution.confidence_score:.2f} "
                    f"below {self.config.min_normalizer_confidence:.2f}."
                ),
                mandatory_action=PolicyAction.BLOCK,
                remediation=("Make the requested datasets, target layer, and operation explicit.",),
            )
        return None

    def _audit(
        self, intent_id: str, stage: str, event_type: str, outcome: str, **details: Any
    ) -> None:
        self.audit_trail.record(
            intent_id=intent_id, stage=str(stage), event_type=event_type, outcome=outcome,
            policy_bundle_version=self.config.policy_bundle_version, **details,
        )

    def _finalize_execution_result(
        self, result: KernelResult, signature: StateSignature, replan_count: int,
    ) -> None:
        intent_id = result.intent_id
        final_state = result.state
        exec_state = result.execution_state
        policy_result = result.policy_result

        self.context_registry.record_execution(
            intent_id=intent_id, outcome=final_state.value,
            signature_hash=signature.signature_hash,
        )
        self._audit(intent_id, PipelinePhase.VALIDATE, "final_decision",
                    final_state.value, signature_hash=signature.signature_hash,
                    replan_count=replan_count,
                    warnings=final_state == DecisionState.APPROVED_WITH_WARNINGS)
        result.add_event(PipelinePhase.VALIDATE, "final_decision",
                         final_state.value, signature_hash=signature.signature_hash,
                         replan_count=replan_count,
                         warnings=final_state == DecisionState.APPROVED_WITH_WARNINGS)

        if not self.config.enable_promotion:
            return

        all_faults: list[str] = []
        if policy_result:
            all_faults.extend(f.code for f in policy_result.faults)
        if exec_state:
            all_faults.extend(f.code for f in exec_state.faults)

        cost_dbu = 0.0
        duration_seconds = 0.0
        if exec_state and exec_state.sandbox_result:
            cost_dbu = exec_state.sandbox_result.aggregate_metrics.cost_dbu
            duration_seconds = exec_state.sandbox_result.aggregate_metrics.duration_seconds

        exec_record = ExecutionRecord(
            signature_hash=signature.signature_hash, timestamp=_utcnow(),
            success=final_state in (DecisionState.APPROVED, DecisionState.APPROVED_WITH_WARNINGS),
            replanned=replan_count > 0, cost_dbu=cost_dbu, duration_seconds=duration_seconds,
            faults=all_faults,
            policy_compliant=final_state not in (DecisionState.ROLLED_BACK, DecisionState.QUARANTINED),
            pii_exposure=any("PII" in code for code in all_faults),
            layer_adherent=final_state != DecisionState.ROLLED_BACK,
        )
        self.promotion_engine.record_execution(exec_record)

        skill, scores = self.promotion_engine.evaluate(
            signature.signature_hash,
            policy_bundle_version=self.config.policy_bundle_version,
            catalog_snapshot_version=self.config.catalog_snapshot_version,
        )
        self._audit(intent_id, PipelinePhase.VALIDATE, "promotion_evaluation",
                    skill.state.value, ifo=scores.ifo, ifs=scores.ifs,
                    ifg=scores.ifg, idi=scores.idi, execution_count=scores.execution_count,
                    skill_state=skill.state.value)
        result.add_event(PipelinePhase.VALIDATE, "promotion_evaluation",
                         skill.state.value, ifo=scores.ifo, ifs=scores.ifs,
                         ifg=scores.ifg, idi=scores.idi, execution_count=scores.execution_count,
                         skill_state=skill.state.value)

        if skill.state == SkillState.ACTIVE and final_state == DecisionState.APPROVED:
            result.state = DecisionState.PROMOTION_CANDIDATE


# ── Standalone helpers ───────────────────────────────────────────────────────


def _apply_interventions(
    signature: StateSignature, policy_result: PolicyResult,
) -> StateSignature | None:
    fault_codes = {f.code for f in policy_result.faults}
    overrides: dict[str, Any] = {}
    if "GOVERNANCE_RAW_PII_IN_PROTECTED_LAYER" in fault_codes:
        overrides["no_pii_raw"] = True
    if "FINOPS_MISSING_TEMPORAL_PREDICATE" in fault_codes:
        if not signature.constraints.partition_by:
            overrides["partition_by"] = ("processing_date",)
    if "CONTRACT_TYPE_ENFORCEMENT_DISABLED" in fault_codes:
        overrides["enforce_types"] = True
    if "CONTRACT_MISSING_MERGE_KEY" in fault_codes:
        overrides["merge_key_required"] = True
    if "FINOPS_SENSITIVE_WITHOUT_PARTITION" in fault_codes:
        if not signature.constraints.partition_by:
            overrides["partition_by"] = ("processing_date",)
    if not overrides:
        return None
    return signature.with_constraints(**overrides)
