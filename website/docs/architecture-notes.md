---
sidebar_position: 21
---

# Architecture Notes

Open questions and design decisions for CFA maturation. These notes are not reasons to dismiss CFA — they are the questions most worth debating.

---

## 1. Whitepaper-to-implementation gap

The whitepaper expresses a strong architectural contract: intent formalization, governed execution, state projection, partial-failure semantics, lifecycle evidence. The implementation already reflects much of that structure, but the real question is whether the **invariants are enforced as strongly as the whitepaper implies**. This should be examined module by module.

---

## 2. Metadata dependency

CFA assumes meaningful metadata quality: dataset classification, PII markers, partition metadata, catalog freshness, environmental context. If those inputs are wrong, the system can become confidently wrong in a disciplined way. The architecture is only as good as the state and catalog substrate it depends on.

---

## 3. Overhead vs. risk profile

CFA introduces multiple decision and validation stages. This creates architectural clarity, governance strength, and better recoverability — but also latency, integration effort, and cognitive load. The unresolved question: in which operational contexts is that overhead justified by the risk profile?

---

## 4. Concurrency model

If multiple requests can interpret overlapping intent, target the same scope, and update shared operational state, the architecture must define how correctness is preserved under contention. Sub-questions:
- Should target scope be lock-based, queue-based, or version-based?
- How should revalidation work under concurrent change?
- What does acceptable consistency look like?

---

## 5. Merge-key contract richness

Today, `merge_key_required` is a boolean signal that merge semantics matter. Should the architecture move to a richer explicit contract for merge behavior, key semantics, and write guarantees? That would make the execution contract more serious, but also more demanding.

---

## 6. Target scope modeling

State projection, lifecycle, and concurrency all depend on how clear the target scope model is. Key questions:
- Is target scope dataset-level, partition-level, or contract-level?
- How should derived targets be named and versioned?
- How should future writes reason about prior projections?

---

## 7. Policy bundle evolution

Policy itself has a lifecycle. Open questions:
- How should policies be versioned and what compatibility guarantees should exist?
- When should policy change trigger re-evaluation or demotion?
- How do teams avoid governance becoming bureaucratic?

---

## 8. Runtime adapter boundaries

The current runtime path is PySpark-oriented. What is generic in CFA, and what is runtime-specific? Candidate future adapters: SQL engines, warehouse-native execution, stream processing, non-data orchestration runtimes.

---

## 9. Long-term language choice

Python is excellent for readability, data tooling alignment, and experimentation. It is weaker for strong compile-time guarantees, deeper invariant enforcement, and some classes of runtime isolation. Should the long-term core stay entirely in Python?

---

## 10. Market validation

What is the smallest real use case that proves CFA creates value for someone outside the project? The strongest current candidate is: `cfa.policy` in an existing orchestrated pipeline before execution. That wedge can test adoption friction, conceptual clarity, real value, and external usability.

---

## 11. Meaningful proof criteria

Good proof would not be another internal demo. Stronger evidence: an external team adopts a small CFA slice, can explain the benefit simply, integration effort is acceptable, and they hit real friction and still find value.

---

## 12. Production readiness measurement

Beyond listing "strong" and "weak" areas, how should the project measure which parts are production-ready? Possible criteria: invariant enforcement strength, operational observability, integration complexity, external usability, failure semantics, runtime maturity.

---

## 13. Next concrete milestones

- **First external adoption**: someone outside the project uses `cfa.policy` in a real pipeline and reports back
- **Invariant hardening**: systematically verify which whitepaper invariants are enforced at runtime vs. only by convention
- **Runtime adapter boundary**: define clearly what is generic CFA and what is PySpark-specific, so a second adapter can be added without rewriting the kernel
- **Concurrency model decision**: choose and implement lock-based, queue-based, or version-based target scope isolation
