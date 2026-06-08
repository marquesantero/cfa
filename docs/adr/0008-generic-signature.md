# ADR-0008: Generic `StateSignature` with vertical + payload + constraints

* Status: accepted
* Date: 2026-06-08
* Tags: types, public-api, breaking-change

## Context and Problem Statement

The 1.1.0 `StateSignature` is shaped for the data vertical:

```python
@dataclass(frozen=True)
class StateSignature:
    domain: str
    intent: str
    target_layer: TargetLayer            # data-specific enum
    datasets: tuple[DatasetRef, ...]     # data-specific
    constraints: SignatureConstraints    # data-specific fields
    execution_context: ExecutionContext
    ...
```

That worked while CFA was a data tool. With the layered architecture in
ADR-0007, the kernel is no longer a data tool — it is a generic decision
layer that hosts verticals. The shape above bakes one vertical into the
kernel.

We need a `StateSignature` that:

- has the same identity guarantees (frozen, deterministic hash, lossless
  serialization);
- knows which vertical it belongs to;
- carries a typed-but-generic payload + constraints that each vertical
  defines via JSON Schema;
- stays hashable, comparable, and round-trippable across processes and
  languages.

## Decision Drivers

- Backward compatibility for serialized `StateSignature` JSON during the
  1.x line — a 1.1.0 signature should still parse in 1.2.0.
- Hash stability for signatures whose payload contents are unchanged.
- No domain knowledge in `cfa.types`. The data fields must move into
  `cfa.verticals.data`.
- JSON Schema is the canonical validation contract for `payload` and
  `constraints` (single source of truth, language-agnostic, future
  cross-SDK story).

## Decision

`StateSignature` becomes:

```python
@dataclass(frozen=True)
class StateSignature:
    vertical: str                            # "data", "agent", "infra", …
    domain: str                              # vertical-defined scope identifier
    intent: str                              # vertical-defined operation identifier
    payload: Mapping[str, Any]               # JSON-serializable, validated by vertical
    constraints: Mapping[str, Any]           # JSON-serializable, validated by vertical
    execution_context: ExecutionContext      # unchanged (kernel-level versioning)
    intent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=_utcnow)
    source_intent_raw: str = ""

    @property
    def signature_hash(self) -> str:
        payload = {
            "vertical": self.vertical,
            "domain": self.domain,
            "intent": self.intent,
            "payload": _canonicalize(self.payload),
            "constraints": _canonicalize(self.constraints),
        }
        return sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
```

Where:

- `Mapping[str, Any]` is JSON-serializable. Tuples and frozensets get
  converted to lists during canonicalization to keep the hash stable.
- `_canonicalize` recursively sorts keys, normalizes datetimes to
  ISO-8601, and converts enums to their `.value`.
- Verticals provide JSON Schemas (`payload_schema()`,
  `constraints_schema()`) that are applied at signature construction
  time. Invalid payloads raise `SignatureValidationError` with the
  failing JSON Pointer.

### Backward compatibility for 1.x

`cfa.verticals.data` ships a `from_legacy_dict` classmethod and a
`build_data_signature(...)` helper that produce a generic
`StateSignature` from the old typed inputs (`DatasetRef`, `TargetLayer`,
etc.). Existing 1.1 JSON shapes parse via a one-shot migration in
`StateSignature.from_dict`:

```python
@classmethod
def from_dict(cls, data: dict[str, Any]) -> StateSignature:
    if "vertical" not in data:
        # Legacy 1.1 shape — translate to data vertical.
        from cfa.verticals.data.migration import migrate_legacy_signature
        data = migrate_legacy_signature(data)
    ...
```

The migration is loss-free and deterministic — same legacy input always
produces the same generic signature. The signature hash is **not**
preserved across the migration (it cannot be — the hashed payload is
literally different), but a `legacy_signature_hash` is recorded inside
`execution_context` for chain-of-custody.

### Hash stability rules

- `payload` and `constraints` are normalized into canonical JSON before
  hashing. Same content → same hash, irrespective of insertion order or
  Python container types.
- Adding a new field to a vertical's schema does **not** automatically
  change the hash. If the field is absent in older signatures, the
  canonicalization treats it as absent; the hash matches. Verticals
  document explicitly which fields are hash-relevant.

## Consequences

Positive:

- The kernel has no idea what a "dataset" is. Adding the agent vertical
  does not touch `cfa.types`.
- JSON Schema gives us validation, IDE hints (via generated `.pyi`
  stubs), and the cross-language story for the future CFA Protocol.
- A signature can travel through any system that handles JSON.

Negative:

- 1.1 callers that read `signature.datasets` or `signature.target_layer`
  directly need to update to `signature.payload["datasets"]` etc., or
  use the typed helpers in `cfa.verticals.data` (e.g.,
  `data.unpack(signature)` returns the dataclass shape).
- `Mapping[str, Any]` is less self-documenting than typed fields. The
  JSON Schemas and the per-vertical helper modules are how we recover
  ergonomics.
- The legacy migration is a one-off compat layer in 1.x. It is removed
  in 2.0 along with all 1.x deprecation surface.

## Alternatives considered

- **Generic `StateSignature` parameterized by `TypeVar`.** Cleaner in
  Python, but doesn't survive serialization or cross-language use.
- **Keep typed `StateSignature` and add a `payload` escape hatch.**
  Doesn't actually decouple — the kernel still imports the data types
  to satisfy typing.
- **Protobuf-shaped Message base.** Pulls in a binary serialization
  dependency and reading-by-grep gets harder. Worth revisiting at 2.0
  if we ship cross-language SDKs.

## See also

- ADR-0001 (the original typed-contract decision; this ADR supersedes the
  data-shaped fields in 0001 while preserving every other property —
  immutability, deterministic hashing, lossless serialization).
- ADR-0007 (layered architecture — why generic is required).
- ADR-0009 (Vertical protocol — where the JSON Schemas live).
