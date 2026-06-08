---
sidebar_position: 1
---

# Airflow Governance Gate

Add a CFA policy gate before Airflow task execution. The smallest realistic adoption wedge — no LLM, no semantic normalizer, no full kernel migration required.

---

## Concept

In a traditional DAG, a task goes straight to execution:

```
Task → Execute
```

With CFA governance gate:

```
Build StateSignature → PolicyEngine → APPROVE/REPLAN/BLOCK → Execute or fail fast
```

---

## Installation

```bash
pip install cfa-kernel
```

---

## Minimal Pattern

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

def governance_gate(**kwargs) -> str:
    """Airflow task that validates a pipeline intent before execution."""

    signature = StateSignature(
        domain="fiscal",
        intent="reconciliation",
        target_layer=TargetLayer.SILVER,
        datasets=(
            DatasetRef("nfe", DatasetClassification.HIGH_VOLUME, size_gb=4000),
            DatasetRef("clientes", DatasetClassification.SENSITIVE, pii_columns=("cpf",)),
        ),
        constraints=SignatureConstraints(
            no_pii_raw=True,
            merge_key_required=True,
            enforce_types=True,
            partition_by=("processing_date",),
            max_cost_dbu=50.0,
        ),
        execution_context=ExecutionContext("prod-v1.0", "catalog_2026", "dag_run_id"),
    )

    result = PolicyEngine().evaluate(signature)

    if result.is_blocked:
        raise ValueError(f"Governance BLOCKED: {result.reasoning}")

    if result.action.value == "replan":
        # Log the replan — CFA auto-applied corrective interventions
        for fault in result.faults:
            print(f"REPLAN: {fault.code} — {fault.message}")

    return result.action.value
```

---

## Airflow DAG Example

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime

def governance_gate(**kwargs):
    from cfa.policy.engine import PolicyEngine, StateSignature, TargetLayer
    # ... (use the pattern above)

def execute_pipeline(**kwargs):
    # Your actual pipeline code
    pass

with DAG(
    dag_id="cfa_governed_pipeline",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
) as dag:

    gate = PythonOperator(
        task_id="cfa_governance_gate",
        python_callable=governance_gate,
    )

    run = PythonOperator(
        task_id="execute_pipeline",
        python_callable=execute_pipeline,
    )

    gate >> run
```

---

## Using a Policy Bundle

```python
from cfa.policy import PolicyEngine

engine = PolicyEngine.from_bundle("policies/prod-v1.yaml")
result = engine.evaluate(signature)
```

---

## CI/CD Integration

```bash
cfa evaluate "Join NFe with Clientes persist Silver" \
    --catalog catalog.json \
    --policy-bundle policies/prod-v1.yaml \
    --exit-code
```

Exit code 1 if BLOCKED. Suitable for GitHub Actions, GitLab CI, etc.

---

## What the Gate Catches

| Issue | Fault Code |
|-------|-----------|
| Raw PII in Silver/Gold | `GOVERNANCE_RAW_PII_IN_PROTECTED_LAYER` |
| Missing merge key | `CONTRACT_MERGE_KEY_REQUIRED` |
| High volume without partition | `FINOPS_MISSING_PREDICATE` |
| Sensitive data without partition | `GOVERNANCE_SENSITIVE_WITHOUT_PARTITION` |
| Type enforcement disabled | `GOVERNANCE_TYPE_ENFORCEMENT_DISABLED` |
| Cost ceiling exceeded | `FINOPS_COST_BUDGET_EXCEEDED` |

---

## What This Is Not

- Not the full CFA kernel
- Not a replacement for orchestration
- Not an Airflow provider package

It is a **validation wedge** — the smallest useful CFA surface for real-world adoption.
