"""
CFA Reporting Engine v2
=======================
Rich, descriptive HTML reports with professional layout.
Inspired by modern review tool designs — user needs to understand
WHAT happened and WHY.
"""

from __future__ import annotations

import html as _html
from datetime import UTC

_CHARTJS = "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"
_INTEGRITY = "sha256-..."  # placeholder for future SRI


_REPORT_STYLE = """
:root {{
    --bg: #f5f1e8;
    --ink: #162c3a;
    --muted: #5e6b73;
    --surface: rgba(255,255,255,.92);
    --line: #e4dacb;
    --navy: #173b57;
    --copper: #b7792f;
    --green: #2f765c;
    --red: #a84436;
    --blue-soft: #e8f0f4;
    --amber-soft: #fbf0dc;
    --green-soft: #e4f2ec;
    --green-bright: #22c55e;
    --red-soft: #f8e8e4;
}}
* {{ box-sizing: border-box; }}
body {{
    margin: 0;
    background:
        radial-gradient(circle at 10% 0%, rgba(183,121,47,.10), transparent 32rem),
        radial-gradient(circle at 92% 10%, rgba(23,59,87,.08), transparent 30rem),
        linear-gradient(135deg, #f9f6ef 0%, var(--bg) 48%, #edf3f5 100%);
    color: var(--ink);
    font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    line-height: 1.56;
}}
main {{
    width: min(1240px, calc(100vw - 36px));
    margin: 34px auto 72px;
}}
.hero {{
    background: linear-gradient(135deg, rgba(255,255,255,.95), rgba(248,244,236,.92));
    border: 1px solid var(--line);
    border-radius: 30px;
    box-shadow: 0 26px 80px rgba(22,44,58,.13);
    padding: 38px;
    overflow: hidden;
    position: relative;
}}
.hero::after {{
    content: "";
    position: absolute;
    right: -100px; top: -100px;
    width: 320px; height: 320px;
    background: radial-gradient(circle, rgba(183,121,47,.12), transparent 70%);
}}
h1 {{
    margin: 0; max-width: 900px;
    font-size: clamp(2.1rem, 5vw, 4.2rem);
    line-height: .98; letter-spacing: -.065em;
    color: var(--navy);
}}
.subtitle {{
    max-width: 850px; color: var(--muted);
    font-size: 1.06rem; margin: 16px 0 0;
}}
.badge-row {{
    display: flex; flex-wrap: wrap; gap: 10px; margin-top: 24px;
}}
.badge {{
    border: 1px solid var(--line);
    background: #fff; color: var(--navy);
    border-radius: 999px; padding: 8px 12px;
    font-size: .88rem; font-weight: 700;
}}
.badge-accept {{ border-color: var(--green); background: var(--green-soft); color: var(--green); }}
.badge-block {{ border-color: var(--red); background: var(--red-soft); color: var(--red); }}
.badge-warn {{ border-color: var(--copper); background: var(--amber-soft); color: var(--copper); }}
.badge-info {{ border-color: #3b82f6; background: #e8f0fe; color: #3b82f6; }}
.grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
.grid3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }}
.grid4 {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; margin: 22px 0; }}
.card {{
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 22px; padding: 20px;
    box-shadow: 0 16px 44px rgba(22,44,58,.08);
}}
.section {{
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 24px; margin: 18px 0; padding: 24px;
    box-shadow: 0 16px 44px rgba(22,44,58,.07);
}}
.section h2 {{
    margin: 0 0 14px; color: var(--navy);
    font-size: 1.35rem; letter-spacing: -.025em;
}}
.kv {{
    display: grid; grid-template-columns: 200px 1fr;
    gap: 8px 16px; color: var(--muted);
}}
.kv strong {{ color: var(--ink); }}
.metric {{
    text-align: center; font-size: 2rem; line-height: 1;
    font-weight: 850; letter-spacing: -.04em; color: var(--navy);
}}
.metric .label {{
    display: block; font-size: .75rem; font-weight: 600;
    color: var(--muted); text-transform: uppercase;
    letter-spacing: .08em; margin-top: 4px;
}}
table {{
    width: 100%; border-collapse: collapse;
    overflow: hidden; border-radius: 14px; font-size: .92rem;
}}
th, td {{
    border-bottom: 1px solid #ebe3d8;
    padding: 11px 12px; text-align: left; vertical-align: top;
}}
th {{
    color: var(--navy); background: #f4ede2;
    font-size: .78rem; text-transform: uppercase;
    letter-spacing: .06em;
}}
tr:last-child td {{ border-bottom: 0; }}
code {{
    background: #f1ede5; border: 1px solid #e1d8c9;
    border-radius: 7px; padding: .1rem .32rem;
    color: #102d42; font-size: .9em;
}}
.timeline {{ position: relative; padding-left: 24px; }}
.timeline-item {{
    padding: 10px 0 10px 20px;
    border-left: 3px solid var(--line);
    position: relative; margin-bottom: 4px;
}}
.timeline-item::before {{
    content: ''; position: absolute; left: -7px; top: 16px;
    width: 11px; height: 11px; border-radius: 50%;
}}
.tl-ok::before {{ background: var(--green); }}
.tl-warn::before {{ background: var(--copper); }}
.tl-err::before {{ background: var(--red); }}
.callout {{
    border-left: 5px solid var(--copper);
    background: var(--amber-soft);
    padding: 14px 16px; border-radius: 14px;
    color: #5c4630; margin: 12px 0;
}}
.callout-green {{
    border-left-color: var(--green);
    background: var(--green-soft); color: #1a4a38;
}}
.callout-red {{
    border-left-color: var(--red);
    background: var(--red-soft); color: #5c2020;
}}
.reasoning {{
    font-size: 1.05rem; color: var(--ink);
    background: var(--amber-soft);
    border-radius: 14px; padding: 14px 18px;
    margin: 16px 0; border: 1px solid #e8d8b0;
}}
.footer {{
    text-align: center; color: var(--muted);
    font-size: .8rem; padding: 24px 0;
    border-top: 2px solid var(--line); margin-top: 32px;
}}
@media print {{
    body {{ background: #fff; }}
    .section, .card, .hero {{ box-shadow: none; border-color: #ddd; }}
}}
@media (max-width: 768px) {{
    .grid2, .grid3, .grid4 {{ grid-template-columns: 1fr; }}
}}
"""


