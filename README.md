# CFA v2

[![CI](https://github.com/marquesantero/cfa/actions/workflows/ci.yml/badge.svg)](https://github.com/marquesantero/cfa/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

**Contextual Flux Architecture** is a governed execution kernel for AI-native systems.

It is designed for the point where language models stop being just conversational interfaces and start participating in real operational flows: transforming data, materializing outputs, touching governed layers, consuming runtime budget, and changing system state.

Most current agentic stacks still move too quickly from prompt to action. CFA introduces a stronger middle layer between those two points: typed intent resolution, declarative policy evaluation, validation, controlled execution, state projection, and auditability.

Instead of asking:

> which agent or skill should act?

CFA asks:

> which state transition is being requested, under which constraints, and can it be executed safely?

## Why CFA exists

The dominant `agents + skills + tools` pattern works well for lightweight automation and low-impact tasks. It becomes much weaker when AI is expected to operate inside real systems.

The core failure mode is not only model quality. It is architectural looseness.

### The three gaps CFA targets

| Gap | What often happens today | What CFA adds |
| --- | --- | --- |
| Silent ambiguity | The model interprets the request and executes on implicit assumptions | Intent is formalized into a typed `StateSignature` before execution |
| Weak governance | Tools run without a strong policy gate for PII, cost, schema, or target constraints | `PolicyEngine` applies declarative rules before execution |
| No explicit state model | The system returns logs or text, but does not persist operational context | `ContextRegistry` projects approved state back into the environment |

In practice, CFA is an attempt to move AI execution from "model interpreted something plausible" to "the system can explain what was requested, what was allowed, what was executed, and what changed afterward."

## What CFA is

CFA is not:

- another prompt wrapper
- a generic agent orchestration framework
- a collection of skills with stronger naming

CFA is:

- a typed contract layer between intent and action
- a governed execution pipeline
- a model for projecting approved execution effects back into system context
- a basis for measuring recurring flow health over time

## Architecture at a glance

The implementation is modular. You can adopt only the layer you need.

| Surface | Purpose | Typical use |
| --- | --- | --- |
| `cfa.governance` | Policy checks and validation before execution | Existing pipelines that need a formal decision gate |
| `cfa.resolution` | Natural-language intent resolution into typed contracts | Systems that need semantic interpretation before action |
| `cfa.lifecycle` | Quantitative health tracking for recurring flows | Promotion, watchlisting, demotion, and retirement |
| `KernelOrchestrator` | Full governed execution flow | End-to-end natural-language to execution outcome |

High-level kernel flow:

```text
intent -> normalization -> confirmation -> policy -> planning -> codegen
-> static validation -> sandbox -> runtime validation -> partial execution
-> state projection -> audit -> lifecycle evaluation
```

## Core concepts

### `StateSignature`

An immutable execution contract that captures:

- domain
- intent
- input datasets
- target layer
- constraints
- execution context

Every kernel decision starts from the signature, not from an opaque prompt interpretation.

### `PolicyEngine`

A declarative policy layer that evaluates whether a request may proceed, must be replanned, or must be blocked.

Typical checks include:

- PII handling
- merge-key requirements
- partition requirements
- type enforcement
- cost guardrails

### `ContextRegistry`

An operational context store for what the system should consider current and relevant. It is not just a log. It exists to inform future decisions with materialized context.

### `AuditTrail`

An append-only chain of events with linked hashes for tamper detection and execution traceability.

### Lifecycle indices

Recurring flows can be evaluated with four indices:

| Index | Meaning |
| --- | --- |
| IFo | Operational fluidity: latency, cost, success rate |
| IFs | Semantic fidelity: schema health, drift, faults |
| IFg | Governance integrity: binary pass/fail signal |
| IDI | Intent drift over the evaluation window |

These scores support evidence-based promotion, watchlisting, demotion, and retirement.

## Quick example

### Governance only

Use CFA as a policy gate in front of an existing pipeline:

```python
from cfa.governance import (
    PolicyEngine,
    StateSignature,
    TargetLayer,
    DatasetRef,
    DatasetClassification,
    SignatureConstraints,
    ExecutionContext,
)

signature = StateSignature(
    domain="fiscal",
    intent="reconciliation",
    target_layer=TargetLayer.SILVER,
    datasets=(
        DatasetRef("nfe", DatasetClassification.HIGH_VOLUME, size_gb=4000),
        DatasetRef("clientes", DatasetClassification.SENSITIVE, pii_columns=("cpf",)),
    ),
    constraints=SignatureConstraints(
        no_pii_raw=True,
        merge_key_required=True,
        enforce_types=True,
        partition_by=("processing_date",),
    ),
    execution_context=ExecutionContext("v1.0", "catalog_2026", "ctx_1"),
)

result = PolicyEngine().evaluate(signature)

if result.is_blocked:
    raise RuntimeError(result.reasoning)
```

### Natural-language resolution

Use CFA to convert free-form requests into typed intent:

```python
from cfa.resolution import IntentNormalizer, MockNormalizerBackend

catalog = {
    "datasets": {
        "nfe": {
            "classification": "high_volume",
            "size_gb": 4000,
            "partition_column": "processing_date",
        },
        "clientes": {
            "classification": "sensitive",
            "size_gb": 0.5,
            "pii_columns": ["cpf", "email"],
        },
    }
}

normalizer = IntentNormalizer(backend=MockNormalizerBackend())
resolution = normalizer.normalize(
    raw_intent="Join NFe with Clientes and persist to Silver",
    environment_state={},
    catalog=catalog,
)

print(resolution.signature.domain)
print(resolution.signature.target_layer.value)
print(resolution.confidence_score)
print(resolution.confirmation_mode.value)
```

### Full kernel

Use the full orchestrator when you want the governed end-to-end flow:

```python
from cfa import KernelOrchestrator

kernel = KernelOrchestrator(catalog=catalog)
result = kernel.process("Join NFe with Clientes and persist to Silver")

print(result.state.value)
```

## What makes the project different

The differentiator is not that CFA uses an LLM somewhere in the pipeline. Many systems do that.

The differentiator is that CFA treats:

- semantic interpretation
- governance
- execution
- state update
- audit
- recurring health

as parts of the same architectural contract.

That makes it a better fit for systems where AI is allowed to do more than answer questions.

## Adoption model

You do not need to adopt CFA all at once.

| Adoption mode | What you get |
| --- | --- |
| Governance only | A formal decision gate before pipeline execution |
| Governance + Resolution | Natural-language requests converted into governed contracts |
| Partial kernel | Validation, controlled execution, and state projection |
| Full kernel | End-to-end governed execution flow |

This matters because architectural replacement rarely happens in one move. The repository is intentionally structured so adoption can happen incrementally.

## Current implementation status

Current repository characteristics:

- Python 3.11+
- modular package layout
- full automated test suite
- deterministic mock backend for semantic resolution
- deterministic PySpark-oriented code generation path
- JSON/JSONL-oriented local persistence backends
- public whitepaper and project site

Test status:

```bash
pytest -q
```

Current suite: `203 passed`.

## Requirements

- Python 3.11+

The repository uses `match` in the code generation path, so Python 3.9 will not execute the full kernel or governance examples correctly.

## Installation

```bash
pip install -e .
pip install -e .[dev]
```

## Running examples

The examples in [`examples`](./examples/) are set up to run from a repository checkout.

```bash
python examples/standalone_resolution.py
python examples/standalone_lifecycle.py
python examples/standalone_governance.py
python examples/full_pipeline.py
```

## Repository structure

```text
src/cfa/
  governance/         standalone policy + validation surface
  resolution/         standalone intent resolution surface
  lifecycle/          standalone indices + promotion surface

  types.py            StateSignature, Fault, enums
  policy.py           PolicyEngine and declarative rules
  normalizer.py       IntentNormalizer and confirmation
  planner.py          Execution planner
  codegen.py          Deterministic PySpark code generator
  static_validation.py
  sandbox.py
  runtime_validation.py
  partial_execution.py
  context.py          Context registry
  state_projection.py
  audit.py            Audit trail
  indices.py          IFo, IFs, IFg, IDI
  promotion.py        Promotion/demotion engine
  kernel.py           Full kernel orchestrator

examples/             standalone and full-kernel examples
tests/                automated test suite
docs/                 repository-facing documentation
```

## Known limitations

- The default normalizer backend is a deterministic mock.
- Code generation currently targets PySpark.
- Persistence defaults to JSON/JSONL-oriented local backends.
- Concurrency is intentionally conservative.

## Where to read next

- [Usage Guide](./docs/guide.md)
- [Examples](./examples/)
- [Project Pages](https://marquesantero.github.io/cfa/)
- [Whitepaper PT-BR](./docs/cfa-v2-whitepaper.html)
- [Whitepaper EN](./docs/cfa-v2-whitepaper.en.html)
- [Contributing](./CONTRIBUTING.md)

## Contributing

If you want to contribute, see [CONTRIBUTING.md](./CONTRIBUTING.md).

Areas especially worth discussion:

- state projection semantics
- policy evolution
- planner contracts
- runtime adapters
- lifecycle evidence thresholds

## License

[MIT](./LICENSE)
