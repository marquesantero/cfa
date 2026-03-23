# CFA

**Contextual Flux Architecture** is a governed execution kernel for AI-native systems.

It replaces the traditional `agents + skills/tools` model with an architecture centered on:

- semantic intent resolution
- typed intent contracts
- policy-driven planning
- validated execution
- context-aware state management
- auditable lifecycle evolution

The core idea is simple: an AI system should not jump directly from prompt to action. It should first convert intent into a governed contract, evaluate that contract against policy, execute under controlled conditions, project the resulting world state, and accumulate evidence over time.

---

## Why CFA Exists

Most agentic systems fail in one or more of these ways:

- **Silent ambiguity**: the model interprets the request incorrectly but still acts confidently.
- **Weak governance**: execution happens before cost, privacy, mutability, or schema constraints are evaluated.
- **No durable world model**: the system forgets what state the environment is in after execution.
- **Poor auditability**: you can inspect prompts and outputs, but not a formal decision trail.
- **No lifecycle discipline**: reusable capabilities emerge accidentally, without evidence-based promotion or demotion.

CFA addresses those problems by making intent resolution, policy, execution, state projection, and lifecycle management first-class architectural concerns.

---

## What CFA Is

CFA is both:

1. **An architectural proposal**
2. **A Python implementation of the core kernel**

The architecture is documented in the whitepaper:

- [`cfa-v2-whitepaper.html`](./cfa-v2-whitepaper.html)
- [`cfa-v2-whitepaper_patched.html`](./cfa-v2-whitepaper_patched.html)

The code in this repository implements the main runtime building blocks described there.

---

## Core Thesis

Instead of asking:

> "Which agent or skill should handle this?"

CFA asks:

> "What is the intended state change, under which constraints, and can it be governed safely?"

That shift changes the system from a prompt-routing architecture into a contract-and-state architecture.

---

## Architectural Model

At a high level, CFA runs the following flow:

`Natural language -> Semantic resolution -> Confirmation -> Policy -> Plan -> Code generation -> Static validation -> Sandbox execution -> Runtime validation -> Partial failure handling -> State projection -> Audit trail -> Lifecycle evaluation`

This repository implements those stages as modular components.

---

## Main Components

### 1. Intent Normalizer

Turns natural language into a typed `StateSignature`.

Responsibilities:

- interpret the request semantically
- consult environment state before signing intent
- produce confidence and ambiguity signals
- derive confirmation mode based on risk

### 2. Confirmation Orchestrator

Applies selective escalation when semantic risk is high.

Modes:

- `auto`
- `soft`
- `hard`
- `human_escalation`

### 3. Policy Engine

Evaluates the signature before execution.

Typical policy concerns:

- PII handling
- write safety
- merge discipline
- partitioning requirements
- cost ceilings
- type enforcement

### 4. Execution Planner

Builds a governed execution DAG from the approved signature.

The planner is intentionally constrained. It does not invent arbitrary workflows; it instantiates approved execution patterns.

### 5. Code Generator

Generates deterministic code from the plan.

Current implementation:

- PySpark-oriented template generation

### 6. Static Validation

Checks generated code before execution.

Examples:

- forbidden imports
- dangerous collection patterns
- missing partition filters
- missing merge semantics
- raw PII leakage in code paths

### 7. Sandbox Executor

Runs the generated plan in a controlled environment and collects execution metrics.

### 8. Runtime Validation

Validates the actual behavior after execution.

Examples:

- cost exceeded
- null ratio drift
- schema mismatch
- shuffle budget violation

### 9. Partial Execution Manager

Applies failure policy and retry strategy when execution is only partially successful.

Supported states:

- `published`
- `degraded`
- `committed_not_published`
- `quarantined`
- `rolled_back`

### 10. Context Registry

Maintains a live model of environment state.

This is not just a log. It is the system's representation of the current world state relevant to future decisions.

### 11. State Projection Protocol

Projects execution outcomes into the `ContextRegistry` so future intents see the correct environmental state.

### 12. Audit Trail

Records append-only decision events with a cryptographic hash chain for tamper detection.

### 13. Indices + Promotion Engine

Evaluates repeated execution health over time and determines whether a signature is:

- a candidate
- active
- watchlisted
- deprecated
- retired
- demoted

---

## Repository Structure

```text
src/cfa/
  __init__.py
  audit.py
  codegen.py
  context.py
  indices.py
  kernel.py
  normalizer.py
  partial_execution.py
  planner.py
  policy.py
  promotion.py
  runtime_validation.py
  sandbox.py
  state_projection.py
  static_validation.py
  types.py

  governance/
  lifecycle/
  resolution/

docs/
  guide.md

examples/
  full_pipeline.py
  standalone_governance.py
  standalone_lifecycle.py
  standalone_resolution.py

tests/
```

---

## Project Status

This repository currently contains:

- a modular CFA kernel implementation
- standalone governance, resolution, and lifecycle modules
- deterministic mock backends for local execution and testing
- persistent context and audit storage backends
- a comprehensive automated test suite

Current verified status:

- `203` tests passing

This means the project is already a solid experimental implementation, but it should still be viewed as an evolving architecture rather than a finished production platform.

---

## Key Concepts

### State Signature

The `StateSignature` is the formal contract of an intent.

It captures:

- domain
- intent
- target layer
- datasets
- constraints
- execution context

The architecture depends on the idea that execution should be governed from a typed signature, not directly from a prompt.

### Context Registry

The `ContextRegistry` stores the execution-relevant state of the environment.

Examples:

- dataset currently published
- target scope quarantined
- partial commit awaiting resolution
- execution history
- snapshot version used by the decision cycle