def _now():
    from datetime import datetime
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _badge(text: str, kind: str = "info") -> str:
    cls = {"accept": "badge-accept", "block": "badge-block", "warn": "badge-warn", "info": "badge-info"}
    return f'<span class="badge {cls.get(kind, "badge-info")}">{text}</span>'


def _severity_badge(sev: str) -> str:
    m = {"critical": "badge-block", "high": "badge-block", "medium": "badge-warn", "warning": "badge-warn", "info": "badge-info"}
    return f'<span class="badge {m.get(sev, "badge-info")}">{sev.upper()}</span>'


def _header(intent: str, state: str) -> str:
    state_kind = "accept" if state in ("approved", "approved_with_warnings", "promotion_candidate") else \
                 "block" if state in ("blocked", "rolled_back") else "warn"
    return f"""<div class="hero">
<h1>CFA Governance Report</h1>
<p class="subtitle">{_html.escape(intent[:120])}</p>
<div class="badge-row">
{_badge(state.upper(), state_kind)}
{_badge("GOVERNED EXECUTION", "info")}
</div>
</div>"""


def _html_page(title: str, body: str, scripts: str = "") -> str:
    ts = _now()
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{_REPORT_STYLE.format(timestamp=ts)}</style>
</head>
<body>
<main>
{body}
<div class="footer">CFA v0.1.9 — Contextual Flux Architecture — Generated {ts}</div>
</main>
<script src="{_CHARTJS}"></script>
{scripts}
</body>
</html>"""


class ReportEngine:
    """Generates rich, descriptive HTML governance reports."""

    def execution_report(
        self, intent: str, intent_id: str, state: str, signature_hash: str,
        policy_bundle: str, replan_count: int, events: list, faults: list,
        sandbox_metrics: dict | None = None,
        domain: str = "", intent_type: str = "", target_layer: str = "",
        datasets: list | None = None, constraints: dict | None = None,
        confidence: float = 0.0, reasoning: str = "",
    ) -> str:
        parts: list[str] = []
        parts.append(_header(intent, state))

        parts.append('<div class="grid4">')
        parts.append(f'<div class="card"><div class="metric">{signature_hash[:12] if signature_hash else "N/A"}</div><div class="label">Signature Hash</div></div>')
        parts.append(f'<div class="card"><div class="metric">{policy_bundle}</div><div class="label">Policy Bundle</div></div>')
        parts.append(f'<div class="card"><div class="metric">{replan_count}</div><div class="label">Replans</div></div>')
        parts.append(f'<div class="card"><div class="metric">{len(events)}</div><div class="label">Audit Events</div></div>')
        parts.append('</div>')

        if reasoning or confidence > 0:
            parts.append('<div class="section"><h2>Intent Analysis</h2>')
            if reasoning:
                parts.append(f'<div class="reasoning">{_html.escape(reasoning)}</div>')
            parts.append('<div class="kv">')
            parts.append(f'<strong>Domain</strong><span>{_html.escape(domain or "general")}</span>')
            parts.append(f'<strong>Intent type</strong><span>{_html.escape(intent_type or "unknown")}</span>')
            parts.append(f'<strong>Target layer</strong><span style="font-weight:800;color:var(--navy)">{target_layer.upper() if target_layer else "?"}</span>')
            parts.append(f'<strong>Confidence</strong><span style="font-weight:800">{confidence:.0%}</span>')
            parts.append('</div></div>')

        if constraints or datasets:
            parts.append('<div class="section"><h2>State Signature</h2><div class="grid2">')
            if constraints:
                c = constraints
                parts.append('<div><table>')
                parts.append('<tr><th colspan="2">Constraints</th></tr>')
                parts.append(f'<tr><td>PII Protection</td><td>{_badge("ENABLED", "accept") if c.get("no_pii_raw") else _badge("RAW PII REQUESTED", "block")}</td></tr>')
                parts.append(f'<tr><td>Merge Key</td><td>{_badge("REQUIRED", "accept") if c.get("merge_key_required") else _badge("MISSING", "block")}</td></tr>')
                parts.append(f'<tr><td>Type Check</td><td>{_badge("ENABLED", "accept") if c.get("enforce_types") else _badge("DISABLED", "warn")}</td></tr>')
                p = c.get("partition_by", [])
                parts.append(f'<tr><td>Partition</td><td><code>{", ".join(p) if p else "NONE"}</code></td></tr>')
                cb = c.get("max_cost_dbu")
                parts.append(f'<tr><td>Cost limit</td><td><code>{cb if cb else "Unlimited"}</code></td></tr>')
                parts.append('</table></div>')
            if datasets:
                parts.append('<div><table><tr><th>Datasets</th></tr>')
                for ds in datasets:
                    parts.append(f'<tr><td><code>{ds}</code></td></tr>')
                parts.append('</table></div>')
            parts.append('</div></div>')

        if sandbox_metrics:
            parts.append('<div class="section"><h2>Execution Metrics</h2><div class="grid4">')
            parts.append(f'<div class="card"><div class="metric" style="color:var(--green)">{sandbox_metrics.get("rows_output", 0):,}</div><div class="label">Rows Output</div></div>')
            parts.append(f'<div class="card"><div class="metric">{sandbox_metrics.get("shuffle_mb", 0):.0f} MB</div><div class="label">Shuffle</div></div>')
            parts.append(f'<div class="card"><div class="metric">{sandbox_metrics.get("duration_seconds", 0):.1f}s</div><div class="label">Duration</div></div>')
            parts.append(f'<div class="card"><div class="metric" style="color:var(--copper)">{sandbox_metrics.get("cost_dbu", 0):.1f} DBU</div><div class="label">Cost</div></div>')
            parts.append('</div></div>')

        parts.append('<div class="section"><h2>Pipeline Phases</h2><div class="timeline">')
        for e in events:
            css_class = "tl-ok" if e.get("outcome", "") in ("ok", "approved", "resolved", "passed") else \
                        "tl-warn" if e.get("outcome", "") in ("replanned", "warning") else "tl-err"
            parts.append(f'<div class="timeline-item {css_class}"><strong>{e.get("phase", e.get("stage", "?"))}</strong> — {e.get("event_type", "")} <span style="color:var(--muted)">({e.get("outcome", "?")})</span></div>')
        parts.append('</div></div>')

        if faults:
            parts.append('<div class="section"><h2>Policy Violations</h2><table>')
            parts.append('<tr><th>Severity</th><th>Code</th><th>Description</th><th>How to Fix</th></tr>')
            for f in faults:
                parts.append(f'<tr><td>{_severity_badge(f.get("severity", "high"))}</td>'
                             f'<td><code>{_html.escape(str(f.get("code", "")))}</code></td>'
                             f'<td>{_html.escape(str(f.get("message", "")))}</td>'
                             f'<td>{"<br>".join(_html.escape(str(r)) for r in f.get("remediation", []))}</td></tr>')
            parts.append('</table></div>')

        state_kind = "accept" if state in ("approved", "approved_with_warnings", "promotion_candidate") else "block" if state in ("blocked", "rolled_back") else "warn"
        callout_class = "callout-green" if state_kind == "accept" else "callout-red" if state_kind == "block" else "callout"
        parts.append(f'<div class="section"><h2>Decision</h2><div class="{callout_class}">')
        if state == "approved":
            parts.append("<strong>APPROVED:</strong> All governance checks passed. Execution can proceed safely.")
        elif state == "blocked":
            parts.append(f"<strong>BLOCKED:</strong> Governance prevented execution. {len(faults)} violations found. See above for remediation.")
        else:
            parts.append(f"<strong>{state.upper()}:</strong> Refer to timeline and faults for details.")
        parts.append('</div></div>')

        return _html_page(f"CFA — {intent[:50]}", "\n".join(parts))

    def audit_report(self, intent_id: str, events: list, chain_intact: bool, policy_bundle: str = "") -> str:
        parts: list[str] = []
        parts.append(f"""<div class="hero">
