# CFA Usage Guide

This guide focuses on the repository implementation, not the GitHub Pages site. It assumes the code in [`src/cfa`](../src/cfa) as the source of truth.

## What was verified

The examples and guide were checked against the current implementation with these practical outcomes:

| Item | Status | Notes |
| --- | --- | --- |
| Test suite | Verified | `pytest -q` passes |
| `standalone_resolution.py` | Verified | Runs successfully directly from the repository checkout |
| `standalone_lifecycle.py` | Verified | Runs successfully directly from the repository checkout |
| `standalone_governance.py` | API-aligned | Requires Python 3.11+ because `codegen.py` uses `match` |
| `full_pipeline.py` | API-aligned | Requires Python 3.11+ for the same reason |

The repository metadata already declares `requires-python = ">=3.11"` in [`pyproject.toml`](../pyproject.toml), so the environment mismatch is local rather than architectural.

## Setup

Requirements:

- Python 3.11+

Recommended install:

```bash
pip install -e .[dev]
```

Run tests:

```bash
pytest -q
```

Run examples from a repository checkout:

```bash
python examples/standalone_resolution.py
python examples/standalone_lifecycle.py
python examples/standalone_governance.py
python examples/full_pipeline.py
```

The examples bootstrap `src` automatically, so editable install is recommended but not strictly required for local exploration.

## Architecture map

The implementation is organized around three standalone surfaces and one full orchestrator:

| Surface | Main purpose | Depends on |
| --- | --- | --- |
| `cfa.governance` | Policy checks and validation before execution | No LLM required |
| `cfa.resolution` | Natural-language intent resolution into typed contracts | A normalizer backend |
| `cfa.lifecycle` | Quantitative evaluation of recurring flows | Execution history |
| `KernelOrchestrator` | End-to-end governed execution flow | All of the above plus execution components |

## 1. Governance only

Use `cfa.governance` when you already have a pipeline and want a formal decision gate before execution.

```python
from cfa.governance import (
    PolicyEngine,
    StateSignature,
    TargetLayer,
    DatasetRef,
    DatasetClassification,
    SignatureConstraints,
    ExecutionContext,
)

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
    execution_context=ExecutionContext("v1.0", "catalog_2026", "ctx_1"),
)

engine = PolicyEngine()
result = engine.evaluate(signature)

if result.is_blocked:
    raise RuntimeError(result.reasoning)
```

Typical fit:

- Airflow or Dagster pipelines that already exist
- scripts that materialize data into governed layers
- systems that need policy gates before human or automated execution

### Built-in policy coverage

| Rule family | Purpose |
| --- | --- |
| PII protection | Blocks or replans unsafe handling of protected fields |
| Merge-key enforcement | Requires merge semantics in protected layers |
| Partition requirements | Pushes high-volume and sensitive flows toward partition-aware execution |
| Type enforcement | Prevents protected-layer execution without explicit typing intent |
| Cost ceiling checks | Prevents invalid or missing cost guardrails |

### Static validation

`StaticValidator` can inspect generated code before runtime:

```python
from cfa.governance import StaticValidator
from cfa.codegen import GeneratedCode

validator = StaticValidator()
generated = GeneratedCode(
    plan_signature_hash="demo",
    intent_id="demo",
    language="pyspark",
    code="df.collect()",
)

result = validator.validate(generated, signature)
print(result.passed, result.fault_codes)
```

## 2. Resolution only

Use `cfa.resolution` when the main problem is semantic interpretation: turning natural-language requests into a stable contract before any operational decision.

```python
from cfa.resolution import IntentNormalizer, MockNormalizerBackend

catalog = {
    "datasets": {
        "nfe": {
            "classification": "high_volume",
            "size_gb": 4000,
            "pii_columns": [],
            "partition_column": "processing_date",
        },
        "clientes": {
            "classification": "sensitive",
            "size_gb": 0.5,
            "pii_columns": ["cpf", "email"],
        },
    }
}

normalizer = IntentNormalizer(backend=MockNormalizerBackend())
resolution = normalizer.normalize(
    raw_intent="Join NFe with Clientes and persist to Silver",
    environment_state={},
    catalog=catalog,
)

print(resolution.signature.domain)
print(resolution.signature.target_layer.value)
print(resolution.confidence_score)
print(resolution.confirmation_mode.value)
```

What comes out of resolution:

