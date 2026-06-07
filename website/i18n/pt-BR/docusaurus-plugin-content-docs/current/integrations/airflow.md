---
sidebar_position: 1
---

# Airflow Governance Gate

Adicione um gate de política CFA antes da execução de tarefas Airflow.

## Conceito

Em uma DAG tradicional, a tarefa vai direto para execução:

```
Task → Executar
```

Com o gate de governança CFA:

```
Task → CFA Policy Gate → Executar (se aprovado)
```

## Uso

```python
from governance_gate import GovernanceRequest, assert_allowed

request = GovernanceRequest(
    domain="fiscal",
    intent="reconciliation",
    target_layer="silver",
    datasets=(
        {"name": "nfe", "classification": "high_volume", "size_gb": 4000,
         "pii_columns": [], "partition_column": "processing_date"},
        {"name": "clientes", "classification": "sensitive", "size_gb": 0.5,
         "pii_columns": ["cpf", "email"], "partition_column": "processing_date"},
    ),
)

assert_allowed(request)
# Se bloqueado, levanta RuntimeError com a razão
```
