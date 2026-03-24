"""
Standalone lifecycle example.

Use this when you already have recurring executions and want quantitative
promotion, watchlist, and demotion logic.
"""

from pathlib import Path
import sys
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cfa.lifecycle import (
    PromotionEngine,
    PromotionPolicy,
    ExecutionRecord,
    IndexCalculator,
)

now = datetime.now(timezone.utc)

engine = PromotionEngine(
    policy=PromotionPolicy(
        min_executions=3,
        evaluation_window_days=30,
        ifo_threshold=0.75,
        ifs_threshold=0.90,
    ),
)

pipeline_hash = "fiscal_reconciliation_silver_abc123"

for i in range(5):
    engine.record_execution(
        ExecutionRecord(
            signature_hash=pipeline_hash,
            timestamp=now - timedelta(days=5 - i),
            success=True,
            cost_dbu=5.0,
            duration_seconds=30.0,
        )
    )

skill, scores = engine.evaluate(pipeline_hash)

print(f"Pipeline: {pipeline_hash[:20]}...")
print(f"State:    {skill.state.value}")
print(f"IFo:      {scores.ifo:.2f}")
print(f"IFs:      {scores.ifs:.2f}")
print(f"IFg:      {scores.ifg:.0f}")
print(f"IDI:      {scores.idi:.2f}")
print(f"Eligible: {scores.promotion_eligible}")

print("\n--- Simulating drift ---")
for i in range(8):
    engine.record_execution(
        ExecutionRecord(
            signature_hash=pipeline_hash,
            timestamp=now - timedelta(hours=i),
            success=True,
            replanned=True,
            cost_dbu=5.0,
            duration_seconds=30.0,
        )
    )

skill, scores = engine.evaluate(pipeline_hash)
print(f"State:    {skill.state.value}")
print(f"IDI:      {scores.idi:.2f}")
print(f"Drift:    {scores.drift_detected}")
print(f"Severe:   {scores.severe_drift}")

print("\nTransition history:")
for entry in skill.history:
    print(f"  {entry['from']} -> {entry['to']}: {entry['reason']}")

print("\n--- Standalone index calculation ---")
calculator = IndexCalculator(window_days=7)
records = [
    ExecutionRecord(
        signature_hash="other_pipeline",
        timestamp=now - timedelta(days=i),
        success=True,
        cost_dbu=2.0,
        duration_seconds=15.0,
    )
    for i in range(10)
]
scores = calculator.compute("other_pipeline", records)
print(
    f"IFo={scores.ifo:.2f} IFs={scores.ifs:.2f} "
    f"IFg={scores.ifg:.0f} IDI={scores.idi:.2f}"
)
