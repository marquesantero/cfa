"""
CFA Kernel Orchestrator
=======================
O maestro do pipeline.

Orquestra o fluxo completo:
Intent → Normalize → Confirm → Policy → Decision

É o ponto de entrada único do CFA Kernel.
Tudo passa por aqui.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from .types import (
    DecisionState,
    FaultFamily,
    FaultSeverity,
    KernelResult,
    PolicyAction,
    PolicyResult,
    SemanticResolution,
    StateSignature,
    Fault,
)
from .normalizer import (
    ConfirmationOrchestrator,
    HumanConfirmationHandler,
    IntentNormalizer,
    NormalizerBackend,
    MockNormalizerBackend,
    AutoApproveHandler,
)
from .policy_engine import PolicyEngine, PolicyRule


# ─── Context Registry (in-memory para o Kernel) ───────────────────────────────

class InMemoryContextRegistry:
    """
    Context Registry em memória para o CFA Kernel.
    Fase 1: sem persistência — suficiente para o kernel funcionar.
    Fase 4: será substituído por implementação com snapshot versionado.
    """

    def __init__(self):
        self._state: dict = {
            "datasets": {},
            "execution_history": [],
            "version_id": "v_initial",
        }

    @property
    def version_id(self) -> str:
        return self._state["version_id"]

    def get_environment_state(self) -> dict:
        return dict(self._state)

    def get_dataset_state(self, name: str) -> dict | None:
        return self._state["datasets"].get(name)

    def set_dataset_state(self, name: str, state: dict) -> None:
        self._state["datasets"][name] = state
        self._state["version_id"] = f"v_{uuid.uuid4().hex[:8]}"

    def record_execution(self, intent_id: str, outcome: str, signature_hash: str) -> None:
        self._state["execution_history"].append({
            "intent_id": intent_id,
            "outcome": outcome,
            "signature_hash": signature_hash,
            "timestamp": datetime.utcnow().isoformat(),
            "version_id": self.version_id,
        })


# ─── Kernel Config ────────────────────────────────────────────────────────────

@dataclass
class KernelConfig:
    """Configuração do Kernel Orchestrator."""
    policy_bundle_version: str = "v1.0"
    catalog_snapshot_version: str = "catalog_default"
    max_replan_attempts: int = 3
    confirmation_timeout_seconds: int = 300
    # Se True, warnings não bloqueiam execução
    warnings_are_blocking: bool = False


# ─── Kernel Orchestrator ──────────────────────────────────────────────────────

class KernelOrchestrator:
    """
    Ponto de entrada único do CFA Kernel.

    Fase 1 do whitepaper:
    - Avalia intenções
    - Produz decisões
    - Não executa código ainda (isso é Fase 2)

    Uso:
        kernel = KernelOrchestrator()
        result = kernel.process("Junte NFe com Clientes e salve na Silver")
        if result.is_executable:
            # prosseguir para execução (Fase 2)
    """

    def __init__(
        self,
        normalizer_backend: NormalizerBackend | None = None,
        human_handler: HumanConfirmationHandler | None = None,
        policy_rules: list[PolicyRule] | None = None,
        context_registry: InMemoryContextRegistry | None = None,
        catalog: dict | None = None,
        config: KernelConfig | None = None,
    ):
        self.config = config or KernelConfig()

        # Componentes
        self.normalizer = IntentNormalizer(
            backend=normalizer_backend or MockNormalizerBackend(),
            policy_bundle_version=self.config.policy_bundle_version,
            catalog_snapshot_version=self.config.catalog_snapshot_version,
        )

        self.confirmation = ConfirmationOrchestrator(
            human_handler=human_handler or AutoApproveHandler(),
            timeout_seconds=self.config.confirmation_timeout_seconds,
        )

        self.policy = PolicyEngine(
            rules=policy_rules,
            policy_bundle_version=self.config.policy_bundle_version,
            max_replan_attempts=self.config.max_replan_attempts,
        )

        self.context_registry = context_registry or InMemoryContextRegistry()
        self.catalog = catalog or {"datasets": {}}

    def process(self, raw_intent: str) -> KernelResult:
        """
        Processa uma intenção em linguagem natural pelo pipeline completo do Kernel.

        Pipeline (Fase 1):
        1.  Consulta Context Registry (environment_state)
        2.  Normalização semântica
        3.  Confirmation Orchestrator
        4.  Policy Engine (com ciclo de replanejamento)
        5.  Decision final

        Args:
            raw_intent: A intenção em linguagem natural

        Returns:
            KernelResult com estado de decisão e signature aprovada (se houver)
        """
        intent_id = str(uuid.uuid4())
        result = KernelResult(
            intent_id=intent_id,
            state=DecisionState.BLOCKED,       # pessimistic default
            signature=None,
            policy_result=None,
            resolution=None,
        )

        # ── Etapa 1: Consultar Context Registry ──────────────────────────────
        environment_state = self.context_registry.get_environment_state()
        result.add_audit_event(
            stage="context_registry",
            event_type="environment_state_consulted",
            outcome="ok",
            version_id=self.context_registry.version_id,
        )

        # ── Etapa 2: Normalização Semântica ───────────────────────────────────
        try:
            resolution = self.normalizer.normalize(
                raw_intent=raw_intent,
                environment_state=environment_state,
                catalog=self.catalog,
                context_registry_version_id=self.context_registry.version_id,
            )
            result.resolution = resolution
            result.add_audit_event(
                stage="intent_normalizer",
                event_type="semantic_resolution",
                outcome="resolved",
                confidence=resolution.confidence_score,
                ambiguity=resolution.ambiguity_level.value,
                confirmation_mode=resolution.confirmation_mode.value,
                signature_hash=resolution.signature.signature_hash,
                domain=resolution.signature.domain,
                datasets=[d.name for d in resolution.signature.datasets],
            )
        except Exception as e:
            result.blocked_reason = f"Falha na normalização semântica: {e}"
            result.add_audit_event(
                stage="intent_normalizer",
                event_type="normalization_error",
                outcome="error",
                error=str(e),
            )
            return result

        # ── Etapa 3: Confirmation Orchestrator ────────────────────────────────
        approved, confirm_reason, confirm_fault = self.confirmation.process(resolution)
        result.add_audit_event(
            stage="confirmation_orchestrator",
            event_type="confirmation",
            outcome="approved" if approved else "rejected",
            mode=resolution.confirmation_mode.value,
            reason=confirm_reason,
        )

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

        # ── Etapa 4: Policy Engine (com ciclo de replanejamento) ──────────────
        signature = resolution.signature
        replan_count = 0

        while True:
            policy_result = self.policy.evaluate(signature, replan_count=replan_count)
            result.policy_result = policy_result

            result.add_audit_event(
                stage="policy_engine",
                event_type="policy_evaluation",
                outcome=policy_result.action.value,
                replan_count=replan_count,
                faults=[f.code for f in policy_result.faults],
                reasoning=policy_result.reasoning,
            )

            if policy_result.action == PolicyAction.APPROVE:
                break

            if policy_result.action == PolicyAction.BLOCK:
                result.state = DecisionState.BLOCKED
                result.blocked_reason = policy_result.reasoning
                result.add_audit_event(
                    stage="policy_engine",
                    event_type="policy_block",
                    outcome="blocked",
                    reason=result.blocked_reason,
                )
                return result

            # REPLAN: tentar aplicar intervenções
            if policy_result.action == PolicyAction.REPLAN:
                result.replan_history.append(policy_result)
                replan_count += 1

                new_signature = self._apply_interventions(signature, policy_result)
                if new_signature is None:
                    # Não conseguiu resolver — block
                    result.state = DecisionState.BLOCKED
                    result.blocked_reason = "Replanejamento falhou: intervenções não aplicáveis."
                    return result

                signature = new_signature
                result.add_audit_event(
                    stage="kernel_orchestrator",
                    event_type="replan_applied",
                    outcome="replanned",
                    replan_count=replan_count,
                    interventions=policy_result.interventions,
                )

        # ── Etapa 5: Decision Final ───────────────────────────────────────────
        has_warnings = any(
            f.severity == FaultSeverity.WARNING
            for f in policy_result.faults
        )

        if has_warnings and self.config.warnings_are_blocking:
            final_state = DecisionState.BLOCKED
            result.blocked_reason = "Warnings tratados como bloqueantes (config)."
        elif has_warnings:
            final_state = DecisionState.APPROVED_WITH_WARNINGS
        elif replan_count > 0:
            final_state = DecisionState.APPROVED_WITH_WARNINGS
        else:
            final_state = DecisionState.APPROVED

        result.state = final_state
        result.signature = signature

        # Registrar no Context Registry
        self.context_registry.record_execution(
            intent_id=intent_id,
            outcome=final_state.value,
            signature_hash=signature.signature_hash,
        )

        result.add_audit_event(
            stage="decision_engine",
            event_type="final_decision",
            outcome=final_state.value,
            signature_hash=signature.signature_hash,
            replan_count=replan_count,
            warnings=has_warnings,
        )

        return result

    def _apply_interventions(
        self,
        signature: StateSignature,
        policy_result: PolicyResult,
    ) -> StateSignature | None:
        """
        Tenta aplicar as intervenções do Policy Engine na Signature.
        Retorna nova Signature corrigida, ou None se não for possível.

        Em Fase 1: aplica correções automáticas conhecidas.
        Em Fase 2+: o Planner poderá fazer ajustes mais sofisticados.
        """
        from dataclasses import replace
        import copy

        fault_codes = {f.code for f in policy_result.faults}
        new_constraints = copy.copy(signature.constraints)
        new_datasets = list(signature.datasets)
        changed = False

        # Correção automática: PII sem política → ativar no_pii_raw
        if "GOVERNANCE_RAW_PII_IN_PROTECTED_LAYER" in fault_codes:
            new_constraints.no_pii_raw = True
            changed = True

        # Correção automática: sem partição → adicionar processing_date
        if "FINOPS_MISSING_TEMPORAL_PREDICATE" in fault_codes:
            if not new_constraints.partition_by:
                new_constraints.partition_by = ["processing_date"]
                changed = True

        # Correção automática: enforce_types desabilitado
        if "CONTRACT_TYPE_ENFORCEMENT_DISABLED" in fault_codes:
            new_constraints.enforce_types = True
            changed = True

        # Correção automática: merge_key ausente em Silver/Gold
        if "CONTRACT_MISSING_MERGE_KEY" in fault_codes:
            new_constraints.merge_key_required = True
            changed = True

        # Correção automática: particionamento ausente em dados sensíveis
        if "FINOPS_SENSITIVE_WITHOUT_PARTITION" in fault_codes:
            if not new_constraints.partition_by:
                new_constraints.partition_by = ["processing_date"]
                changed = True

        if not changed:
            # Nenhuma correção automática disponível
            return None

        # Criar nova Signature com corrections
        # (nova Signature = novo execution_context para rastreabilidade)
        from .types import ExecutionContext
        new_ctx = ExecutionContext(
            policy_bundle_version=signature.execution_context.policy_bundle_version,
            catalog_snapshot_version=signature.execution_context.catalog_snapshot_version,
            context_registry_version_id=signature.execution_context.context_registry_version_id,
        )

        return StateSignature(
            domain=signature.domain,
            intent=signature.intent,
            target_layer=signature.target_layer,
            datasets=new_datasets,
            constraints=new_constraints,
            execution_context=new_ctx,
            intent_id=signature.intent_id,            # mantém o mesmo intent_id
            source_intent_raw=signature.source_intent_raw,
        )

    def describe(self) -> dict:
        """Retorna descrição do estado atual do Kernel."""
        return {
            "config": {
                "policy_bundle_version": self.config.policy_bundle_version,
                "catalog_snapshot_version": self.config.catalog_snapshot_version,
                "max_replan_attempts": self.config.max_replan_attempts,
            },
            "context_registry_version": self.context_registry.version_id,
            "catalog_datasets": list(self.catalog.get("datasets", {}).keys()),
            "policy_rules": len(self.policy.rules),
            "active_rules": [r["name"] for r in self.policy.describe_rules()],
        }
