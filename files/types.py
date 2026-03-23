"""
CFA Core Types
==============
Tipos fundamentais que definem o contrato do sistema.
Toda intenção, assinatura, decisão e fault passa por aqui.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any
import hashlib
import json
import uuid


# ─── Enums de Estado ──────────────────────────────────────────────────────────

class DecisionState(str, Enum):
    """Estados terminais possíveis de uma intenção no Decision Engine."""
    APPROVED                = "approved"
    APPROVED_WITH_WARNINGS  = "approved_with_warnings"
    REPLANNED               = "replanned"
    BLOCKED                 = "blocked"
    PARTIALLY_COMMITTED     = "partially_committed"
    QUARANTINED             = "quarantined"
    ROLLED_BACK             = "rolled_back"
    PROMOTION_CANDIDATE     = "promotion_candidate"


class ConfirmationMode(str, Enum):
    """Modos de confirmação semântica do Confirmation Orchestrator."""
    AUTO              = "auto"
    SOFT              = "soft"
    HARD              = "hard"
    HUMAN_ESCALATION  = "human_escalation"


class AmbiguityLevel(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


class FaultFamily(str, Enum):
    SEMANTIC    = "semantic_faults"
    STATIC      = "static_safety_faults"
    RUNTIME     = "runtime_behavioral_faults"
    ENVIRONMENT = "environmental_faults"


class FaultSeverity(str, Enum):
    INFO     = "info"
    WARNING  = "warning"
    HIGH     = "high"
    CRITICAL = "critical"


class PolicyAction(str, Enum):
    APPROVE  = "approve"
    REPLAN   = "replan"
    BLOCK    = "block"


class DatasetClassification(str, Enum):
    PUBLIC       = "public"
    INTERNAL     = "internal"
    SENSITIVE    = "sensitive"
    HIGH_VOLUME  = "high_volume"


class TargetLayer(str, Enum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD   = "gold"


# ─── Tipos de Dados Base ──────────────────────────────────────────────────────

@dataclass
class DatasetRef:
    """Referência a um dataset com metadados de governança."""
    name: str
    classification: DatasetClassification = DatasetClassification.INTERNAL
    size_gb: float = 0.0
    pii_columns: list[str] = field(default_factory=list)
    partition_column: str | None = None

    @property
    def contains_pii(self) -> bool:
        return len(self.pii_columns) > 0


@dataclass
class ExecutionContext:
    """
    Contexto normativo da execução.
    Parte da Signature — garante reprodutibilidade (Invariante I8).
    """
    policy_bundle_version: str
    catalog_snapshot_version: str
    context_registry_version_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SignatureConstraints:
    """Restrições declaradas na State Signature."""
    no_pii_raw: bool = True
    merge_key_required: bool = True
    enforce_types: bool = True
    partition_by: list[str] = field(default_factory=list)
    max_cost_dbu: float | None = None
    custom: dict[str, Any] = field(default_factory=dict)


# ─── State Signature ──────────────────────────────────────────────────────────

@dataclass
class StateSignature:
    """
    Contrato formal da intenção.
    Imutável após geração — qualquer replanejamento gera nova Signature.
    """
    domain: str
    intent: str
    target_layer: TargetLayer
    datasets: list[DatasetRef]
    constraints: SignatureConstraints
    execution_context: ExecutionContext

    # Gerados automaticamente
    intent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    source_intent_raw: str = ""

    @property
    def signature_hash(self) -> str:
        """
        Hash determinístico da Signature.
        Mesmo intent + mesmo domínio + mesmos datasets = mesmo hash.
        Usado como chave no Promotion Engine e Pre-cost Estimator.
        """
        payload = {
            "domain": self.domain,
            "intent": self.intent,
            "target_layer": self.target_layer.value,
            "datasets": sorted([d.name for d in self.datasets]),
            "constraints": {
                "no_pii_raw": self.constraints.no_pii_raw,
                "merge_key_required": self.constraints.merge_key_required,
                "partition_by": sorted(self.constraints.partition_by),
            }
        }
        content = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    @property
    def contains_pii(self) -> bool:
        return any(d.contains_pii for d in self.datasets)

    @property
    def writes_to_protected_layer(self) -> bool:
        return self.target_layer in (TargetLayer.SILVER, TargetLayer.GOLD)

    def to_dict(self) -> dict:
        return {
            "intent_id": self.intent_id,
            "signature_hash": self.signature_hash,
            "domain": self.domain,
            "intent": self.intent,
            "target_layer": self.target_layer.value,
            "datasets": [
                {
                    "name": d.name,
                    "classification": d.classification.value,
                    "contains_pii": d.contains_pii,
                    "pii_columns": d.pii_columns,
                }
                for d in self.datasets
            ],
            "constraints": {
                "no_pii_raw": self.constraints.no_pii_raw,
                "merge_key_required": self.constraints.merge_key_required,
                "partition_by": self.constraints.partition_by,
            },
            "execution_context": {
                "policy_bundle_version": self.execution_context.policy_bundle_version,
                "catalog_snapshot_version": self.execution_context.catalog_snapshot_version,
                "context_registry_version_id": self.execution_context.context_registry_version_id,
            }
        }


# ─── Semantic Resolution ──────────────────────────────────────────────────────

@dataclass
class SemanticResolution:
    """
    Resultado da resolução semântica do Intent Normalizer.
    Alimenta o Confirmation Orchestrator.
    """
    signature: StateSignature
    confidence_score: float                              # [0.0 - 1.0]
    ambiguity_level: AmbiguityLevel
    competing_interpretations: list[str] = field(default_factory=list)
    confirmation_mode: ConfirmationMode = ConfirmationMode.AUTO
    environment_constraints_injected: list[str] = field(default_factory=list)
    reasoning: str = ""

    def __post_init__(self):
        """Deriva o confirmation_mode a partir do contexto se não foi forçado."""
        if self.confirmation_mode == ConfirmationMode.AUTO:
            self.confirmation_mode = self._derive_confirmation_mode()

    def _derive_confirmation_mode(self) -> ConfirmationMode:
        sig = self.signature

        # Gold write → sempre human escalation
        if sig.target_layer == TargetLayer.GOLD:
            return ConfirmationMode.HUMAN_ESCALATION

        # Baixa confiança + PII → human escalation
        if self.confidence_score < 0.65 and sig.contains_pii:
            return ConfirmationMode.HUMAN_ESCALATION

        # Múltiplas interpretações → human escalation
        if len(self.competing_interpretations) > 1:
            return ConfirmationMode.HUMAN_ESCALATION

        # Silver + PII → hard
        if sig.writes_to_protected_layer and sig.contains_pii:
            return ConfirmationMode.HARD

        # Confiança média → soft
        if self.confidence_score < 0.80 or self.ambiguity_level == AmbiguityLevel.MEDIUM:
            return ConfirmationMode.SOFT

        return ConfirmationMode.AUTO


# ─── Fault ────────────────────────────────────────────────────────────────────

@dataclass
class Fault:
    """
    Evento de falha governado.
    Erros no CFA não são exceções — são Faults tipados.
    """
    code: str
    family: FaultFamily
    severity: FaultSeverity
    stage: str
    message: str
    mandatory_action: PolicyAction
    remediation: list[str] = field(default_factory=list)
    detected_before_execution: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __str__(self) -> str:
        return f"[{self.severity.value.upper()}] {self.code}: {self.message}"


# ─── Policy Result ────────────────────────────────────────────────────────────

@dataclass
class PolicyResult:
    """Resultado da avaliação do Policy Engine."""
    action: PolicyAction
    faults: list[Fault] = field(default_factory=list)
    interventions: list[str] = field(default_factory=list)  # ações obrigatórias no replan
    replan_count: int = 0
    reasoning: str = ""

    @property
    def is_blocked(self) -> bool:
        return self.action == PolicyAction.BLOCK

    @property
    def needs_replan(self) -> bool:
        return self.action == PolicyAction.REPLAN

    @property
    def critical_faults(self) -> list[Fault]:
        return [f for f in self.faults if f.severity == FaultSeverity.CRITICAL]


# ─── Kernel Result ────────────────────────────────────────────────────────────

@dataclass
class KernelResult:
    """
    Resultado final do Kernel Orchestrator para uma intenção.
    Contém o estado de decisão, a signature aprovada (se houver)
    e o trail completo de eventos para o Audit Trail.
    """
    intent_id: str
    state: DecisionState
    signature: StateSignature | None
    policy_result: PolicyResult | None
    resolution: SemanticResolution | None
    audit_events: list[dict] = field(default_factory=list)
    blocked_reason: str = ""
    replan_history: list[PolicyResult] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_executable(self) -> bool:
        """True se o Kernel aprovou a execução e gerou uma Signature válida."""
        return (
            self.state in (DecisionState.APPROVED, DecisionState.APPROVED_WITH_WARNINGS)
            and self.signature is not None
        )

    def add_audit_event(self, stage: str, event_type: str, outcome: str, **kwargs):
        self.audit_events.append({
            "stage": stage,
            "event_type": event_type,
            "outcome": outcome,
            "timestamp": datetime.utcnow().isoformat(),
            "intent_id": self.intent_id,
            **kwargs
        })

    def summary(self) -> str:
        lines = [
            f"KernelResult",
            f"  intent_id : {self.intent_id}",
            f"  state     : {self.state.value}",
        ]
        if self.signature:
            lines.append(f"  sig_hash  : {self.signature.signature_hash}")
            lines.append(f"  domain    : {self.signature.domain}")
        if self.blocked_reason:
            lines.append(f"  blocked   : {self.blocked_reason}")
        if self.policy_result and self.policy_result.faults:
            lines.append(f"  faults    : {[f.code for f in self.policy_result.faults]}")
        return "\n".join(lines)
