---
sidebar_position: 3
---

# CFA v0.1.9 Whitepaper

Contextual Flux Architecture — Governed execution for AI agents and data systems.

---

## 1. Introduction

CFA (Contextual Flux Architecture) is a **governance kernel** that inserts a formal decision layer between user intent and operational execution in AI-native data systems. Rather than moving directly from prompt to action, CFA mandates that every execution request is formalized, validated against declarative policy, planned, generated, sandboxed, and audited before any side effects occur.

**Formal definition**: CFA is a tuple `(Φ, Γ, Π, Ω, Σ)` where:
- **Φ** — Formalize: resolve natural-language intent into a typed `StateSignature`
- **Γ** — Govern: evaluate the signature against declarative policy rules via `PolicyEngine`
- **Π** — Plan & Generate: produce deterministic execution code from approved plans
- **Ω** — Execute & Validate: run in an isolated sandbox, validate runtime metrics
- **Σ** — State & Audit: project state into the `ContextRegistry`, record tamper-evident audit events, compute lifecycle indices

**Core flow**: `CLI/MCP → Resolution → Governance → Execution → State → Evolution → Reports/OTel`

The architecture is designed for **progressive adoption** — you can use only the governance layer as a gate before existing pipelines, or adopt the full kernel for end-to-end governed execution.

---

## 2. Problems CFA Solves

### 2.1 Fragile Routing
Current agentic stacks use prompt-to-tool routing without structured validation. A slightly ambiguous phrase ("join sales data") can route to the wrong tool with no guardrail. CFA formalizes intent into a typed contract before any routing decision.

### 2.2 Static Catalog
Most systems treat data catalogs as passive metadata stores. CFA makes the catalog **operational** — dataset classification, PII markers, and partition metadata actively drive policy decisions.

### 2.3 Missing Enforcement
Tools run without a policy gate for PII handling, schema constraints, cost ceilings, or target layer restrictions. CFA's `PolicyEngine` applies declarative rules before execution with three outcomes: `APPROVE`, `REPLAN` (auto-correct), or `BLOCK`.

### 2.4 Implicit State
AI agents operate statelessly — there is no persisted record of what was done, under what constraints, or what changed. CFA's `ContextRegistry` maintains an explicit state model through `StateProjection` after every execution.

### 2.5 No Standard Protocol
There is no standard way for AI agents to query governance rules, validate intents, or verify audit trails. CFA exposes all capabilities via the **Model Context Protocol** (MCP) — a JSON-RPC 2.0 interface callable by any MCP-compatible agent.

### 2.6 Observability Gap
Logs and traces show *what happened* but not *whether it should have happened*. CFA fills this gap with SHA-256 hash chains (tamper-evident audit), lifecycle indices (IFo/IFs/IFg/IDI), OpenTelemetry spans, and Prometheus metrics.

---

## 3. Foundational Principles

1. **Intent Formalization** — Every execution begins with a typed `StateSignature`, not an opaque prompt. Domain, intent, datasets, constraints, and execution context are explicit.

2. **Policy Before Execution** — Governance rules are evaluated *before* any code runs. No side effects occur without policy clearance.

3. **Deterministic Code Generation** — From an approved plan, the system generates code deterministically. No runtime LLM calls in the execution path.

4. **Strong Validation** — Static validation inspects generated code before sandbox execution. Runtime validation checks cardinality, shuffle, cost, schema, and null ratios after execution.

5. **State Projection** — After every execution (success, partial, or failure), the system projects state back into the `ContextRegistry`. The system always knows what happened.

6. **Tamper-Evident Audit** — Every governance event is recorded in an append-only chain with SHA-256 linked hashes. Integrity can be verified at any time.

---

## 4. Architecture

### Phase 1: Formalize
Natural-language intent enters the system. The `IntentNormalizer` resolves it into a `StateSignature` — an immutable contract containing domain, intent, target layer, dataset references, constraints, and execution context. A `ConfirmationOrchestrator` determines whether the request proceeds automatically (`AUTO`), requires soft confirmation (`SOFT`), hard confirmation (`HARD`), or human escalation (`HUMAN_ESCALATION`).

