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
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cfa.core.codegen import GeneratedCode
    from cfa.core.planner import ExecutionPlan
    from cfa.execution.partial import PartialExecutionState
    from cfa.sandbox import SandboxResult
    from cfa.validation.runtime import RuntimeValidationResult
    from cfa.validation.static import StaticValidationResult


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ── Enums ────────────────────────────────────────────────────────────────────


class DecisionState(StrEnum):
    APPROVED = "approved"
    APPROVED_WITH_WARNINGS = "approved_with_warnings"
    REPLANNED = "replanned"
    BLOCKED = "blocked"
    PARTIALLY_COMMITTED = "partially_committed"
    QUARANTINED = "quarantined"
    ROLLED_BACK = "rolled_back"
    PROMOTION_CANDIDATE = "promotion_candidate"


class ConfirmationMode(StrEnum):
    AUTO = "auto"
    SOFT = "soft"
    HARD = "hard"
    HUMAN_ESCALATION = "human_escalation"


class AmbiguityLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FaultFamily(StrEnum):
    SEMANTIC = "semantic_faults"
    STATIC = "static_safety_faults"
    RUNTIME = "runtime_behavioral_faults"
    ENVIRONMENT = "environmental_faults"


class FaultSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class PolicyAction(StrEnum):
    APPROVE = "approve"
    REPLAN = "replan"
    BLOCK = "block"


class DatasetClassification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    SENSITIVE = "sensitive"
    HIGH_VOLUME = "high_volume"


class TargetLayer(StrEnum):
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
    merge_keys: tuple[str, ...] = ()

    @property
    def contains_pii(self) -> bool:
        return len(self.pii_columns) > 0

    @property
    def join_key(self) -> str:
        return self.merge_keys[0] if self.merge_keys else "id"


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
        return hashlib.sha256(content.encode()).hexdigest()

    @property
    def contains_pii(self) -> bool:
        return any(d.contains_pii for d in self.datasets)

    @property
    def writes_to_protected_layer(self) -> bool:
        return self.target_layer in (TargetLayer.SILVER, TargetLayer.GOLD)

    @property
    def target_dataset_name(self) -> str:
        """Deterministic target scope derived from the approved signature."""
        layer = self.target_layer.value
        if len(self.datasets) == 1:
            return f"{layer}_{self.datasets[0].name}"
        return f"{layer}_{self.domain}"

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

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "intent": self.intent,
            "target_layer": self.target_layer.value,
            "datasets": [
                {
                    "name": d.name,
                    "classification": d.classification.value,
                    "size_gb": d.size_gb,
                    "pii_columns": list(d.pii_columns),
                    "partition_column": d.partition_column,
                    "merge_keys": list(d.merge_keys),
                }
                for d in self.datasets
            ],
            "constraints": {
                "no_pii_raw": self.constraints.no_pii_raw,
                "merge_key_required": self.constraints.merge_key_required,
                "enforce_types": self.constraints.enforce_types,
                "partition_by": list(self.constraints.partition_by),
                "max_cost_dbu": self.constraints.max_cost_dbu,
                "custom": self.constraints.custom,
            },
            "execution_context": {
                "policy_bundle_version": self.execution_context.policy_bundle_version,
                "catalog_snapshot_version": self.execution_context.catalog_snapshot_version,
                "context_registry_version_id": self.execution_context.context_registry_version_id,
            },
            "intent_id": self.intent_id,
            "source_intent_raw": self.source_intent_raw,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StateSignature:
        layer_map = {"bronze": TargetLayer.BRONZE, "silver": TargetLayer.SILVER, "gold": TargetLayer.GOLD}
        cls_map = {
            "public": DatasetClassification.PUBLIC, "internal": DatasetClassification.INTERNAL,
            "sensitive": DatasetClassification.SENSITIVE, "high_volume": DatasetClassification.HIGH_VOLUME,
        }
        datasets = tuple(
            DatasetRef(
                name=d["name"],
                classification=cls_map.get(d.get("classification", "internal"), DatasetClassification.INTERNAL),
                size_gb=d.get("size_gb", 0.0),
                pii_columns=tuple(d.get("pii_columns", [])),
                partition_column=d.get("partition_column"),
                merge_keys=tuple(d.get("merge_keys", [])),
            )
            for d in data.get("datasets", [])
        )
        c = data.get("constraints", {})
        constraints = SignatureConstraints(
            no_pii_raw=c.get("no_pii_raw", True),
            merge_key_required=c.get("merge_key_required", True),
            enforce_types=c.get("enforce_types", True),
            partition_by=tuple(c.get("partition_by", [])),
            max_cost_dbu=c.get("max_cost_dbu"),
            custom=c.get("custom", {}),
        )
        ctx = data.get("execution_context", {})
        execution_context = ExecutionContext(
            policy_bundle_version=ctx.get("policy_bundle_version", "unknown"),
            catalog_snapshot_version=ctx.get("catalog_snapshot_version", "unknown"),
            context_registry_version_id=ctx.get("context_registry_version_id", "unknown"),
        )
        return cls(
            domain=data.get("domain", ""),
            intent=data.get("intent", ""),
            target_layer=layer_map.get(data.get("target_layer", "silver"), TargetLayer.SILVER),
            datasets=datasets,
            constraints=constraints,
            execution_context=execution_context,
            intent_id=data.get("intent_id", str(uuid.uuid4())),
            source_intent_raw=data.get("source_intent_raw", ""),
        )

    @classmethod
    def from_json(cls, json_str: str) -> StateSignature:
        return cls.from_dict(json.loads(json_str))


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "faults": [
                {
                    "code": f.code, "family": f.family.value,
                    "severity": f.severity.value, "stage": f.stage,
                    "message": f.message, "mandatory_action": f.mandatory_action.value,
                    "remediation": list(f.remediation),
                    "detected_before_execution": f.detected_before_execution,
                }
                for f in self.faults
            ],
            "interventions": self.interventions,
            "replan_count": self.replan_count,
            "reasoning": self.reasoning,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


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
    execution_plan: ExecutionPlan | None = None          # type: ignore[name-defined]
    generated_code: GeneratedCode | None = None          # type: ignore[name-defined]
    static_validation: StaticValidationResult | None = None  # type: ignore[name-defined]
    sandbox_result: SandboxResult | None = None          # type: ignore[name-defined]
    runtime_validation: RuntimeValidationResult | None = None  # type: ignore[name-defined]
    execution_state: PartialExecutionState | None = None  # type: ignore[name-defined]
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

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "intent_id": self.intent_id,
            "state": self.state.value,
            "blocked_reason": self.blocked_reason,
            "replan_count": len(self.replan_history),
            "audit_events": self.audit_events,
            "created_at": self.created_at.isoformat(),
        }
        if self.signature:
            d["signature"] = self.signature.to_dict()
        if self.policy_result:
            d["policy_result"] = self.policy_result.to_dict()
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)
