---
sidebar_position: 1
---

# CFA v1.0.0

Governed execution for AI agents and data systems.

## What is CFA?

CFA is a governance layer that validates state transitions before they execute. It acts as an agnostic decision engine:

1. **Receives a contract** — `StateSignature` (JSON, YAML, or natural language)
2. **Validates the contract** — structure, enums, required fields
3. **Cross-references against catalog** — datasets must exist with matching metadata
4. **Evaluates declarative policies** — PII, FinOps, merge keys, partitions, costs
5. **Decides** — `approve` / `replan` (with suggested fixes) / `block`
6. **Records an auditable decision** — SHA-256 hash chain, artifact hashes
7. **Tracks lifecycle health** — IFo, IFs, IFg, IDI indices per pipeline

## Quick Install

```bash
pip install cfa-kernel
# or: pip install git+https://github.com/marquesantero/cfa.git
cfa init
cfa evaluate "Join NFe with Clientes and persist to Silver" --catalog .cfa/catalog.json
```

## Core concepts

### StateSignature

The universal contract. Any system — CLI, API, agent, orchestrator — can produce one:

```json
{
  "domain": "fiscal",
  "intent": "reconciliation",
  "target_layer": "silver",
  "datasets": [
    {"name": "nfe", "classification": "high_volume", "pii_columns": [], "merge_keys": ["nfe_id"]}
  ],
  "constraints": {"no_pii_raw": true, "merge_key_required": true, "partition_by": ["processing_date"]},
  "execution_context": {"policy_bundle_version": "prod-v1.0", "catalog_snapshot_version": "v1", "context_registry_version_id": "ctx1"}
}
```

### Policy bundles

Declarative YAML. No code needed to define governance rules:

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

### Decision output

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
  "faults": [{"code": "GOVERNANCE_RAW_PII", "severity": "critical", "remediation": [...]}],
  "audit_event_hash": "..."
}
```

## Key Differentiators

| Feature | CFA | Others |
|---------|-----|--------|
| SHA-256 audit trail (tamper-evident) | ✅ | ❌ |
| Artifact hashing (catalog + policy + signature) | ✅ | ❌ |
| REPLAN with auto-interventions | ✅ | ❌ |
| Lifecycle indices (IFo/IFs/IFg/IDI) | ✅ | ❌ |
| Backend-agnostic (PySpark, SQL, dbt) | ✅ | ❌ |
| MCP protocol for AI agents | ✅ | ❌ |
| SQLite storage with retention management | ✅ | ❌ |
| Config file with auto-discovery | ✅ | ❌ |
| Zero runtime dependencies (core) | ✅ | ❌ |

## Where to go next

- **[Getting Started](./getting-started)** — Install and run your first governance check
- **[CLI Reference](./cli)** — All `cfa` commands
- **[Policy Bundles](./policy-bundles)** — Declarative YAML policy rules
- **[Backends](./backends)** — PySpark, SQL, dbt code generation
- **[MCP Server](./mcp-server)** — Expose CFA to AI agents
- **[Reporting](./reporting)** — HTML reports and dashboards
- **[Architecture Notes](./architecture-notes)** — Design decisions and trade-offs
