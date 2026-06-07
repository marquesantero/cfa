"""
CFA Reporting — charts data preparation
=======================================
Prepares data structures for Chart.js inline chart rendering.
Zero Python dependencies — generates JSON configs for Chart.js CDN.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChartConfig:
    """JSON-serializable Chart.js configuration."""
    chart_type: str  # "line", "bar", "pie", "doughnut"
    labels: list[str]
    datasets: list[dict[str, Any]]
    options: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        import json
        return json.dumps({
            "type": self.chart_type,
            "data": {
                "labels": self.labels,
                "datasets": self.datasets,
            },
            "options": self.options,
        })


COLORS = {
    "green": "rgba(34, 197, 94, {a})",
    "red": "rgba(239, 68, 68, {a})",
    "yellow": "rgba(234, 179, 8, {a})",
    "blue": "rgba(59, 130, 246, {a})",
    "purple": "rgba(168, 85, 247, {a})",
    "cyan": "rgba(6, 182, 212, {a})",
    "orange": "rgba(249, 115, 22, {a})",
    "gray": "rgba(156, 163, 175, {a})",
}


def lifecycle_trend_chart(
    dates: list[str],
    ifo_values: list[float],
    ifs_values: list[float],
    idi_values: list[float],
    ifg_values: list[float],
) -> ChartConfig:
    """Multi-line chart showing IFo, IFs, IDI, IFg over time."""
    return ChartConfig(
        chart_type="line",
        labels=dates,
        datasets=[
            {
                "label": "IFo (Fluidez Operacional)",
                "data": ifo_values,
                "borderColor": COLORS["blue"].format(a="1"),
                "backgroundColor": COLORS["blue"].format(a="0.1"),
                "tension": 0.3,
                "fill": False,
            },
            {
                "label": "IFs (Fidelidade Semântica)",
                "data": ifs_values,
                "borderColor": COLORS["purple"].format(a="1"),
                "backgroundColor": COLORS["purple"].format(a="0.1"),
                "tension": 0.3,
                "fill": False,
            },
            {
                "label": "IDI (Intent Drift)",
                "data": idi_values,
                "borderColor": COLORS["cyan"].format(a="1"),
                "backgroundColor": COLORS["cyan"].format(a="0.1"),
                "tension": 0.3,
                "fill": False,
                "borderDash": [5, 5],
            },
            {
                "label": "IFg (Governança)",
                "data": ifg_values,
                "borderColor": COLORS["green"].format(a="1"),
                "backgroundColor": COLORS["green"].format(a="0.1"),
                "tension": 0.3,
                "fill": False,
                "stepped": True,
            },
        ],
        options={
            "responsive": True,
            "plugins": {
                "legend": {"position": "bottom", "labels": {"color": "#d1d5db"}},
            },
            "scales": {
                "x": {"ticks": {"color": "#9ca3af"}, "grid": {"color": "rgba(75,85,99,0.2)"}},
                "y": {
                    "min": 0, "max": 1,
                    "ticks": {"color": "#9ca3af", "callback": "value => (value * 100).toFixed(0) + '%'"},
                    "grid": {"color": "rgba(75,85,99,0.2)"},
                },
            },
        },
    )


def decisions_pie_chart(approved: int, replanned: int, blocked: int) -> ChartConfig:
    """Doughnut chart of policy decisions distribution."""
    return ChartConfig(
        chart_type="doughnut",
        labels=["Approved", "Replanned", "Blocked"],
        datasets=[{
            "data": [approved, replanned, blocked],
            "backgroundColor": [
                COLORS["green"].format(a="0.8"),
                COLORS["yellow"].format(a="0.8"),
                COLORS["red"].format(a="0.8"),
            ],
            "borderColor": [
                COLORS["green"].format(a="1"),
                COLORS["yellow"].format(a="1"),
                COLORS["red"].format(a="1"),
            ],
            "borderWidth": 1,
        }],
        options={
            "responsive": True,
            "plugins": {
                "legend": {"position": "bottom", "labels": {"color": "#d1d5db"}},
            },
        },
    )


def faults_bar_chart(fault_counts: dict[str, int]) -> ChartConfig:
    """Horizontal bar chart of top faults by frequency."""
    sorted_faults = sorted(fault_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    return ChartConfig(
        chart_type="bar",
        labels=[f[0] for f in sorted_faults],
        datasets=[{
            "label": "Occurrences",
            "data": [f[1] for f in sorted_faults],
            "backgroundColor": COLORS["red"].format(a="0.7"),
            "borderColor": COLORS["red"].format(a="1"),
            "borderWidth": 1,
        }],
        options={
            "indexAxis": "y",
            "responsive": True,
            "plugins": {
                "legend": {"display": False},
            },
            "scales": {
                "x": {"ticks": {"color": "#9ca3af"}, "grid": {"color": "rgba(75,85,99,0.2)"}},
                "y": {"ticks": {"color": "#9ca3af"}, "grid": {"color": "rgba(75,85,99,0.2)"}},
            },
        },
    )


def cost_trend_chart(dates: list[str], costs: list[float], budget_line: float = 50.0) -> ChartConfig:
    """Line chart of cost over time with budget threshold."""
    return ChartConfig(
        chart_type="line",
        labels=dates,
        datasets=[
            {
                "label": "Cost (DBU)",
                "data": costs,
                "borderColor": COLORS["orange"].format(a="1"),
                "backgroundColor": COLORS["orange"].format(a="0.1"),
                "tension": 0.3,
                "fill": True,
            },
            {
                "label": "Budget Limit",
                "data": [budget_line] * len(dates),
                "borderColor": COLORS["red"].format(a="0.5"),
                "borderDash": [8, 4],
                "fill": False,
                "pointRadius": 0,
            },
        ],
        options={
            "responsive": True,
            "plugins": {
                "legend": {"position": "bottom", "labels": {"color": "#d1d5db"}},
            },
            "scales": {
                "x": {"ticks": {"color": "#9ca3af"}, "grid": {"color": "rgba(75,85,99,0.2)"}},
                "y": {"ticks": {"color": "#9ca3af"}, "grid": {"color": "rgba(75,85,99,0.2)"}},
            },
        },
    )


def severity_pie_chart(critical: int, high: int, medium: int, warning: int, info: int) -> ChartConfig:
    """Pie chart of fault severity distribution."""
    return ChartConfig(
        chart_type="pie",
        labels=["Critical", "High", "Medium", "Warning", "Info"],
        datasets=[{
            "data": [critical, high, medium, warning, info],
            "backgroundColor": [
                COLORS["red"].format(a="0.8"),
                COLORS["orange"].format(a="0.8"),
                COLORS["yellow"].format(a="0.8"),
                COLORS["blue"].format(a="0.8"),
                COLORS["gray"].format(a="0.8"),
            ],
            "borderWidth": 1,
        }],
        options={
            "responsive": True,
            "plugins": {
                "legend": {"position": "bottom", "labels": {"color": "#d1d5db"}},
            },
        },
    )
