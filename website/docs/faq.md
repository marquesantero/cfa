---
sidebar_position: 20
---

# FAQ

## What problem does CFA solve?

CFA addresses the governance gap in AI-native data systems: who decides what an AI agent or data pipeline is allowed to do, under what constraints, and with what evidence? Instead of "which tool should I call?", CFA asks "what state transition is being requested, under what constraints, and can it be executed safely?"

## How is CFA different from Great Expectations or Soda?

Great Expectations and Soda validate **data quality** — they check if data meets expectations. CFA validates **execution governance** — it checks if an intent (what you want to do) complies with policy before execution. CFA operates at the intent level, not the data level.

## How is CFA different from ASSERT or RAMPART?

ASSERT and RAMPART evaluate **AI agent behavior** — they test if agents produce correct/safe outputs. CFA governs **data operations** — it validates that any agent or pipeline writing to data systems complies with PII, schema, cost, and partition policies. CFA has a hash-chain audit trail, state projection, and lifecycle indices that none of these tools offer.

## How is CFA different from ACS (Agent Control Specification)?

ACS is a policy engine for AI agents — YAML-based, MIT-licensed, backed by KPMG/IBM/Zscaler. Like CFA, it acts as a governance gate before agent actions. The key differences:

| Aspect | ACS | CFA |
|--------|-----|-----|
| State model | Stateless (allow/deny) | Stateful (StateSignature + ContextRegistry) |
| Decision | Binary (pass/fail) | Ternary (approve/replan/block) |
| Audit trail | Standard logs | SHA-256 hash chain (tamper-evident) |
| Lifecycle | Not present | IFo/IFs/IFg/IDI indices |
| State projection | No | Yes (post-execution) |
| Backend targets | Agent actions | Data pipelines + agents (PySpark, SQL, dbt) |

ACS excels at agent safety in enterprise environments. CFA adds stateful governance across both agents and data pipelines with cryptographic auditability.

## Does CFA require an LLM?

No. The default `IntentNormalizer` uses a deterministic mock backend (keyword matching). The Policy Engine, Planner, CodeGen, Sandbox, and Validators all operate without LLMs. LLM backends are optional plugins.

## What languages/runtimes does CFA support?

CFA core is Python 3.11+ with zero mandatory runtime dependencies. The default code generation target is PySpark (Delta Lake). The backend registry supports plugging in any target (DuckDB, BigQuery, SQL, REST APIs).

## Can I use CFA in CI/CD?

Yes. `cfa evaluate --exit-code` returns exit code 1 when an intent is BLOCKED, making it suitable for GitHub Actions, GitLab CI, or any CI pipeline. The repository includes an example workflow at `.github/workflows/governance.yml`.

## What is the REPLAN state?

REPLAN is CFA's unique intermediate state between APPROVE and BLOCK. When a policy rule fires with `action: replan`, the kernel automatically applies corrective interventions to the signature (e.g., adding partition filters, enabling PII anonymization) and re-evaluates. This happens up to 3 times before terminal BLOCK.

## What are IFo, IFs, IFg, and IDI?

Four quantitative lifecycle indices:

- **IFo** (Fluidez Operacional): `(1 - norm_latency) × (1 - norm_cost) × success_rate`
- **IFs** (Fidelidade Semântica): `schema_match × (1 - replan_rate) × fault_free_rate`
- **IFg** (Governança): binary — 1.0 if no violations, 0.0 otherwise
- **IDI** (Intent Drift): `1 - (replanned / total)` over a time window

These feed the Promotion Engine: ACTIVE (IFo ≥ 0.75, IFs ≥ 0.90, IFg = 1.0), WATCHLIST (IDI < 0.75), DEMOTED (IDI < 0.50).

## How does the audit trail work?

Every governance event (normalization, confirmation, policy evaluation, replan, code generation, validation, execution, projection, decision) is recorded as an `AuditEvent` with a SHA-256 hash. Each event links to the previous event's hash, forming a tamper-evident chain. `cfa audit verify` checks the chain integrity.

## What is State Projection (I4)?

Invariant I4: after every execution (success, partial, or failure), the `StateProjectionProtocol` updates the `ContextRegistry` with the new state of all affected datasets. This means the system always knows what happened and can make informed decisions about subsequent intents.

## Can CFA handle streaming data?

CFA 1.x targets batch and micro-batch execution. Streaming support is planned for a future major. The architecture's concurrency model assumes `single_active_intent_per_target_scope`.

## Is CFA production-ready?

CFA 1.0.0 shipped to PyPI with 534 passing tests, a full CLI, an MCP server, and rich reporting. It is designed for production governance gates. As with any governance tool, deploy with monitoring and start with `cfa evaluate` in CI before moving to runtime gates. The `1.1.0` cycle adds deprecation shims, consolidation, and editorial polish — see the [roadmap](https://github.com/marquesantero/cfa/blob/main/drafts/ROADMAP.md).
