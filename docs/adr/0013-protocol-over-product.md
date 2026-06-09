# ADR-0013: Protocol over product — dual-track substrate + relevance

* Status: accepted
* Date: 2026-06-08
* Tags: strategy, releases, governance

## Context and Problem Statement

CFA enters 2026 with three honest signals:

1. **The technical foundation is solid.** 599 tests, plugin contracts
   wired (ADR-0007 .. 0012), vertical-aware `StateSignature`
   (ADR-0008), shipped reference vertical `cfa.verticals.data`.
2. **The AI-era window is short.** Frameworks become hot and get
   abandoned in months, not years. LangChain → LangGraph → MCP
   shifted in 18 months. Cursor went from launch to category leader
   in 12. Anything that depends on a current framework to be
   relevant ages out at the same speed.
3. **CFA must do both — long-game substrate AND short-term
   relevance.** A pure substrate play (protocol spec, no
   integrations) gets ignored. A pure relevance play (chase the
   integration of the week) gets abandoned with the integration.

The trap to avoid: optimizing one at the expense of the other.

## Decision Drivers

- The AI era compresses adoption windows. We cannot wait 18-24
  months for "becoming reference"; the tooling ecosystem reshapes
  faster than that.
- Substrate-shaped projects (SQLite, Postgres, Markdown, OAuth, MCP)
  survive multiple hype cycles because their core is a **protocol**
  with reference implementations, not a framework.
- Adoption-shaped projects (most OSS libraries) die when their
  framework-of-attachment dies.
- CFA's distinctive primitives — content-hashed signature, REPLAN
  with structured remediation, offline-verifiable audit chain — are
  more valuable as a **shared format** than as a single Python
  library.
- A solo maintainer cannot win on framework chase or on protocol
  evangelism alone. Both have to be optimised in parallel, in
  every release.

## Decision

**Every CFA release ships two things together:**

1. A **substrate** deliverable — a spec, a portability proof, a
   protocol version, a conformance test, or a stability guarantee.
   This is the bet that CFA survives the next hype cycle.
2. An **adoption** deliverable — a concrete, useful, immediately
   shippable integration or demo aimed at the current ecosystem.
   This is the bet that CFA matters this quarter.

The two reinforce each other: the adoption deliverable drives people
to try CFA; the substrate deliverable gives them a reason to bet on
it.

### The protocol becomes the product

We elevate **CFA Protocol** from a 2.0 aspirational item to a
first-class deliverable starting in 1.2.0:

- A separate repository `cfa-protocol` holds the spec (JSON Schema
  for signatures, audit chain format, decision result schema,
  policy bundle schema), conformance tests, and an `examples/`
  directory.
- Each `cfa-kernel` release that changes the protocol bumps a
  protocol version number independently from the kernel's library
  version (e.g., `cfa-kernel 1.4.0` ships `cfa-protocol 0.4`).
- The protocol is what third-party tools implement. The Python
  kernel is *one implementation*, not *the* implementation.

### Reference implementations in multiple languages

Single-language libraries don't make substrates. By 1.5.0:

- The Python kernel (`cfa-kernel`) — full reference implementation.
- A standalone Go binary `cfa-verify` — verifies audit chains and
  signatures from any conforming producer without requiring a
  Python interpreter. Proof of portability.
- A TypeScript signature builder + audit-chain consumer —
  demonstrates the protocol's reach into the JS/agent ecosystem.

These are **not** ports of the Python kernel. They are
implementations of the protocol. Their existence proves the
protocol is portable.

### Verticals as specs, not code

Each shipped vertical (`data`, future `agent`, future `infra`)
publishes its JSON Schemas as part of the protocol spec. A
third-party implementing the agent vertical in Rust can use the same
schemas as the Python implementation. The vertical name + schema is
the contract; the code is one realisation.

### Stability as a strategy

From 1.2.0 onward, the **kernel public API is stable**. New
behavior lands as new verticals, integrations, or sinks — never as
modifications to existing surfaces. This is the substrate's
defining property: code written against CFA in 2026 still works in
2030.

### Release cadence

Six-to-eight weeks per minor release. Each minor pairs:

- One substrate deliverable (spec advance, portability proof, or
  stability milestone).
- One adoption deliverable (production-ready integration, demo, or
  case study).

## Consequences

Positive:

- The project survives the framework of the week dying. If dbt is
  replaced, `cfa-int-dbt` becomes a maintenance package; `cfa-int-<successor>`
  ships next. The protocol is untouched.
- New implementers (third parties writing CFA-compatible tools)
  don't have to take a dependency on `cfa-kernel`. They implement
  the spec. The substrate game becomes winnable solo because
  contributions arrive as spec implementations elsewhere, not as PRs
  here.
- Each release has a concrete adoption hook (an integration to try
  in 5 minutes) AND a permanence story (the spec advance), satisfying
  both the "try it" and "bet on it" audiences.
- The maintainer can shift effort between substrate and adoption
  cycles without abandoning either. When energy is low, fewer
  integrations ship but the spec keeps advancing; when energy is
  high, multiple integrations land against an unchanging spec.

Negative:

- More effort per release. Two deliverables instead of one. We
  accept the cost as the price of dual-track survival.
- Protocol governance becomes a thing we own (spec proposals,
  conformance tests, versioning). We mitigate by keeping the
  governance lightweight (no formal committee until 2.0).
- Some integrations will be subsidized by the kernel (we have to
  write them ourselves at first) before the ecosystem produces
  them. Same problem every protocol bootstrap has; not unique to
  CFA.

## Alternatives considered

- **Pure substrate.** Ship `cfa-protocol` only; no integrations
  beyond the data vertical. Result: invisible. No one tries it,
  no one implements it. Substrates need at least one
  demonstrably-useful implementation to bootstrap.
- **Pure adoption.** Ship integrations as fast as possible, no
  protocol work. Result: aged out by the framework cycle.
  Implementations become technical debt within a year.
- **Two separate projects.** A "protocol" project and a "kernel"
  project shipped independently. Considered, rejected — at our
  scale, the cognitive overhead of two repos exceeds the benefit.
  We can publish the protocol as a sub-deliverable inside the
  kernel repo until size justifies the split.

## See also

- ADR-0007 (layered architecture — the structural pre-condition for
  this strategy).
- ADR-0008 (generic StateSignature — the central piece of the spec).
- ADR-0009/0010 (Vertical / Integration protocols — the extension
  contracts the spec formalizes).
- `drafts/ROADMAP.md` — the operational expression of this ADR.
