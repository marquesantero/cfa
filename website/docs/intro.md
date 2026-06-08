---
sidebar_position: 1
---

# Introduction

CFA is a typed, pre-execution governance gate for AI agents and data pipelines.

You declare what you intend to do as a `StateSignature`. CFA answers
`approve`, `replan(remediations)`, or `block(reason)` — deterministically —
and writes the decision into a SHA-256 hash chain you can verify offline.

The current release on PyPI is `1.0.0`. The next release (`1.1.0`) is an
editorial cycle: cuts, consolidation, deprecation shims, and a rewritten
site — no new features. See the [roadmap](https://github.com/marquesantero/cfa/blob/main/drafts/ROADMAP.md).

## What CFA does

1. **Receives a contract.** A `StateSignature` (JSON, YAML, or natural
   language passed through a normalizer).
2. **Validates the contract.** Structure, enums, required fields.
3. **Cross-references the catalog.** Datasets must exist with matching
   metadata.
4. **Evaluates declarative policies.** PII, FinOps, merge keys, partitions,
   cost ceilings.
5. **Decides.** `approve` / `replan(remediations)` / `block(reason)`.
6. **Records an auditable decision.** SHA-256 hash chain plus artifact
   hashes for catalog, policy bundle, and signature.
7. **Tracks lifecycle health.** IFo, IFs, IFg, IDI indices per pipeline
   (covered in `docs/lifecycle-indices` once 1.4.0 lands).

## What CFA is **not**

- **Not an LLM observability tool.** It decides before execution, not after.
  Pair with LangSmith, Phoenix, or Patronus for traces and eval.
- **Not a generic policy engine.** Pair with OPA when you need policy-as-code
  across infra, APIs, and CI/CD. CFA wins when the policies are
  dataset-aware (PII, partition, classification, merge key).
- **Not a data catalog.** Pair with Unity Catalog, Atlan, or DataHub for
  discovery, lineage, and access control. CFA reads catalogs; it does not
  replace them.
- **Not a data-quality-at-rest tool.** Pair with Great Expectations or Soda
  for expectations on already-written data. CFA decides before the write.

See [Compare](./compare) for side-by-side breakdowns.

## Quick install

```bash
pip install cfa-kernel
cfa init
cfa evaluate "Join NFe with Clientes and persist to Silver" \
  --catalog .cfa/catalog.json
```

## Core concepts

### StateSignature

The universal contract. Any system — CLI, API, agent, orchestrator — can
produce one. It is content-hashed: same content always yields the same hash.

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

Declarative YAML. No code required to define governance rules:

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
        - "Apply sha256 on PII columns before the operation"
```

### Decision

Every decision is structured and versioned:

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

The `audit_event_hash` chains into the previous event. The chain is
verifiable offline with `cfa audit verify`.

## The five primitives

These are the parts of CFA that are deliberately distinctive. They are not
expected to change between releases.

| Primitive | Where it lives |
|-----------|----------------|
| Typed, content-hashed `StateSignature` | `cfa.types.StateSignature` |
| `REPLAN` as a first-class outcome | `cfa.policy.PolicyResult` + `cfa.types.PolicyAction` |
| Offline-verifiable SHA-256 audit chain | `cfa.audit.AuditTrail.verify_chain()` |
| Operational catalog (PII, partition, classification, merge_key as policy primitives) | `cfa.types.DatasetRef` + `cfa.policy.catalog` |
| Deterministic by default; LLM as optional normalizer | `cfa.normalizer.base.NormalizerBackend` |

## Where to go next

- **[Getting Started](./getting-started)** — install and run your first
  governance check.
- **[CLI Reference](./cli)** — every `cfa` command.
- **[Policy Bundles](./policy-bundles)** — declarative YAML policy rules.
- **[Backends](./backends)** — PySpark, SQL, dbt code generation.
- **[MCP Server](./mcp-server)** — expose CFA to AI agents.
- **[Use cfa_guard with any framework](./integrations/use-cfa-guard-with-frameworks)** — LangGraph, CrewAI, AutoGen, DSPy, OpenAI Agents SDK.
- **[Compare](./compare)** — CFA vs OPA, LangSmith, Great Expectations, Unity Catalog.
- **[Architecture Notes](./architecture-notes)** — design decisions and trade-offs.
- **[FAQ](./faq)**.
