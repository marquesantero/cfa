# CFA v0.1.9

[![CI](https://github.com/marquesantero/cfa/actions/workflows/ci.yml/badge.svg)](https://github.com/marquesantero/cfa/actions/workflows/ci.yml)
[![codecov](https://codecov.io/github/marquesantero/cfa/graph/badge.svg?token=P5NFQBZGYT)](https://codecov.io/github/marquesantero/cfa)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Tests](https://img.shields.io/badge/tests-536%20passed-brightgreen)](https://github.com/marquesantero/cfa/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/cfa-kernel)](https://pypi.org/project/cfa-kernel/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Docs](https://img.shields.io/badge/docs-docusaurus-blue.svg)](https://marquesantero.github.io/cfa/)

**Governed execution for AI agents and data systems.**

Instead of asking _"which agent or skill should act?"_, CFA asks _"which state transition is being requested, under which constraints, and can it be executed safely?"_ and produces a cryptographically verifiable decision.

## Quick Start

```bash
pip install cfa-kernel
# or: pip install git+https://github.com/marquesantero/cfa.git
cfa init
cfa evaluate "Join NFe with Clientes and persist to Silver" --catalog .cfa/catalog.json
```

## What CFA does

| Step | What happens |
|------|-------------|
| **Formalize** | Natural language or JSON → typed `StateSignature` contract |
| **Govern** | Policy Engine evaluates PII, cost, schema, partition constraints |
| **Generate** | Execution planner + deterministic code generation (PySpark, SQL, dbt) |
| **Execute** | Pluggable sandbox with metrics collection + runtime validation |
| **Validate** | State projection, SHA-256 audit trail, lifecycle indices |

## Surfaces

All interfaces are backend-agnostic. CFA evaluates a `StateSignature` contract — however it was produced.

| Surface | For | Example |
|---------|-----|---------|
| `cfa` CLI | Everyone | `cfa policy check --signature sig.json` |
| `cfa catalog` CLI | Data platform teams | `cfa catalog validate catalog.json` |
| `cfa policy` CLI | Security/compliance | `cfa policy validate policies/prod.yaml` |
| `cfa storage` CLI | Operations | `cfa storage stats --db cfa.db` |
| `cfa lifecycle` CLI | Platform teams | `cfa lifecycle evaluate --db cfa.db` |
| `cfa signature` CLI | External systems | `cfa signature validate request.json` |
| `cfa.testing` | CI/CD | `evaluate("intent", catalog=catalog)` with pytest |
| `cfa.runtime` | Production | `RuntimeGate` as decorator/context-manager |
| `cfa.mcp` | AI agents | MCP server for any MCP-compatible client |
| `cfa.adapters` | AI frameworks | LangGraph, OpenAI Agents, CrewAI, AutoGen, DSPy |

## Architecture

```text
CLI / MCP / Adapter / API
        │
        ▼
   ┌─ Formalize ──┐   NL / JSON / Tool call → typed StateSignature contract
   ├─ Govern ──────┤   Policy check + REPLAN cycle (approve / replan / block)
   ├─ Generate ────┤   Plan + code (PySpark / SQL / dbt) + static validation
   ├─ Execute ─────┤   Pluggable sandbox + runtime validation
   └─ Validate ────┘   State projection + SHA-256 audit + lifecycle indices
                           │
                           ▼
            Decision JSON / Audit Trail / OTel / Prometheus
```

## Key Differentiators

| Feature | CFA | Others |
|---------|-----|--------|
| SHA-256 audit trail (tamper-evident) | ✅ | ❌ |
| State projection between executions | ✅ | ❌ |
| Lifecycle indices (IFo/IFs/IFg/IDI) | ✅ | ❌ |
| REPLAN with auto-interventions | ✅ | ❌ |
| Backend-agnostic (PySpark, SQL, dbt) | ✅ | ❌ |
| Artifact hashing (catalog + policy + signature) | ✅ | ❌ |
| MCP protocol for AI agents | ✅ | ❌ |
| SQLite storage with retention management | ✅ | ❌ |
| Config file with auto-discovery | ✅ | ❌ |
| Zero runtime dependencies (core) | ✅ | ❌ |

## CLI

```bash
# Governance & evaluation
cfa evaluate "intent" --catalog catalog.json --strict
cfa policy check --signature signature.json --policy-bundle policies/prod.yaml
cfa policy check --signature sig.json --catalog cat.json --strict --audit-log audit.jsonl

# Validation (CI-ready with JSON output and exit codes)
cfa catalog validate catalog.json --require-datasets --format json
cfa signature validate signature.json --format json
cfa policy validate policies/prod.yaml --format json

# Audit & verification
cfa audit show --id INTENT_ID --file audit.jsonl --format json
cfa audit verify --file audit.jsonl

# Policy rules
cfa rules list
cfa rules explain FAULT_CODE

# Storage management
cfa storage stats --db cfa.db --format json
cfa storage cleanup --db cfa.db --retention 90
cfa storage vacuum --db cfa.db

# Lifecycle management
cfa lifecycle evaluate --db cfa.db --window 30
cfa lifecycle list --db cfa.db

# Project health
cfa status --format json

# Bootstrap
cfa init

# Backends
cfa backend list
```

## From Python

```python
from cfa.testing import evaluate, assert_passed

result = evaluate(
    "Join NFe with Clientes and persist to Silver",
    catalog=MY_CATALOG,
    policy_rules=my_rules,
    backend="pyspark",
)
assert_passed(result)
```

### Policy check with audit

```python
from cfa.policy.engine import PolicyEngine
from cfa.types import StateSignature

signature = StateSignature.from_dict(signature_dict)
engine = PolicyEngine(policy_bundle_version="prod-v1.0")
result = engine.evaluate(signature)
# result.action → approve / replan / block
```

### Runtime gate

```python
from cfa.runtime import RuntimeGate, GateConfig

gate = RuntimeGate(
    config=GateConfig(policy_bundle="prod_v1.0", sandbox="mock"),
    catalog=PROD_CATALOG,
)

@gate.guard("aggregate sales with PII protected")
def my_pipeline():
    ...
```

### SQLite storage

```python
from cfa.storage import SqliteStorage

store = SqliteStorage("cfa.db")
store.ensure_schema()

# Audit
store.audit_append(event)

# Execution records (lifecycle)
store.execution_append(record_dict)

# Lifecycle skills
store.skill_upsert("hash_a", skill_data)
```

## Policy Bundles

Declarative YAML policy rules — separate governance from code:

```yaml
# policies/prod-v1.yaml
policy_bundle:
  version: "prod-v1.0"
  rules:
    - name: forbid_raw_pii
      condition: pii_in_protected_layer
      action: block
      fault_code: GOVERNANCE_RAW_PII
      severity: critical
      message: "PII in protected layer without anonymization."
      remediation:
        - "Apply sha256 on PII columns before the operation"
```

Validated at load time — unknown conditions, duplicate fault codes, and invalid enums are caught immediately.

## Config File

```yaml
# cfa.yaml (auto-discovered by all commands)
version: "1.0"
storage:
  backend: sqlite
  path: cfa.db
  retention_days: 90
defaults:
  catalog: .cfa/catalog.json
  policy_bundle: .cfa/policies/prod-v1.yaml
  backend: pyspark
```

## Backends

Three governed code generation backends, all pluggable via `BackendRegistry`:

| Backend | Language | Features |
|---------|----------|----------|
| `pyspark` | PySpark + Delta Lake | Merge, partition overwrite, PII anonymization |
| `sql` | ANSI SQL | MERGE INTO, INSERT OVERWRITE, partition clauses |
| `dbt` | dbt models + schema.yml | Config blocks, refs, not_null/unique tests, PII annotations |

Each backend declares its own forbidden tokens for static validation.

## MCP Server

Expose CFA governance to any AI agent via Model Context Protocol:

```json
{
  "mcpServers": {
    "cfa": {
      "command": "python",
      "args": ["-m", "cfa.mcp"]
    }
  }
}
```

5 tools: `cfa_evaluate_signature`, `cfa_describe_rules`, `cfa_explain_fault`, `cfa_audit_check`, `cfa_list_backends`.

## Repository

```text
src/cfa/
├── core/              Kernel, Planner, CodeGen, Conditions, Phases
├── policy/            PolicyEngine, PolicyBundle, Catalog validation
├── validation/        Static, Runtime, Signature validation
├── audit/             AuditTrail, Context, Hashing
├── observability/     Metrics, OTel, Notify, Indices, Promotion
├── normalizer/        Rule-based normalizer, LLM normalizer
├── execution/         Partial execution, State projection
├── adapters/          LangGraph, OpenAI, CrewAI, AutoGen, DSPy
├── backends/          PySpark, SQL, dbt (pluggable)
├── sandbox/           Pluggable sandbox backend + registry + executor
├── cli/               CLI commands by family (core/, governance/, reporting/, project/, infrastructure/)
├── storage/           SQLite + JSONL backends (stats, cleanup, vacuum)
├── mcp/               MCP server (JSON-RPC over stdio)
├── reporting/         HTML reports
├── runtime/           Production governance gate
├── testing/           pytest-native evaluate() + fixtures
├── config.py          CFA config (discovery, defaults)
├── types.py           StateSignature, Fault, KernelResult
└── _lazy.py           Reusable lazy loader for package __init__
```

## Docs

All documentation at **[marquesantero.github.io/cfa](https://marquesantero.github.io/cfa/)**:

- [Getting Started](https://marquesantero.github.io/cfa/docs/getting-started)
- [CLI Reference](https://marquesantero.github.io/cfa/docs/cli)
- [Policy Bundles](https://marquesantero.github.io/cfa/docs/policy-bundles)
- [Backends](https://marquesantero.github.io/cfa/docs/backends)
- [MCP Server](https://marquesantero.github.io/cfa/docs/mcp-server)
- [Reporting](https://marquesantero.github.io/cfa/docs/reporting)
- [Architecture Notes](https://marquesantero.github.io/cfa/docs/architecture-notes)
- [FAQ](https://marquesantero.github.io/cfa/docs/faq)

## License

[MIT](./LICENSE) · [Antero Marques](https://github.com/marquesantero)
