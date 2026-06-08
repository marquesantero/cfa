# CFA — Contextual Flux Architecture

[![CI](https://github.com/marquesantero/cfa/actions/workflows/ci.yml/badge.svg)](https://github.com/marquesantero/cfa/actions/workflows/ci.yml)
[![codecov](https://codecov.io/github/marquesantero/cfa/graph/badge.svg?token=P5NFQBZGYT)](https://codecov.io/github/marquesantero/cfa)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Tests](https://img.shields.io/badge/tests-536%20passed-brightgreen)](https://github.com/marquesantero/cfa/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/cfa-kernel)](https://pypi.org/project/cfa-kernel/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Docs](https://img.shields.io/badge/docs-docusaurus-blue.svg)](https://marquesantero.github.io/cfa/)

**A typed, pre-execution governance gate for AI agents and data pipelines.**

You declare what you intend to do as a `StateSignature`. CFA answers
`approve`, `replan(remediations)`, or `block(reason)` — deterministically —
in **under 3 ms p99** on a warm kernel, and writes the decision into a
SHA-256 hash chain you can verify offline with `cfa audit verify`. No
network. No server. No keys.

## Why CFA exists

Six things CFA does today that no adjacent tool gives you together:

1. **Structured remediation, not just yes/no.** When a fixable rule fails,
   CFA returns the fix as data. The caller — an LLM agent, a CI step, a
   human — applies it and retries. The recovery loop is part of the
   contract, bounded at three attempts, and audited.
   ```json
   { "action": "replan",
     "faults": [{"code": "GOVERNANCE_RAW_PII_IN_PROTECTED_LAYER", ...}],
     "interventions": [
       "Set constraints.no_pii_raw=True",
       "Apply sha256() on PII columns before the join"
     ]
   }
   ```

2. **Offline-verifiable audit chain.** Every decision is a
   content-hashed event linked into a SHA-256 chain. `cfa audit verify`
   replays the chain on any host that has the JSONL file. No vendor, no
   server, no API key.
   ```bash
   $ cfa audit verify --file audit.jsonl
   OK · 1 274 events verified · last_hash=a4f3…6c01
   ```

3. **Dataset-aware policy primitives baked in.** PII columns,
   partitioning, classification, merge keys, target layer — these are
   first-class primitives, not metadata you re-encode in Rego. A typical
   rule fits in six YAML lines:
   ```yaml
   - name: forbid_raw_pii
     condition: pii_in_protected_layer
     action: block
     fault_code: GOVERNANCE_RAW_PII
     severity: critical
     remediation: ["Apply sha256() on PII columns before the write"]
   ```

4. **One signature, three production backends.** The same approved
   `StateSignature` compiles to PySpark + Delta Lake, ANSI SQL with
   `MERGE INTO`, or dbt models with `schema.yml`. Each backend declares
   its own forbidden tokens for static validation. New backends register
   through `BackendRegistry` without touching the kernel.

5. **MCP server, working today.** Any MCP-compatible agent (Claude
   Desktop, Cursor, Continue, custom LangGraph nodes) calls CFA before
   it touches production data. Five tools: `cfa_evaluate_signature`,
   `cfa_describe_rules`, `cfa_explain_fault`, `cfa_audit_check`,
   `cfa_list_backends`.

6. **Deterministic by default; LLM is opt-in.** The decision path is a
   pure function of `(signature, policy_bundle, catalog)`. Same inputs
   produce the same decision and the same hash, every time, with no
   network call. LLMs participate only on the front edge (intent →
   signature) and only if you ask for them via the `[llm]` extra.

Each of these is a recorded
[Architecture Decision Record](docs/adr/). The reasoning, the
alternatives we rejected, and the boundaries are written down.

## Quick start

```bash
pip install cfa-kernel
cfa init
cfa evaluate "Join NFe with Clientes and persist to Silver" \
  --catalog .cfa/catalog.json
```

For a real CI gate, the four-line decorator form:

```python
from cfa.adapters import cfa_guard

@cfa_guard("Join NFe with Clientes anonymize CPF persist Silver",
           policy_bundle="policies/prod-v1.yaml", catalog=CATALOG)
def my_pipeline(): ...
```

The decorator caches a single `KernelOrchestrator` per guard and adds
~2.4 ms p99 to your call. Production-friendly.

## Where CFA pairs (instead of replacing)

CFA is **not** an LLM observability tool, a generic policy engine, a
data catalog, or a data-quality-at-rest tool. Pair with LangSmith /
Phoenix / Patronus, OPA, Unity Catalog / Atlan / DataHub, and Great
Expectations / Soda respectively. The [Compare](https://marquesantero.github.io/cfa/docs/compare)
page has the side-by-side breakdowns.

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
| `cfa.adapters` | Any framework | Universal `cfa_guard` decorator (LangGraph, CrewAI, AutoGen, DSPy, OpenAI Agents SDK) |

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

The full plan lives in [`drafts/ROADMAP.md`](drafts/ROADMAP.md). The short
version:

- **1.1.0 (current)** — distinctive primitives recorded as ADRs, package
  layout consolidated, perf baselines landed, site rewritten.
- **1.2.0 (next)** — `cfa dbt check` reads `target/manifest.json`,
  derives a signature per model, runs the policy bundle in CI.
- **1.3.0** — Airflow `CFAGateOperator` (provider package).
- **1.4.0** — Lifecycle indices (IFo/IFs/IFg/IDI) produtized as a
  promotion/demotion dashboard.
- **1.5.0** — MCP server positioned as a governance authority for LLM
  agents, with a reference implementation.
- **1.6.0** — Snowflake, BigQuery, and Iceberg backends.
- **2.0.0** — semver-strict API freeze, third-party security audit,
  cross-language SDKs.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for development setup, test conventions, and the PR checklist. By participating, you agree to the [Code of Conduct](./CODE_OF_CONDUCT.md). Security issues: see [SECURITY.md](./SECURITY.md).

## License

[MIT](./LICENSE) · [Antero Marques](https://github.com/marquesantero)
