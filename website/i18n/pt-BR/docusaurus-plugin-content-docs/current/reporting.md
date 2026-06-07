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