### Phase 2: Govern
The `PolicyEngine` evaluates the `StateSignature` against declarative rules (PII protection, merge-key enforcement, partition requirements, type enforcement, cost ceilings). Each rule produces one of: `APPROVE`, `REPLAN` (apply corrective interventions and re-evaluate up to 3 times), or `BLOCK` (terminal denial).

### Phase 3: Generate
An `ExecutionPlanner` produces a structured plan from the approved signature. The `CodeGen` backend (default: PySpark) generates deterministic code from the plan. `StaticValidator` inspects the generated code for disallowed patterns before execution.

### Phase 4: Execute
Generated code runs in an isolated `Sandbox` that captures runtime metrics (rows, shuffle, duration, cost). `RuntimeValidator` checks cardinality, schema compliance, null ratios, and shuffle budget. `PartialExecution` handles retries, failures, and quarantine/rollback.

### Phase 5: Validate
The `StateProjectionProtocol` updates the `ContextRegistry` with the new state of all affected datasets. The `AuditTrail` records the full event chain with SHA-256 hashes. `Lifecycle` evaluation computes IFo, IFs, IFg, and IDI scores, feeding the `PromotionEngine` for state transitions (candidate → active → watchlist → demoted → retired).

---

## 5. Core Components

### StateSignature
Immutable typed contract for every execution request. Fields: `domain`, `intent`, `target_layer`, `datasets` (with classification, size, PII columns), `constraints` (no_pii_raw, merge_key_required, enforce_types, partition_by, max_cost_dbu), `execution_context` (policy version, catalog version, context ID).

### PolicyEngine
Evaluates `StateSignature` against declarative rules. Supports 10 built-in conditions and custom conditions via `register_condition()`. Returns `PolicyResult` with faults and remediation steps.

### ExecutionPlanner
Produces a structured `ExecutionPlan` from an approved `StateSignature`. The plan specifies merge operations, anonymization steps, partition filters, and write targets.

### Sandbox
Isolated execution environment that runs generated code and captures metrics. Returns `SandboxResult` with row counts, shuffle MB, duration, cost DBU, and success status.

### AuditTrail
Append-only event store with SHA-256 hash chain. Each `AuditEvent` links to the previous event's hash. Supports `verify_chain()` for integrity checking. Pluggable storage backends (default: JSON Lines).

### ContextRegistry
Operational state store for what the system considers current and relevant. Updated by `StateProjectionProtocol` after each execution. Informs future governance decisions with materialized context.

### StateProjection
Implements Invariant I4: after every execution, projects the new state of all affected datasets back into the `ContextRegistry`. Handles success, partial success, and failure projections.

### Lifecycle Indices
Four quantitative indices for recurring flows:
- **IFo** (Fluidez Operacional): `(1 − norm_latency) × (1 − norm_cost) × success_rate`
- **IFs** (Fidelidade Semântica): `schema_match × (1 − replan_rate) × fault_free_rate`
- **IFg** (Governança): binary — 1.0 if no violations, 0.0 otherwise
- **IDI** (Intent Drift): `1 − (replanned / total)` over a time window

### Promotion Engine
Uses lifecycle indices to drive state transitions: `CANDIDATE → ACTIVE` (IFo ≥ 0.75, IFs ≥ 0.90, IFg = 1.0), `ACTIVE → WATCHLIST` (IDI < 0.75), `WATCHLIST → DEMOTED` (IDI < 0.50), `* → RETIRED` (prolonged inactivity or catalog incompatibility).

### Fault Model
Structured faults with code, severity (info/warning/critical), family (semantic/finops/contract/governance), message, and remediation steps. Used by `PolicyEngine` to communicate violations and corrective actions.

### Decision Engine
Produces terminal decisions from policy evaluation: `APPROVE` (proceed), `REPLAN` (auto-correct and retry, max 3 attempts), or `BLOCK` (terminal denial with reasoning).

---

## 6. System Invariants

| ID | Invariant | Precedence |
|----|-----------|-----------|
| I1 | No PII in Silver/Gold without anonymization | Highest — blocks execution |
| I2 | Merge key required for all protected layer writes | High — replan or block |
| I3 | High-volume datasets require partition filter | High — replan or block |
| I4 | State must be projected after every execution | Medium — architectural guarantee |
| I5 | Audit chain must remain tamper-evident | Highest — verified on read |
| I6 | Policy bundle version is immutable for a given execution | Highest — audit requirement |
| I7 | No execution without prior policy clearance | Highest — architectural guarantee |
| I8 | Single active intent per target scope | Medium — concurrency invariant |

