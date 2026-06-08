---
sidebar_position: 1
---

# Introduction

**A typed, pre-execution governance gate for AI agents and data pipelines.**

You declare what you intend to do as a `StateSignature`. CFA answers
`approve`, `replan(remediations)`, or `block(reason)` — deterministically —
in **under 3 ms p99** on a warm kernel, and writes the decision into a
SHA-256 hash chain you can verify offline with `cfa audit verify`. No
network. No server. No keys.

## Why CFA exists

Six things CFA does today that no adjacent tool gives you together:

### 1. Structured remediation, not just yes/no

When a fixable rule fails, CFA returns the fix as data. The caller — an
LLM agent, a CI step, a human — applies the remediation and retries.
The recovery loop is part of the contract, bounded at three attempts,
and recorded in the audit trail.

```json
{
  "action": "replan",
  "faults": [
    {
      "code": "GOVERNANCE_RAW_PII_IN_PROTECTED_LAYER",
      "severity": "critical",
      "message": "PII detected without treatment in write to protected layer."
    }
  ],
  "interventions": [
    "Set constraints.no_pii_raw=True",
    "Apply sha256() on PII columns before the join"
  ]
}
```

### 2. Offline-verifiable audit chain

Every decision is a content-hashed event linked into a SHA-256 chain.
`cfa audit verify` replays the chain on any host that has the JSONL
file — no vendor, no server, no API key, no network call.

```bash
$ cfa audit verify --file audit.jsonl
OK · 1 274 events verified · last_hash=a4f3…6c01
```

This is the kind of evidence a compliance reviewer can take home on a
flash drive and re-verify a year later.

### 3. Dataset-aware policy primitives baked in

PII columns, partitioning, classification, merge keys, target layer —
these are first-class primitives, not metadata you re-encode in Rego.
A typical rule fits in six YAML lines:

```yaml
- name: forbid_raw_pii
  condition: pii_in_protected_layer
  action: block
  fault_code: GOVERNANCE_RAW_PII
  severity: critical
  remediation:
    - "Apply sha256() on PII columns before the write"
```

The same primitives drive cost ceilings, partition enforcement on
high-volume datasets, merge-key requirements for Silver/Gold writes,
and schema contract enforcement.

### 4. One signature, three production backends

The same approved `StateSignature` compiles to **PySpark + Delta Lake**,
**ANSI SQL with `MERGE INTO`**, or **dbt models with `schema.yml`**.
Each backend declares its own forbidden tokens for static validation.
New backends register through `BackendRegistry` without touching the
kernel.

### 5. MCP server, working today

Any MCP-compatible agent (Claude Desktop, Cursor, Continue, custom
LangGraph nodes) calls CFA before it touches production data. Five
tools exposed:

- `cfa_evaluate_signature` — submit an intent, get a decision.
- `cfa_describe_rules` — list active policy rules.
- `cfa_explain_fault` — get remediation for a fault code.
- `cfa_audit_check` — verify the audit chain.
- `cfa_list_backends` — list registered codegen backends.

### 6. Deterministic by default; LLM is opt-in

The decision path is a pure function of `(signature, policy_bundle,
catalog)`. Same inputs produce the same decision and the same hash,
every time, with no network call. LLMs participate only on the front
edge (intent → signature) and only if you ask for them via the `[llm]`
extra. Compliance reviewers can replay every historical decision from
JSON.

Each of these is recorded as an
[Architecture Decision Record](https://github.com/marquesantero/cfa/tree/main/docs/adr).
The reasoning, the alternatives we rejected, and the boundaries are
written down.

## Quick install

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
~2.4 ms p99 to your call.

## Core concepts

### StateSignature

The universal contract. Any system — CLI, API, agent, orchestrator — can
produce one. It is content-hashed: same content always yields the same
hash.

```json
{
  "domain": "fiscal",
  "intent": "reconciliation",
  "target_layer": "silver",
  "datasets": [
    {
      "name": "nfe",
      "classification": "high_volume",
      "pii_columns": [],
      "merge_keys": ["nfe_id"]
    }
  ],
  "constraints": {
    "no_pii_raw": true,
    "merge_key_required": true,
    "partition_by": ["processing_date"]
  },
  "execution_context": {
    "policy_bundle_version": "prod-v1.0",
    "catalog_snapshot_version": "v1",
    "context_registry_version_id": "ctx1"
  }
}
```

### Policy bundle

Declarative YAML. No code required:

```yaml
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
        - "Apply sha256() on PII columns before the operation"
```

### Decision

Every decision is structured, versioned, and chained:

```json
{
  "schema_version": "cfa.policy_check.v1",
  "decision_id": "...",
  "signature_hash": "...",
  "catalog_hash": "...",
  "policy_bundle_hash": "...",
  "action": "block",
  "passed": false,
  "faults": [
    {
      "code": "GOVERNANCE_RAW_PII",
      "severity": "critical",
      "remediation": ["..."]
    }
  ],
  "audit_event_hash": "..."
}
```

The `audit_event_hash` chains into the previous event.

## Where CFA pairs (instead of replacing)

CFA is **not** an LLM observability tool, a generic policy engine, a
data catalog, or a data-quality-at-rest tool. Pair with
[LangSmith](https://www.langchain.com/langsmith) /
[Phoenix](https://phoenix.arize.com/) /
[Patronus](https://www.patronus.ai/),
[OPA](https://www.openpolicyagent.org/),
[Unity Catalog](https://www.databricks.com/product/unity-catalog) /
[Atlan](https://atlan.com/) /
[DataHub](https://datahubproject.io/), and
[Great Expectations](https://greatexpectations.io/) /
[Soda](https://www.soda.io/) respectively.

The [Compare](./compare) page has the side-by-side breakdowns.

## Where to go next

- **[Getting Started](./getting-started)** — install and run your first
  governance check.
- **[CLI Reference](./cli)** — every `cfa` command.
- **[Policy Bundles](./policy-bundles)** — declarative YAML policy rules.
- **[Backends](./backends)** — PySpark, SQL, dbt code generation.
- **[MCP Server](./mcp-server)** — expose CFA to AI agents.
- **[Use cfa_guard with any framework](./integrations/use-cfa-guard-with-frameworks)**
  — LangGraph, CrewAI, AutoGen, DSPy, OpenAI Agents SDK.
- **[Compare](./compare)** — CFA vs OPA, LangSmith, Great Expectations,
  Unity Catalog.
- **[Extending CFA](./extending)** — build your own vertical,
  integration, or DecisionSink as a separate pip package.
- **[Architecture Notes](./architecture-notes)** — design decisions and
  trade-offs.
- **[FAQ](./faq)**.