### Faults

CFA models failures as typed `Fault` objects instead of raw exceptions wherever possible.

Faults are grouped into families such as:

- semantic faults
- static safety faults
- runtime behavioral faults
- environmental faults

### Indices

The lifecycle model uses four indices:

- **IFo**: operational fluidity
- **IFs**: semantic fidelity
- **IFg**: governance compliance
- **IDI**: intent drift

These support evidence-based promotion and demotion of reusable capabilities.

---

## What Problem This Solves in Practice

CFA is useful when you want AI to participate in operational systems without turning the entire stack into opaque prompt orchestration.

Typical application areas:

- governed data pipelines
- AI-assisted ETL and transformation planning
- human-in-the-loop data operations
- internal copilots that trigger real system actions
- execution kernels for platform teams
- regulated or auditable AI workflows

It is particularly relevant when:

- execution has cost implications
- data carries privacy sensitivity
- partial failures matter
- environment state must influence future decisions
- repeatability and traceability are required

---

## Usage Modes

You do not need to adopt the full pipeline at once.

The project is intentionally modular.

### Governance only

Use the policy engine and validators without any LLM or execution backend.

### Resolution only

Use the normalizer and confirmation stages to convert natural-language requests into typed intent contracts.

### Lifecycle only

Use execution indices and promotion logic on top of an existing workflow platform.

### Full pipeline

Use `KernelOrchestrator` when you want the end-to-end governed flow.

---

## Quick Start

### Requirements

- Python `3.11+`

### Install locally

```bash
pip install -e .
```

For development:

```bash
pip install -e .[dev]
```

### Run tests

```bash
pytest -q
```

---

## Example: Full Kernel

```python
from cfa import KernelOrchestrator

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
            "partition_column": "processing_date",
        },
    }
}

kernel = KernelOrchestrator(catalog=catalog)
result = kernel.process("Join NFe com Clientes e persista na Silver")

print(result.state.value)
print(result.signature.signature_hash if result.signature else None)
```

---

## Example: Governance Only

```python
from cfa.policy import PolicyEngine
from cfa.types import (
    DatasetClassification,
    DatasetRef,
    ExecutionContext,
    SignatureConstraints,
    StateSignature,
    TargetLayer,
)

signature = StateSignature(
    domain="fiscal",
    intent="reconciliation",
    target_layer=TargetLayer.SILVER,
    datasets=(
        DatasetRef(name="nfe", classification=DatasetClassification.HIGH_VOLUME),
        DatasetRef(
            name="clientes",
            classification=DatasetClassification.SENSITIVE,
            pii_columns=("cpf",),
        ),
    ),
    constraints=SignatureConstraints(
        no_pii_raw=True,
        merge_key_required=True,
        enforce_types=True,
        partition_by=("processing_date",),
    ),
    execution_context=ExecutionContext(
        policy_bundle_version="v1.0",
        catalog_snapshot_version="catalog_demo",
        context_registry_version_id="ctx_demo",
    ),
)

engine = PolicyEngine()
result = engine.evaluate(signature)

print(result.action.value)
print(result.reasoning)
```

---

## Design Principles

The implementation follows a few strong principles:

- **Govern before execution**
- **Model uncertainty explicitly**
- **Treat world state as a first-class system input**
- **Keep planning constrained**
- **Represent failure structurally**
- **Prefer deterministic artifacts over opaque prompt chains**
- **Promote reuse through evidence, not convenience**

---

## What This Repository Is Not

Non-goals include:

- general-purpose agent framework abstraction
- uncontrolled autonomous execution
- prompt-only routing architecture
- distributed multi-writer concurrency platform
- production-ready Spark runtime for every environment out of the box

This repository is focused on the CFA kernel and its architectural mechanics.

---

## Current Limitations

This project is still evolving. A few limitations are worth stating explicitly:

- the default normalizer backend is a deterministic mock
- code generation is currently PySpark-oriented
- concurrency assumptions remain intentionally conservative
- some extension points are represented by interfaces and mock implementations rather than production adapters
- the architecture is deeper than the current runtime integrations

These are expected constraints for the current phase of the project.

---

## Roadmap

Near-term directions include:

- stronger production backends for semantic resolution
- richer planner contracts
- explicit merge key and target scope modeling
- broader execution backends
- deeper runtime observability
- improved GitHub collaboration structure
- CI automation and packaging hardening

---

## Documentation

Additional material in this repository:

- [`docs/guide.md`](./docs/guide.md): implementation-oriented usage guide
- [`examples/`](./examples): standalone and full-pipeline examples
- [`tests/`](./tests): behavioral and integration test coverage
- [`cfa-v2-whitepaper.html`](./cfa-v2-whitepaper.html): architecture reference

---

## Contributing

Contributions are welcome, especially in:

- architecture review
- runtime adapters
- planner and policy modeling
- documentation
- test coverage
- real-world integration scenarios

If you open issues or PRs, it helps to distinguish clearly between:

- **architectural proposal changes**
- **implementation bugs**
- **runtime adapter additions**
- **documentation improvements**

Contribution support files included in this repository:

- [`CONTRIBUTING.md`](./CONTRIBUTING.md)
- [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md)
- [`.github/workflows/ci.yml`](./.github/workflows/ci.yml)

---

## License

This repository is licensed under the MIT License.

See [`LICENSE`](./LICENSE).

---

## Summary

CFA is an attempt to make AI execution systems more rigorous.

Instead of routing prompts into opaque autonomous behaviors, it formalizes intent, governs execution, models state, records decisions, and evolves reusable capabilities through evidence. This repository is the beginning of that kernel.
