# CFA FAQ

This FAQ is meant to help technical readers understand what CFA is, what it solves, how it works, and how to start evaluating it in practice.

For deeper architectural debates, open questions, and unresolved tradeoffs, see [Open Questions](./open-questions.md).

---

## 1. What is CFA?

CFA, or **Contextual Flux Architecture**, is a governed execution architecture for AI-native systems.

Its main idea is simple:

- natural-language intent should not go straight into operational action
- intent should first become a typed contract
- that contract should pass through policy, validation, and execution control
- approved effects should be projected back into system state

In short, CFA treats AI-driven execution as a governed state transition problem rather than as a prompt-routing problem.

---

## 2. What problem does CFA solve?

CFA is aimed at the gap between:

- AI as a conversational interface
- AI as an operational actor inside real systems

Many current agentic systems can call tools and finish tasks. They are much weaker at:

- enforcing governance before execution
- keeping an explicit model of state
- handling partial failure
- deciding what should count as valid context afterward

That is the gap CFA tries to close.

---

## 3. How is CFA different from a typical agent framework?

Most agent frameworks are centered around:

- prompts
- tool calls
- skills
- memory
- orchestration flows

CFA is centered around:

- formalized intent
- policy
- validation
- execution semantics
- state projection
- auditability

You can still build agentic behavior around CFA, but the architecture itself is not primarily about agent identity. It is about execution discipline.

---

## 4. What is a `StateSignature`?

`StateSignature` is the core contract type in CFA.

It formalizes an intended operation using fields such as:

- domain
- intent
- target layer
- input datasets
- constraints
- execution context

That makes intent something the system can:

- validate
- hash
- audit
- replan
- compare across executions

---

## 5. Why is intent formalization so important?

Because operational systems should not execute directly from an implicit interpretation of text.

Once intent is formalized, the system can distinguish between:

- what was requested
- what was understood
- what was allowed
- what was executed

Without that step, governance and audit become much weaker.

---

## 6. What does the `IntentNormalizer` do?

The `IntentNormalizer` transforms natural-language input into a typed semantic result.

That result includes:

- a `StateSignature`
- a confidence score
- an ambiguity level
- a confirmation mode

This stage exists so the rest of the system works on a contract instead of on raw prompt text.

---

## 7. What is the `ConfirmationOrchestrator` for?

It decides whether a normalized request can proceed automatically or should require stronger confirmation.

This is useful when:

- confidence is low
- ambiguity is high
- protected data is involved
- target scope is sensitive

Instead of treating human escalation as an exception, CFA treats it as an architectural mode.

---

## 8. What does the `PolicyEngine` do?

The `PolicyEngine` evaluates a `StateSignature` against declarative rules and returns one of three outcomes:

- `APPROVE`
- `REPLAN`
- `BLOCK`

It is the main pre-execution governance gate in CFA.

Typical policy concerns include:

- PII handling
- merge semantics
- partition requirements
- type enforcement
- cost guardrails

---

## 9. What does `REPLAN` mean?

`REPLAN` means the request is not necessarily invalid, but it is not safe or complete in its current form.

That lets the architecture say:

> this may proceed, but not like this

It is a useful middle state between unconditional approval and terminal denial.

---

## 10. What is `State Projection`?

`State Projection` is how approved execution effects are written back into operational context.

It answers questions like:

- what was successfully materialized?
- what state is now valid?
- what state is quarantined or stale?
- what should future requests see as true?

This is one of the most distinctive parts of CFA because it treats post-execution state as part of the architecture, not just as a logging concern.

---

## 11. Why does CFA care so much about partial execution?

Because real operational systems often fail partially rather than cleanly.

Examples:

- some partitions succeed while others fail
- one part of a pipeline materializes while another does not
- output is good enough to quarantine but not to publish

CFA models outcomes such as:

- approved
- partially committed
- quarantined
- rolled back

That makes the execution record more realistic and more useful for future decisions.

---

## 12. What is the `ContextRegistry`?

The `ContextRegistry` is the architecture’s explicit model of relevant operational state.

It is not just a log. Its job is to hold the state that future decisions depend on, such as:

- projected dataset state
- version references
- partial commit status
- target-scope context

This is how CFA avoids relying on chat memory as a substitute for operational truth.

---

## 13. What is the audit trail for?

The audit trail records the path from:

- request
- normalization
- confirmation
- policy decision
- execution
- state projection

Its purpose is not only observability, but causal traceability.

That matters when execution affects governed data, cost, compliance, or durable state.

---

## 14. What is the lifecycle layer?

The lifecycle layer evaluates recurring flows over time and decides whether they should be:

- promoted
- kept active
- watchlisted
- demoted
- deprecated
- retired

