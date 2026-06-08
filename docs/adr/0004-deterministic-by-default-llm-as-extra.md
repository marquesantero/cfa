# ADR-0004: Deterministic decisions by default; LLM as opt-in extra

* Status: accepted
* Date: 2026-06-08
* Tags: design-principles, public-api

## Context and Problem Statement

CFA targets governance decisions. Governance has to be:

- reproducible across runs of the same input;
- explainable to a non-LLM auditor;
- testable without network or per-call cost;
- offline-capable.

LLMs are the opposite of all four. They are non-deterministic, expensive,
networked, and opaque. They also happen to be very good at the *front
edge* of CFA — turning a sentence into a typed `StateSignature`. So we
need to keep them around without letting them poison the decision path.

## Decision Drivers

- A decision must remain a pure function of `(StateSignature, policy_bundle,
  catalog)`. Inputs in → decision out. Always.
- An LLM may participate, but only as a *resolver* on the way in. Once
  the `StateSignature` is constructed, the LLM has done its job.
- Tests must be able to run offline. CI must not require an API key.

## Decision

The kernel's critical path is deterministic. Everything LLM-shaped is on
the input side and is a pluggable backend.

```text
raw_intent → [NormalizerBackend] → StateSignature → [PolicyEngine] → decision
                  ▲                                      ▲
                  │                                      │
    optional, pluggable                       pure function — never LLM
    (rule-based default; LLM extra)
```

Implementation:

- `cfa.resolve.NormalizerBackend` is the abstract interface for
  resolution. The production default is `RuleBasedNormalizerBackend` —
  catalog-grounded, English-default keyword maps, fully deterministic.
- `cfa.resolve.llm` is the LLM backend (OpenAI-compatible providers). It
  is gated by the `[llm]` optional extra in `pyproject.toml` and never
  imported from the core path.
- `cfa.testing` patches `_detect_llm_backend` to return `None` during
  test runs to keep the suite hermetic.
- The CLI defaults to `--normalizer auto`, which prefers the rule-based
  backend unless `OPENAI_API_KEY` / `DEEPSEEK_API_KEY` is set explicitly.

The five primitives (signature, REPLAN, hash chain, operational catalog,
determinism) are independent of LLM. Removing the LLM extra leaves CFA
functional.

## Consequences

Positive:

- The decision path is reviewable line-by-line — no embeddings, no
  prompts, no probabilities to interpret.
- CI is fast, free, and offline.
- Compliance reviewers can run `cfa audit verify` on a JSONL file and
  reconstruct exactly what happened.
- The LLM surface can evolve aggressively (prompt updates, new
  providers) without touching the kernel.

Negative:

- The rule-based normalizer is intentionally simple. It is *not* a
  semantic oracle. Underspecified intents fall through to "general"
  domain and lower confidence, which the kernel surfaces clearly. We
  consider this honest; some users will read it as "weak."
- LLM-specific features (semantic disambiguation, multi-language) live
  behind an extra and are easier to miss.

## Alternatives considered

- **LLM in the policy engine.** Rejected — see context. The decision
  must be replayable from JSON.
- **Two parallel kernels (deterministic / LLM).** Rejected — doubles
  surface, halves clarity.
- **LLM-required default.** Rejected — would require an API key for any
  CI to run. Ships poorly to regulated customers.

## See also

- [`src/cfa/resolve/base.py`](../../src/cfa/resolve/base.py)
- [`src/cfa/resolve/llm.py`](../../src/cfa/resolve/llm.py)
- [`pyproject.toml`](../../pyproject.toml) — `[project.optional-dependencies] llm = ...`
- ADR-0001, ADR-0003 (the typed contract + REPLAN make this division
  cheap to enforce).
