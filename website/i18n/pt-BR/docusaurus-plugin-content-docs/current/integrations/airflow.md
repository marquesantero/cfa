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
from cfa.policy.engine import (
    PolicyEngine,
    StateSignature,
    TargetLayer,
    DatasetRef,
    DatasetClassification,
    SignatureConstraints,
    ExecutionContext,
)

engine = PolicyEngine(policy_bundle_version="prod-v1.0")

signature = StateSignature(
    domain="fiscal",
    intent="reconciliation",
    target_layer=TargetLayer.SILVER,
    datasets=(
        DatasetRef(name="nfe", classification=DatasetClassification.HIGH_VOLUME, size_gb=4000),
        DatasetRef(name="clientes", classification=DatasetClassification.SENSITIVE, size_gb=0.5,
                   pii_columns=("cpf", "email")),
    ),
    constraints=SignatureConstraints(
        no_pii_raw=False, merge_key_required=True, partition_by=("processing_date",),
    ),
    execution_context=ExecutionContext(
        policy_bundle_version="prod-v1.0",
        catalog_snapshot_version="catalog_default",
        context_registry_version_id="ctx-default",
    ),
)

result = engine.evaluate(signature)
if result.action.value == "block":
    raise RuntimeError(result.reasoning)
```
