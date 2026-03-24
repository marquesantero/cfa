# CFA v2

[![CI](https://github.com/marquesantero/cfa/actions/workflows/ci.yml/badge.svg)](https://github.com/marquesantero/cfa/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

**Contextual Flux Architecture** is a governed execution kernel for AI-native data systems.

Most agentic stacks jump straight from prompt to action. CFA inserts typed intent resolution, policy evaluation, validation, controlled execution, state projection, and auditability between those two points. Instead of asking _"which agent or skill should act?"_, CFA asks _"which state transition is being requested, under which constraints, and can it be executed safely?"_

## The three gaps CFA targets

| Gap | What happens in many current stacks | What CFA does |
| --- | --- | --- |
| Silent ambiguity | The model interprets intent and executes with implicit assumptions | Formalizes intent as a `StateSignature` before execution |
| Weak governance | Skills/tools run without explicit checks for PII, cost, schema, or policy | `PolicyEngine` evaluates declarative rules before execution |
| No explicit state model | The system returns text/logs but does not persist operational context | `ContextRegistry` projects approved state back into the environment |

## Modular by design

Each subsystem can be adopted independently:

```text
cfa.governance   Evaluate operations against policy rules.
cfa.resolution   Convert natural language into typed intent.
cfa.lifecycle    Track recurring execution health with quantitative indices.
```

The full kernel (`KernelOrchestrator`) composes all of them when you need the complete flow.

## Requirements

- Python 3.11+

The repository uses `match` statements in the code generation path, so Python 3.9 will not execute the full kernel or governance examples correctly.

## Installation

```bash
pip install -e .
pip install -e .[dev]
```

Run tests:

```bash
pytest -q
```

Current suite: `203 passed`.

## Running the examples

The examples in [`examples`](./examples/) are written to run directly from a repository checkout. If you prefer not to install the package, run them with Python 3.11 from the repo root:

```bash
python examples/standalone_resolution.py
python examples/standalone_lifecycle.py
python examples/standalone_governance.py
python examples/full_pipeline.py
```

If you are embedding CFA into another environment, the standard editable install remains the cleanest option.

## `cfa.governance`

Add governance to an existing pipeline without requiring an LLM, Spark cluster, or runtime adapter.

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

sig = StateSignature(
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

engine = PolicyEngine()
result = engine.evaluate(sig)

if result.is_blocked:
    raise RuntimeError(f"Blocked: {result.reasoning}")
```

Built-in policy coverage includes PII handling, merge-key enforcement, partition requirements, type enforcement, and cost constraints.

`StaticValidator` can also scan generated PySpark code for disallowed patterns such as `collect`, `toPandas`, `crossJoin`, and `import os`.

## `cfa.resolution`

Convert natural-language requests into typed intent contracts.

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

sig = resolution.signature
print(sig.domain)
print(sig.target_layer)
print(sig.contains_pii)
print(resolution.confidence_score)
print(resolution.confirmation_mode)
```

The bundled `MockNormalizerBackend` is deterministic and intended for tests and demos. Production usage should implement `NormalizerBackend` against an actual LLM or rules-based semantic resolver.

The `ConfirmationOrchestrator` escalates automatically when confidence is low, ambiguity is high, or protected data is involved.

## `cfa.lifecycle`

Track recurring execution quality and decide whether a flow should be promoted, watchlisted, deprecated, or retired.

```python
from datetime import datetime, timezone
from cfa.lifecycle import PromotionEngine, PromotionPolicy, ExecutionRecord

engine = PromotionEngine(policy=PromotionPolicy(min_executions=5))

engine.record_execution(
    ExecutionRecord(
        signature_hash="pipeline_fiscal_abc",
        timestamp=datetime.now(timezone.utc),
        success=True,
        cost_dbu=5.0,
        duration_seconds=30.0,
    )
)

skill, scores = engine.evaluate("pipeline_fiscal_abc")
print(skill.state.value)
print(scores.ifo, scores.ifs, scores.ifg, scores.idi)
```

The lifecycle model computes four indices:

| Index | Meaning |
| --- | --- |
| IFo | Operational fluidity: latency, cost, success rate |
| IFs | Semantic fidelity: schema health, drift, faults |
| IFg | Governance integrity: binary pass/fail signal |
| IDI | Intent drift over the evaluation window |

## Full kernel

When you need the full path from natural language to execution outcome:

```python
from cfa import KernelOrchestrator

kernel = KernelOrchestrator(catalog=catalog)
result = kernel.process("Join NFe with Clientes and persist to Silver")

print(result.state.value)
```

High-level flow:

```text
intent -> normalization -> confirmation -> policy -> planning -> codegen
-> static validation -> sandbox -> runtime validation -> partial execution
-> state projection -> audit -> lifecycle evaluation
```

Each phase can be disabled through `KernelConfig`.

## Key concepts

**StateSignature**  
Immutable execution contract capturing domain, intent, datasets, constraints, and execution context. It carries a deterministic SHA256 hash.

**ContextRegistry**  
Persistent operational context store. It is not just a log; it represents the environment state relevant to future decisions.

**Faults**  
Typed faults grouped into semantic, static, runtime, and environmental families instead of generic execution errors.

**AuditTrail**  
Append-only event chain with SHA256 hash linking for tamper detection.

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
docs/                 guide and repository-facing documents
```

## Known limitations

- The default normalizer backend is a deterministic mock.
- Code generation currently targets PySpark.
- Persistence defaults to JSON/JSONL-oriented local backends.
- Concurrency is intentionally conservative.

## Documentation

- [Usage Guide](./docs/guide.md)
- [Repository Article Draft](./docs/linkedin-article.md)
- [Examples](./examples/)
- [Project Pages](https://marquesantero.github.io/cfa/)
- [Whitepaper PT-BR](./docs/cfa-v2-whitepaper.html)
- [Whitepaper EN](./docs/cfa-v2-whitepaper.en.html)

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md).

## License

[MIT](./LICENSE)
