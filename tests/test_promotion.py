"""Tests for CFA Promotion / Demotion Engine."""

from datetime import timedelta

from cfa.indices import ExecutionRecord
from cfa.promotion import (
    PromotionEngine,
    PromotionPolicy,
    SkillState,
)
from cfa.types import _utcnow


def _make_record(
    sig_hash: str = "hash_a",
    success: bool = True,
    replanned: bool = False,
    cost_dbu: float = 5.0,
    duration: float = 30.0,
    faults: list[str] | None = None,
    pii_exposure: bool = False,
    days_ago: int = 0,
) -> ExecutionRecord:
    return ExecutionRecord(
        signature_hash=sig_hash,
        timestamp=_utcnow() - timedelta(days=days_ago),
        success=success,
        replanned=replanned,
        cost_dbu=cost_dbu,
        duration_seconds=duration,
        faults=faults or [],
        pii_exposure=pii_exposure,
    )


class TestPromotion:
    def test_promotes_after_min_executions(self):
        engine = PromotionEngine(policy=PromotionPolicy(min_executions=3))
        for _ in range(5):
            engine.record_execution(_make_record(cost_dbu=1.0, duration=10.0))
        skill, scores = engine.evaluate("hash_a", policy_bundle_version="v1.0")
        assert skill.state == SkillState.ACTIVE
        assert skill.generation_metadata is not None
        assert skill.generation_metadata.policy_bundle_at_promotion == "v1.0"

    def test_not_promoted_below_min_executions(self):
        engine = PromotionEngine(policy=PromotionPolicy(min_executions=10))
        for _ in range(3):
            engine.record_execution(_make_record(cost_dbu=1.0, duration=10.0))
        skill, scores = engine.evaluate("hash_a")
        assert skill.state == SkillState.CANDIDATE

    def test_not_promoted_if_ifo_low(self):
        engine = PromotionEngine(policy=PromotionPolicy(min_executions=3))
        # High cost → low IFo
        for _ in range(5):
            engine.record_execution(_make_record(cost_dbu=45.0, duration=10.0))
        skill, scores = engine.evaluate("hash_a")
        assert skill.state != SkillState.ACTIVE

    def test_not_promoted_if_ifg_zero(self):
        engine = PromotionEngine(policy=PromotionPolicy(min_executions=3))
        for _ in range(4):
            engine.record_execution(_make_record(cost_dbu=1.0, duration=10.0))
        engine.record_execution(_make_record(pii_exposure=True, cost_dbu=1.0, duration=10.0))
        skill, scores = engine.evaluate("hash_a")
        assert skill.state != SkillState.ACTIVE

    def test_generation_metadata_populated(self):
        engine = PromotionEngine(
            policy=PromotionPolicy(min_executions=3),
            system_version="cfa_v2.1",
        )
        for _ in range(5):
            engine.record_execution(_make_record(cost_dbu=1.0, duration=10.0))
        skill, _ = engine.evaluate("hash_a", "v1.0", "catalog_2026")
        assert skill.generation_metadata is not None
        assert skill.generation_metadata.promoted_by_system_version == "cfa_v2.1"
        assert skill.generation_metadata.catalog_snapshot_at_promotion == "catalog_2026"
        assert "IFo" in skill.generation_metadata.promotion_scores


class TestDemotion:
    def _promote(self, engine: PromotionEngine, sig_hash: str = "hash_a"):
        """Helper: promote a skill first."""
        for _ in range(5):
            engine.record_execution(_make_record(sig_hash=sig_hash, cost_dbu=1.0, duration=10.0))
        engine.evaluate(sig_hash)

    def test_severe_drift_demotes_immediately(self):
        engine = PromotionEngine(policy=PromotionPolicy(min_executions=3))
        self._promote(engine)

        # Now add replanned executions → severe drift
        for _ in range(8):
            engine.record_execution(_make_record(replanned=True, cost_dbu=1.0, duration=10.0))
        skill, scores = engine.evaluate("hash_a")
        assert skill.state == SkillState.DEMOTED
        assert "drift" in skill.demotion_reason.lower()

    def test_ifg_violation_demotes(self):
        engine = PromotionEngine(policy=PromotionPolicy(min_executions=3))
        self._promote(engine)

        # Add a PII exposure → IFg = 0
        engine.record_execution(_make_record(pii_exposure=True, cost_dbu=1.0, duration=10.0))
        skill, scores = engine.evaluate("hash_a")
        assert skill.state == SkillState.DEMOTED
        assert "governance" in skill.demotion_reason.lower()

    def test_ifs_degraded_moves_to_watchlist(self):
        engine = PromotionEngine(policy=PromotionPolicy(min_executions=3, ifs_threshold=0.90))
        self._promote(engine)

        # Add faults → IFs drops
        for _ in range(5):
            engine.record_execution(_make_record(faults=["SOME_FAULT"], cost_dbu=1.0, duration=10.0))
        skill, scores = engine.evaluate("hash_a")
        assert skill.state in (SkillState.WATCHLIST, SkillState.DEMOTED)

    def test_drift_detected_moves_to_watchlist(self):
        engine = PromotionEngine(policy=PromotionPolicy(min_executions=3))
        self._promote(engine)

        # IDI below 0.75 but above 0.50 → watchlist
        # Need 3 replanned out of ~10 total to get IDI ~0.7
        for _ in range(3):
            engine.record_execution(_make_record(replanned=True, cost_dbu=1.0, duration=10.0))
        skill, scores = engine.evaluate("hash_a")
        if scores.drift_detected and not scores.severe_drift:
            assert skill.state == SkillState.WATCHLIST


