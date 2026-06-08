# ADR-0007: Layered architecture — kernel / contracts / verticals / integrations

* Status: accepted
* Date: 2026-06-08
* Tags: architecture, plugins, public-api

## Context and Problem Statement

CFA started as a tool for governing data writes because the maintainer is a
data engineer and the data vertical had clear primitives to test against
(PII, partitions, classifications, layers). The kernel itself, however,
never depended on the idea of "data": it sits between *intent* and
*execution* and is structurally indifferent to what is being executed.

If CFA stays a "data tool" in code, every new vertical (agent tool calls,
infrastructure plans, financial transactions, schema migrations, ML model
deploys) requires changing the kernel. That is the opposite of what the
project should be — the kernel should be **closed for modification but
open for extension** ([Open/Closed Principle](https://en.wikipedia.org/wiki/Open%E2%80%93closed_principle)),
so a new vertical or integration ships as a separate package and registers
itself.

## Decision Drivers

- New verticals and integrations must land as **additive** packages, never
  as core modifications.
- Third parties must be able to publish verticals and integrations to PyPI
  that CFA discovers automatically.
- The kernel must never import from a vertical or integration — only the
  other direction.
- Migration from today's data-coupled types to a generic kernel must keep
  the data vertical working as a first-class shipped citizen.

## Decision

CFA is organised into **five layers**, with dependencies flowing strictly
downward (a higher layer may import from a lower layer; the reverse is
forbidden):

```text
┌─────────────────────────────────────────────────────────────────┐
│ Layer 5 — Integrations          dbt · Airflow · GitHub · …      │
│ Each: external input → Signature builder + DecisionSink         │
├─────────────────────────────────────────────────────────────────┤
│ Layer 4 — Backends (per vertical)                               │
│ cfa.verticals.<X>.backends — codegen/exec specific to vertical  │
├─────────────────────────────────────────────────────────────────┤
│ Layer 3 — Verticals                                             │
│ cfa.verticals.data · cfa.verticals.agent · third-party packages │
│ Each: payload/constraint schema · named conditions · default    │
│       rules · optional catalog schema                           │
├─────────────────────────────────────────────────────────────────┤
│ Layer 2 — Contracts (the only API verticals/integrations need)  │
│ Vertical · Integration · DecisionSink · BackendRegistry         │
│ ConditionRegistry · CatalogLoader · NormalizerBackend           │
├─────────────────────────────────────────────────────────────────┤
│ Layer 1 — Kernel (zero vertical knowledge)                      │
│ KernelOrchestrator · 5 phases · PolicyEngine · StateSignature   │
│ AuditTrail · Fault · PolicyAction · DecisionState               │
└─────────────────────────────────────────────────────────────────┘
```

**The rule of thumb.** A grep for `from cfa.verticals` or `from cfa.integrations`
inside `cfa.core/`, `cfa.policy/`, `cfa.audit/`, `cfa.types`, or
`cfa.resolve/` must return zero results, forever. Lint enforces it from
Phase 1 onward (a custom Ruff rule or a simple `tests/test_no_back_imports.py`).

**Verticals** ship inside `cfa-kernel` (e.g., `cfa.verticals.data`) when
they are part of the project's first-party scope. Third-party verticals
are separate distributions that register via Python entry points
(see ADR-0009).

**Integrations** are equally pluggable. They depend on the vertical they
target plus the public kernel API — never on internal modules. They
register via entry points (see ADR-0010).

## Consequences

Positive:

- A new vertical (or integration) is a new pip package. No PR in the
  core. No coupling between verticals.
- The kernel can evolve internally without breaking verticals as long as
  the contracts in Layer 2 are preserved.
- Third parties have a clear extension contract. Builds the conditions
  for an ecosystem.
- Each layer is independently testable.

Negative:

- The kernel API surface freezes around the Layer 2 contracts. Changes
  to those contracts become breaking (2.x territory).
- A vertical author has to read three to four protocols before they
  start. We mitigate this with the "Extending CFA" guide and the
  reference mock vertical in `tests/contract/`.
- Entry-point discovery is slightly slower than direct imports. We make
  it lazy (registry queries trigger discovery, not import time).

## Alternatives considered

- **Keep everything in `cfa.types` and accept coupling.** Rejected — the
  whole point of the project is that the kernel is the asset, not the
  data domain.
- **Mono-repo with subpackages but no contract layer.** Rejected — the
  hard part is the contract, not the file layout.
- **Build a single generic "policy engine" and let users wire everything
  themselves.** Rejected — that is OPA, and OPA already exists.
  CFA's value is that the typed contracts ship pre-built.

## See also

- ADR-0008 — generic `StateSignature` (the contract every vertical extends).
- ADR-0009 — Vertical protocol + registry.
- ADR-0010 — Integration protocol + DecisionSink.
- ADR-0011 — ConditionRegistry hardening.
- ADR-0012 — Per-vertical backends.
