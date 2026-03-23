"""
CFA Intent Normalizer + Confirmation Orchestrator
==================================================
Transforma linguagem natural em State Signature tipada.

O Normalizer é o componente mais crítico do pipeline:
um erro aqui contamina todo o sistema com perfeição determinística.

Arquitetura:
- Interface `NormalizerBackend` — agnóstico de LLM
- `IntentNormalizer` — orquestra resolução, contexto e assinatura
- `ConfirmationOrchestrator` — escalonamento por risco
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from .types import (
    AmbiguityLevel,
    ConfirmationMode,
    DatasetClassification,
    DatasetRef,
    ExecutionContext,
    FaultFamily,
    FaultSeverity,
    PolicyAction,
    SemanticResolution,
    SignatureConstraints,
    StateSignature,
    TargetLayer,
    Fault,
)


# ─── Interface do Backend ─────────────────────────────────────────────────────

@dataclass
class NormalizerInput:
    """Input para o backend de normalização."""
    raw_intent: str
    environment_state: dict           # do Context Registry
    catalog: dict                     # datasets disponíveis e metadados
    policy_bundle_version: str
    catalog_snapshot_version: str
    context_registry_version_id: str


@dataclass
class NormalizerOutput:
    """Output esperado do backend de normalização."""
    domain: str
    intent: str
    target_layer: str                 # "bronze" | "silver" | "gold"
    datasets: list[dict]              # [{"name": str, "classification": str, "pii_columns": [...]}]
    constraints: dict
    confidence_score: float           # [0.0 - 1.0]
    ambiguity_level: str              # "low" | "medium" | "high"
    competing_interpretations: list[str] = field(default_factory=list)
    environment_constraints_injected: list[str] = field(default_factory=list)
    reasoning: str = ""


class NormalizerBackend(ABC):
    """
    Interface que qualquer backend de resolução semântica deve implementar.

    Extension point declarado no whitepaper:
    - LLM (GPT-4, Claude, Gemini)
    - Rule-based parser
    - Hybrid (rules + LLM)
    - Mock para testes
    """

    @abstractmethod
    def resolve(self, input: NormalizerInput) -> NormalizerOutput:
        """Resolve a intenção em linguagem natural para estrutura formal."""
        ...


# ─── Backend Mock (para testes e desenvolvimento) ────────────────────────────

class MockNormalizerBackend(NormalizerBackend):
    """
    Backend determinístico para testes.
    Usa palavras-chave simples para simular resolução semântica.
    """

    LAYER_KEYWORDS = {
        TargetLayer.GOLD:   ["gold", "ouro", "master", "curated", "final"],
        TargetLayer.SILVER: ["silver", "prata", "refined", "trusted", "join", "reconcil"],
        TargetLayer.BRONZE: ["bronze", "raw", "ingest", "landing", "bronze"],
    }

    def resolve(self, input: NormalizerInput) -> NormalizerOutput:
        raw = input.raw_intent.lower()

        # Detectar camada alvo
        target_layer = "silver"
        for layer, keywords in self.LAYER_KEYWORDS.items():
            if any(kw in raw for kw in keywords):
                target_layer = layer.value
                break

        # Detectar datasets mencionados no catálogo
        datasets_found = []
        for dataset_name, meta in input.catalog.get("datasets", {}).items():
            if dataset_name.lower() in raw:
                datasets_found.append({
                    "name": dataset_name,
                    "classification": meta.get("classification", "internal"),
                    "pii_columns": meta.get("pii_columns", []),
                    "size_gb": meta.get("size_gb", 0.0),
                    "partition_column": meta.get("partition_column"),
                })

        # Detectar domínio
        domain = "general"
        domain_keywords = {
            "fiscal_data_processing": ["nfe", "nota fiscal", "fiscal", "tribut"],
            "customer_data":          ["client", "customer", "cpf", "cadastro"],
            "financial_data":         ["payment", "transac", "financ", "pagamento"],
        }
        for dom, keywords in domain_keywords.items():
            if any(kw in raw for kw in keywords):
                domain = dom
                break

        # Detectar intenção
        intent = "transform_and_persist"
        if any(w in raw for w in ["join", "reconcil", "merg"]):
            intent = "reconciliation_and_persist"
        elif any(w in raw for w in ["ingest", "load", "import"]):
            intent = "ingest"
        elif any(w in raw for w in ["aggregat", "summ", "group"]):
            intent = "aggregate_and_persist"

        # Detectar PII e calcular confiança
        has_pii = any(d.get("pii_columns") for d in datasets_found)
        confidence = 0.85 if datasets_found else 0.45
        if has_pii and target_layer in ("silver", "gold"):
            confidence -= 0.1  # mais incerteza com dados sensíveis

        # Verificar constraints do ambiente
        env_constraints = []
        for ds_name, ds_state in input.environment_state.get("datasets", {}).items():
            if ds_state.get("state") == "partially_committed":
                env_constraints.append(
                    f"{ds_name}.state=partially_committed → publish_allowed=false"
                )

        return NormalizerOutput(
            domain=domain,
            intent=intent,
            target_layer=target_layer,
            datasets=datasets_found,
            constraints={
                "no_pii_raw": True,
                "merge_key_required": target_layer in ("silver", "gold"),
                "enforce_types": True,
                "partition_by": ["processing_date"] if datasets_found else [],
            },
            confidence_score=round(confidence, 2),
            ambiguity_level="low" if confidence > 0.80 else "medium" if confidence > 0.60 else "high",
            competing_interpretations=[],
            environment_constraints_injected=env_constraints,
            reasoning=f"Mock backend: detected layer={target_layer}, "
                      f"datasets={[d['name'] for d in datasets_found]}, "
                      f"pii={has_pii}",
        )


# ─── Intent Normalizer ────────────────────────────────────────────────────────

class IntentNormalizer:
    """
    Transforma linguagem natural em State Signature tipada.

    Inputs obrigatórios (conforme whitepaper):
    1. user_intent (linguagem natural)
    2. context_registry.environment_state
    3. data_catalog

    O backend é injetável — qualquer NormalizerBackend pode ser usado.
    """

    def __init__(
        self,
        backend: NormalizerBackend,
        policy_bundle_version: str = "v1.0",
        catalog_snapshot_version: str = "catalog_default",
    ):
        self.backend = backend
        self.policy_bundle_version = policy_bundle_version
        self.catalog_snapshot_version = catalog_snapshot_version

    def normalize(
        self,
        raw_intent: str,
        environment_state: dict,
        catalog: dict,
        context_registry_version_id: str = "v_initial",
    ) -> SemanticResolution:
        """
        Resolve a intenção e retorna SemanticResolution.

        Raises:
            NormalizerError: se o backend falhar ou a saída for inválida
        """

        # Preparar input
        norm_input = NormalizerInput(
            raw_intent=raw_intent,
            environment_state=environment_state,
            catalog=catalog,
            policy_bundle_version=self.policy_bundle_version,
            catalog_snapshot_version=self.catalog_snapshot_version,
            context_registry_version_id=context_registry_version_id,
        )

        # Chamar backend
        output = self.backend.resolve(norm_input)

        # Construir State Signature
        signature = self._build_signature(output, raw_intent, context_registry_version_id)

        # Derivar ambiguity level
        ambiguity_map = {
            "low": AmbiguityLevel.LOW,
            "medium": AmbiguityLevel.MEDIUM,
            "high": AmbiguityLevel.HIGH,
        }
        ambiguity = ambiguity_map.get(output.ambiguity_level, AmbiguityLevel.MEDIUM)

        # Criar SemanticResolution (modo de confirmação é derivado automaticamente)
        resolution = SemanticResolution(
            signature=signature,
            confidence_score=output.confidence_score,
            ambiguity_level=ambiguity,
            competing_interpretations=output.competing_interpretations,
            environment_constraints_injected=output.environment_constraints_injected,
            reasoning=output.reasoning,
        )

        return resolution

    def _build_signature(
        self,
        output: NormalizerOutput,
        raw_intent: str,
        context_registry_version_id: str,
    ) -> StateSignature:
        """Converte NormalizerOutput em StateSignature tipada."""

        # Converter datasets
        layer_map = {
            "bronze": TargetLayer.BRONZE,
            "silver": TargetLayer.SILVER,
            "gold":   TargetLayer.GOLD,
        }
        target_layer = layer_map.get(output.target_layer, TargetLayer.SILVER)

        datasets = []
        for d in output.datasets:
            cls_map = {
                "public":      DatasetClassification.PUBLIC,
                "internal":    DatasetClassification.INTERNAL,
                "sensitive":   DatasetClassification.SENSITIVE,
                "high_volume": DatasetClassification.HIGH_VOLUME,
            }
            classification = cls_map.get(d.get("classification", "internal"),
                                         DatasetClassification.INTERNAL)
            datasets.append(DatasetRef(
                name=d["name"],
                classification=classification,
                size_gb=d.get("size_gb", 0.0),
                pii_columns=d.get("pii_columns", []),
                partition_column=d.get("partition_column"),
            ))

        # Converter constraints
        c = output.constraints
        constraints = SignatureConstraints(
            no_pii_raw=c.get("no_pii_raw", True),
            merge_key_required=c.get("merge_key_required", True),
            enforce_types=c.get("enforce_types", True),
            partition_by=c.get("partition_by", []),
            max_cost_dbu=c.get("max_cost_dbu"),
        )

        # Montar execution_context (contrato de reprodutibilidade — I8)
        execution_context = ExecutionContext(
            policy_bundle_version=self.policy_bundle_version,
            catalog_snapshot_version=self.catalog_snapshot_version,
            context_registry_version_id=context_registry_version_id,
        )

        return StateSignature(
            domain=output.domain,
            intent=output.intent,
            target_layer=target_layer,
            datasets=datasets,
            constraints=constraints,
            execution_context=execution_context,
            source_intent_raw=raw_intent,
        )


# ─── Confirmation Orchestrator ────────────────────────────────────────────────

@dataclass
class ConfirmationRequest:
    """Pedido de confirmação para escalamento."""
    resolution: SemanticResolution
    reason: str
    timeout_seconds: int = 300


@dataclass
class ConfirmationResponse:
    """Resposta a um pedido de confirmação."""
    approved: bool
    modified_signature: StateSignature | None = None
    reviewer: str = "system"
    notes: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


class HumanConfirmationHandler(ABC):
    """
    Interface para o handler de confirmação humana.
    Em produção: Slack bot, web UI, email, etc.
    Em testes: mock que auto-aprova ou auto-rejeita.
    """

    @abstractmethod
    def request_confirmation(self, request: ConfirmationRequest) -> ConfirmationResponse | None:
        """
        Solicita confirmação. Retorna None se timeout.
        """
        ...


class AutoApproveHandler(HumanConfirmationHandler):
    """Handler de teste que auto-aprova tudo."""

    def request_confirmation(self, request: ConfirmationRequest) -> ConfirmationResponse:
        return ConfirmationResponse(
            approved=True,
            reviewer="auto_approve_mock",
            notes="Auto-aprovado (handler de teste)",
        )


class AutoRejectHandler(HumanConfirmationHandler):
    """Handler de teste que auto-rejeita tudo."""

    def request_confirmation(self, request: ConfirmationRequest) -> ConfirmationResponse:
        return ConfirmationResponse(
            approved=False,
            reviewer="auto_reject_mock",
            notes="Auto-rejeitado (handler de teste)",
        )


class ConfirmationOrchestrator:
    """
    Interpõe escalonamento entre Semantic Resolution e Policy Engine.
    Ativado seletivamente por risco — sem atrito em 90% dos casos.

    Modos:
    - auto:             passa direto
    - soft:             registra e passa
    - hard:             requer confirmação explícita
    - human_escalation: envia para revisão humana com timeout
    """

    def __init__(
        self,
        human_handler: HumanConfirmationHandler | None = None,
        timeout_seconds: int = 300,
    ):
        self.human_handler = human_handler or AutoApproveHandler()
        self.timeout_seconds = timeout_seconds

    def process(self, resolution: SemanticResolution) -> tuple[bool, str, Fault | None]:
        """
        Processa a SemanticResolution conforme o modo de confirmação.

        Returns:
            (approved: bool, reason: str, fault: Fault | None)
        """
        mode = resolution.confirmation_mode

        if mode == ConfirmationMode.AUTO:
            return True, "Auto-confirmado: baixo risco.", None

        if mode == ConfirmationMode.SOFT:
            # Registra mas avança
            return True, f"Soft-confirmado: confiança={resolution.confidence_score:.2f}", None

        if mode == ConfirmationMode.HARD:
            return self._handle_hard(resolution)

        if mode == ConfirmationMode.HUMAN_ESCALATION:
            return self._handle_human_escalation(resolution)

        return True, "Modo desconhecido — aprovado por default.", None

    def _handle_hard(self, resolution: SemanticResolution) -> tuple[bool, str, Fault | None]:
        """Hard confirmation — bloqueia até confirmação explícita."""
        sig = resolution.signature

        reasons = []
        if sig.writes_to_protected_layer and sig.contains_pii:
            reasons.append("escrita em camada protegida com PII")
        if resolution.ambiguity_level == AmbiguityLevel.HIGH:
            reasons.append("ambiguidade semântica alta")

        request = ConfirmationRequest(
            resolution=resolution,
            reason=f"Hard confirmation requerido: {', '.join(reasons)}",
            timeout_seconds=self.timeout_seconds,
        )

        response = self.human_handler.request_confirmation(request)
        if response and response.approved:
            return True, f"Hard confirmation aprovado por: {response.reviewer}", None

        fault = Fault(
            code="CONFIRMATION_HARD_REJECTED",
            family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.HIGH,
            stage="confirmation_orchestrator",
            message="Hard confirmation rejeitado ou timeout.",
            mandatory_action=PolicyAction.BLOCK,
            remediation=["Revisar a intenção e resubmeter"],
        )
        return False, "Hard confirmation rejeitado.", fault

    def _handle_human_escalation(self, resolution: SemanticResolution) -> tuple[bool, str, Fault | None]:
        """Human escalation — timeout resulta em block + notify."""
        sig = resolution.signature

        reasons = []
        if sig.target_layer == TargetLayer.GOLD:
            reasons.append("escrita em camada Gold")
        if resolution.confidence_score < 0.65 and sig.contains_pii:
            reasons.append(f"baixa confiança ({resolution.confidence_score:.2f}) com PII")
        if len(resolution.competing_interpretations) > 1:
            reasons.append(f"{len(resolution.competing_interpretations)} interpretações concorrentes")

        request = ConfirmationRequest(
            resolution=resolution,
            reason=f"Escalonamento humano: {', '.join(reasons) or 'risco elevado'}",
            timeout_seconds=self.timeout_seconds,
        )

        response = self.human_handler.request_confirmation(request)

        if response is None:
            # Timeout
            fault = Fault(
                code="CONFIRMATION_HUMAN_TIMEOUT",
                family=FaultFamily.SEMANTIC,
                severity=FaultSeverity.CRITICAL,
                stage="confirmation_orchestrator",
                message=f"Timeout de {self.timeout_seconds}s sem confirmação humana.",
                mandatory_action=PolicyAction.BLOCK,
                remediation=["Notificar governance_team", "Aguardar revisão manual"],
                metadata={"timeout_seconds": self.timeout_seconds},
            )
            return False, "Timeout de confirmação humana.", fault

        if response.approved:
            sig_to_use = response.modified_signature or sig
            return True, f"Escalamento aprovado por: {response.reviewer}", None

        fault = Fault(
            code="CONFIRMATION_HUMAN_REJECTED",
            family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.HIGH,
            stage="confirmation_orchestrator",
            message=f"Intenção rejeitada por: {response.reviewer}. {response.notes}",
            mandatory_action=PolicyAction.BLOCK,
            remediation=["Revisar a intenção conforme feedback do revisor"],
        )
        return False, f"Escalamento rejeitado por: {response.reviewer}", fault
