# Changelog

All notable changes to CFA are recorded here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
uses [SemVer](https://semver.org/).

Architectural decisions referenced from each release live in
[`docs/adr/`](docs/adr/).

## [Unreleased]

The work that follows 1.1.0 lays the architecture for everything
1.2.0 → 2.0 will ship. It is **purely additive**: no existing API
changes, no behavior changes, no version bump. CFA becomes a
plugin-shaped kernel where verticals (data, agent, infra, …) and
integrations (dbt, Airflow, GitHub, Slack, …) are pip-installable
external packages that the kernel discovers via Python entry points.

### Added

- Six new ADRs in `docs/adr/`:
  [0007](docs/adr/0007-layered-architecture.md) layered architecture,
  [0008](docs/adr/0008-generic-signature.md) generic `StateSignature`,
  [0009](docs/adr/0009-vertical-protocol.md) Vertical protocol,
  [0010](docs/adr/0010-integration-protocol.md) Integration + DecisionSink,
  [0011](docs/adr/0011-condition-registry.md) ConditionRegistry,
  [0012](docs/adr/0012-per-vertical-backends.md) per-vertical backends.
- `cfa.core.vertical` — `Vertical` protocol and `VerticalRegistry`
  singleton with lazy entry-point discovery via the
  `cfa.verticals` group.
- `cfa.core.integration` — `Integration` and `DecisionSink` protocols
  plus their registries (`cfa.integrations` and `cfa.decision_sinks`
  entry-point groups). `IntegrationInputError` exception for typed
  reporting of malformed input.
- `cfa.core.conditions.ConditionRegistry` — object-oriented form of the
  pre-existing module-level registry. `ConditionSpec` data class with
  `name`, `factory`, `doc`, and `expected_params`. `describe()` and
  `describe_all()` for introspection. The data-vertical conditions
  shipped today register at import time with proper docstrings and
  parameter descriptions.
- `website/docs/extending.md` — full plugin author guide for
  verticals, integrations, and decision sinks.
- `tests/contract/` — reference mock vertical, mock integration, and
  mock decision sinks that exercise the contracts end to end (34 new
  tests; 571 passing in total).

### Changed

- `cfa.core.__init__.__getattr__` now lazy-loads `Vertical`,
  `VerticalRegistry`, `Integration`, `IntegrationRegistry`,
  `DecisionSink`, `DecisionSinkRegistry`, and `IntegrationInputError`
  alongside the existing names.
- `register_condition` now emits a `DeprecationWarning` when the same
  name is silently re-registered. New code should call
  `ConditionRegistry.register(..., overwrite=True)` to make the
  intent explicit.

## [1.1.0] — 2026-06-08

The 1.1.0 cycle is editorial. There are no new features. The goal was
to remove what dilutes the project's distinctive primitives, consolidate
the package layout, and write down the decisions that drive future work.

1.0.0 had no real adopters, so this release performs breaking renames
directly rather than carrying deprecation shims. Strict semver
(breaking changes only in major) resumes the moment external adoption
appears.

### Highlights

- Package layout cut from 20 subpackages to 16 (target ~13 by 1.3).
- The five distinctive primitives (typed `StateSignature`, REPLAN as
  first-class outcome, SHA-256 audit chain, operational catalog,
  deterministic-by-default) are now documented as ADRs.
- The rule-based normalizer's hard-coded fiscal/Portuguese vocabulary
  was extracted into a runnable example
  (`examples/fiscal_pt_br_normalizer.py`).
- A perf suite at `tests/perf/` (opt-in via `--run-perf`) records
  baselines for guard overhead and evaluation throughput.

### Breaking changes

These are renames; everything still works, but imports change.

- `cfa.normalizer` and `cfa.resolution` → **`cfa.resolve`**.
  The split between "engine" and "curated re-export" is gone; both
  surfaces are now in `cfa.resolve`.

- `cfa.governance` → **absorbed into `cfa.policy`**.
  The "standalone governance" curated surface (types + `StaticValidator`
  + `RuntimeValidator`) now lives in `cfa.policy.__init__`.

- `cfa.validation` → **`cfa.validate`**.

- `cfa.observability` → **`cfa.obs`**.

- **Removed**: `cfa.adapters.langgraph`, `cfa.adapters.crewai`,
  `cfa.adapters.autogen`, `cfa.adapters.dspy`,
  `cfa.adapters.openai_agents`. These were aliases of the same
  `cfa.adapters.cfa_guard` decorator. Use `cfa_guard` directly with
  any framework. See [ADR-0006](docs/adr/0006-no-fake-adapters.md).

- **Removed**: hard-coded fiscal/Portuguese keywords from
  `RuleBasedNormalizerBackend.DEFAULT_DOMAIN_KEYWORDS`. The defaults
  are now empty; domain detection requires the caller to inject a
  vocabulary via the new `domain_keywords` constructor kwarg. See
  `examples/fiscal_pt_br_normalizer.py` for the Brazilian vocabulary
  that used to be the default.

### Added

- `docs/adr/` — six MADR-format Architecture Decision Records:
  - [0001](docs/adr/0001-typed-signature-as-contract.md) — Typed
    `StateSignature` as the universal contract.
  - [0002](docs/adr/0002-sha256-hash-chain-offline-verifiable.md) —
    SHA-256 audit chain verifiable offline.
  - [0003](docs/adr/0003-replan-as-first-class.md) — `REPLAN` as a
    first-class policy outcome.
  - [0004](docs/adr/0004-deterministic-by-default-llm-as-extra.md) —
    Deterministic decisions by default; LLM as opt-in extra.
  - [0005](docs/adr/0005-package-consolidation-1.1.0.md) — Package
    consolidation in 1.1.0.
  - [0006](docs/adr/0006-no-fake-adapters.md) — No per-framework
    adapter shims.
- `RuleBasedNormalizerBackend(layer_keywords=..., domain_keywords=...,
  intent_keywords=...)` — three injection points for tailoring the
  rule-based normalizer to a project's vocabulary.
- `examples/fiscal_pt_br_normalizer.py` — runnable example with the
  Brazilian fiscal vocabulary (NF-e, SPED, CPF, CNPJ, "ouro", "prata",
  etc.) that used to be the default.
- `tests/perf/` — opt-in performance suite.
  - `test_guard_overhead.py` — p99 of a guarded call. Baseline ~2.4 ms,
    asserts ≤ 10 ms.
  - `test_evaluate_throughput.py` — throughput of
    `cfa.testing.evaluate`. Baseline ~930 ops/sec, asserts ≥ 20.
  - Skipped by default; enable with `pytest --run-perf` or
    `CFA_RUN_PERF=1`.
- `website/docs/integrations/use-cfa-guard-with-frameworks.md` —
  single, honest integrations page replacing the five per-framework
  pages.
- `website/docs/compare.md` — side-by-side comparison against OPA,
  LangSmith / Phoenix / Patronus, Great Expectations / Soda, Unity
  Catalog / Atlan / DataHub, and dbt contracts.
- `drafts/ROADMAP.md` — the planning document driving the 1.x cycle.

### Changed

- `CFAGuard` caches the underlying `KernelOrchestrator` on first
  guarded call. Subsequent calls reuse the same kernel instance.
  Measured guarded-call p99 is now ~2.4 ms on the reference machine.
- README, `website/docs/intro.md`, and the homepage were rewritten in
  operational language (drop "Technical Whitepaper" eyebrow, drop the
  ✅/❌ marketing table, drop the Greek-letter `(Φ, Γ, Π, Ω, Σ)`
  formalization from the public whitepaper). The formal version is
  preserved in `drafts/WHITEPAPER_FORMAL.md`.
- The Docusaurus site now shows a non-closable status banner on every
  page: `1.0.0 on PyPI · 1.1.0.dev0 in progress · roadmap →`.
- LLM normalizer prompt no longer enumerates `fiscal_data_processing /
  customer_data / financial_data` as a closed list; it now asks for a
  stable snake_case identifier appropriate to the application.

### Removed

- Five per-framework adapter modules (see "Breaking changes" above).
- Docusaurus blog template content (Lorem ipsum from `yangshun` /
  `slorber`).
- Inconsistent "v1.0.0" references in `website/src/pages/index.tsx`,
  `website/docs/intro.md`, `website/docs/api.md`, `website/docs/faq.md`,
  `website/docs/whitepaper.md`.
- Planning documents at the repo root
  (`CFA_IMPLEMENTATION_PLAN.md`, `CFA_MARKET_RESEARCH_2026.md`,
  `MANUAL_TESTING_GUIDE.md`) — moved to `drafts/`.

### Fixed

- `.gitignore` patterns `*draft*` / `*DRAFT*` no longer swallow the
  entire `drafts/` folder; planning documents at the repo root are
  still ignored.

### Migration guide (1.0.0 → 1.1.0)

Find-and-replace in your code:

```text
cfa.normalizer.base       → cfa.resolve.base
cfa.normalizer.llm        → cfa.resolve.llm
cfa.resolution            → cfa.resolve
cfa.governance            → cfa.policy
cfa.validation.static     → cfa.validate.static
cfa.validation.runtime    → cfa.validate.runtime
cfa.validation.signature  → cfa.validate.signature
cfa.observability.*       → cfa.obs.*
```

For the per-framework adapters:

```python
# Before
from cfa.adapters.langgraph import cfa_guard
from cfa.adapters.openai_agents import cfa_tool_guard
from cfa.adapters.crewai import cfa_crew_guard
from cfa.adapters.autogen import cfa_agent_guard
from cfa.adapters.dspy import cfa_module_guard

# After (one decorator for everything)
from cfa.adapters import cfa_guard
```

If you relied on the rule-based normalizer recognizing Brazilian fiscal
terms ("nfe", "fiscal", "tribut", "cpf", "cadastro"):

```python
# Before
from cfa.resolve import RuleBasedNormalizerBackend
backend = RuleBasedNormalizerBackend()

# After (one option)
from examples.fiscal_pt_br_normalizer import build_fiscal_pt_br_backend
backend = build_fiscal_pt_br_backend()

# After (another option, defining your own vocabulary)
from cfa.resolve import RuleBasedNormalizerBackend
backend = RuleBasedNormalizerBackend(
    domain_keywords={"fiscal_data_processing": ["nfe", "nota fiscal", ...]},
)
```

## [1.0.0] — 2026-06-08

Initial publish to PyPI. The "API freeze" framing was premature — the
1.1.0 cycle clarifies the layout. The five primitives that distinguish
CFA (typed signature, REPLAN, hash chain, operational catalog,
deterministic-by-default) are unchanged.

## [0.1.9] and earlier

See `git log`. Pre-1.0 work.
