"""Tests for cfa.reporting — rich HTML report generation."""

from __future__ import annotations

import tempfile
from pathlib import Path

from cfa.reporting import ReportEngine, generate_report
from cfa.reporting.charts import (
    cost_trend_chart,
    decisions_pie_chart,
    faults_bar_chart,
    lifecycle_trend_chart,
    severity_pie_chart,
)


class TestCharts:
    def test_lifecycle_trend_chart(self):
        cfg = lifecycle_trend_chart(
            ["D1", "D2"], [0.9, 0.8], [0.95, 0.85], [0.88, 0.78], [1.0, 1.0],
        )
        assert cfg.chart_type == "line"
        assert len(cfg.datasets) == 4
        assert cfg.to_json()

    def test_decisions_pie_chart(self):
        cfg = decisions_pie_chart(10, 5, 2)
        assert cfg.chart_type == "doughnut"
        assert cfg.datasets[0]["data"] == [10, 5, 2]
        assert cfg.to_json()

    def test_faults_bar_chart(self):
        cfg = faults_bar_chart({"F1": 5, "F2": 3})
        assert cfg.chart_type == "bar"
        assert cfg.to_json()

    def test_cost_trend_chart(self):
        cfg = cost_trend_chart(["D1", "D2"], [10, 20], budget_line=50)
        assert cfg.chart_type == "line"
        assert len(cfg.datasets) == 2
        assert cfg.to_json()

    def test_severity_pie_chart(self):
        cfg = severity_pie_chart(2, 3, 1, 4, 0)
        assert cfg.datasets[0]["data"] == [2, 3, 1, 4, 0]


class TestReportEngine:
    def test_execution_report_creates_html(self):
        engine = ReportEngine()
        html = engine.execution_report(
            intent="test intent", intent_id="abc123", state="approved",
            signature_hash="7f83b165", policy_bundle="v1.0", replan_count=0,
            events=[{"phase": "formalize", "event_type": "test", "outcome": "ok"}],
            faults=[],
        )
        assert "<!doctype html>" in html.lower()
        assert "test intent" in html
        assert "approved" in html.upper() or "APPROVED" in html

    def test_execution_report_with_faults(self):
        engine = ReportEngine()
        html = engine.execution_report(
            intent="bad", intent_id="x", state="blocked",
            signature_hash="hash", policy_bundle="v1", replan_count=2,
            events=[],
            faults=[{"code": "F1", "severity": "critical", "message": "err", "remediation": ["fix"]}],
        )
        assert "F1" in html
        assert "critical" in html.upper() or "CRITICAL" in html

    def test_execution_report_with_sandbox(self):
        engine = ReportEngine()
        html = engine.execution_report(
            intent="t", intent_id="i", state="approved",
            signature_hash="h", policy_bundle="v1", replan_count=0,
            events=[],
            faults=[],
            sandbox_metrics={"rows_output": 1000, "shuffle_mb": 50, "duration_seconds": 2.5, "cost_dbu": 1.0},
        )
        assert "1,000" in html
        assert "50 MB" in html or "50.0 MB" in html

    def test_audit_report(self):
        engine = ReportEngine()
        html = engine.audit_report(
            intent_id="abc123", events=[
                {"timestamp": "2026-01-01T00:00:00", "phase": "govern", "event_type": "check", "outcome": "ok", "event_hash": "hash123"},
            ],
            chain_intact=True, policy_bundle="v1")
        assert "abc123" in html
        assert "INTACT" in html
        assert "audit" in html.lower()

    def test_lifecycle_report(self):
        engine = ReportEngine()
        html = engine.lifecycle_report(
            period_days=30,
            skills=[{"hash": "abc", "ifo": 0.92, "ifs": 0.95, "ifg": 1.0, "idi": 0.88, "state": "active"}],
            trend_dates=["D1", "D2"], ifo_vals=[0.9, 0.8], ifs_vals=[0.95, 0.85],
            idi_vals=[0.88, 0.78], ifg_vals=[1.0, 1.0],
            cost_dates=["D1", "D2"], cost_vals=[10, 20],
            decisions={"approved": 10, "replanned": 2, "blocked": 1},
        )
        assert "Lifecycle Dashboard" in html
        assert "ACTIVE" in html

    def test_compliance_report(self):
        engine = ReportEngine()
        html = engine.compliance_report(
            policy_bundle="prod-v1", total_evaluations=100,
            approved=90, replanned=8, blocked=2,
            rules=[{"name": "r1", "action": "block", "fault_code": "F1", "severity": "critical"}],
            pii_incidents_prevented=5, audit_events_total=200, chain_intact=True)
        assert "Compliance" in html
        assert "APPROVED" in html.upper()


class TestGenerateReport:
    def test_generate_execution(self):
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = generate_report("execution", f.name,
                intent="test", intent_id="id", state="approved",
                signature_hash="h", policy_bundle="v1", replan_count=0,
                events=[], faults=[])
            assert Path(path).exists()
            content = Path(path).read_text()
            assert "test" in content

    def test_generate_audit(self):
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = generate_report("audit", f.name,
                intent_id="x", events=[], chain_intact=True)
            assert Path(path).exists()

    def test_generate_lifecycle(self):
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = generate_report("lifecycle", f.name,
                period_days=7, skills=[], trend_dates=["D1"],
                ifo_vals=[1.0], ifs_vals=[1.0], idi_vals=[1.0], ifg_vals=[1.0],
                cost_dates=["D1"], cost_vals=[10],
                decisions={"approved": 1, "replanned": 0, "blocked": 0})
            assert Path(path).exists()

    def test_generate_compliance(self):
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = generate_report("compliance", f.name,
                policy_bundle="v1", total_evaluations=1,
                approved=1, replanned=0, blocked=0,
                rules=[], pii_incidents_prevented=0,
                audit_events_total=0, chain_intact=True)
            assert Path(path).exists()

    def test_unknown_report_type_raises(self):
        import pytest
        with pytest.raises(ValueError, match="Unknown report type"):
            generate_report("invalid", "out.html", intent="x", intent_id="y", state="z",
                          signature_hash="h", policy_bundle="v1", replan_count=0, events=[], faults=[])
