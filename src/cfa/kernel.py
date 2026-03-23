"""
CFA Kernel Orchestrator
=======================
The maestro of the pipeline.

Orchestrates the full flow:
Intent -> Normalize -> Confirm -> Policy -> Plan -> CodeGen -> StaticValidation -> Sandbox -> RuntimeValidation -> Decision

Single entry point for the CFA Kernel.
Everything passes through here.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from .audit import AuditTrail
from .context import ContextRegistry
from .normalizer import (
    AutoApproveHandler,
    ConfirmationHandler,
    ConfirmationOrchestrator,
    IntentNormalizer,
    MockNormalizerBackend,
    NormalizerBackend,
)
from .codegen import CodeGenBackend, GeneratedCode, PySparkGenerator
from .planner import ExecutionPlan, ExecutionPlanner
from .policy import PolicyEngine, PolicyRule
from .static_validation import StaticValidationResult, StaticValidator
from .sandbox import SandboxBackend, SandboxExecutor, MockSandboxBackend
from .runtime_validation import RuntimeValidator, RuntimeThresholds
from .state_projection import StateProjectionProtocol
from .indices import ExecutionRecord, IndexCalculator
from .promotion import PromotionEngine, PromotionPolicy, SkillState
from .partial_execution import (
    FailurePolicy,
    PartialExecutionManager,
    PartialExecutionState,
    PublishState,
    RetryPolicy,
)
from .types import (
    DecisionState,
    FaultSeverity,
    KernelResult,
    PolicyAction,
    PolicyResult,
    StateSignature,
    _utcnow,
)


# ── Kernel Config ────────────────────────────────────────────────────────────


@dataclass
class KernelConfig:
    policy_bundle_version: str = "v1.0"
    catalog_snapshot_version: str = "catalog_default"
    max_replan_attempts: int = 3
    confirmation_timeout_seconds: int = 300
    warnings_are_blocking: bool = False
    enable_planning: bool = True      # Phase 2: generate execution plan
    enable_codegen: bool = True       # Phase 2: generate code from plan
    enable_static_validation: bool = True  # Phase 2: validate code before execution
    enable_sandbox: bool = True       # Phase 3: execute in sandbox
    failure_policy: FailurePolicy = FailurePolicy.SELECTIVE_QUARANTINE
    enable_promotion: bool = True     # Phase 5: promotion/demotion lifecycle


# ── Kernel Orchestrator ──────────────────────────────────────────────────────


class KernelOrchestrator:
    """
    Single entry point for the CFA Kernel.

    Phase 1:
    - Evaluates intents
    - Produces decisions
    - Does NOT execute code (that's Phase 2)

    Usage:
        kernel = KernelOrchestrator(catalog=CATALOG)
        result = kernel.process("Join NFe with Clientes and save to Silver")
        if result.is_executable:
            # proceed to execution (Phase 2)
    """

    def __init__(
        self,
        normalizer_backend: NormalizerBackend | None = None,
        confirmation_handler: ConfirmationHandler | None = None,
        policy_rules: list[PolicyRule] | None = None,
        context_registry: ContextRegistry | None = None,
        audit_trail: AuditTrail | None = None,
        catalog: dict[str, Any] | None = None,
        config: KernelConfig | None = None,
        planner: ExecutionPlanner | None = None,
        codegen_backend: CodeGenBackend | None = None,
        static_validator: StaticValidator | None = None,
        sandbox_backend: SandboxBackend | None = None,
        runtime_validator: RuntimeValidator | None = None,
        retry_policy: RetryPolicy | None = None,
        promotion_engine: PromotionEngine | None = None,
        schema_contract: dict[str, Any] | None = None,
    ) -> None:
        self.config = config or KernelConfig()
        self.context_registry = context_registry or ContextRegistry()
        self.audit_trail = audit_trail or AuditTrail()
        self.catalog = catalog or {"datasets": {}}
        self.schema_contract = schema_contract

        self.normalizer = IntentNormalizer(
            backend=normalizer_backend or MockNormalizerBackend(),
            policy_bundle_version=self.config.policy_bundle_version,
            catalog_snapshot_version=self.config.catalog_snapshot_version,
        )

        self.confirmation = ConfirmationOrchestrator(
            handler=confirmation_handler or AutoApproveHandler(),
            timeout_seconds=self.config.confirmation_timeout_seconds,
        )

        self.policy = PolicyEngine(
            rules=policy_rules,
            policy_bundle_version=self.config.policy_bundle_version,
            max_replan_attempts=self.config.max_replan_attempts,
        )

        # Phase 2 components
        self.planner = planner or ExecutionPlanner()
        self.codegen = codegen_backend or PySparkGenerator()
        self.static_validator = static_validator or StaticValidator()

        # Phase 3 components
        self.sandbox_executor = SandboxExecutor(backend=sandbox_backend or MockSandboxBackend())
        self.runtime_validator = runtime_validator or RuntimeValidator()
        self.retry_policy = retry_policy or RetryPolicy()
        self.partial_execution_manager = PartialExecutionManager(
            sandbox=self.sandbox_executor,
            runtime_validator=self.runtime_validator,
            failure_policy=self.config.failure_policy,
            retry_policy=self.retry_policy,
        )

        # Phase 4 components
        self.state_projection = StateProjectionProtocol(self.context_registry)

        # Phase 5 components
        self.promotion_engine = promotion_engine or PromotionEngine(
            system_version="cfa_v2.0",
        )

    def process(self, raw_intent: str) -> KernelResult:
        """
        Process a natural language intent through the full Kernel pipeline.

        Pipeline (Phase 1):
        1. Consult Context Registry (environment_state)
        2. Semantic normalization
        3. Confirmation Orchestrator
        4. Policy Engine (with replan cycle)
        5. Final decision
        """
        intent_id = str(uuid.uuid4())
        result = KernelResult(
            intent_id=intent_id,
            state=DecisionState.BLOCKED,  # pessimistic default
        )
        pbv = self.config.policy_bundle_version

        # ── Step 1: Consult Context Registry ─────────────────────────────
        environment_state = self.context_registry.get_environment_state()
        self._audit(intent_id, "context_registry", "environment_state_consulted", "ok",
                    version_id=self.context_registry.version_id)
        result.add_event("context_registry", "environment_state_consulted", "ok",
                         version_id=self.context_registry.version_id)

        # ── Step 2: Semantic Normalization ───────────────────────────────
        try:
            resolution = self.normalizer.normalize(
                raw_intent=raw_intent,
                environment_state=environment_state,
                catalog=self.catalog,
                context_registry_version_id=self.context_registry.version_id,
            )
            result.resolution = resolution
            self._audit(intent_id, "intent_normalizer", "semantic_resolution", "resolved",
                        confidence=resolution.confidence_score,
                        confirmation_mode=resolution.confirmation_mode.value)
            result.add_event("intent_normalizer", "semantic_resolution", "resolved",
                             confidence=resolution.confidence_score,
                             confirmation_mode=resolution.confirmation_mode.value)
        except Exception as e:
            result.blocked_reason = f"Normalization failed: {e}"
            self._audit(intent_id, "intent_normalizer", "normalization_error", "error", error=str(e))
            result.add_event("intent_normalizer", "normalization_error", "error", error=str(e))
            return result

        # ── Step 3: Confirmation Orchestrator ────────────────────────────
        approved, confirm_reason, confirm_fault = self.confirmation.process(resolution)
        self._audit(intent_id, "confirmation_orchestrator", "confirmation",
                    "approved" if approved else "rejected",
                    mode=resolution.confirmation_mode.value, reason=confirm_reason)
        result.add_event("confirmation_orchestrator", "confirmation",
                         "approved" if approved else "rejected",
                         mode=resolution.confirmation_mode.value, reason=confirm_reason)

        if not approved:
            result.state = DecisionState.BLOCKED
            result.blocked_reason = confirm_reason
            if confirm_fault:
                result.policy_result = PolicyResult(
                    action=PolicyAction.BLOCK,
                    faults=[confirm_fault],
                    reasoning=confirm_reason,
                )
            return result

        # ── Step 4: Policy Engine (with replan cycle) ────────────────────
        signature = resolution.signature
        replan_count = 0

        while True:
            policy_result = self.policy.evaluate(signature, replan_count=replan_count)
            result.policy_result = policy_result

            self._audit(intent_id, "policy_engine", "policy_evaluation", policy_result.action.value,
                        replan_count=replan_count,
                        faults=[f.code for f in policy_result.faults])
            result.add_event("policy_engine", "policy_evaluation", policy_result.action.value,
                             replan_count=replan_count,
                             faults=[f.code for f in policy_result.faults])

            if policy_result.action == PolicyAction.APPROVE:
                break

            if policy_result.action == PolicyAction.BLOCK:
                result.state = DecisionState.BLOCKED
                result.blocked_reason = policy_result.reasoning
                return result

            # REPLAN
            result.replan_history.append(policy_result)
            replan_count += 1

            new_signature = self._apply_interventions(signature, policy_result)
            if new_signature is None:
                result.state = DecisionState.BLOCKED
                result.blocked_reason = "Replan failed: interventions not applicable."
                return result

            signature = new_signature
            self._audit(intent_id, "kernel_orchestrator", "replan_applied", "replanned",
                        replan_count=replan_count,
                        interventions=policy_result.interventions)
            result.add_event("kernel_orchestrator", "replan_applied", "replanned",
                             replan_count=replan_count,
                             interventions=policy_result.interventions)

        # ── Step 5: Execution Planning (Phase 2) ──────────────────────────
        if self.config.enable_planning:
            plan = self.planner.plan(signature)
            result.execution_plan = plan
            self._audit(intent_id, "execution_planner", "plan_generated", "ok",
                        step_count=plan.step_count,
                        consistency_unit=plan.consistency_unit.value,
                        write_mode=plan.write_mode.value)
            result.add_event("execution_planner", "plan_generated", "ok",
                             step_count=plan.step_count,
                             consistency_unit=plan.consistency_unit.value,
                             write_mode=plan.write_mode.value)

            # ── Step 6: Code Generation (Phase 2) ────────────────────────
            if self.config.enable_codegen:
                generated = self.codegen.generate(plan)
                result.generated_code = generated
                self._audit(intent_id, "code_generator", "code_generated", "ok",
                            language=generated.language,
                            line_count=generated.line_count)
                result.add_event("code_generator", "code_generated", "ok",
                                 language=generated.language,
                                 line_count=generated.line_count)

                # ── Step 7: Static Validation (Phase 2) ──────────────────
                if self.config.enable_static_validation:
                    sv_result = self.static_validator.validate(
                        generated, signature, self.schema_contract
                    )
                    result.static_validation = sv_result
                    sv_outcome = "passed" if sv_result.passed else "blocked"
                    self._audit(intent_id, "static_validation", "code_analysis", sv_outcome,
                                checks=sv_result.checks_performed,
                                faults=[f.code for f in sv_result.faults])
                    result.add_event("static_validation", "code_analysis", sv_outcome,
                                     checks=sv_result.checks_performed,
                                     faults=[f.code for f in sv_result.faults])

                    if not sv_result.passed:
                        result.state = DecisionState.BLOCKED
                        result.blocked_reason = (
                            f"Static validation failed: "
                            f"{', '.join(sv_result.fault_codes)}"
                        )
                        result.signature = signature
                        return result

                    # ── Step 8: Sandbox Execution (Phase 3) ─────────────
                    if self.config.enable_sandbox:
                        exec_state = self.partial_execution_manager.execute(
                            plan, generated, signature, self.schema_contract
                        )
                        result.execution_state = exec_state
                        result.sandbox_result = exec_state.sandbox_result
                        result.runtime_validation = exec_state.runtime_validation

                        self._audit(
                            intent_id, "sandbox", "execution_completed",
                            exec_state.publish_state.value,
                            publish_state=exec_state.publish_state.value,
                            quarantined=exec_state.quarantined_steps,
                            committed=exec_state.committed_steps,
                        )
                        result.add_event(
                            "sandbox", "execution_completed",
                            exec_state.publish_state.value,
                            publish_state=exec_state.publish_state.value,
                            quarantined=exec_state.quarantined_steps,
                            committed=exec_state.committed_steps,
                        )

                        # ── Step 9: State Projection (Phase 4, Invariant I4) ──
                        projection = self.state_projection.project(signature, exec_state)
                        self._audit(
                            intent_id, "state_projection", "projected",
                            projection.projection_type,
                            snapshot_version=projection.snapshot_version,
                            datasets_updated=projection.dataset_states_updated,
                            projected=projection.projected,
                            audit_only=projection.audit_only,
                        )
                        result.add_event(
                            "state_projection", "projected",
                            projection.projection_type,
                            snapshot_version=projection.snapshot_version,
                            datasets_updated=projection.dataset_states_updated,
                            projected=projection.projected,
                            audit_only=projection.audit_only,
                        )

                        if exec_state.publish_state == PublishState.ROLLED_BACK:
                            result.state = DecisionState.ROLLED_BACK
                            result.blocked_reason = "Execution rolled back."
                            result.signature = signature
                            self._finalize_execution_result(result, signature, replan_count)
                            return result

                        if exec_state.publish_state == PublishState.QUARANTINED:
                            result.state = DecisionState.QUARANTINED
                            result.blocked_reason = (
                                f"Steps quarantined: {exec_state.quarantined_steps}"
                            )
                            result.signature = signature
                            self._finalize_execution_result(result, signature, replan_count)
                            return result

                        if exec_state.publish_state == PublishState.COMMITTED_NOT_PUBLISHED:
                            result.state = DecisionState.PARTIALLY_COMMITTED
                            result.signature = signature
                            self._finalize_execution_result(result, signature, replan_count)
                            return result

        # ── Step 9: Final Decision ───────────────────────────────────────
        has_warnings = any(f.severity == FaultSeverity.WARNING for f in policy_result.faults)

        if has_warnings and self.config.warnings_are_blocking:
            final_state = DecisionState.BLOCKED
            result.blocked_reason = "Warnings treated as blocking (config)."
        elif has_warnings or replan_count > 0:
            final_state = DecisionState.APPROVED_WITH_WARNINGS
        else:
            final_state = DecisionState.APPROVED

        result.state = final_state
        result.signature = signature
        self._finalize_execution_result(result, signature, replan_count)

        return result

    def _apply_interventions(
        self, signature: StateSignature, policy_result: PolicyResult
    ) -> StateSignature | None:
        """
        Attempt to apply Policy Engine interventions to the Signature.
        Returns new corrected Signature, or None if not possible.
        """
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

    def _audit(self, intent_id: str, stage: str, event_type: str, outcome: str, **details: Any) -> None:
        self.audit_trail.record(
            intent_id=intent_id,
            stage=stage,
            event_type=event_type,
            outcome=outcome,
            policy_bundle_version=self.config.policy_bundle_version,
            **details,
        )

    def describe(self) -> dict[str, Any]:
        return {
            "config": {
                "policy_bundle_version": self.config.policy_bundle_version,
                "catalog_snapshot_version": self.config.catalog_snapshot_version,
                "max_replan_attempts": self.config.max_replan_attempts,
            },
            "context_registry_version": self.context_registry.version_id,
            "catalog_datasets": list(self.catalog.get("datasets", {}).keys()),
            "policy_rules": len(self.policy.rules),
            "audit_events": self.audit_trail.event_count,
        }

    def _finalize_execution_result(
        self,
        result: KernelResult,
        signature: StateSignature,
        replan_count: int,
    ) -> None:
        """Persist final outcome and feed lifecycle metrics for executed intents."""
        intent_id = result.intent_id
        final_state = result.state
        exec_state = result.execution_state
        policy_result = result.policy_result

        self.context_registry.record_execution(
            intent_id=intent_id,
            outcome=final_state.value,
            signature_hash=signature.signature_hash,
        )

        self._audit(
            intent_id,
            "decision_engine",
            "final_decision",
            final_state.value,
            signature_hash=signature.signature_hash,
            replan_count=replan_count,
            warnings=final_state == DecisionState.APPROVED_WITH_WARNINGS,
        )
        result.add_event(
            "decision_engine",
            "final_decision",
            final_state.value,
            signature_hash=signature.signature_hash,
            replan_count=replan_count,
            warnings=final_state == DecisionState.APPROVED_WITH_WARNINGS,
        )

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
            signature_hash=signature.signature_hash,
            timestamp=_utcnow(),
            success=final_state in (DecisionState.APPROVED, DecisionState.APPROVED_WITH_WARNINGS),
            replanned=replan_count > 0,
            cost_dbu=cost_dbu,
            duration_seconds=duration_seconds,
            faults=all_faults,
            policy_compliant=final_state not in (
                DecisionState.ROLLED_BACK,
                DecisionState.QUARANTINED,
            ),
            pii_exposure=any("PII" in code for code in all_faults),
            layer_adherent=final_state != DecisionState.ROLLED_BACK,
        )
        self.promotion_engine.record_execution(exec_record)

        skill, scores = self.promotion_engine.evaluate(
            signature.signature_hash,
            policy_bundle_version=self.config.policy_bundle_version,
            catalog_snapshot_version=self.config.catalog_snapshot_version,
        )

        self._audit(
            intent_id,
            "promotion_engine",
            "promotion_evaluation",
            skill.state.value,
            ifo=scores.ifo,
            ifs=scores.ifs,
            ifg=scores.ifg,
            idi=scores.idi,
            execution_count=scores.execution_count,
            skill_state=skill.state.value,
        )
        result.add_event(
            "promotion_engine",
            "promotion_evaluation",
            skill.state.value,
            ifo=scores.ifo,
            ifs=scores.ifs,
            ifg=scores.ifg,
            idi=scores.idi,
            execution_count=scores.execution_count,
            skill_state=skill.state.value,
        )

        if skill.state == SkillState.ACTIVE and final_state == DecisionState.APPROVED:
            result.state = DecisionState.PROMOTION_CANDIDATE
