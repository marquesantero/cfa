---
sidebar_position: 15
---

# Reporting

CFA generates self-contained HTML reports with Chart.js — zero Python dependencies, single `.html` files ready to open in any browser.

## Report Types

### Execution Report

Pipeline execution with timeline, sandbox metrics, fault details, and severity charts.

```bash
cfa report execution --intent "Join NFe with Clientes persist Silver" --output report.html
```

### Audit Report

Hash chain visualization, event timeline, integrity verification badge.

```bash
cfa report audit --intent-id abc12345 --output audit.html
```

### Lifecycle Dashboard

IFo/IFs/IFg/IDI trend charts, cost dashboard with budget line, skill state table.

```bash
cfa report lifecycle --period 90 --output dashboard.html
```

### Compliance Report

Governance health score, policy decisions doughnut, rules summary, PII incidents.

```bash
cfa report compliance --policy-bundle prod-v1.0 --output compliance.html
```

### Interactive Dashboard

Multi-pipeline dashboard with charts and skills table.

```bash
cfa report dashboard --period 90 --output dashboard.html
cfa serve --port 8765     # Live dashboard server
```

## Programmatic API

```python
from cfa.reporting import generate_report

generate_report("execution", "report.html",
    intent="my intent", intent_id="abc", state="approved",
    signature_hash="hash", policy_bundle="v1.0", replan_count=0,
    events=[...], faults=[...])

generate_report("audit", "audit.html",
    intent_id="abc", events=[...], chain_intact=True)

generate_report("lifecycle", "dashboard.html",
    period_days=90, skills=[...], trend_dates=[...],
    ifo_vals=[...], ifs_vals=[...], idi_vals=[...], ifg_vals=[...],
    cost_dates=[...], cost_vals=[...], decisions={...})

generate_report("compliance", "compliance.html",
    policy_bundle="v1.0", total_evaluations=100,
    approved=90, replanned=8, blocked=2,
    rules=[...], pii_incidents_prevented=5,
    audit_events_total=200, chain_intact=True)
```

## Design

- **Single-file HTML** — self-contained, portable, shareable
- **Chart.js** — loaded from CDN, interactive charts rendered in browser
- **Dark theme** — professional, printable, responsive
- **Zero Python deps** — pure stdlib, all rendering happens in browser