<h1>CFA Audit Trail</h1>
<p class="subtitle">Intent: {_html.escape(intent_id)} | Bundle: {_html.escape(policy_bundle)}</p>
<div class="badge-row">
{_badge(f"CHAIN {'INTACT' if chain_intact else 'BROKEN'}", "accept" if chain_intact else "block")}
{_badge(f"{len(events)} EVENTS", "info")}
</div></div>""")

        parts.append('<div class="section"><h2>Event Timeline</h2><table>')
        parts.append('<tr><th>#</th><th>Timestamp</th><th>Phase</th><th>Event</th><th>Outcome</th></tr>')
        for i, e in enumerate(events[:100]):
            ts = str(e.get("timestamp", ""))[:19]
            parts.append(f'<tr><td>{i+1}</td><td style="font-size:12px">{ts}</td>'
                         f'<td>{e.get("phase", e.get("stage", ""))}</td>'
                         f'<td>{e.get("event_type", "")}</td>'
                         f'<td>{e.get("outcome", "")}</td></tr>')
        parts.append('</table></div>')

        return _html_page(f"CFA Audit — {intent_id[:16]}", "\n".join(parts))

    def compliance_report(self, policy_bundle: str, total_evaluations: int,
                          approved: int, replanned: int, blocked: int,
                          rules: list, pii_incidents_prevented: int,
                          audit_events_total: int, chain_intact: bool) -> str:
        pct = (approved / max(total_evaluations, 1)) * 100
        parts: list[str] = []
        parts.append(f"""<div class="hero">
