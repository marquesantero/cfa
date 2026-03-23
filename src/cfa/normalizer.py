"""
CFA Intent Normalizer + Confirmation Orchestrator
==================================================
Transforms natural language into a typed State Signature.

The Normalizer is the most critical pipeline component:
an error here contaminates the entire system with deterministic perfection.

Architecture:
- NormalizerBackend ABC — LLM-agnostic
- IntentNormalizer — orchestrates resolution, context and signature
- ConfirmationOrchestrator — risk-based escalation
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Protocol

from .types import (
    AmbiguityLevel,
    ConfirmationMode,
    DatasetClassification,
    DatasetRef,
    ExecutionContext,
    Fault,
    FaultFamily,
    FaultSeverity,
    PolicyAction,
    SemanticResolution,
    SignatureConstraints,
    StateSignature,
    TargetLayer,
    _utcnow,
)


# ── Backend contract ─────────────────────────────────────────────────────────


@dataclass
class NormalizerInput:
    raw_intent: str
    environment_state: dict[str, Any]
    catalog: dict[str, Any]
    policy_bundle_version: str
    catalog_snapshot_version: str
    context_registry_version_id: str


@dataclass
class NormalizerOutput:
    domain: str
    intent: str
    target_layer: str
    datasets: list[dict[str, Any]]
    constraints: dict[str, Any]
    confidence_score: float
    ambiguity_level: str
    competing_interpretations: list[str] = field(default_factory=list)
    environment_constraints_injected: list[str] = field(default_factory=list)
    reasoning: str = ""


class NormalizerBackend(ABC):
    """
    Interface for any semantic resolution backend.
    Extension point: LLM, rule-based, hybrid, mock.
    """

    @abstractmethod
    def resolve(self, inp: NormalizerInput) -> NormalizerOutput: ...


# ── Mock backend ─────────────────────────────────────────────────────────────


class MockNormalizerBackend(NormalizerBackend):
    """Deterministic backend for tests. Uses keyword matching."""

    _LAYER_KEYWORDS: dict[TargetLayer, list[str]] = {
        TargetLayer.GOLD: ["gold", "ouro", "master", "curated", "final"],
        TargetLayer.SILVER: ["silver", "prata", "refined", "trusted", "join", "reconcil"],
        TargetLayer.BRONZE: ["bronze", "raw", "ingest", "landing"],
    }

    _DOMAIN_KEYWORDS: dict[str, list[str]] = {
        "fiscal_data_processing": ["nfe", "nota fiscal", "fiscal", "tribut"],
        "customer_data": ["client", "customer", "cpf", "cadastro"],
        "financial_data": ["payment", "transac", "financ", "pagamento"],
    }

    def resolve(self, inp: NormalizerInput) -> NormalizerOutput:
        raw = inp.raw_intent.lower()

        target_layer = self._detect_layer(raw)
        datasets = self._detect_datasets(raw, inp.catalog)
        domain = self._detect_domain(raw)
        intent = self._detect_intent(raw)
        has_pii = any(d.get("pii_columns") for d in datasets)

        confidence = 0.85 if datasets else 0.45
        if has_pii and target_layer in ("silver", "gold"):
            confidence -= 0.1

        env_constraints = self._detect_env_constraints(inp.environment_state)

        ambiguity = "low" if confidence > 0.80 else "medium" if confidence > 0.60 else "high"

        return NormalizerOutput(
            domain=domain,
            intent=intent,
            target_layer=target_layer,
            datasets=datasets,
            constraints={
                "no_pii_raw": True,
                "merge_key_required": target_layer in ("silver", "gold"),
                "enforce_types": True,
                "partition_by": ["processing_date"] if datasets else [],
            },
            confidence_score=round(confidence, 2),
            ambiguity_level=ambiguity,
            environment_constraints_injected=env_constraints,
            reasoning=(
                f"Mock: layer={target_layer}, "
                f"datasets={[d['name'] for d in datasets]}, "
                f"pii={has_pii}"
            ),
        )

    def _detect_layer(self, raw: str) -> str:
        for layer, keywords in self._LAYER_KEYWORDS.items():
            if any(kw in raw for kw in keywords):
                return layer.value
        return "silver"

    def _detect_datasets(self, raw: str, catalog: dict[str, Any]) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        for name, meta in catalog.get("datasets", {}).items():
            if name.lower() in raw:
                found.append(
                    {
                        "name": name,
                        "classification": meta.get("classification", "internal"),
                        "pii_columns": meta.get("pii_columns", []),
                        "size_gb": meta.get("size_gb", 0.0),
                        "partition_column": meta.get("partition_column"),
                    }
                )
        return found

    def _detect_domain(self, raw: str) -> str:
        for domain, keywords in self._DOMAIN_KEYWORDS.items():
            if any(kw in raw for kw in keywords):
                return domain
        return "general"

    def _detect_intent(self, raw: str) -> str:
        if any(w in raw for w in ["join", "reconcil", "merg"]):
            return "reconciliation_and_persist"
        if any(w in raw for w in ["ingest", "load", "import", "carregar"]):
            return "ingest"
        if any(w in raw for w in ["aggregat", "summ", "group"]):
            return "aggregate_and_persist"
        return "transform_and_persist"

    def _detect_env_constraints(self, env_state: dict[str, Any]) -> list[str]:
        constraints: list[str] = []
        for name, state in env_state.get("datasets", {}).items():
            if state.get("state") == "partially_committed":
                constraints.append(
                    f"{name}.state=partially_committed -> publish_allowed=false"
                )
        return constraints


# ── Intent Normalizer ────────────────────────────────────────────────────────


class IntentNormalizer:
    """
    Transforms natural language into a typed State Signature.

    Mandatory inputs (per whitepaper):
    1. user_intent (natural language)
    2. context_registry.environment_state
    3. data_catalog
    """

    def __init__(
        self,
        backend: NormalizerBackend,
        policy_bundle_version: str = "v1.0",
        catalog_snapshot_version: str = "catalog_default",
    ) -> None:
        self.backend = backend
        self.policy_bundle_version = policy_bundle_version
        self.catalog_snapshot_version = catalog_snapshot_version

    def normalize(
        self,
        raw_intent: str,
        environment_state: dict[str, Any],
        catalog: dict[str, Any],
        context_registry_version_id: str = "v_initial",
    ) -> SemanticResolution:
        inp = NormalizerInput(
            raw_intent=raw_intent,
            environment_state=environment_state,
            catalog=catalog,
            policy_bundle_version=self.policy_bundle_version,
            catalog_snapshot_version=self.catalog_snapshot_version,
            context_registry_version_id=context_registry_version_id,
        )
        output = self.backend.resolve(inp)
        signature = self._build_signature(output, raw_intent, context_registry_version_id)

        ambiguity_map = {
            "low": AmbiguityLevel.LOW,
            "medium": AmbiguityLevel.MEDIUM,
            "high": AmbiguityLevel.HIGH,
        }

        return SemanticResolution(
            signature=signature,
            confidence_score=output.confidence_score,
            ambiguity_level=ambiguity_map.get(output.ambiguity_level, AmbiguityLevel.MEDIUM),
            competing_interpretations=output.competing_interpretations,
            environment_constraints_injected=output.environment_constraints_injected,
            reasoning=output.reasoning,
        )

    def _build_signature(
        self,
        output: NormalizerOutput,
        raw_intent: str,
        context_registry_version_id: str,
    ) -> StateSignature:
        layer_map = {"bronze": TargetLayer.BRONZE, "silver": TargetLayer.SILVER, "gold": TargetLayer.GOLD}
        target_layer = layer_map.get(output.target_layer, TargetLayer.SILVER)

        cls_map = {
            "public": DatasetClassification.PUBLIC,
            "internal": DatasetClassification.INTERNAL,
            "sensitive": DatasetClassification.SENSITIVE,
            "high_volume": DatasetClassification.HIGH_VOLUME,
        }

        datasets = tuple(
            DatasetRef(
                name=d["name"],
                classification=cls_map.get(d.get("classification", "internal"), DatasetClassification.INTERNAL),
                size_gb=d.get("size_gb", 0.0),
                pii_columns=tuple(d.get("pii_columns", [])),
                partition_column=d.get("partition_column"),
            )
            for d in output.datasets
        )

        c = output.constraints
        constraints = SignatureConstraints(
            no_pii_raw=c.get("no_pii_raw", True),
            merge_key_required=c.get("merge_key_required", True),
            enforce_types=c.get("enforce_types", True),
            partition_by=tuple(c.get("partition_by", [])),
            max_cost_dbu=c.get("max_cost_dbu"),
        )

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


# ── Confirmation Orchestrator ────────────────────────────────────────────────


class ConfirmationHandler(Protocol):
    """Interface for confirmation handlers (Slack bot, web UI, mock, etc.)."""

    def confirm(self, resolution: SemanticResolution, reason: str) -> bool: ...


class AutoApproveHandler:
    def confirm(self, resolution: SemanticResolution, reason: str) -> bool:
        return True


class AutoRejectHandler:
    def confirm(self, resolution: SemanticResolution, reason: str) -> bool:
        return False


class ConfirmationOrchestrator:
    """
    Interposes escalation between Semantic Resolution and Policy Engine.
    Selectively activated by risk — no friction in 90% of cases.

    Modes:
    - auto:             pass through
    - soft:             log and pass
    - hard:             require explicit confirmation
    - human_escalation: send for human review with timeout
    """

    def __init__(
        self,
        handler: ConfirmationHandler | None = None,
        timeout_seconds: int = 300,
    ) -> None:
        self.handler = handler or AutoApproveHandler()
        self.timeout_seconds = timeout_seconds

    def process(self, resolution: SemanticResolution) -> tuple[bool, str, Fault | None]:
        """Returns (approved, reason, fault_or_none)."""
        mode = resolution.confirmation_mode

        if mode == ConfirmationMode.AUTO:
            return True, "Auto-confirmed: low risk.", None

        if mode == ConfirmationMode.SOFT:
            return True, f"Soft-confirmed: confidence={resolution.confidence_score:.2f}", None

        reason = self._build_reason(resolution)
        approved = self.handler.confirm(resolution, reason)

        if approved:
            label = "Hard" if mode == ConfirmationMode.HARD else "Human escalation"
            return True, f"{label} approved.", None

        fault = Fault(
            code=f"CONFIRMATION_{mode.value.upper()}_REJECTED",
            family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.HIGH if mode == ConfirmationMode.HARD else FaultSeverity.CRITICAL,
            stage="confirmation_orchestrator",
            message=f"Confirmation rejected (mode={mode.value}).",
            mandatory_action=PolicyAction.BLOCK,
            remediation=("Review the intent and resubmit.",),
        )
        return False, f"Confirmation rejected (mode={mode.value}).", fault

    def _build_reason(self, resolution: SemanticResolution) -> str:
        sig = resolution.signature
        reasons: list[str] = []
        if sig.target_layer == TargetLayer.GOLD:
            reasons.append("Gold layer write")
        if sig.writes_to_protected_layer and sig.contains_pii:
            reasons.append("protected layer write with PII")
        if resolution.confidence_score < 0.65:
            reasons.append(f"low confidence ({resolution.confidence_score:.2f})")
        if len(resolution.competing_interpretations) > 1:
            reasons.append(f"{len(resolution.competing_interpretations)} competing interpretations")
        return "; ".join(reasons) or "elevated risk"
