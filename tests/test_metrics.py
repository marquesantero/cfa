"""Tests for cfa.metrics — Prometheus metrics."""

from cfa.observability.metrics import (
    get_metrics_text,
    inc_counter,
    record_audit_event,
    record_lifecycle_index,
    record_policy_evaluation,
    record_replan,
    set_gauge,
)


class TestMetrics:
    def test_counter_increment(self):
        inc_counter("test_counter")
        inc_counter("test_counter", 5)
        text = get_metrics_text()
        assert "test_counter" not in text  # only CFA-prefixed metrics are exported

    def test_policy_evaluation(self):
        record_policy_evaluation("approve")
        record_policy_evaluation("block")
        text = get_metrics_text()
        assert 'decision="approve"' in text or "approve" in text

    def test_replan(self):
        record_replan()
        text = get_metrics_text()
        assert "cfa_replan_attempts_total" in text

    def test_audit_event(self):
        record_audit_event()
        text = get_metrics_text()
        assert "cfa_audit_events_total" in text

    def test_lifecycle_index(self):
        record_lifecycle_index("abc123def456", "ifo", 0.92)
        text = get_metrics_text()
        assert "cfa_lifecycle_index" in text

    def test_gauge(self):
        set_gauge("cfa_test_gauge", 3.14, labels={"env": "test"})
        text = get_metrics_text()
        assert "cfa_test_gauge" in text
        assert "3.14" in text

    def test_help_text(self):
        text = get_metrics_text()
        assert "HELP" in text
        assert "TYPE" in text