<h1>CFA Compliance Summary</h1>
<p class="subtitle">Policy: {policy_bundle} | {total_evaluations} evaluations</p>
<div class="badge-row">
{_badge(f"{pct:.0f}% COMPLIANT", "accept")}
{_badge(f"{pii_incidents_prevented} PII PREVENTED", "info")}
{_badge(f"CHAIN {'INTACT' if chain_intact else 'BROKEN'}", "accept" if chain_intact else "block")}
</div></div>""")

        parts.append('<div class="grid4">')
        parts.append(f'<div class="card"><div class="metric" style="color:var(--green)">{approved}</div><div class="label">Approved</div></div>')
        parts.append(f'<div class="card"><div class="metric" style="color:var(--copper)">{replanned}</div><div class="label">Replanned</div></div>')
        parts.append(f'<div class="card"><div class="metric" style="color:var(--red)">{blocked}</div><div class="label">Blocked</div></div>')
        parts.append(f'<div class="card"><div class="metric">{audit_events_total}</div><div class="label">Audit Events</div></div>')
        parts.append('</div>')

        parts.append('<div class="section"><h2>Policy Rules</h2><table>')
        parts.append('<tr><th>Rule</th><th>Action</th><th>Code</th><th>Severity</th></tr>')
        for r in rules:
            parts.append(f'<tr><td>{r.get("name", "")}</td>'
                         f'<td>{r.get("action", "").upper()}</td>'
                         f'<td><code>{r.get("fault_code", "")}</code></td>'
                         f'<td>{_severity_badge(r.get("severity", "high"))}</td></tr>')
        parts.append('</table></div>')

        return _html_page("CFA Compliance", "\n".join(parts))

    def lifecycle_report(self, period_days: int, skills: list, trend_dates: list,
                         ifo_vals: list, ifs_vals: list, idi_vals: list, ifg_vals: list,
                         cost_dates: list, cost_vals: list, decisions: dict) -> str:
        parts: list[str] = []
        active_count = sum(1 for s in skills if s.get("state") == "active")
        watch_count = sum(1 for s in skills if s.get("state") == "watchlist")
        parts.append(f"""<div class="hero">
