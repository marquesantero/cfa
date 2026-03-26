# CFA v2

[![CI](https://github.com/marquesantero/cfa/actions/workflows/ci.yml/badge.svg)](https://github.com/marquesantero/cfa/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

**Contextual Flux Architecture** is a governed execution kernel for AI-native systems.

Most current agentic stacks move too quickly from prompt to action. CFA introduces a stronger middle layer: typed intent resolution, declarative policy evaluation, controlled execution, state projection, and auditability.

Instead of asking _"which agent or skill should act?"_, CFA asks _"which state transition is being requested, under which constraints, and can it be executed safely?"_

## Installation

```bash
pip install -e .        # core
pip install -e .[dev]   # with pytest
```

```bash
pytest -q
```

## Quick example

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

More examples: [governance](./examples/standalone_governance.py) | [resolution](./examples/standalone_resolution.py) | [lifecycle](./examples/standalone_lifecycle.py) | [full kernel](./examples/full_pipeline.py)

## Why CFA exists

The `agents + skills + tools` pattern works for lightweight automation. It becomes weaker when AI operates inside real systems.

| Gap | What happens today | What CFA adds |
| --- | --- | --- |
| Silent ambiguity | The model interprets and executes on implicit assumptions | Intent is formalized into a typed `StateSignature` before execution |
| Weak governance | Tools run without a policy gate for PII, cost, schema, or target constraints | `PolicyEngine` applies declarative rules before execution |
| No explicit state model | The system returns logs or text, but does not persist operational context | `ContextRegistry` projects approved state back into the environment |

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

An immutable execution contract: domain, intent, input datasets, target layer, constraints, and execution context. Every kernel decision starts from the signature, not from an opaque prompt interpretation.

### `PolicyEngine`

Evaluates whether a request may proceed (`APPROVE`), must be adjusted (`REPLAN`), or must be denied (`BLOCK`). Checks PII handling, merge-key requirements, partition constraints, type enforcement, and cost guardrails.

### `ContextRegistry`

An operational context store for what the system should consider current and relevant. It exists to inform future decisions with materialized context, not just to log what happened.

### `AuditTrail`

An append-only chain of events with SHA-256 linked hashes for tamper detection and execution traceability.

### Lifecycle indices

| Index | Meaning |
| --- | --- |
| IFo | Operational fluidity: latency, cost, success rate |
| IFs | Semantic fidelity: schema health, drift, faults |
| IFg | Governance integrity: binary pass/fail signal |
| IDI | Intent drift over the evaluation window |

These scores support evidence-based promotion, watchlisting, demotion, and retirement of recurring flows.

## Adoption model

You do not need to adopt CFA all at once.

| Adoption mode | What you get |
| --- | --- |
| Governance only | A formal decision gate before pipeline execution |
| Governance + Resolution | Natural-language requests converted into governed contracts |
| Partial kernel | Validation, controlled execution, and state projection |
| Full kernel | End-to-end governed execution flow |

## Known limitations

- The default semantic backend is a deterministic mock.
- Code generation currently targets PySpark.
- Persistence defaults to JSON/JSONL-oriented local backends.
- Concurrency is intentionally conservative.

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
integrations/         adoption wedges (Airflow, etc.)
```

## Where to read next

- [FAQ](./docs/faq.md)
- [Usage Guide](./docs/guide.md)
- [Architecture Notes](./docs/architecture-notes.md)
- [Airflow Governance Gate](./integrations/airflow-governance-gate/README.md)
- [Project Pages](https://marquesantero.github.io/cfa/)
- [Whitepaper PT-BR](https://marquesantero.github.io/cfa/cfa-v2-whitepaper.html)
- [Whitepaper EN](https://marquesantero.github.io/cfa/cfa-v2-whitepaper.en.html)

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md). Areas especially worth discussion:

- state projection semantics
- policy evolution
- planner contracts
- runtime adapters
- lifecycle evidence thresholds

## License

[MIT](./LICENSE)