It uses quantitative signals such as:

- IFo
- IFs
- IFg
- IDI

This makes recurring execution health something the architecture can reason about explicitly.

---

## 15. Does CFA require an LLM?

Not everywhere.

Some parts are useful without any LLM at all, especially:

- `cfa.governance`
- validation logic
- lifecycle scoring

Natural-language resolution usually assumes some semantic backend, but the architecture is modular enough that not every adoption path needs one on day one.

---

## 16. When should I use CFA?

CFA is a good fit when:

- AI affects operational behavior
- governed data is involved
- execution cost matters
- partial failure matters
- auditability matters
- the system needs explicit state between runs

It is especially relevant for:

- data pipelines
- internal data platforms
- AI-assisted ETL or ELT
- governed execution environments

---

## 17. When should I not use CFA?

CFA is probably too heavy when:

- the task is mostly conversational
- errors are cheap and reversible
- governance is minimal
- latency is the main concern
- the workflow does not really depend on state

It is not meant to be the default architecture for every AI use case.

---

## 18. What is the smallest useful adoption path?

The strongest small adoption wedge is usually:

- `cfa.governance`
- inside an existing orchestrated pipeline
- as a pre-execution decision gate

That path is attractive because it:

- does not require an LLM
- does not require full kernel adoption
- gives immediate value
- is easy to explain to data and platform teams

---

## 19. What does governance-only usage look like?

Here is the smallest useful pattern:

```python
from cfa.governance import (
    PolicyEngine,
    StateSignature,
    TargetLayer,
    DatasetRef,
    DatasetClassification,
    SignatureConstraints,
    ExecutionContext,
)

signature = StateSignature(
    domain="fiscal",
    intent="reconciliation",
    target_layer=TargetLayer.SILVER,
    datasets=(
        DatasetRef("nfe", DatasetClassification.HIGH_VOLUME, size_gb=4000),
        DatasetRef("clientes", DatasetClassification.SENSITIVE, pii_columns=("cpf",)),
    ),
    constraints=SignatureConstraints(
        no_pii_raw=True,
        merge_key_required=True,
        enforce_types=True,
        partition_by=("processing_date",),
    ),
    execution_context=ExecutionContext("v1.0", "catalog_2026", "ctx_1"),
)

result = PolicyEngine().evaluate(signature)

print(result.action.value)
print(result.reasoning)
```

---

## 20. What does natural-language resolution look like?

```python
from cfa.resolution import IntentNormalizer, MockNormalizerBackend

catalog = {
    "datasets": {
        "nfe": {"classification": "high_volume", "size_gb": 4000},
        "clientes": {
            "classification": "sensitive",
            "size_gb": 0.5,
            "pii_columns": ["cpf", "email"],
        },
    }
}

normalizer = IntentNormalizer(backend=MockNormalizerBackend())
resolution = normalizer.normalize(
    raw_intent="Join NFe with Clientes and persist to Silver",
    environment_state={},
    catalog=catalog,
)

print(resolution.signature.domain)
print(resolution.signature.target_layer.value)
print(resolution.confidence_score)
print(resolution.confirmation_mode.value)
```

---

## 21. What does full-kernel usage look like?

```python
from cfa import KernelOrchestrator

catalog = {"datasets": {}}

kernel = KernelOrchestrator(catalog=catalog)
result = kernel.process("Join NFe with Clientes and persist to Silver")

print(result.state.value)
```

Use the full kernel when you want the entire governed flow:

- intent normalization
- confirmation
- policy
- planning
- execution control
- state projection
- lifecycle evaluation

---

## 22. Is there a concrete orchestration integration example?

Yes.

There is a separate minimal adoption wedge here:

- [Airflow Governance Gate](../integrations/airflow-governance-gate/README.md)

That example keeps the core architecture separate while showing how CFA can act as a lightweight decision layer inside an existing DAG.

---

## 23. What are the current limitations?

Current limitations include:

- the default semantic backend is a deterministic mock
- code generation currently targets PySpark
- persistence defaults are intentionally simple
- concurrency is still a future pressure point
- architectural claims still need broader external validation through real use

These limitations do not invalidate the proposal, but they are part of the honest current state of the project.

---

## 24. What should I read next?

If you want to go deeper, use this order:

1. [README](../README.md)
2. [Usage Guide](./guide.md)
3. [Airflow Governance Gate](../integrations/airflow-governance-gate/README.md)
4. [Whitepaper PT-BR](https://marquesantero.github.io/cfa/cfa-v2-whitepaper.html)
5. [Whitepaper EN](https://marquesantero.github.io/cfa/cfa-v2-whitepaper.en.html)
6. [Open Questions](./open-questions.md)
