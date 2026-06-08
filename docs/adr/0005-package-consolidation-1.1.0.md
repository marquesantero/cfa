# ADR-0005: Consolidate the package layout in 1.1.0

* Status: accepted
* Date: 2026-06-08
* Tags: refactor, public-api, 1.1.0

## Context and Problem Statement

The 1.0.0 layout had **20 subpackages**, several of them with overlapping
responsibilities or "curated re-export" facades:

```text
src/cfa/
├── core/
├── policy/                # engine + bundle + catalog
├── governance/            # curated re-export of policy + types + validation
├── validation/            # static + runtime + signature
├── resolution/            # curated re-export of normalizer
├── normalizer/            # the actual resolver implementation
├── observability/
├── ...
```

This produced:

- Three different ways to validate a signature against rules.
- Two different ways to construct an `IntentNormalizer`.
- Long, academic-sounding package names (`observability/`,
  `validation/`) that read as boilerplate in imports.
- A `cfa.governance` module whose entire purpose was to re-export from
  three other modules.

1.0.0 had **zero real adopters** (no external pip installs of substance,
no third-party imports, no issues). The window for a free refactor was
open and clearly time-limited.

## Decision Drivers

- Shorter names that read as operations, not as architecture.
- Each surface has one obvious home, not three.
- No façade packages whose only job is re-export.
- Pragmatic on semver: 1.0.0 had no users to protect, so renames are
  direct rather than deprecation-laddered.

## Decision

Renamed and consolidated as follows in 1.1.0:

| Old | New | Note |
|-----|-----|------|
| `cfa.normalizer` + `cfa.resolution` | `cfa.resolve` | One resolver surface, lazy-loaded |
| `cfa.governance` | (absorbed into `cfa.policy`) | Curated re-export moved into `cfa.policy.__init__` |
| `cfa.validation` | `cfa.validate` | Shorter |
| `cfa.observability` | `cfa.obs` | Shorter |

`cfa.policy.__init__` now exposes:

- Engine: `PolicyEngine`, `PolicyRule`, `PolicyResult`, `build_default_ruleset`.
- Bundles: `PolicyBundle`, validation helpers.
- Catalog: `validate_catalog`.
- The former `cfa.governance` curated surface: types
  (`StateSignature`, `DatasetRef`, etc.) and validators
  (`StaticValidator`, `RuntimeValidator`).

`cfa.resolve.__init__` now exposes:

- Engine: `IntentNormalizer`, `RuleBasedNormalizerBackend`,
  `MockNormalizerBackend`, `NormalizerBackend`, `NormalizerInput`,
  `NormalizerOutput`.
- Confirmation: `ConfirmationOrchestrator`, handlers.
- LLM: `LLMNormalizerBackend`, `OpenAILMProvider` (require the `[llm]`
  extra).
- Re-exported domain types for convenience (`StateSignature`,
  `SemanticResolution`, `AmbiguityLevel`, `ConfirmationMode`).

Net result: **20 packages → 16**. The remaining redundancy
(`behavior/` + `resolve/`) is scheduled to fold during 1.3.

## Consequences

Positive:

- Imports look operational: `from cfa.resolve import IntentNormalizer`
  instead of `from cfa.normalizer.base import IntentNormalizer`.
- One canonical home per concept. Future contributors don't have to
  guess between `governance/` and `policy/`.
- The deletion is permanent — no shim folder to maintain.

Negative:

- Anyone who already imported from the 1.0.0 paths will see
  `ModuleNotFoundError`. We accepted this because the population was
  empty in practice. We added a regression test that asserts the old
  module paths raise `ImportError`, so we don't accidentally restore
  them.
- The 1.0.0 → 1.1.0 transition is technically a breaking change in
  semver terms. We documented this in `CHANGELOG.md` and the release
  notes. Strict semver (no breaking changes outside major) resumes
  the moment we see external adoption.

## Alternatives considered

- **Deprecation shims for every renamed module.** Restored briefly on
  day 2 of the 1.1.0 cycle and then removed once the "zero adopters"
  reality was acknowledged. See ADR-0006 for the analogous decision on
  fake adapters.
- **Stay at 1.0.0 layout.** Rejected — locking in confusing naming with
  no upside.
- **Major-bump (1.0 → 2.0).** Considered. Decided against because the
  consolidation is editorial; the underlying contracts (the five
  primitives in ADR-0001-0004) are unchanged. A 2.0 will come when those
  contracts evolve.

## See also

- ADR-0006 (no per-framework adapter shims — same logic, same release).
- `drafts/ROADMAP.md` — Sprint 2 detailed plan.
- [`CHANGELOG.md`](../../CHANGELOG.md) — migration notes.
