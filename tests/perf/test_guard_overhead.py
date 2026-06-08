"""Micro-benchmark: per-call overhead of the ``cfa_guard`` decorator.

The decorator caches a single ``KernelOrchestrator`` after the first call.
Subsequent calls are dominated by ``KernelOrchestrator.process(intent)``.

Target: p99 single-call overhead <= 5 ms on the reference machine (Win10 +
Python 3.11). The asserted threshold is 10 ms to absorb CI jitter and slow
shared runners. See ``tests/perf/baselines.py`` for the recorded baseline.

Run with::

    pytest tests/perf/test_guard_overhead.py --run-perf -q
"""

from __future__ import annotations

import statistics
import time

import pytest

from cfa.adapters import CFAGuard

from .baselines import GUARD_CALL_P99_MS

CATALOG = {
    "datasets": {
        "nfe": {
            "classification": "high_volume",
            "size_gb": 4000,
            "pii_columns": [],
            "partition_column": "processing_date",
            "merge_keys": ["nfe_id"],
        }
    }
}

INTENT = "ingest nfe to bronze"
WARMUP = 20
SAMPLE = 200


@pytest.fixture(scope="module")
def warm_guard() -> CFAGuard:
    guard = CFAGuard(catalog=CATALOG, mode="warn")

    @guard.guard(INTENT)
    def warm_call() -> int:
        return 1

    # Warm cache: first call instantiates the kernel.
    for _i in range(WARMUP):
        warm_call()
    return guard


def test_p99_under_threshold(warm_guard: CFAGuard) -> None:
    """p99 latency of a guarded call stays under the threshold."""

    @warm_guard.guard(INTENT)
    def call() -> int:
        return 1

    timings: list[float] = []
    for _i in range(SAMPLE):
        t0 = time.perf_counter()
        call()
        timings.append((time.perf_counter() - t0) * 1000.0)

    timings.sort()
    p50 = statistics.median(timings)
    p99 = timings[int(0.99 * len(timings)) - 1]
    p_max = max(timings)

    print(
        f"\nguard call latency over {SAMPLE} runs (after {WARMUP} warm-ups): "
        f"p50={p50:.3f}ms p99={p99:.3f}ms max={p_max:.3f}ms"
    )

    assert p99 <= GUARD_CALL_P99_MS.value_ms, (
        f"p99 latency {p99:.3f}ms exceeded baseline {GUARD_CALL_P99_MS.value_ms}ms; "
        f"investigate regressions in cfa.core.kernel.process or adapters._check."
    )
