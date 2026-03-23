"""
CFA Intent Indices
==================
Quantitative signals for intent lifecycle management.

Four indices track the health and maturity of each intent_signature_hash:

- IFo (Índice de Fluidez Operacional): operational fluidity
  IFo = (1 - normalized_latency) × (1 - normalized_cost) × execution_stability

- IFs (Índice de Fidelidade Semântica): semantic fidelity
  IFs = output_contract_adherence × absence_of_semantic_drift × invariant_preservation

- IFg (Índice de Governança): governance compliance — BINARY by design
  IFg = policy_compliance × absence_of_pii_exposure × layer_adherence
  IFg = 1 is the ONLY acceptable value. IFg < 1 means systemic failure.

- IDI (Intent Drift Index): drift detection
  IDI = 1 - (replanned_executions / total_executions) over last 30 days
  IDI near 1.0 = stable; IDI < 0.75 = watchlist; IDI < 0.50 = immediate demotion
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from .types import _utcnow


# ── Execution Record ────────────────────────────────────────────────────────


@dataclass
class ExecutionRecord:
    """Single execution record for index computation."""

    signature_hash: str
    timestamp: datetime
    success: bool
    replanned: bool = False
    cost_dbu: float = 0.0
    duration_seconds: float = 0.0
    faults: list[str] = field(default_factory=list)
    schema_match: bool = True
    pii_exposure: bool = False
    policy_compliant: bool = True
    layer_adherent: bool = True

    # Normalization baselines (configurable per domain)
    max_expected_duration: float = 300.0  # 5 minutes baseline
    max_expected_cost: float = 50.0       # 50 DBU baseline


# ── Index Results ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class IndexScores:
    """Computed index scores for a signature_hash."""

    signature_hash: str
    ifo: float  # Operational Fluidity [0, 1]
    ifs: float  # Semantic Fidelity [0, 1]
    ifg: float  # Governance — binary: 0 or 1
    idi: float  # Drift Index [0, 1]
    execution_count: int
    window_days: int
    computed_at: datetime = field(default_factory=_utcnow)

    @property
    def promotion_eligible(self) -> bool:
        """Quick check against default thresholds."""
        return self.ifo >= 0.75 and self.ifs >= 0.90 and self.ifg == 1.0

    @property
    def drift_detected(self) -> bool:
        return self.idi < 0.75

    @property
    def severe_drift(self) -> bool:
        return self.idi < 0.50


# ── Index Calculator ────────────────────────────────────────────────────────


class IndexCalculator:
    """
    Computes IFo, IFs, IFg, IDI from execution records.

    Operates on a time window (default 30 days).
    All indices are per signature_hash.
    """

    def __init__(self, window_days: int = 30) -> None:
        self.window_days = window_days

    def compute(
        self, signature_hash: str, records: list[ExecutionRecord]
    ) -> IndexScores:
        cutoff = _utcnow() - timedelta(days=self.window_days)
        windowed = [r for r in records if r.signature_hash == signature_hash and r.timestamp >= cutoff]

        if not windowed:
            return IndexScores(
                signature_hash=signature_hash,
                ifo=0.0, ifs=0.0, ifg=1.0, idi=1.0,
                execution_count=0,
                window_days=self.window_days,
            )

        ifo = self._compute_ifo(windowed)
        ifs = self._compute_ifs(windowed)
        ifg = self._compute_ifg(windowed)
        idi = self._compute_idi(windowed)

        return IndexScores(
            signature_hash=signature_hash,
            ifo=ifo, ifs=ifs, ifg=ifg, idi=idi,
            execution_count=len(windowed),
            window_days=self.window_days,
        )

    def _compute_ifo(self, records: list[ExecutionRecord]) -> float:
        """IFo = (1 - norm_latency) × (1 - norm_cost) × execution_stability"""
        if not records:
            return 0.0

        # Normalized latency: avg(duration / max_expected_duration), clamped to [0, 1]
        latencies = [
            min(r.duration_seconds / max(r.max_expected_duration, 0.01), 1.0)
            for r in records
        ]
        norm_latency = sum(latencies) / len(latencies)

        # Normalized cost: avg(cost / max_expected_cost), clamped to [0, 1]
        costs = [
            min(r.cost_dbu / max(r.max_expected_cost, 0.01), 1.0)
            for r in records
        ]
        norm_cost = sum(costs) / len(costs)

        # Execution stability: success_rate
        success_rate = sum(1 for r in records if r.success) / len(records)

        return (1 - norm_latency) * (1 - norm_cost) * success_rate

    def _compute_ifs(self, records: list[ExecutionRecord]) -> float:
        """IFs = schema_adherence × absence_of_drift × invariant_preservation"""
        if not records:
            return 0.0

        # Schema adherence: fraction of executions with matching schema
        schema_match_rate = sum(1 for r in records if r.schema_match) / len(records)

        # Absence of drift: 1 - (replanned / total)
        replan_rate = sum(1 for r in records if r.replanned) / len(records)
        absence_drift = 1 - replan_rate

        # Invariant preservation: fraction without faults
        fault_free_rate = sum(1 for r in records if not r.faults) / len(records)

        return schema_match_rate * absence_drift * fault_free_rate

    def _compute_ifg(self, records: list[ExecutionRecord]) -> float:
        """IFg = binary. 1.0 if ALL executions are governance-compliant, else 0.0."""
        for r in records:
            if r.pii_exposure or not r.policy_compliant or not r.layer_adherent:
                return 0.0
        return 1.0

    def _compute_idi(self, records: list[ExecutionRecord]) -> float:
        """IDI = 1 - (replanned_executions / total_executions)"""
        if not records:
            return 1.0
        replanned = sum(1 for r in records if r.replanned)
        return 1 - (replanned / len(records))
