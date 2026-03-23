"""
CFA Core Types
==============
Every intent, signature, decision and fault flows through these types.
Immutable after creation — any replanning generates new instances.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Enums ────────────────────────────────────────────────────────────────────


class DecisionState(str, Enum):
    APPROVED = "approved"
    APPROVED_WITH_WARNINGS = "approved_with_warnings"
    REPLANNED = "replanned"
    BLOCKED = "blocked"
    PARTIALLY_COMMITTED = "partially_committed"
    QUARANTINED = "quarantined"
    ROLLED_BACK = "rolled_back"
    PROMOTION_CANDIDATE = "promotion_candidate"


class ConfirmationMode(str, Enum):
    AUTO = "auto"
    SOFT = "soft"
    HARD = "hard"
    HUMAN_ESCALATION = "human_escalation"


class AmbiguityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FaultFamily(str, Enum):
    SEMANTIC = "semantic_faults"
    STATIC = "static_safety_faults"
    RUNTIME = "runtime_behavioral_faults"
    ENVIRONMENT = "environmental_faults"


class FaultSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class PolicyAction(str, Enum):
    APPROVE = "approve"
    REPLAN = "replan"
    BLOCK = "block"


class DatasetClassification(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    SENSITIVE = "sensitive"
    HIGH_VOLUME = "high_volume"


class TargetLayer(str, Enum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"


# ── Data types ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DatasetRef:
    """Reference to a dataset with governance metadata."""

    name: str
    classification: DatasetClassification = DatasetClassification.INTERNAL
    size_gb: float = 0.0
    pii_columns: tuple[str, ...] = ()
    partition_column: str | None = None

    @property
    def contains_pii(self) -> bool:
        return len(self.pii_columns) > 0


@dataclass(frozen=True)
class ExecutionContext:
    """
    Normative context of the execution.
    Part of the Signature — guarantees reproducibility (Invariant I8).
    """

    policy_bundle_version: str
    catalog_snapshot_version: str
    context_registry_version_id: str
    timestamp: datetime = field(default_factory=_utcnow)


@dataclass(frozen=True)
class SignatureConstraints:
    """Constraints declared in the State Signature."""

    no_pii_raw: bool = True
    merge_key_required: bool = True
    enforce_types: bool = True
    partition_by: tuple[str, ...] = ()
    max_cost_dbu: float | None = None
    custom: dict[str, Any] = field(default_factory=dict)


# ── State Signature ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class StateSignature:
    """
    Formal contract of the intent.
    Immutable after generation — any replanning generates a new Signature.
    """

    domain: str
    intent: str
    target_layer: TargetLayer
    datasets: tuple[DatasetRef, ...]
    constraints: SignatureConstraints
    execution_context: ExecutionContext
    intent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=_utcnow)
    source_intent_raw: str = ""

    @property
    def signature_hash(self) -> str:
        payload = {
            "domain": self.domain,
            "intent": self.intent,
            "target_layer": self.target_layer.value,
            "datasets": sorted(d.name for d in self.datasets),
            "constraints": {
                "no_pii_raw": self.constraints.no_pii_raw,
                "merge_key_required": self.constraints.merge_key_required,
                "partition_by": sorted(self.constraints.partition_by),
            },
        }
        content = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    @property
    def contains_pii(self) -> bool:
        return any(d.contains_pii for d in self.datasets)

    @property
    def writes_to_protected_layer(self) -> bool:
        return self.target_layer in (TargetLayer.SILVER, TargetLayer.GOLD)

    def with_constraints(self, **overrides: Any) -> StateSignature:
        """Return a new Signature with updated constraints (immutable update)."""
        current = {
            "no_pii_raw": self.constraints.no_pii_raw,
            "merge_key_required": self.constraints.merge_key_required,
            "enforce_types": self.constraints.enforce_types,
            "partition_by": self.constraints.partition_by,
            "max_cost_dbu": self.constraints.max_cost_dbu,
            "custom": self.constraints.custom,
        }
        current.update(overrides)
        new_constraints = SignatureConstraints(**current)
        new_ctx = ExecutionContext(
            policy_bundle_version=self.execution_context.policy_bundle_version,
            catalog_snapshot_version=self.execution_context.catalog_snapshot_version,
            context_registry_version_id=self.execution_context.context_registry_version_id,
        )
        return StateSignature(
            domain=self.domain,
            intent=self.intent,
            target_layer=self.target_layer,
            datasets=self.datasets,
            constraints=new_constraints,
            execution_context=new_ctx,
            intent_id=self.intent_id,
            source_intent_raw=self.source_intent_raw,
        )


# ── Semantic Resolution ──────────────────────────────────────────────────────


@dataclass
class SemanticResolution:
    """
    Result of the Intent Normalizer's semantic resolution.
    Feeds the Confirmation Orchestrator.
    """

    signature: StateSignature
    confidence_score: float
    ambiguity_level: AmbiguityLevel
    competing_interpretations: list[str] = field(default_factory=list)
    confirmation_mode: ConfirmationMode = ConfirmationMode.AUTO
    environment_constraints_injected: list[str] = field(default_factory=list)
    reasoning: str = ""

    def __post_init__(self) -> None:
        if self.confirmation_mode == ConfirmationMode.AUTO:
            self.confirmation_mode = self._derive_confirmation_mode()

    def _derive_confirmation_mode(self) -> ConfirmationMode:
        sig = self.signature
        if sig.target_layer == TargetLayer.GOLD:
            return ConfirmationMode.HUMAN_ESCALATION
        if self.confidence_score < 0.65 and sig.contains_pii:
            return ConfirmationMode.HUMAN_ESCALATION
        if len(self.competing_interpretations) > 1:
            return ConfirmationMode.HUMAN_ESCALATION
        if sig.writes_to_protected_layer and sig.contains_pii:
            return ConfirmationMode.HARD
        if self.confidence_score < 0.80 or self.ambiguity_level == AmbiguityLevel.MEDIUM:
            return ConfirmationMode.SOFT
        return ConfirmationMode.AUTO


# ── Fault ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Fault:
    """
    Governed failure event.
    Errors in CFA are not exceptions — they are typed Faults.
    """

    code: str
    family: FaultFamily
    severity: FaultSeverity
    stage: str
    message: str
    mandatory_action: PolicyAction
    remediation: tuple[str, ...] = ()
    detected_before_execution: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=_utcnow)

    def __str__(self) -> str:
        return f"[{self.severity.value.upper()}] {self.code}: {self.message}"


# ── Policy Result ────────────────────────────────────────────────────────────


@dataclass
class PolicyResult:
    """Result of a Policy Engine evaluation."""

    action: PolicyAction
    faults: list[Fault] = field(default_factory=list)
    interventions: list[str] = field(default_factory=list)
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


# ── Kernel Result ────────────────────────────────────────────────────────────


@dataclass
class KernelResult:
    """
    Final result of the Kernel Orchestrator for an intent.
    Contains the decision state, the approved signature (if any),
    and the complete trail of events for the Audit Trail.
    """

    intent_id: str
    state: DecisionState
    signature: StateSignature | None = None
    policy_result: PolicyResult | None = None
    resolution: SemanticResolution | None = None
    execution_plan: Any = None       # Phase 2: ExecutionPlan (avoid circular import)
    generated_code: Any = None       # Phase 2: GeneratedCode
    static_validation: Any = None    # Phase 2: StaticValidationResult
    sandbox_result: Any = None       # Phase 3: SandboxResult
    runtime_validation: Any = None   # Phase 3: RuntimeValidationResult
    execution_state: Any = None      # Phase 3: PartialExecutionState
    audit_events: list[dict[str, Any]] = field(default_factory=list)
    blocked_reason: str = ""
    replan_history: list[PolicyResult] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utcnow)

    @property
    def is_executable(self) -> bool:
        return (
            self.state in (DecisionState.APPROVED, DecisionState.APPROVED_WITH_WARNINGS)
            and self.signature is not None
        )

    def add_event(self, stage: str, event_type: str, outcome: str, **kwargs: Any) -> None:
        self.audit_events.append(
            {
                "stage": stage,
                "event_type": event_type,
                "outcome": outcome,
                "timestamp": _utcnow().isoformat(),
                "intent_id": self.intent_id,
                **kwargs,
            }
        )

    def summary(self) -> str:
        lines = [
            f"KernelResult [{self.intent_id[:8]}]",
            f"  state     : {self.state.value}",
        ]
        if self.signature:
            lines.append(f"  sig_hash  : {self.signature.signature_hash}")
            lines.append(f"  domain    : {self.signature.domain}")
        if self.blocked_reason:
            lines.append(f"  blocked   : {self.blocked_reason}")
        if self.policy_result and self.policy_result.faults:
            lines.append(f"  faults    : {[str(f) for f in self.policy_result.faults]}")
        return "\n".join(lines)
