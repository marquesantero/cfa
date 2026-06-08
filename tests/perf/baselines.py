"""Performance baselines recorded for the perf suite.

Each baseline records the threshold the suite will assert against and a
short note on the measurement methodology. When you regenerate a baseline,
keep the old value as a comment so we can see drift over time.

Hardware and Python version that produced the recorded numbers:
  - Windows 10 / Python 3.11
  - 1.1.0.dev0 working tree

If you legitimately need to raise a threshold (e.g. you added work to the
critical path), record the new value here AND in the corresponding test's
docstring. Don't quietly bump in the assertion.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Baseline:
    name: str
    value_ms: float
    notes: str


# Single guarded call after the kernel is warm.
# Recorded at 1.1.0.dev0: typical p99 is well below 5ms on Mock sandbox.
GUARD_CALL_P99_MS = Baseline(
    name="cfa_guard.call.p99",
    value_ms=10.0,
    notes=(
        "5ms target on cold machines; threshold set at 10ms to absorb CI jitter. "
        "If this regresses, profile core/kernel.process and adapters/_check."
    ),
)

# Throughput of cfa.testing.evaluate with the rule-based normalizer.
# Recorded at 1.1.0.dev0: easily clears 50 ops/s on the reference machine.
EVALUATE_THROUGHPUT_OPS = Baseline(
    name="evaluate.throughput.ops_per_second",
    value_ms=50.0,  # interpreted as "at least N ops/sec"
    notes="Run with the in-memory mock backend and no audit persistence.",
)
