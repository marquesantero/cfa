"""
CFA Prometheus Metrics
======================
Optional Prometheus metrics exposition for production monitoring.

Exposes counters and gauges for:
- Policy evaluations (total by decision)
- Replan attempts
- Audit trail events and chain integrity
- Lifecycle indices (per pipeline)

Usage:
    from cfa.observability.metrics import get_metrics_text
    print(get_metrics_text())  # Prometheus text format

    # Or: cfa serve --metrics-port 9090
    # → http://localhost:9090/metrics

Zero dependencies in core — uses plain text format.
"""

from __future__ import annotations

import threading

# In-memory metric counters
_COUNTERS: dict[str, int] = {}
_GAUGES: dict[str, float] = {}
_LOCK = threading.Lock()


def inc_counter(name: str, value: int = 1, labels: dict[str, str] | None = None) -> None:
    key = _metric_key(name, labels)
    with _LOCK:
        _COUNTERS[key] = _COUNTERS.get(key, 0) + value


def set_gauge(name: str, value: float, labels: dict[str, str] | None = None) -> None:
    key = _metric_key(name, labels)
    with _LOCK:
        _GAUGES[key] = value


def _metric_key(name: str, labels: dict[str, str] | None) -> str:
    if not labels:
        return name
    label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    return f"{name}{{{label_str}}}"


def record_policy_evaluation(decision: str) -> None:
    inc_counter("cfa_policy_evaluations_total", labels={"decision": decision})


def record_replan() -> None:
    inc_counter("cfa_replan_attempts_total")


def record_audit_event(outcome: str = "ok") -> None:
    inc_counter("cfa_audit_events_total")


def record_lifecycle_index(pipeline_hash: str, index_name: str, value: float) -> None:
    set_gauge("cfa_lifecycle_index", value, labels={"pipeline": pipeline_hash[:12], "index": index_name})


def get_metrics_text() -> str:
    with _LOCK:
        counters = dict(_COUNTERS)
        gauges = dict(_GAUGES)
    lines: list[str] = []
    lines.append("# HELP cfa_policy_evaluations_total Total CFA policy evaluations by decision.")
    lines.append("# TYPE cfa_policy_evaluations_total counter")
    for key, val in counters.items():
        if key.startswith("cfa_policy_evaluations"):
            lines.append(f"{key} {val}")
    lines.append("# HELP cfa_replan_attempts_total Total CFA replan attempts.")
    lines.append("# TYPE cfa_replan_attempts_total counter")
    for key, val in counters.items():
        if key.startswith("cfa_replan"):
            lines.append(f"{key} {val}")
    lines.append("# HELP cfa_audit_events_total Total audit events recorded.")
    lines.append("# TYPE cfa_audit_events_total counter")
    for key, val in counters.items():
        if key.startswith("cfa_audit"):
            lines.append(f"{key} {val}")
    lines.append("# HELP cfa_lifecycle_index Current lifecycle index value per pipeline.")
    lines.append("# TYPE cfa_lifecycle_index gauge")
    for key, val in gauges.items():
        lines.append(f"{key} {val}")
    return "\n".join(lines) + "\n"