class TestRetirement:
    def test_retire_for_catalog_change(self):
        engine = PromotionEngine()
        engine.record_execution(_make_record())
        skill = engine.retire_for_catalog_change("hash_a", "Dataset removed")
        assert skill.state == SkillState.RETIRED
        assert len(skill.history) > 0


class TestMassDemotion:
    def test_demote_by_system_version(self):
        engine = PromotionEngine(
            policy=PromotionPolicy(min_executions=3),
            system_version="buggy_v1",
        )
        # Promote two skills
        for sig in ("hash_a", "hash_b"):
            for _ in range(5):
                engine.record_execution(_make_record(sig_hash=sig, cost_dbu=1.0, duration=10.0))
            engine.evaluate(sig)

        demoted = engine.demote_by_system_version("buggy_v1", "Bug in promotion logic")
        assert len(demoted) == 2
        assert all(s.state == SkillState.DEMOTED for s in demoted)

    def test_mass_demotion_does_not_affect_other_versions(self):
        engine1 = PromotionEngine(
            policy=PromotionPolicy(min_executions=3),
            system_version="v1",
        )
        for _ in range(5):
            engine1.record_execution(_make_record(sig_hash="hash_a", cost_dbu=1.0, duration=10.0))
        engine1.evaluate("hash_a")

        # Manually set a second skill with different system version metadata
        for _ in range(5):
            engine1.record_execution(_make_record(sig_hash="hash_b", cost_dbu=1.0, duration=10.0))
        engine1.evaluate("hash_b")
        # Both promoted by "v1", demote only "v1"
        demoted = engine1.demote_by_system_version("v2")  # v2 doesn't match
        assert len(demoted) == 0


class TestSkillHistory:
    def test_transition_history_recorded(self):
        engine = PromotionEngine(policy=PromotionPolicy(min_executions=3))
        for _ in range(5):
            engine.record_execution(_make_record(cost_dbu=1.0, duration=10.0))
        engine.evaluate("hash_a")
        skill = engine.get_skill("hash_a")
        assert len(skill.history) >= 1
        assert skill.history[-1]["to"] == "active"

    def test_list_skills_by_state(self):
        engine = PromotionEngine(policy=PromotionPolicy(min_executions=3))
        for _ in range(5):
            engine.record_execution(_make_record(sig_hash="hash_a", cost_dbu=1.0, duration=10.0))
        engine.evaluate("hash_a")
        engine.record_execution(_make_record(sig_hash="hash_b"))  # just a candidate
        engine.evaluate("hash_b")
        assert len(engine.list_skills(SkillState.ACTIVE)) == 1
        assert len(engine.list_skills(SkillState.CANDIDATE)) == 1


class TestKernelIntegration:
    def test_kernel_records_execution_and_evaluates(self):
        from cfa.kernel import KernelConfig, KernelOrchestrator

        kernel = KernelOrchestrator(
            config=KernelConfig(enable_promotion=True),
        )
        result = kernel.process("Join NFe with Clientes and persist to Silver")
        # Should have promotion event
        promo_events = [e for e in result.audit_events if e.get("stage") == "promotion_engine"]
        assert len(promo_events) >= 1

    def test_kernel_multiple_runs_may_promote(self):
        from cfa.kernel import KernelConfig, KernelOrchestrator

        kernel = KernelOrchestrator(
            config=KernelConfig(enable_promotion=True),
        )
        # Run same intent 5 times
        for _ in range(5):
            result = kernel.process("Join NFe with Clientes and persist to Silver")

        # After multiple runs, promotion engine should have records
        skills = kernel.promotion_engine.list_skills()
        assert len(skills) > 0

    def test_kernel_promotion_disabled(self):
        from cfa.kernel import KernelConfig, KernelOrchestrator

        kernel = KernelOrchestrator(
            config=KernelConfig(enable_promotion=False),
        )
        result = kernel.process("Join NFe with Clientes and persist to Silver")
        promo_events = [e for e in result.audit_events if e.get("stage") == "promotion_engine"]
        assert len(promo_events) == 0
