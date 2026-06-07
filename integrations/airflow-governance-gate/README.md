# Airflow Governance Gate

This integration package is intentionally separate from the CFA core.

Its goal is simple: validate whether `cfa.governance` can deliver immediate value inside an existing Airflow pipeline without requiring a full CFA rollout.

## What this integration is testing

The hypothesis is:

> a data team can add a governance gate before pipeline execution in a small amount of code and receive a useful `APPROVE`, `REPLAN`, or `BLOCK` decision.

This is the smallest realistic adoption wedge for CFA because it does not require:

- an LLM
- a semantic normalizer
- a planner
- generated code
- sandbox execution
- a full kernel migration

It only requires that the pipeline can describe what it is about to do through a `StateSignature`.

## Folder contents

```text
integrations/airflow-governance-gate/
  README.md
  requirements.txt
  dags/
    cfa_governance_gate_demo.py
  src/
    governance_gate.py
```

## Minimal idea

In a traditional DAG, a task goes straight to execution.

With this integration, the flow becomes:

```text
build StateSignature -> evaluate PolicyEngine -> continue or fail fast
```

## Example decision contract

The policy gate can catch issues such as:

- protected-layer writes with raw PII
- high-volume processing without partition constraints
- protected-layer writes without merge-key enforcement
- invalid cost guardrails

## How to use

### 1. Install dependencies

Inside an Airflow environment, install CFA and this integration's requirements:

```bash
pip install -e .
pip install -r integrations/airflow-governance-gate/requirements.txt
```

### 2. Copy or adapt the helper

See:

- [`src/governance_gate.py`](./src/governance_gate.py)

It exposes a minimal helper that:

- builds a `StateSignature`
- evaluates `PolicyEngine`
- returns the policy result
- raises a clear exception for blocked execution if desired

The helper intentionally imports only the narrow policy and type modules it
needs. That keeps the Airflow wedge decoupled from the broader execution path.

### 3. Use the DAG example

See:

- [`dags/cfa_governance_gate_demo.py`](./dags/cfa_governance_gate_demo.py)

The demo shows a simple Airflow flow where governance runs before the execution task.

## Copy-paste usage

If you want the smallest useful pattern, it is essentially this:

```python
from governance_gate import GovernanceRequest, assert_allowed

result = assert_allowed(
    GovernanceRequest(
        domain="fiscal",
        intent="reconciliation",
        target_layer="silver",
        datasets=(
            {"name": "nfe", "classification": "high_volume", "size_gb": 4000},
            {"name": "clientes", "classification": "sensitive", "pii_columns": ["cpf"]},
        ),
        no_pii_raw=True,
        merge_key_required=True,
        enforce_types=True,
        partition_by=("processing_date",),
    )
)

print(result.action.value)
```

## What success looks like

This integration is successful if an external user can:

1. understand the example quickly
2. adapt it to an existing DAG without deep CFA knowledge
3. get a useful decision before execution
4. describe at least one real case where the gate prevented an unsafe run

## What this is not

This integration is not:

- the full CFA kernel
- a replacement for orchestration
- an Airflow provider package
- a production-ready deployment bundle

It is a validation wedge for real-world adoption.
