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
from enum import Enum
from typing import Any

from .indices import ExecutionRecord, IndexCalculator, IndexScores
from .types import _utcnow


# ── Lifecycle States ────────────────────────────────────────────────────────


class SkillState(str, Enum):
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
    promoted_by_system_version: str = "cfa_v2.0"
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
    """

    def __init__(
        self,
        policy: PromotionPolicy | None = None,
        system_version: str = "cfa_v2.0",
    ) -> None:
        self.policy = policy or PromotionPolicy()
        self.system_version = system_version
        self._skills: dict[str, SkillRecord] = {}
        self._records: list[ExecutionRecord] = []
        self._calculator = IndexCalculator(window_days=self.policy.evaluation_window_days)

    def get_skill(self, signature_hash: str) -> SkillRecord:
        if signature_hash not in self._skills:
            self._skills[signature_hash] = SkillRecord(signature_hash=signature_hash)
        return self._skills[signature_hash]

    def record_execution(self, record: ExecutionRecord) -> None:
        """Record an execution for index computation."""
        self._records.append(record)

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
            return skill, scores

        # ── Check promotion gate ────────────────────────────────────────
        if skill.state in (SkillState.CANDIDATE, SkillState.WATCHLIST, SkillState.DEMOTED):
            self._check_promotion(
                skill, scores, policy_bundle_version, catalog_snapshot_version
            )

        # ── Check inactivity ────────────────────────────────────────────
        if scores.execution_count == 0 and skill.state in (SkillState.ACTIVE, SkillState.WATCHLIST):
            skill.consecutive_inactive_windows += 1
            if skill.consecutive_inactive_windows >= self.policy.inactivity_periods_for_deprecation:
                skill.transition(SkillState.DEPRECATED, "Low reuse — no executions for multiple windows")
        else:
            skill.consecutive_inactive_windows = 0

        return skill, scores

    def _check_promotion(
        self,
        skill: SkillRecord,
        scores: IndexScores,
        policy_bundle_version: str,
        catalog_snapshot_version: str,
    ) -> None:
        """Check if skill meets promotion gate."""
        if scores.execution_count < self.policy.min_executions:
            return

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
                demoted.append(skill)
        return demoted

    def list_skills(self, state: SkillState | None = None) -> list[SkillRecord]:
        if state is None:
            return list(self._skills.values())
        return [s for s in self._skills.values() if s.state == state]
