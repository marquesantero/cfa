"""
CFA Promotion / Demotion Engine
================================
Intent lifecycle management through evidence-based promotion and demotion.

Lifecycle states:
  candidate → active → watchlist → deprecated → retired
                ↑                      ↓
                └─── re-promotion ─────┘

Promotion requires accumulated evidence over a time window:
  Promote ⟸ IFo ≥ T1 AND IFs ≥ T2 AND IFg = 1 AND executions ≥ min_executions

Demotion triggers:
  - Schema drift → watchlist → deprecated
  - Policy change → demoted
  - IFs degraded → watchlist
  - IFo consistently low → watchlist
  - Low reuse → watchlist → deprecated
  - Catalog incompatibility → retired
  - IDI < 0.50 → immediate demotion (severe drift)

Every promoted skill carries generation_metadata for traceability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from cfa.obs.indices import ExecutionRecord, IndexCalculator, IndexScores
from cfa.types import _utcnow


def _parse_storage_timestamp(ts: str) -> datetime | None:
    """Parse a storage timestamp string to timezone-aware datetime."""
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.UTC)
        return dt
    except (ValueError, TypeError):
        return None

# ── Lifecycle States ────────────────────────────────────────────────────────


class SkillState(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    WATCHLIST = "watchlist"
    DEPRECATED = "deprecated"
    RETIRED = "retired"
    DEMOTED = "demoted"


# ── Promotion Policy ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PromotionPolicy:
    """Configurable thresholds for promotion gate."""

    min_executions: int = 3
    evaluation_window_days: int = 7
    ifo_threshold: float = 0.75
    ifs_threshold: float = 0.90
    ifg_threshold: float = 1.0  # binary — no exception
    idi_watchlist_threshold: float = 0.75
    idi_demotion_threshold: float = 0.50
    inactivity_periods_for_deprecation: int = 3  # consecutive windows without execution


# ── Skill Record ────────────────────────────────────────────────────────────


@dataclass
class SkillGenerationMetadata:
    """Provenance metadata for promoted skills (traceability)."""

    promoted_at: datetime = field(default_factory=_utcnow)
    promoted_by_system_version: str = "cfa_v1.0.0"
    policy_bundle_at_promotion: str = ""
    catalog_snapshot_at_promotion: str = ""
    promotion_scores: dict[str, float] = field(default_factory=dict)
    execution_count_at_promotion: int = 0
    evaluation_window: str = ""


@dataclass
class SkillRecord:
    """Tracked lifecycle record for a signature_hash."""

    signature_hash: str
    state: SkillState = SkillState.CANDIDATE
    generation_metadata: SkillGenerationMetadata | None = None
    last_evaluation: datetime | None = None
    demotion_reason: str = ""
    consecutive_inactive_windows: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)

    def transition(self, new_state: SkillState, reason: str = "") -> None:
        self.history.append({
            "from": self.state.value,
            "to": new_state.value,
            "reason": reason,
            "timestamp": _utcnow().isoformat(),
        })
        self.state = new_state
        if new_state == SkillState.DEMOTED:
            self.demotion_reason = reason


# ── Promotion / Demotion Engine ─────────────────────────────────────────────


class PromotionEngine:
    """
    Evaluates intent_signature_hash lifecycle.

    Called after execution to:
    1. Compute indices (IFo, IFs, IFg, IDI)
    2. Evaluate promotion gate
    3. Check demotion triggers
    4. Update skill state

    When ``storage`` is provided, execution records and skill state are
    persisted to SQLite (or any object with compatible methods).
    """

    def __init__(
        self,
        policy: PromotionPolicy | None = None,
        system_version: str = "cfa_v1.0.0",
        storage: object | None = None,
    ) -> None:
        self.policy = policy or PromotionPolicy()
        self.system_version = system_version
        self._storage = storage
        self._skills: dict[str, SkillRecord] = {}
        self._records: list[ExecutionRecord] = []
        self._calculator = IndexCalculator(window_days=self.policy.evaluation_window_days)
        if self._storage is not None:
            self._load_from_storage()

    def _load_from_storage(self) -> None:
        if not hasattr(self._storage, "execution_load_all"):
            return
        for rec_dict in self._storage.execution_load_all():
            self._records.append(ExecutionRecord(
                signature_hash=rec_dict["signature_hash"],
                timestamp=_parse_storage_timestamp(rec_dict.get("timestamp", "")) or _utcnow(),
                success=rec_dict.get("success", True),
                replanned=rec_dict.get("replanned", False),
                cost_dbu=rec_dict.get("cost_dbu", 0.0),
                duration_seconds=rec_dict.get("duration_seconds", 0.0),
                faults=rec_dict.get("faults", []),
                schema_match=rec_dict.get("schema_match", True),
                pii_exposure=rec_dict.get("pii_exposure", False),
                policy_compliant=rec_dict.get("policy_compliant", True),
                layer_adherent=rec_dict.get("layer_adherent", True),
                max_expected_duration=rec_dict.get("max_expected_duration", 300.0),
                max_expected_cost=rec_dict.get("max_expected_cost", 50.0),
            ))
        if hasattr(self._storage, "skill_load_all"):
            for skill_dict in self._storage.skill_load_all():
                sig_hash = skill_dict["signature_hash"]
                skill = SkillRecord(signature_hash=sig_hash)
                skill.state = SkillState(skill_dict.get("state", "candidate"))
                if skill_dict.get("generation_metadata"):
                    gm = skill_dict["generation_metadata"]
                    skill.generation_metadata = SkillGenerationMetadata(
                        promoted_by_system_version=gm.get("promoted_by_system_version", ""),
                        policy_bundle_at_promotion=gm.get("policy_bundle_at_promotion", ""),
                        catalog_snapshot_at_promotion=gm.get("catalog_snapshot_at_promotion", ""),
                        promotion_scores=gm.get("promotion_scores", {}),
                        execution_count_at_promotion=gm.get("execution_count_at_promotion", 0),
                        evaluation_window=gm.get("evaluation_window", ""),
                    )
                skill.demotion_reason = skill_dict.get("demotion_reason", "")
                skill.consecutive_inactive_windows = skill_dict.get("consecutive_inactive_windows", 0)
                skill.history = skill_dict.get("history", [])
                self._skills[sig_hash] = skill

    def get_skill(self, signature_hash: str) -> SkillRecord:
        if signature_hash not in self._skills:
            self._skills[signature_hash] = SkillRecord(signature_hash=signature_hash)
        return self._skills[signature_hash]

    def record_execution(self, record: ExecutionRecord) -> None:
        """Record an execution for index computation."""
        self._records.append(record)
        if self._storage is not None and hasattr(self._storage, "execution_append"):
            self._storage.execution_append({
                "signature_hash": record.signature_hash,
                "timestamp": record.timestamp.isoformat(),
                "success": record.success,
                "replanned": record.replanned,
                "cost_dbu": record.cost_dbu,
                "duration_seconds": record.duration_seconds,
                "faults": record.faults,
                "schema_match": record.schema_match,
                "pii_exposure": record.pii_exposure,
                "policy_compliant": record.policy_compliant,
                "layer_adherent": record.layer_adherent,
                "max_expected_duration": record.max_expected_duration,
                "max_expected_cost": record.max_expected_cost,
            })

    def _persist_skill(self, signature_hash: str) -> None:
        if self._storage is None or not hasattr(self._storage, "skill_upsert"):
            return
        skill = self._skills.get(signature_hash)
        if skill is None:
            return
        gm = {}
        if skill.generation_metadata is not None:
            gm = {
                "promoted_by_system_version": skill.generation_metadata.promoted_by_system_version,
                "policy_bundle_at_promotion": skill.generation_metadata.policy_bundle_at_promotion,
                "catalog_snapshot_at_promotion": skill.generation_metadata.catalog_snapshot_at_promotion,
                "promotion_scores": skill.generation_metadata.promotion_scores,
                "execution_count_at_promotion": skill.generation_metadata.execution_count_at_promotion,
                "evaluation_window": skill.generation_metadata.evaluation_window,
            }
        self._storage.skill_upsert(signature_hash, {
            "state": skill.state.value,
            "generation_metadata": gm,
            "last_evaluation": skill.last_evaluation.isoformat() if skill.last_evaluation else "",
            "demotion_reason": skill.demotion_reason,
            "consecutive_inactive_windows": skill.consecutive_inactive_windows,
            "history": skill.history,
        })

    def evaluate(
        self,
        signature_hash: str,
        policy_bundle_version: str = "",
        catalog_snapshot_version: str = "",
    ) -> tuple[SkillRecord, IndexScores]:
        """
        Evaluate a signature_hash for promotion or demotion.
        Returns updated SkillRecord and computed IndexScores.
        """
        skill = self.get_skill(signature_hash)
        scores = self._calculator.compute(signature_hash, self._records)
        skill.last_evaluation = _utcnow()

        # ── Check demotion triggers first (demotion takes precedence) ───
        demoted = self._check_demotion(skill, scores)
        if demoted:
            self._persist_skill(signature_hash)
            return skill, scores

        # ── Check promotion gate ────────────────────────────────────────
        promoted = False
        if skill.state in (SkillState.CANDIDATE, SkillState.WATCHLIST, SkillState.DEMOTED):
            promoted = self._check_promotion(
                skill, scores, policy_bundle_version, catalog_snapshot_version
            )

        # ── Check inactivity ────────────────────────────────────────────
        if scores.execution_count == 0 and skill.state in (SkillState.ACTIVE, SkillState.WATCHLIST):
            skill.consecutive_inactive_windows += 1
            if skill.consecutive_inactive_windows >= self.policy.inactivity_periods_for_deprecation:
                skill.transition(SkillState.DEPRECATED, "Low reuse — no executions for multiple windows")
        else:
            skill.consecutive_inactive_windows = 0

        if demoted or promoted or skill.consecutive_inactive_windows > 0:
            self._persist_skill(signature_hash)
        return skill, scores

    def _check_promotion(
        self,
        skill: SkillRecord,
        scores: IndexScores,
        policy_bundle_version: str,
        catalog_snapshot_version: str,
    ) -> bool:
        """Check if skill meets promotion gate. Returns True if promoted."""
        if scores.execution_count < self.policy.min_executions:
            return False

        gate = (
            scores.ifo >= self.policy.ifo_threshold
            and scores.ifs >= self.policy.ifs_threshold
            and scores.ifg >= self.policy.ifg_threshold
        )

        if gate:
            skill.generation_metadata = SkillGenerationMetadata(
                promoted_by_system_version=self.system_version,
                policy_bundle_at_promotion=policy_bundle_version,
                catalog_snapshot_at_promotion=catalog_snapshot_version,
                promotion_scores={"IFo": scores.ifo, "IFs": scores.ifs, "IFg": scores.ifg},
                execution_count_at_promotion=scores.execution_count,
                evaluation_window=f"last_{self.policy.evaluation_window_days}_days",
            )
            skill.transition(SkillState.ACTIVE, "Promotion gate passed")
            return True
        return False

    def _check_demotion(self, skill: SkillRecord, scores: IndexScores) -> bool:
        """Check demotion triggers. Returns True if demoted/watchlisted."""
        if skill.state not in (SkillState.ACTIVE, SkillState.WATCHLIST):
            return False

        # IDI < 0.50 → immediate demotion (severe drift)
        if scores.severe_drift:
            skill.transition(SkillState.DEMOTED, f"Severe drift: IDI={scores.idi:.2f}")
            return True

        # IFg < 1 → systemic failure, immediate demotion
        if scores.ifg < 1.0 and scores.execution_count > 0:
            skill.transition(SkillState.DEMOTED, f"Governance violation: IFg={scores.ifg}")
            return True

        # IDI < 0.75 → watchlist
        if scores.drift_detected and skill.state == SkillState.ACTIVE:
            skill.transition(SkillState.WATCHLIST, f"Drift detected: IDI={scores.idi:.2f}")
            return True

        # IFs below threshold → watchlist
        if scores.ifs < self.policy.ifs_threshold and skill.state == SkillState.ACTIVE:
            skill.transition(SkillState.WATCHLIST, f"IFs degraded: {scores.ifs:.2f}")
            return True

        # IFo below threshold → watchlist
        if scores.ifo < self.policy.ifo_threshold and skill.state == SkillState.ACTIVE:
            skill.transition(SkillState.WATCHLIST, f"IFo low: {scores.ifo:.2f}")
            return True

        # Watchlist + still below thresholds → deprecated
        if skill.state == SkillState.WATCHLIST:
            still_bad = (
                scores.ifs < self.policy.ifs_threshold
                or scores.ifo < self.policy.ifo_threshold
            )
            if still_bad and scores.execution_count >= self.policy.min_executions:
                skill.transition(SkillState.DEPRECATED, "Sustained degradation in watchlist")
                return True

        return False

    def retire_for_catalog_change(self, signature_hash: str, reason: str = "") -> SkillRecord:
        """Force-retire a skill due to catalog incompatibility."""
        skill = self.get_skill(signature_hash)
        skill.transition(
            SkillState.RETIRED,
            reason or "Catalog incompatibility — dataset or domain removed",
        )
        self._persist_skill(signature_hash)
        return skill

    def demote_by_system_version(self, system_version: str, reason: str = "") -> list[SkillRecord]:
        """Mass-demote all skills promoted by a specific system version."""
        demoted = []
        for skill in self._skills.values():
            if (
                skill.generation_metadata is not None
                and skill.generation_metadata.promoted_by_system_version == system_version
                and skill.state == SkillState.ACTIVE
            ):
                skill.transition(
                    SkillState.DEMOTED,
                    reason or f"Mass demotion: system version {system_version} flagged",
                )
                self._persist_skill(skill.signature_hash)
                demoted.append(skill)
        return demoted

    def list_skills(self, state: SkillState | None = None) -> list[SkillRecord]:
        if state is None:
            return list(self._skills.values())
        return [s for s in self._skills.values() if s.state == state]
