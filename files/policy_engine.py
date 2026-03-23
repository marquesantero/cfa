"""
CFA Policy Engine
=================
Aplica regras de governança, FinOps e contrato ANTES da execução.
Nenhum plano é executado sem passar por aqui.

Princípios:
- Regras são declarativas: condição + ação + fault_code
- Versionadas via policy_bundle_version
- Resultado: approve / replan / block
- Max 3 replans antes de block terminal
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .types import (
    StateSignature,
    PolicyResult,
    PolicyAction,
    Fault,
    FaultFamily,
    FaultSeverity,
    TargetLayer,
    DatasetClassification,
)


MAX_REPLAN_ATTEMPTS = 3


# ─── Contrato de Regra ────────────────────────────────────────────────────────

@dataclass
class PolicyRule:
    """
    Unidade mínima de uma regra de governança.
    Condition: função que recebe a Signature e retorna True se a regra dispara.
    Action: o que fazer quando dispara.
    """
    name: str
    condition: Callable[[StateSignature], bool]
    action: PolicyAction
    fault_code: str
    fault_family: FaultFamily
    severity: FaultSeverity
    message: str
    remediation: list[str] = field(default_factory=list)
    detected_before_execution: bool = True

    def evaluate(self, signature: StateSignature) -> Fault | None:
        """Retorna Fault se a regra disparou, None caso contrário."""
        if self.condition(signature):
            return Fault(
                code=self.fault_code,
                family=self.fault_family,
                severity=self.severity,
                stage="policy_engine",
                message=self.message,
                mandatory_action=self.action,
                remediation=self.remediation,
                detected_before_execution=self.detected_before_execution,
            )
        return None


# ─── Ruleset Padrão ───────────────────────────────────────────────────────────

def build_default_ruleset() -> list[PolicyRule]:
    """
    Conjunto de regras padrão do CFA.
    Em produção, este ruleset seria carregado de um policy_bundle versionado.
    """
    return [

        # ── Governança / PII ──────────────────────────────────────────────────
        PolicyRule(
            name="forbid_raw_pii_in_silver_or_gold",
            condition=lambda sig: (
                sig.writes_to_protected_layer
                and sig.contains_pii
                and not sig.constraints.no_pii_raw  # dispara quando NÃO há política de PII
            ),
            action=PolicyAction.REPLAN,
            fault_code="GOVERNANCE_RAW_PII_IN_PROTECTED_LAYER",
            fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.CRITICAL,
            message="PII detectado sem tratamento em escrita para camada protegida.",
            remediation=[
                "Aplicar sha256() nas colunas PII antes do join",
                "Ou usar drop() para remover colunas sensíveis",
                "Verificar: datasets com pii_columns devem ter transformação explícita",
            ],
        ),

        PolicyRule(
            name="require_pii_anonymization_declaration",
            condition=lambda sig: (
                sig.contains_pii
                and not sig.constraints.no_pii_raw
            ),
            action=PolicyAction.BLOCK,
            fault_code="GOVERNANCE_PII_WITHOUT_POLICY",
            fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.CRITICAL,
            message="Datasets com PII presentes mas no_pii_raw=False sem justificativa.",
            remediation=[
                "Definir explicitamente constraints.no_pii_raw=True",
                "Ou adicionar justificativa de tratamento de PII ao domínio",
            ],
        ),

        # ── FinOps ────────────────────────────────────────────────────────────
        PolicyRule(
            name="require_partition_filter_for_high_volume",
            condition=lambda sig: (
                any(d.classification == DatasetClassification.HIGH_VOLUME
                    for d in sig.datasets)
                and len(sig.constraints.partition_by) == 0
            ),
            action=PolicyAction.REPLAN,
            fault_code="FINOPS_MISSING_TEMPORAL_PREDICATE",
            fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.HIGH,
            message="Dataset de alto volume sem filtro de partição — risco de full scan.",
            remediation=[
                "Adicionar constraints.partition_by com coluna temporal",
                "Exemplo: partition_by: [processing_date]",
            ],
        ),

        PolicyRule(
            name="warn_on_sensitive_without_partition",
            condition=lambda sig: (
                any(d.classification == DatasetClassification.SENSITIVE
                    for d in sig.datasets)
                and len(sig.constraints.partition_by) == 0
            ),
            action=PolicyAction.REPLAN,
            fault_code="FINOPS_SENSITIVE_WITHOUT_PARTITION",
            fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.WARNING,
            message="Dataset sensível sem particionamento declarado.",
            remediation=[
                "Adicionar partition_by para limitar escopo de processamento",
            ],
        ),

        # ── Contrato de Dados ─────────────────────────────────────────────────
        PolicyRule(
            name="require_merge_key_for_silver_gold",
            condition=lambda sig: (
                sig.writes_to_protected_layer
                and not sig.constraints.merge_key_required
            ),
            action=PolicyAction.BLOCK,
            fault_code="CONTRACT_MISSING_MERGE_KEY",
            fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.CRITICAL,
            message="Escrita em Silver/Gold sem merge_key declarada — append direto proibido.",
            remediation=[
                "Definir constraints.merge_key_required=True",
                "Garantir que o Planner use operação merge, não append",
            ],
        ),

        PolicyRule(
            name="enforce_type_checking",
            condition=lambda sig: (
                sig.writes_to_protected_layer
                and not sig.constraints.enforce_types
            ),
            action=PolicyAction.REPLAN,
            fault_code="CONTRACT_TYPE_ENFORCEMENT_DISABLED",
            fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.HIGH,
            message="enforce_types=False em escrita para camada protegida.",
            remediation=[
                "Habilitar constraints.enforce_types=True",
                "Definir schema esperado no catálogo",
            ],
        ),

        # ── Cost Ceiling ──────────────────────────────────────────────────────
        PolicyRule(
            name="enforce_cost_ceiling",
            condition=lambda sig: (
                sig.constraints.max_cost_dbu is not None
                and sig.constraints.max_cost_dbu <= 0
            ),
            action=PolicyAction.BLOCK,
            fault_code="FINOPS_INVALID_COST_CEILING",
            fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.HIGH,
            message="max_cost_dbu inválido (deve ser > 0).",
            remediation=["Definir constraints.max_cost_dbu com valor positivo"],
        ),
    ]


# ─── Policy Engine ────────────────────────────────────────────────────────────

class PolicyEngine:
    """
    Aplica todas as regras de governança à State Signature.

    Fluxo:
    1. Avalia cada regra contra a Signature
    2. Coleta todos os Faults
    3. Determina ação: approve / replan / block
    4. Controla limite de replanejamentos
    """

    def __init__(
        self,
        rules: list[PolicyRule] | None = None,
        policy_bundle_version: str = "v1.0",
        max_replan_attempts: int = MAX_REPLAN_ATTEMPTS,
    ):
        self.rules = rules or build_default_ruleset()
        self.policy_bundle_version = policy_bundle_version
        self.max_replan_attempts = max_replan_attempts

    def evaluate(
        self,
        signature: StateSignature,
        replan_count: int = 0,
    ) -> PolicyResult:
        """
        Avalia a Signature contra todas as regras.

        Args:
            signature: A State Signature a avaliar
            replan_count: Número de replans já realizados neste ciclo

        Returns:
            PolicyResult com action, faults e intervenções obrigatórias
        """

        # Limite de replanejamentos atingido → block terminal
        if replan_count >= self.max_replan_attempts:
            return PolicyResult(
                action=PolicyAction.BLOCK,
                replan_count=replan_count,
                reasoning=(
                    f"Limite de {self.max_replan_attempts} replanejamentos atingido. "
                    "Intervenção manual necessária."
                ),
                faults=[
                    Fault(
                        code="POLICY_MAX_REPLAN_EXCEEDED",
                        family=FaultFamily.SEMANTIC,
                        severity=FaultSeverity.CRITICAL,
                        stage="policy_engine",
                        message=f"Máximo de {self.max_replan_attempts} replans excedido.",
                        mandatory_action=PolicyAction.BLOCK,
                        remediation=["Revisar a intenção manualmente e corrigir os faults anteriores"],
                    )
                ],
            )

        # Avaliar todas as regras
        faults: list[Fault] = []
        for rule in self.rules:
            fault = rule.evaluate(signature)
            if fault:
                faults.append(fault)

        # Determinar ação final
        action = self._determine_action(faults)

        # Coletar intervenções obrigatórias (para guiar o replanejamento)
        interventions = []
        if action == PolicyAction.REPLAN:
            for fault in faults:
                interventions.extend(fault.remediation)

        # Gerar reasoning
        reasoning = self._build_reasoning(action, faults, replan_count)

        return PolicyResult(
            action=action,
            faults=faults,
            interventions=list(dict.fromkeys(interventions)),  # deduplica mantendo ordem
            replan_count=replan_count,
            reasoning=reasoning,
        )

    def _determine_action(self, faults: list[Fault]) -> PolicyAction:
        """
        Regra de decisão: o fault mais severo determina a ação.
        BLOCK > REPLAN > APPROVE
        """
        if not faults:
            return PolicyAction.APPROVE

        # Se há qualquer fault com ação BLOCK → block
        if any(f.mandatory_action == PolicyAction.BLOCK for f in faults):
            return PolicyAction.BLOCK

        # Se há faults com ação REPLAN → replan
        if any(f.mandatory_action == PolicyAction.REPLAN for f in faults):
            return PolicyAction.REPLAN

        # Apenas warnings → approve (com warnings registrados)
        return PolicyAction.APPROVE

    def _build_reasoning(
        self,
        action: PolicyAction,
        faults: list[Fault],
        replan_count: int,
    ) -> str:
        if not faults:
            return "Todas as regras passaram. Execução aprovada."

        fault_summary = "; ".join(f.code for f in faults)
        base = f"Action={action.value} | Faults=[{fault_summary}]"

        if action == PolicyAction.REPLAN:
            base += f" | Replan {replan_count + 1}/{self.max_replan_attempts}"
        elif action == PolicyAction.BLOCK:
            if replan_count >= self.max_replan_attempts:
                base += " | TERMINAL: limite de replans atingido"
            else:
                base += " | TERMINAL: fault crítico irrecuperável"

        return base

    def add_rule(self, rule: PolicyRule) -> None:
        """Adiciona uma regra custom ao engine."""
        self.rules.append(rule)

    def describe_rules(self) -> list[dict]:
        """Retorna descrição de todas as regras ativas."""
        return [
            {
                "name": r.name,
                "action": r.action.value,
                "fault_code": r.fault_code,
                "severity": r.severity.value,
            }
            for r in self.rules
        ]
