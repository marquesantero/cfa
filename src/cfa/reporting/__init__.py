"""
CFA Reporting — Rich HTML reports
==================================
Self-contained HTML reports with Chart.js charts.

Report types:
- execution: pipeline execution with timeline, metrics, faults
- audit: hash chain visualization with event timeline
- lifecycle: IFo/IFs/IFg/IDI dashboard with trend charts
- compliance: governance health summary for auditors

Usage:
    from cfa.reporting import generate_report

    generate_report("execution", "report.html", intent="...", state="approved", ...)
    generate_report("audit", "audit.html", intent_id="...", events=[...], chain_intact=True)
    generate_report("lifecycle", "dashboard.html", period_days=90, skills=[...], ...)
    generate_report("compliance", "compliance.html", policy_bundle="prod-v1", ...)
"""

from __future__ import annotations

from .charts import (
    ChartConfig,
    cost_trend_chart,
    decisions_pie_chart,
    faults_bar_chart,
    lifecycle_trend_chart,
    severity_pie_chart,
)
from .engine import ReportEngine, generate_report

__all__ = [
    "ReportEngine",
    "generate_report",
    "ChartConfig",
    "lifecycle_trend_chart",
    "decisions_pie_chart",
    "faults_bar_chart",
    "cost_trend_chart",
    "severity_pie_chart",
]
