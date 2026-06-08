"""Macro-benchmark: throughput of ``cfa.testing.evaluate``.

Measures how many full evaluations the rule-based normalizer can sustain
per second on a hot kernel. Useful as a regression guard for the policy
engine and the orchestration loop.

Target: at least 50 ops/sec on the reference machine. The asserted
threshold is set to 20 ops/sec to absorb CI jitter.

Run with::

    pytest tests/perf/test_evaluate_throughput.py --run-perf -q
"""

from __future__ import annotations

import time

import pytest

from cfa.testing import evaluate

from .baselines import EVALUATE_THROUGHPUT_OPS

CATALOG = {
    "datasets": {
        "nfe": {
            "classification": "high_volume",
            "size_gb": 4000,
            "pii_columns": [],
            "partition_column": "processing_date",
            "merge_keys": ["nfe_id"],
        },
        "clientes": {
            "classification": "sensitive",
            "size_gb": 0.5,
            "pii_columns": ["cpf", "email"],
            "partition_column": "processing_date",
            "merge_keys": ["cliente_id"],
        },
    }
}

INTENT = "Join NFe with Clientes and persist to Silver"
WARMUP = 10
SAMPLE = 200


@pytest.fixture(scope="module")
def warm() -> None:
    for _i in range(WARMUP):
        evaluate(INTENT, catalog=CATALOG)


def test_throughput_above_threshold(warm: None) -> None:
    """Sustained throughput stays above the recorded baseline."""
    t0 = time.perf_counter()
    for _i in range(SAMPLE):
        evaluate(INTENT, catalog=CATALOG)
    elapsed = time.perf_counter() - t0

    ops = SAMPLE / elapsed
    print(
        f"\nevaluate throughput: {SAMPLE} calls in {elapsed:.3f}s "
        f"= {ops:.1f} ops/sec"
    )

    # 50 ops/sec target; 20 ops/sec asserted to absorb CI variability.
    threshold = max(EVALUATE_THROUGHPUT_OPS.value_ms * 0.4, 20.0)
    assert ops >= threshold, (
        f"throughput {ops:.1f} ops/sec under threshold {threshold}; "
        f"investigate regressions in PolicyEngine or KernelPhases."
    )
