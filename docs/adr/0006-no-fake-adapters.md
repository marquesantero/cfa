# ADR-0006: No per-framework adapter shims

* Status: accepted
* Date: 2026-06-08
* Tags: public-api, 1.1.0, integrations

## Context and Problem Statement

CFA 1.0.0 shipped five "framework adapter" modules:

- `cfa.adapters.langgraph`
- `cfa.adapters.crewai`
- `cfa.adapters.autogen`
- `cfa.adapters.dspy`
- `cfa.adapters.openai_agents`

Each file was 15–20 lines and did exactly one thing: re-export
`cfa.adapters.cfa_guard` under a slightly different name
(`cfa_tool_guard`, `cfa_crew_guard`, `cfa_agent_guard`,
`cfa_module_guard`, and `cfa_guard` itself in the LangGraph case).

There was no framework-specific behavior in any of them.

The five modules existed because every adjacent project at the time
(LangChain, CrewAI, AutoGen, DSPy, OpenAI Agents SDK) had a corresponding
"integration" section in their docs, and CFA wanted to look feature-comparable
in marketing materials. The result was honest cost (a maintenance burden, a
test surface, a documentation page per framework) for dishonest signal
(implying integration depth that did not exist).

The first reasonable issue from any external user — "I imported
`cfa.adapters.langgraph` and it's a 19-line file?" — would have been
embarrassing. We pre-empted it.

## Decision Drivers

- Honesty in deliverables. A listed adapter must be an adapter.
- One way to do something is better than five identical ways with
  different names.
- Documentation is product. A separate doc per framework is a separate
  contract to maintain.

## Decision

1. **Remove the five framework adapter modules.** `cfa.adapters` exposes
   exactly one decorator: `cfa_guard` (and the underlying class
   `CFAGuard`). It works in any Python codebase — LangGraph nodes,
   CrewAI tasks, AutoGen agents, DSPy modules, OpenAI Agents SDK tools,
   Airflow tasks, Lambda handlers, raw scripts.
2. **Replace the five per-framework documentation pages with one
   honest page** —
   [`docs/integrations/use-cfa-guard-with-frameworks.md`](../../website/docs/integrations/use-cfa-guard-with-frameworks.md)
   — that shows the usage pattern once and lists examples per framework.
3. **Add a regression test** asserting the old module paths raise
   `ImportError`, so we don't accidentally re-introduce them.
4. **Real integrations** (different from cosmetic re-exports) live under
   `cfa.integrations.*` from 1.2 onward. The first is `cfa.integrations.dbt`
   (`cfa dbt check` reads `target/manifest.json` and runs the policy
   bundle); planned next are Airflow and Databricks Jobs. Each will
   have real, framework-specific code or it will not exist.

## Consequences

Positive:

- One decorator to learn. One doc to maintain. One file to test.
- Signal-to-noise of the `adapters/` directory is now 1:1.
- Future "is X a real integration?" questions have a clear answer:
  `cfa.integrations.X` if it does framework-specific work; otherwise
  use `cfa.adapters.cfa_guard`.

Negative:

- The 1.0.0 user who imported `from cfa.adapters.langgraph import
  cfa_guard` (population: zero in practice, but in principle) will see
  `ModuleNotFoundError`. We accept this. See ADR-0005 for the analogous
  call.
- We give up the marketing optics of a 5-adapter list. The five
  README badges we lose are replaced by one honest sentence.

## Alternatives considered

- **Keep as deprecation shims with `DeprecationWarning`.** Briefly tried
  on day 2 of the 1.1.0 cycle. Removed once the "zero adopters" reality
  was acknowledged — same logic as ADR-0005.
- **Add real framework-specific behavior to each.** Would have justified
  the modules but requires building five separate integrations to a
  similar quality level. Way out of scope for a solo maintainer at this
  stage. We may revisit one or two of these as actual
  `cfa.integrations.*` modules later if there is demand.

## See also

- ADR-0005 (the package consolidation that hit the same logic).
- [`docs/integrations/use-cfa-guard-with-frameworks.md`](../../website/docs/integrations/use-cfa-guard-with-frameworks.md).
- [`src/cfa/adapters/__init__.py`](../../src/cfa/adapters/__init__.py).
