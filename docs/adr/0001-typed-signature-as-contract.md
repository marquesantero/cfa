# ADR-0001: StateSignature as the universal typed contract

* Status: accepted
* Date: 2026-06-08
* Tags: types, public-api, primitives

## Context and Problem Statement

Every interface that asks CFA for a decision needs a shared shape: CLI,
MCP, decorator, runtime gate, dbt integration, Airflow operator. We need a
single representation of "what the caller wants done" that:

- can be serialized and reproduced across processes;
- carries enough metadata to drive policy decisions (PII columns,
  partitioning, classification, target layer, merge keys);
- can be content-hashed so that the same logical intent always yields the
  same identifier — enabling cache, replay, and idempotency.

Two obvious alternatives:

1. **Untyped dict.** Pass `{"intent": "...", "datasets": [...], ...}`
   everywhere. Easy to start; brittle as the system grows.
2. **Free-form strings + LLM coercion.** Push everything through a
   normalizer at every boundary. Non-deterministic, expensive, brittle.

## Decision Drivers

- The decision path must be **a pure function**: same inputs → same
  decision → same hash → same audit event.
- The shape must be expressible by *non-LLM* sources (CLI, MCP, dbt
  manifest, Airflow operator) without translation overhead.
- The shape must be immutable after construction; any policy-driven
  remediation should create a new instance, not mutate the original.
- Serialization round-trip must be lossless and stable across versions.

## Decision

CFA exposes a single typed dataclass — `cfa.types.StateSignature` — as
the universal contract for every governance request.

```python
@dataclass(frozen=True)
class StateSignature:
    domain: str
    intent: str
    target_layer: TargetLayer            # bronze | silver | gold
    datasets: tuple[DatasetRef, ...]     # tuples, not lists
    constraints: SignatureConstraints
    execution_context: ExecutionContext
    intent_id: str = uuid4
    created_at: datetime
    source_intent_raw: str = ""
```

Key invariants:

- `frozen=True`. Any change generates a new instance via
  `with_constraints(...)`.
- `signature_hash` is SHA-256 over a canonicalized payload (sorted keys,
  enum `.value`, sorted dataset names). Same content → same hash.
- `to_dict()` / `from_dict()` are symmetric and lossless.
- Every other surface (resolver, normalizer, MCP server, dbt integration,
  CLI) produces *or consumes* this dataclass — nothing else.

## Consequences

Positive:

- All decision and audit code can rely on stable types; no runtime guard
  rails to defend against malformed dicts.
- Hashing is trivially deterministic across processes and languages
  (because we control the canonical form).
- Adding a new front-end means "build this dataclass"; nothing else
  changes downstream.

Negative:

- Schema evolution is governed by semver — adding required fields is a
  breaking change. We chose `frozen=True`, which makes evolution
  visible.
- Some callers will want to send extra metadata not in the schema. We
  added `SignatureConstraints.custom: dict[str, Any]` as the escape
  hatch, with explicit policy that it is not part of the hash payload.

## Alternatives considered

- **Pydantic models.** Adds a runtime dependency. We rejected this for
  the core; we'd rather keep the core dependency-free and let downstream
  build Pydantic adapters if they want.
- **Protobuf / Avro.** Solves cross-language for free but adds tooling
  weight that's unjustified for the current ICP.
- **Open schema (dict).** Rejected — see context.

## Open questions

- A Protocol-shaped (CFA Protocol) JSON Schema spec is planned for the
  2.0 cycle; that will be the cross-language contract. `StateSignature`
  remains the Python truth source until then.

## See also

- [`src/cfa/types.py`](../../src/cfa/types.py)
- ADR-0002 (hash chain), ADR-0003 (REPLAN), ADR-0004 (determinism).
