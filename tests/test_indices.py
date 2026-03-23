"""Tests for CFA Intent Indices (IFo, IFs, IFg, IDI)."""

from datetime import timedelta

from cfa.indices import ExecutionRecord, IndexCalculator, IndexScores
from cfa.types import _utcnow


def _make_record(
    sig_hash: str = "hash_a",
    success: bool = True,
    replanned: bool = False,
    cost_dbu: float = 5.0,
    duration: float = 30.0,
    faults: list[str] | None = None,
    schema_match: bool = True,
    pii_exposure: bool = False,
    policy_compliant: bool = True,
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
        schema_match=schema_match,
        pii_exposure=pii_exposure,
        policy_compliant=policy_compliant,
    )


class TestIFo:
    def test_perfect_ifo(self):
        """Low latency, low cost, all successful → IFo near 1.0."""
        calc = IndexCalculator(window_days=30)
        records = [_make_record(cost_dbu=1.0, duration=10.0) for _ in range(5)]
        scores = calc.compute("hash_a", records)
        assert scores.ifo > 0.80

    def test_high_cost_lowers_ifo(self):
        calc = IndexCalculator(window_days=30)
        records = [_make_record(cost_dbu=45.0, duration=10.0) for _ in range(5)]
        scores = calc.compute("hash_a", records)
        assert scores.ifo < 0.50

    def test_high_latency_lowers_ifo(self):
        calc = IndexCalculator(window_days=30)
        records = [_make_record(cost_dbu=1.0, duration=280.0) for _ in range(5)]
        scores = calc.compute("hash_a", records)
        assert scores.ifo < 0.30

    def test_failures_lower_ifo(self):
        calc = IndexCalculator(window_days=30)
        records = [_make_record(success=False) for _ in range(5)]
        scores = calc.compute("hash_a", records)
        assert scores.ifo == 0.0


class TestIFs:
    def test_perfect_ifs(self):
        calc = IndexCalculator(window_days=30)
        records = [_make_record() for _ in range(5)]
        scores = calc.compute("hash_a", records)
        assert scores.ifs == 1.0

    def test_replanning_lowers_ifs(self):
        calc = IndexCalculator(window_days=30)
        records = [_make_record(replanned=True) for _ in range(5)]
        scores = calc.compute("hash_a", records)
        assert scores.ifs == 0.0  # all replanned → absence_drift = 0

    def test_schema_mismatch_lowers_ifs(self):
        calc = IndexCalculator(window_days=30)
        records = [_make_record(schema_match=False) for _ in range(3)]
        records += [_make_record(schema_match=True) for _ in range(2)]
        scores = calc.compute("hash_a", records)
        assert scores.ifs < 1.0

    def test_faults_lower_ifs(self):
        calc = IndexCalculator(window_days=30)
        records = [_make_record(faults=["SOME_FAULT"]) for _ in range(5)]
        scores = calc.compute("hash_a", records)
        assert scores.ifs == 0.0  # fault_free_rate = 0


class TestIFg:
    def test_perfect_governance(self):
        calc = IndexCalculator(window_days=30)
        records = [_make_record() for _ in range(5)]
        scores = calc.compute("hash_a", records)
        assert scores.ifg == 1.0

    def test_pii_exposure_breaks_governance(self):
        calc = IndexCalculator(window_days=30)
        records = [_make_record() for _ in range(4)]
        records.append(_make_record(pii_exposure=True))
        scores = calc.compute("hash_a", records)
        assert scores.ifg == 0.0

    def test_policy_violation_breaks_governance(self):
        calc = IndexCalculator(window_days=30)
        records = [_make_record(policy_compliant=False)]
        scores = calc.compute("hash_a", records)
        assert scores.ifg == 0.0


class TestIDI:
    def test_no_replanning_perfect_idi(self):
        calc = IndexCalculator(window_days=30)
        records = [_make_record() for _ in range(5)]
        scores = calc.compute("hash_a", records)
        assert scores.idi == 1.0

    def test_all_replanned_zero_idi(self):
        calc = IndexCalculator(window_days=30)
        records = [_make_record(replanned=True) for _ in range(5)]
        scores = calc.compute("hash_a", records)
        assert scores.idi == 0.0

    def test_partial_replanning(self):
        calc = IndexCalculator(window_days=30)
        records = [_make_record(replanned=True) for _ in range(2)]
        records += [_make_record(replanned=False) for _ in range(8)]
        scores = calc.compute("hash_a", records)
        assert scores.idi == 0.8  # 2/10 replanned

    def test_drift_detected_threshold(self):
        calc = IndexCalculator(window_days=30)
        records = [_make_record(replanned=True) for _ in range(3)]
        records += [_make_record(replanned=False) for _ in range(7)]
        scores = calc.compute("hash_a", records)
        assert scores.idi == 0.7
        assert scores.drift_detected  # < 0.75

    def test_severe_drift_threshold(self):
        calc = IndexCalculator(window_days=30)
        records = [_make_record(replanned=True) for _ in range(6)]
        records += [_make_record(replanned=False) for _ in range(4)]
        scores = calc.compute("hash_a", records)
        assert scores.idi == 0.4
        assert scores.severe_drift  # < 0.50


class TestWindowFiltering:
    def test_old_records_excluded(self):
        calc = IndexCalculator(window_days=7)
        old = [_make_record(days_ago=10, success=False) for _ in range(5)]
        recent = [_make_record(days_ago=1) for _ in range(3)]
        scores = calc.compute("hash_a", old + recent)
        assert scores.execution_count == 3
        assert scores.ifo > 0  # only recent (successful) records count

    def test_empty_records(self):
        calc = IndexCalculator(window_days=30)
        scores = calc.compute("hash_a", [])
        assert scores.execution_count == 0
        assert scores.ifo == 0.0
        assert scores.idi == 1.0

    def test_filters_by_signature_hash(self):
        calc = IndexCalculator(window_days=30)
        records_a = [_make_record(sig_hash="hash_a") for _ in range(3)]
        records_b = [_make_record(sig_hash="hash_b") for _ in range(5)]
        scores = calc.compute("hash_a", records_a + records_b)
        assert scores.execution_count == 3


class TestIndexScores:
    def test_promotion_eligible(self):
        scores = IndexScores(
            signature_hash="h", ifo=0.80, ifs=0.95, ifg=1.0, idi=0.9,
            execution_count=5, window_days=7,
        )
        assert scores.promotion_eligible

    def test_not_eligible_low_ifo(self):
        scores = IndexScores(
            signature_hash="h", ifo=0.50, ifs=0.95, ifg=1.0, idi=0.9,
            execution_count=5, window_days=7,
        )
        assert not scores.promotion_eligible

    def test_not_eligible_ifg_zero(self):
        scores = IndexScores(
            signature_hash="h", ifo=0.80, ifs=0.95, ifg=0.0, idi=0.9,
            execution_count=5, window_days=7,
        )
        assert not scores.promotion_eligible