<h1>CFA Lifecycle Dashboard</h1>
<p class="subtitle">Last {period_days} days | {len(skills)} pipelines</p>
<div class="badge-row">
{_badge(f"{active_count} ACTIVE", "accept")}
{_badge(f"{watch_count} WATCHLIST", "warn")}
</div></div>""")

        parts.append('<div class="grid3">')
        parts.append(f'<div class="card"><div class="metric" style="color:var(--green)">{decisions.get("approved", 0)}</div><div class="label">Approved</div></div>')
        parts.append(f'<div class="card"><div class="metric" style="color:var(--copper)">{decisions.get("replanned", 0)}</div><div class="label">Replanned</div></div>')
        parts.append(f'<div class="card"><div class="metric" style="color:var(--red)">{decisions.get("blocked", 0)}</div><div class="label">Blocked</div></div>')
        parts.append('</div>')

        parts.append('<div class="section"><h2>Pipeline Skills</h2><table>')
        parts.append('<tr><th>Pipeline</th><th>IFo</th><th>IFs</th><th>IFg</th><th>IDI</th><th>State</th></tr>')
        for s in skills:
            st = s.get("state", "candidate")
            st_kind = "accept" if st == "active" else "warn" if st == "watchlist" else "block"
            parts.append(f'<tr><td><code>{s.get("hash", "?")[:16]}</code></td>'
                         f'<td>{s.get("ifo", 0):.2f}</td><td>{s.get("ifs", 0):.2f}</td>'
                         f'<td>{s.get("ifg", 0):.2f}</td><td>{s.get("idi", 0):.2f}</td>'
                         f'<td>{_badge(st.upper(), st_kind)}</td></tr>')
        parts.append('</table></div>')

        return _html_page("CFA Lifecycle", "\n".join(parts))

    def dashboard(self, period_days: int, skills: list, trend_dates: list,
                  ifo_vals: list, faults_summary: dict, decisions: dict) -> str:
        parts: list[str] = []
        parts.append(f"""<div class="hero">
<h1>CFA Dashboard</h1>
<p class="subtitle">{len(skills)} pipelines | Last {period_days} days</p>
</div>""")

        parts.append('<div class="grid3">')
        parts.append(f'<div class="card"><div class="metric" style="color:var(--green)">{decisions.get("approved", 0)}</div><div class="label">Approved</div></div>')
        parts.append(f'<div class="card"><div class="metric" style="color:var(--copper)">{decisions.get("replanned", 0)}</div><div class="label">Replanned</div></div>')
        parts.append(f'<div class="card"><div class="metric" style="color:var(--red)">{decisions.get("blocked", 0)}</div><div class="label">Blocked</div></div>')
        parts.append('</div>')

        parts.append('<div class="section"><h2>Top Faults</h2><table>')
        parts.append('<tr><th>Fault</th><th>Count</th></tr>')
        for code, count in sorted(faults_summary.items(), key=lambda x: x[1], reverse=True)[:10]:
            parts.append(f'<tr><td><code>{code}</code></td><td>{count}</td></tr>')
        parts.append('</table></div>')

        return _html_page("CFA Dashboard", "\n".join(parts))


def generate_report(report_type: str, output_path: str, **kwargs) -> str:
    engine = ReportEngine()
    dispatch = {
        "execution": engine.execution_report,
        "audit": engine.audit_report,
        "lifecycle": engine.lifecycle_report,
        "compliance": engine.compliance_report,
        "dashboard": engine.dashboard,
    }
    handler = dispatch.get(report_type)
    if handler is None:
        raise ValueError(f"Unknown report type '{report_type}'. Choose: {', '.join(dispatch)}")
    html = handler(**kwargs)
    from pathlib import Path
    out = Path(output_path)
    out.write_text(html, encoding="utf-8")
    return str(out)
