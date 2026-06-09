# Architecture Decision Records

Each significant architectural decision in CFA is recorded as a small,
dated markdown file in this directory. The format is [MADR](https://adr.github.io/madr/)-lite:
context, decision drivers, decision, consequences, and (when relevant)
alternatives considered.

## Why ADRs?

Decisions tend to look obvious in retrospect — until someone proposes
the opposite a year later. Writing the *why* down lets future contributors
(including future-Antero) understand the trade-offs that were taken without
having to dig through commits.

## Conventions

- Numbered sequentially, four digits: `0001-…`, `0002-…`.
- Kebab-case slug after the number.
- Each ADR has a single status: `proposed`, `accepted`, `deprecated`, or
  `superseded by ADR-NNNN`.
- Superseded ADRs stay in the repo. They are not deleted; new decisions
  reference them.
- Length: ideally one screen. Long contexts mean the ADR is doing two
  things; split it.

## Index

| # | Title | Status |
|---|-------|--------|
| [0001](./0001-typed-signature-as-contract.md) | StateSignature as the universal typed contract | accepted |
| [0002](./0002-sha256-hash-chain-offline-verifiable.md) | SHA-256 audit chain, verifiable offline | accepted |
| [0003](./0003-replan-as-first-class.md) | REPLAN as a first-class policy outcome | accepted |
| [0004](./0004-deterministic-by-default-llm-as-extra.md) | Deterministic decisions by default; LLM as opt-in extra | accepted |
| [0005](./0005-package-consolidation-1.1.0.md) | Consolidate the package layout in 1.1.0 | accepted |
| [0006](./0006-no-fake-adapters.md) | No per-framework adapter shims | accepted |
| [0007](./0007-layered-architecture.md) | Layered architecture: kernel / contracts / verticals / integrations | accepted |
| [0008](./0008-generic-signature.md) | Generic `StateSignature` with vertical + payload + constraints | accepted |
| [0009](./0009-vertical-protocol.md) | Vertical protocol and registry via entry points | accepted |
| [0010](./0010-integration-protocol.md) | Integration protocol and DecisionSink | accepted |
| [0011](./0011-condition-registry.md) | `ConditionRegistry` as the canonical way to attach policy rules | accepted |
| [0012](./0012-per-vertical-backends.md) | Backends scoped per-vertical | accepted |
| [0013](./0013-protocol-over-product.md) | Protocol over product — dual-track substrate + relevance | accepted |

## Adding a new ADR

1. Pick the next number.
2. Copy the format used by an existing ADR (e.g. 0001).
3. Open a PR. Mark status `proposed`.
4. After feedback, flip to `accepted` (or `rejected` and merge anyway with
   that status as record).
5. Update this index.

For background, see the [MADR project](https://adr.github.io/madr/) and
[Michael Nygard's original post](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions).
