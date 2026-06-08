# ADR-0002: SHA-256 audit chain, verifiable offline

* Status: accepted
* Date: 2026-06-08
* Tags: audit, security, primitives

## Context and Problem Statement

CFA's main value proposition is that every governance decision is provable
after the fact. The audit log can't be "you trust the database"; it has to
survive subpoena, internal compliance review, and a hostile reviewer.

Constraints we hit when looking at off-the-shelf options:

- We do not want a runtime dependency on a remote audit service (a vendor
  could disappear, lose access, change terms).
- We do not want to require a network call on the critical path of a
  decision.
- We want a forensic reviewer to be able to verify the chain without our
  code being installed, ideally with `sha256sum` and a JSON parser.

## Decision Drivers

- **Offline verifiability.** No server, no key, no internet.
- **Deterministic.** Same event content → same hash.
- **Tamper-evident.** Modifying any event invalidates every event after
  it.
- **Storage-pluggable.** In-memory for tests, JSONL for production, SQLite
  for queries, future S3/Kafka for scale — all behind one interface.

## Decision

`cfa.audit.AuditTrail` records every event as `AuditEvent` and links
events through a SHA-256 hash chain:

```python
event.previous_hash = trail.last_hash
event.event_hash = sha256_canonical(event)   # excludes own event_hash
trail.last_hash = event.event_hash
```

The canonicalization:

- JSON dump with `sort_keys=True`, `default=str` (datetimes → ISO).
- Includes `intent_id`, `stage`, `event_type`, `outcome`, `timestamp`,
  `previous_hash`, and `details`.
- Excludes `event_hash` itself.

`AuditTrail.verify_chain()` recomputes each event's hash, checks the
linkage, and returns a single boolean. It works on any
`AuditStorageBackend` implementation:

- `InMemoryAuditStorage` for tests.
- `JsonLinesAuditStorage` for production filesystem audits.
- `SqliteStorage` (via `cfa.storage`) for queryable history.

A legacy hash variant is accepted for verification only — events written
by pre-3.1 versions used a truncated hash. We do not write that form
anymore.

## Consequences

Positive:

- Verifying an audit trail off the production host is trivial. The JSONL
  file is self-contained.
- New storage backends do not break the chain — they only need to honor
  the append-only contract.
- Zero coupling to a vendor.

Negative:

- No global ordering across intents. The chain is per-`AuditTrail`
  instance; concurrent writers need synchronization. We chose this on
  purpose to keep verification trivial.
- Rewriting the canonicalization is a breaking change (the hash differs).
  Any change here has to bump major. Compensating for the pre-3.1
  variant via `_compute_hash_legacy` was the first and (we hope) last
  exception.
- The chain protects integrity, not confidentiality. Sensitive payloads
  must be hashed or omitted by the caller before they enter `details`.

## Alternatives considered

- **Use a transparency log (Sigstore / Rekor).** Powerful, but pulls in a
  network dependency and operational complexity we don't need at this
  stage. Worth reconsidering at 2.x if a hosted CFA story emerges.
- **HMAC instead of SHA-256.** Adds key management. Doesn't add value
  for the threat model we care about (tamper detection, not access
  control).
- **Blockchain.** No.

## See also

- [`src/cfa/audit/trail.py`](../../src/cfa/audit/trail.py)
- `cfa audit verify` CLI command
- ADR-0001 (signature hash uses the same canonicalization style).