**Precedence rules**: I1 > I2 > I3 > I7 > I5 > I6 > I4 > I8. If a higher-precedence invariant is violated, lower-precedence checks may be skipped.

---

## 7. Extension Points

### Backend Registry
Pluggable system for registering code generation backends. Built-in: `pyspark`. Register custom backends via `BackendRegistry.singleton().register(name, factory)`.

### Normalizer Backends
The `IntentNormalizer` accepts pluggable backends. Default: `MockNormalizerBackend` (keyword matching, no LLM). Optional: OpenAI, Anthropic, or custom backends.

### CodeGen Backends
Implement `BackendAdapter` to target any language or runtime. Interface: `get_capabilities()` and `generate(plan)`. Capabilities include merge support, anonymization methods, and partition overwrite.

### Sandbox Backends
Pluggable sandbox implementations for different execution environments (local process, Docker container, remote cluster).

### Storage Backends
Pluggable storage for audit trails and context registry. Default: JSON Lines files. Extensible to databases, blob storage, or event streams.

### Framework Adapters
Thin governance wrappers (3-5 lines each) for AI agent frameworks:
- `cfa.adapters.langgraph` → `cfa_guard`
- `cfa.adapters.openai_agents` → `cfa_tool_guard`
- `cfa.adapters.crewai` → `cfa_crew_guard`
- `cfa.adapters.autogen` → `cfa_agent_guard`
- `cfa.adapters.dspy` → `cfa_module_guard`

---

## 8. v3 Capabilities

### CLI — 11 Subcommands
`evaluate`, `validate`, `rules list`, `rules explain`, `audit show`, `audit verify`, `taxonomy generate`, `taxonomy test-intents`, `report`, `backend list`, `serve`, `init`. Zero dependencies beyond Python stdlib.

### MCP Server — 5 Tools
`cfa_evaluate_signature`, `cfa_describe_rules`, `cfa_explain_fault`, `cfa_audit_check`, `cfa_list_backends`. JSON-RPC 2.0 over stdin/stdout.

### Rich HTML Reporting — 5 Types
**Execution report** (pipeline timeline + sandbox metrics), **Audit report** (hash chain + integrity badge), **Lifecycle dashboard** (IFo/IFs/IFg/IDI trends + cost charts), **Compliance report** (governance health score + PII incidents), **Interactive dashboard** (multi-pipeline overview). All single-file HTML with Chart.js, dark theme, zero Python deps.

### Policy Bundles — 3 Built-in
`prod-v1.yaml` (balanced safety/cost, 7 rules), `finops-strict-v1.yaml` (aggressive cost control, 5 rules), `compliance-strict-v1.yaml` (regulated industries, 7 rules). Versioned, loadable YAML with semantic versioning.

### Framework Adapters — 5 Frameworks
LangGraph, OpenAI Agents SDK, CrewAI, AutoGen, DSPy. Each adapter is a 3-5 line thin wrapper that intercepts tool calls and validates against CFA policy.

### OpenTelemetry
Traces every kernel phase as OTel spans. Export to any OTel-compatible backend (Jaeger, Zipkin, Azure Monitor).

### Prometheus
Exposes metrics on `/metrics` via `cfa serve --metrics-port 9090`. Counters for evaluations, replans, blocks; gauges for lifecycle indices.

### Test Suite — 534 tests
Comprehensive test coverage across governance, resolution, lifecycle, kernel, adapters, CLI, MCP, and reporting.

---

## 9. Conclusion

CFA v0.1.9 establishes a governance kernel that bridges the gap between AI agent flexibility and production-grade safety. By formalizing intent, enforcing policy before execution, generating deterministic code, sandboxing runtime, projecting state, and maintaining tamper-evident audit trails, CFA provides the guardrails that AI-native data systems require to operate in regulated, high-stakes environments.

The architecture is designed for **progressive adoption**: start with a single policy gate before an existing pipeline, then expand to full kernel orchestration as confidence grows. Every component is pluggable, every decision is auditable, and every state transition is recorded.

**CFA doesn't replace your agents. It governs them.**