- a typed `StateSignature`
- a confidence score
- an ambiguity level
- a confirmation mode
- optional competing interpretations
- environment constraints injected from current state

### Confirmation modes

The `ConfirmationOrchestrator` decides whether the request can proceed automatically or should be escalated.

| Typical condition | Outcome |
| --- | --- |
| High confidence, low ambiguity, no protected risk | `AUTO` |
| Medium confidence | `SOFT` |
| Protected data in a sensitive target | `HARD` |
| Very low confidence or severe ambiguity | `HUMAN_ESCALATION` |

The repository includes `AutoApproveHandler` and `AutoRejectHandler` for deterministic flows and tests.

## 3. Lifecycle only

Use `cfa.lifecycle` when you already have repeated executions and want evidence-based promotion, watchlisting, demotion, or retirement.

```python
from datetime import datetime, timezone
from cfa.lifecycle import PromotionEngine, PromotionPolicy, ExecutionRecord

engine = PromotionEngine(policy=PromotionPolicy(min_executions=3))

engine.record_execution(
    ExecutionRecord(
        signature_hash="fiscal_reconciliation_silver_abc123",
        timestamp=datetime.now(timezone.utc),
        success=True,
        cost_dbu=5.0,
        duration_seconds=30.0,
    )
)

skill, scores = engine.evaluate("fiscal_reconciliation_silver_abc123")
print(skill.state.value)
print(scores.ifo, scores.ifs, scores.ifg, scores.idi)
```

### The four indices

| Index | What it measures |
| --- | --- |
| IFo | Operational fluidity: latency, cost, success |
| IFs | Semantic fidelity: drift and fault health |
| IFg | Governance integrity: whether execution stayed within governance boundaries |
| IDI | Intent drift over the active evaluation window |

### Promotion and demotion

Promotion requires enough executions plus thresholds from `PromotionPolicy`.

Demotion can be triggered by:

- severe drift
- governance violations
- sustained degradation while on the watchlist
- prolonged inactivity
- catalog incompatibility through explicit retirement

The implementation also supports mass demotion by system version:

```python
engine.demote_by_system_version("cfa_v2.0", "Promotion logic regression")
```

## 4. Full kernel

Use `KernelOrchestrator` when you need the entire governed flow from natural language to execution outcome.

```python
from cfa import KernelOrchestrator, KernelConfig

catalog = {
    "datasets": {
        "nfe": {
            "classification": "high_volume",
            "size_gb": 4000,
            "partition_column": "processing_date",
        },
        "clientes": {
            "classification": "sensitive",
            "size_gb": 0.5,
            "pii_columns": ["cpf", "email"],
        },
    }
}

kernel = KernelOrchestrator(
    catalog=catalog,
    config=KernelConfig(
        enable_planning=True,
        enable_codegen=True,
        enable_static_validation=True,
        enable_sandbox=True,
        enable_promotion=True,
    ),
)

result = kernel.process("Join NFe with Clientes and persist to Silver")
print(result.state.value)
```

### Kernel phases

```text
context registry -> normalization -> confirmation -> policy
-> planning -> code generation -> static validation
-> sandbox execution -> runtime validation -> partial execution
-> state projection -> audit -> lifecycle evaluation
```

### Partial execution behavior

The implementation includes:

- retry policy via `RetryPolicy`
- failure policy via `FailurePolicy`
- terminal publish states such as quarantine and rollback handling

The execution path records history into lifecycle scoring for approved and non-approved terminal states, which keeps the operational record more honest than a success-only ledger.

## Integration patterns

### Existing orchestrator

```python
from cfa.governance import PolicyEngine, StateSignature

def validate_before_run(signature_dict: dict) -> None:
    result = PolicyEngine().evaluate(StateSignature(**signature_dict))
    if result.is_blocked:
        raise RuntimeError(result.reasoning)
```

### Runtime-generated requests

```python
from cfa import KernelOrchestrator

kernel = KernelOrchestrator(catalog=my_catalog)
result = kernel.process(user_request)

if result.state.value == "approved":
    print("Execution completed under governed flow")
else:
    print(result.blocked_reason or result.state.value)
```

## Pointers

- [README](../README.md)
- [Examples](../examples/)
- [Issue templates](../.github/ISSUE_TEMPLATE/)
- [Pull request template](../.github/PULL_REQUEST_TEMPLATE.md)
