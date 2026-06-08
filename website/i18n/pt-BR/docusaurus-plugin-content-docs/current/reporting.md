---
sidebar_position: 15
---

# Relatórios

CFA gera relatórios HTML autocontidos com Chart.js — zero dependências Python, arquivos `.html` únicos prontos para abrir em qualquer navegador.

## Tipos de Relatório

### Relatório de Execução

Pipeline com timeline, métricas do sandbox, detalhes de faults e gráficos de severidade.

```bash
cfa report execution --intent "Juntar NFe com Clientes persistir Silver" --output relatorio.html
```

### Relatório de Auditoria

Linha do tempo de eventos com integridade da cadeia de hash e contagem de eventos.

```bash
cfa report audit --intent-id <id> --policy-bundle prod-v1.0 --output auditoria.html
```

### Dashboard de Ciclo de Vida

Índices IFo/IFs/IFg/IDI com gráficos de tendência.

```bash
cfa report lifecycle --period 90 --audit-file audit.jsonl --output dashboard.html
```

### Resumo de Compliance

Resumo para auditores com total de avaliações, aprovações, replans, bloqueios e incidentes de PII prevenidos.

```bash
cfa report compliance --policy-bundle prod-v1.0 --audit-file audit.jsonl --output compliance.html
```

### Multi-Pipeline Dashboard

Visão agregada de múltiplos pipelines com métricas de execução.

```bash
cfa report dashboard --period 90 --audit-file audit.jsonl --output dashboard.html
```

## Dados Reais

Todos os relatórios usam dados reais via `--audit-file`. Sem `--audit-file`, o relatório é gerado com valores zero e um aviso é emitido.

## API Programática

```python
from cfa.reporting import generate_report

# Relatório de compliance
generate_report(
    "compliance",
    "compliance.html",
    policy_bundle="prod-v1.0",
    total_evaluations=1000,
    approved=820,
    replanned=120,
    blocked=60,
    rules=[
        {"name": "forbid_raw_pii", "fired": 60, "severity": "critical"},
        {"name": "require_partition", "fired": 120, "severity": "high"},
    ],
    pii_incidents_prevented=60,
    audit_events_total=2000,
    chain_intact=True,
)

# Relatório de ciclo de vida
import datetime
now = datetime.date.today()
dates = [(now - datetime.timedelta(days=d)).isoformat() for d in range(29, -1, -1)]

generate_report(
    "lifecycle",
    "lifecycle.html",
    period_days=30,
    skills=[
        {"name": "fiscal_pipeline", "state": "active", "ifo": 0.91, "ifs": 0.96, "ifg": 1.0, "idi": 0.95},
    ],
    trend_dates=dates,
    ifo_vals=[0.85 + (i % 5) * 0.02 for i in range(30)],
    ifs_vals=[0.90 + (i % 4) * 0.01 for i in range(30)],
    idi_vals=[0.88 + (i % 6) * 0.015 for i in range(30)],
    ifg_vals=[1.0 if i % 10 != 7 else 0.0 for i in range(30)],
    decisions={"approved": 820, "replanned": 120, "blocked": 60},
)
```

