# CFA — Contextual Flux Architecture

[![CI](https://github.com/marquesantero/cfa/actions/workflows/ci.yml/badge.svg)](https://github.com/marquesantero/cfa/actions/workflows/ci.yml)
[![codecov](https://codecov.io/github/marquesantero/cfa/graph/badge.svg?token=P5NFQBZGYT)](https://codecov.io/github/marquesantero/cfa)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Tests](https://img.shields.io/badge/tests-535%20passed-brightgreen)](https://github.com/marquesantero/cfa/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/cfa-kernel)](https://pypi.org/project/cfa-kernel/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Docs](https://img.shields.io/badge/docs-docusaurus-blue.svg)](https://marquesantero.github.io/cfa/)

**A typed, pre-execution governance gate for AI agents and data pipelines.**

You declare what you intend to do as a `StateSignature`. CFA answers `approve`, `replan(remediations)`, or `block(reason)` — deterministically — and writes the decision into a SHA-256 hash chain you can verify offline.

> **Status:** the `1.0.0` API freeze shipped early. We are entering a focused `1.1.0` cycle: editorial cuts, package consolidation, deprecation shims for everything that will leave in `2.0.0`. See the [roadmap](drafts/ROADMAP.md).

## What CFA is

A small, deterministic library that sits between *whoever asked for a governed write* (a human, an LLM agent, an orchestrator) and *whatever runs the write* (PySpark, SQL, dbt, anything). Three outcomes per request:

- **`approve`** — the intent passes every rule. Return the decision; let the caller proceed.
- **`replan(remediations)`** — the intent fails a fixable rule. Return a structured list of corrections the caller can apply and resubmit.
- **`block(reason)`** — the intent fails an unrecoverable rule. Return a typed fault with code, severity, and remediation hints.

Every decision is content-hashed and appended to a tamper-evident chain.

## What CFA is **not**

- **Not an LLM observability tool.** It runs before execution, not after. Use [LangSmith](https://www.langchain.com/langsmith), [Phoenix](https://phoenix.arize.com/), or [Patronus](https://www.patronus.ai/) for traces and eval.
- **Not a generic policy engine.** Use [OPA](https://www.openpolicyagent.org/) when you need generic policy-as-code with Rego across infra, APIs, and CI/CD. CFA wins only when the policies are dataset-aware (PII, partition, classification, merge key).
- **Not a data catalog.** Use [Unity Catalog](https://www.databricks.com/product/unity-catalog), [Atlan](https://atlan.com/), or [DataHub](https://datahubproject.io/) for discovery, lineage, and access control. CFA reads catalogs; it does not replace them.
- **Not a data-quality-at-rest tool.** Use [Great Expectations](https://greatexpectations.io/) or [Soda](https://www.soda.io/) when you need expectations on data already written. CFA decides *before* the write.

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

## Capabilities

| Capability | What it gives you |
|------------|-------------------|
| SHA-256 audit trail | Tamper-evident chain of decisions, verifiable offline (`cfa audit verify`) |
| State projection | Each execution carries the typed state of the prior one — no implicit globals |
| Lifecycle indices (IFo/IFs/IFg/IDI) | Quantifies how often an intent recurs, stabilizes, and qualifies for promotion to a reusable skill |
| REPLAN cycle | Failed policy checks emit a structured remediation, not a hard stop |
| Backend-agnostic codegen | Same signature compiles to PySpark, ANSI SQL, or dbt — pluggable via `BackendRegistry` |
| Artifact hashing | Catalog, policy bundle, and signature are content-hashed and bound to every decision |
| MCP protocol | Any MCP-compatible agent can call CFA as a governance tool |
| SQLite + JSONL storage | First-class persistence with stats, retention cleanup, and vacuum |
| Config auto-discovery | `cfa.yaml` walked up the tree; all CLI commands respect it |
| Zero core dependencies | Optional extras for `yaml`, `otel`, `mcp`, `llm` — none required for the kernel |

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
├── policy/            PolicyEngine, PolicyBundle, catalog validation, standalone-governance surface
├── resolve/           Intent → StateSignature (rule-based + LLM backends, confirmation orchestrator)
├── validate/          Static, runtime, and signature validation
├── obs/               Metrics, OTel, Notify, Indices, Promotion
├── behavior/          BehaviorSpec + Systematizer (human intent → policy rules)
├── audit/             AuditTrail, Context, Hashing
├── lifecycle/         IFo/IFs/IFg/IDI indices + Promotion/Demotion engine
├── execution/         Partial execution, State projection
├── adapters/          Universal cfa_guard decorator for any framework
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

> The 1.1.0 cycle consolidated five packages from the 1.0.0 layout: `governance` → `policy`, `validation` → `validate`, `observability` → `obs`, `normalizer` + `resolution` → `resolve`. `adapters/` lost the per-framework shim files (langgraph/crewai/autogen/dspy/openai_agents) in favor of a single universal decorator.

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

## Demos

Two complete notebooks, tested on Databricks with CFA 1.0.0, 0 errors:

| File | Format | Description |
|------|--------|-------------|
| `demos/cfa_demo_complete` | `.dbc` / `.py` | Rule-based governance — APPROVE, REPLAN, BLOCK, codegen, audit, storage |
| `demos/cfa_llm_demo_complete` | `.dbc` / `.py` | LLM-powered — semantic normalizer, systematizer, strict mode, compare |

Import the `.dbc` into Databricks or run the `.py` files anywhere.

## Roadmap

The active plan is in [`drafts/ROADMAP.md`](drafts/ROADMAP.md). The short version:

- **1.1.0 (next)** — editorial focus. Package consolidation. Deprecation shims for per-framework adapters (`cfa.adapters.langgraph` and friends). Site rewrite. No new features.
- **1.2.0** — first real integration. `cfa dbt check` reads `target/manifest.json`, derives a signature for each model, runs the policy bundle.
- **1.3.0** — Airflow `CFAGateOperator` (provider package).
- **1.4.0** — Lifecycle indices (IFo/IFs/IFg/IDI) documented and produtized.
- **1.5.0** — MCP server as a governance authority for LLM agents.
- **1.6.0** — Extra backends (Snowflake, BigQuery, Iceberg).
- **2.0.0** — re-stabilized API, removal of 1.x deprecation shims, third-party security audit.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for development setup, test conventions, and the PR checklist. By participating, you agree to the [Code of Conduct](./CODE_OF_CONDUCT.md). Security issues: see [SECURITY.md](./SECURITY.md).

## License

[MIT](./LICENSE) · [Antero Marques](https://github.com/marquesantero)
