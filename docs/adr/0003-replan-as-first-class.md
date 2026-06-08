# ADR-0003: REPLAN as a first-class policy outcome

* Status: accepted
* Date: 2026-06-08
* Tags: policy, primitives, public-api

## Context and Problem Statement

Every existing policy engine we surveyed answers the same way: `allow` or
`deny` (sometimes with a structured reason). That's enough for an admission
controller; it's not enough for a governance gate that wants to *help*
agents and pipelines recover.

Concrete example. An LLM agent asks: "join NF-e with clientes and persist
to Silver." The agent forgot to declare `no_pii_raw=True`. Two responses
are possible:

1. **`deny`.** "PII detected in protected layer." The agent now has to
   reverse-engineer the rule.
2. **A structured response that names the fix.** "REPLAN. Set
   `constraints.no_pii_raw=True` and reapply `sha256()` on PII columns
   before the join." The agent applies the suggestion, re-submits, and
   the request goes through.

CFA targets workflows where the second response is the productive one.

## Decision Drivers

- LLM-driven callers need actionable feedback — strings the model can
  parse and act on.
- Human callers (CI checks, developer tooling) also benefit: errors come
  with `pip install`-style remediation snippets.
- The shape must stay typed, not free-form text.
- The recovery loop must terminate. There must be a way to say "no more
  replans; this is blocked."

## Decision

`cfa.types.PolicyAction` is a three-way enum: `APPROVE`, `REPLAN`,
`BLOCK`. `PolicyResult` carries:

```python
@dataclass
class PolicyResult:
    action: PolicyAction
    faults: list[Fault]
    interventions: list[str]   # de-duped remediation strings
    replan_count: int
    reasoning: str
```

`Fault` carries `remediation: tuple[str, ...]` per occurrence; the engine
collects, de-duplicates, and returns them in `interventions` when the
action is `REPLAN`.

`PolicyEngine.evaluate(signature, replan_count)` enforces a hard cap on
the recovery loop. Default `max_replan_attempts=3`; once that's reached,
the engine returns `BLOCK` with code `POLICY_MAX_REPLAN_EXCEEDED`.

The kernel orchestrator (`cfa.core.kernel.KernelOrchestrator`) drives the
loop: it consumes interventions, generates a new `StateSignature`, and
re-evaluates until `APPROVE` or `BLOCK`. Each cycle is captured in
`KernelResult.replan_history`.

## Consequences

Positive:

- LLM agents using CFA via MCP get actionable feedback. Same for dbt
  check, Airflow operator, decorator.
- The recovery loop is bounded and visible; replan history is part of the
  audit trail.
- Rule authors think about *fix-and-retry* upfront, not just
  *allow-or-deny*.

Negative:

- Rule authors need to actually write good remediation strings. We added
  validation at policy bundle load time to catch missing
  `remediation` fields when the action is `replan`.
- The kernel is more complex than a simple "evaluate once" engine. The
  complexity sits in one place (`KernelPhases.govern`) and we accepted
  that.
- Auto-remediation on the kernel side is intentionally conservative —
  CFA does not silently mutate user intent; it produces a new
  `StateSignature` for transparency.

## Alternatives considered

- **`allow` with warnings.** Hides the issue. The agent / pipeline runs;
  the audit pile fills with green checks; nobody reads them.
- **Single-string "advice" field.** Doesn't compose. We already had to
  collect across rules; might as well make it a list.
- **External webhook for remediation.** Adds latency, network surface,
  failure modes. Out of scope.

## See also

- [`src/cfa/types.py`](../../src/cfa/types.py) — `PolicyAction`,
  `PolicyResult`, `Fault`
- [`src/cfa/policy/engine.py`](../../src/cfa/policy/engine.py)
- ADR-0001 (signature is what gets re-emitted).
