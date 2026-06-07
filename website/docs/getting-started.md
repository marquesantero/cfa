---
sidebar_position: 2
---

# Getting Started

Install CFA and run your first governance check in under 5 minutes.

## Prerequisites

- Python 3.11 or later
- pip

## Installation

```bash
pip install cfa-kernel
# or directly from GitHub:
# pip install git+https://github.com/marquesantero/cfa.git
```

Optional features:

```bash
pip install cfa-kernel[yaml]       # YAML policy bundles
pip install cfa-kernel[llm]        # LLM-powered intent normalization (OpenAI)
pip install cfa-kernel[otel]       # OpenTelemetry tracing
pip install cfa-kernel[mcp]        # MCP server protocol
pip install cfa-kernel[all]        # Everything
```

## Initialize a project

```bash
cfa init
```

Creates `.cfa/` with:

```text
.cfa/
├── config.yaml              # CFA configuration
├── catalog.json             # Example data catalog
├── policies/
│   └── prod-v1.yaml         # Example policy bundle
└── .gitignore
```

## Your first governance check

### Via natural language

```bash
cfa evaluate "Join NFe with Clientes and persist to Silver" --catalog .cfa/catalog.json
```

### Via structured contract (recommended for CI/API)

```bash
cfa policy check --signature signature.json --policy-bundle .cfa/policies/prod-v1.yaml --format json
```

### With strict cross-validation

```bash
cfa policy check \
  --signature signature.json \
  --catalog .cfa/catalog.json \
  --policy-bundle .cfa/policies/prod-v1.yaml \
  --strict \
  --audit-log audit.jsonl \
  --exit-code
```

## Validating artifacts

```bash
# Validate a catalog
cfa catalog validate .cfa/catalog.json --require-datasets --format json

# Validate a policy bundle
cfa policy validate .cfa/policies/prod-v1.yaml --format json

# Validate a signature
cfa signature validate request.json --require-datasets --format json
```

All validation commands return exit code 1 on failure — ready for CI pipelines.

## Audit trail

```bash
# Verify chain integrity
cfa audit verify --file audit.jsonl

# Show events for an intent
cfa audit show --id <intent_id> --file audit.jsonl --format json
```

## Storage management

```bash
# Check storage stats
cfa storage stats --db cfa.db

# Clean up records older than retention
cfa storage cleanup --db cfa.db --retention 90

# Compact SQLite database
cfa storage vacuum --db cfa.db
```

## Using from Python

```python
from cfa.testing import evaluate, assert_passed

result = evaluate(
    "Join NFe with Clientes and persist to Silver",
    catalog=MY_CATALOG,
    backend="pyspark",
)
assert_passed(result)
```

### Runtime gate

```python
from cfa.runtime import RuntimeGate, GateConfig

gate = RuntimeGate(
    config=GateConfig(policy_bundle="prod_v1.0"),
    catalog=PROD_CATALOG,
)

# Pre-execution validation
result = gate.validate("aggregate sales with PII protected")

# Decorator guard
@gate.guard("aggregate sales")
def my_pipeline():
    ...
```

### Storage backend

```python
from cfa.storage import SqliteStorage

store = SqliteStorage("cfa.db")
store.ensure_schema()

# Record audit event
store.audit_append(event)

# Record execution for lifecycle tracking
store.execution_append(record_dict)

# Query lifecycle skills
skills = store.skill_load_all()
```

### Policy engine

```python
from cfa.policy.engine import PolicyEngine
from cfa.types import StateSignature

signature = StateSignature.from_dict(signature_dict)
engine = PolicyEngine(policy_bundle_version="prod-v1.0")
result = engine.evaluate(signature)
# result.action → approve / replan / block
```
