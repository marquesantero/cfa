---
sidebar_position: 2
---

# CFA compared to adjacent tools

CFA sits in a specific position: **pre-execution, dataset-aware, with
structured remediation and an offline-verifiable audit chain**. Most of the
tools below are complements, not replacements. This page is meant to be
brutally honest about where CFA wins, where it loses, and where it should
be paired with something else.

## At a glance

| Question | Use CFA | Use the other tool |
|----------|---------|---------------------|
| "Did our agent / pipeline hallucinate or drift after running?" | — | LangSmith / Phoenix / Patronus |
| "Should this agent be allowed to call this tool at all (generic policy)?" | — | OPA |
| "Should this agent be allowed to write this *specific dataset* under these *dataset-aware constraints*?" | **CFA** | — |
| "Where does this column come from? Who owns it?" | — | Unity Catalog / Atlan / DataHub |
| "Does the data we already wrote match our expectations?" | — | Great Expectations / Soda |
| "Before we run, can we deterministically decide *approve / replan / block* with a verifiable audit event?" | **CFA** | — |

## CFA vs OPA (Open Policy Agent)

| Dimension | CFA | OPA |
|-----------|-----|-----|
| Maturity | 1.x, alpha-quality | CNCF graduated, production at scale |
| Domain | Dataset-aware writes | Generic policy-as-code (Kubernetes, APIs, CI/CD, infra) |
| Language | Python types + YAML bundles | Rego DSL |
| Decision shape | `approve / replan(remediations) / block(reason)` | `allow / deny`, custom data |
| First-class primitives | PII, classification, partition, merge_key, layer | None (you encode them in Rego) |
| Hash chain | Built in, offline verifiable | External (you bring your own audit pipeline) |
| Deploy footprint | Library import | Sidecar / daemon / library |

**When to pick CFA over OPA:** when your policies are about *what gets
written where, with what dataset metadata*. Writing those rules in Rego is
possible but reimplements primitives CFA already has.

**When to pick OPA over CFA:** when your policies cover Kubernetes admission,
API authz, Terraform plans, or other non-data domains. OPA is the right tool
across the rest of the stack.

**When to pair them:** OPA at the API gateway / cluster level; CFA at the
pipeline / agent-tool level. They do not overlap.

## CFA vs LangSmith / Phoenix / Patronus

| Dimension | CFA | LangSmith / Phoenix / Patronus |
|-----------|-----|---------------------------------|
| When it runs | Before execution | After execution |
| What it answers | "May this happen?" | "What happened? Was it good?" |
| Determinism | Pure function of inputs | Probabilistic eval / LLM-as-judge |
| Audit shape | SHA-256 chain over decisions | Spans + traces in a UI |

**Pair them.** CFA decides whether to proceed; LangSmith/Phoenix tell you,
afterwards, whether the call did what it claimed. The two surfaces produce
different evidence.

## CFA vs Great Expectations / Soda

| Dimension | CFA | Great Expectations / Soda |
|-----------|-----|---------------------------|
| When it runs | Before the write | After the write |
| What it validates | Intent (signature) | Data (rows, columns, distributions) |
| Failure mode | Don't write | Write happened, now flag it |

**Pair them.** CFA prevents a class of bad writes from happening; GE catches
the bad data that did get written. CFA also reduces the load GE has to
absorb because malformed intents never reach the write step.

## CFA vs Unity Catalog / Atlan / DataHub

| Dimension | CFA | UC / Atlan / DataHub |
|-----------|-----|-----------------------|
| Primary surface | Pre-execution decision | Discovery, lineage, access control |
| Catalog role | Operational (drives policy) | Reference (humans browse it) |
| Authority | Decides | Stores authoritative metadata |

**Pair them.** CFA reads the catalog. From 1.3.x CFA will federate UC,
Atlan, and DataHub as catalog sources so the same metadata that powers
discovery also powers decisions.

## CFA vs dbt contracts / dbt tests

| Dimension | CFA | dbt contracts/tests |
|-----------|-----|---------------------|
| Scope | Whole intent before run | Per-model schema and per-row checks |
| Outcome | `approve / replan / block` with remediation | Pass / fail per assertion |
| Decision target | The intent | The output table |

**Pair them.** `cfa dbt check` (planned for 1.2.0) reads `target/manifest.json`,
derives a signature per model, and runs the policy bundle. dbt contracts
keep validating the schema of each individual model. CFA covers the things
dbt contracts can't express (cross-dataset PII rules, cost ceilings,
catalog cross-reference).

## What CFA does *not* try to be

- **An orchestrator.** Use Airflow, Dagster, Prefect, or dbt itself.
- **A code generator that replaces SQL/Python.** CFA generates governed
  scaffolding from approved intents — the engineer still writes the real
  transformation.
- **An LLM evaluation harness.** Use the tools above.
- **A vector store.** State projection is operational state, not embeddings.

## Honest disclaimers

- CFA is at `1.0.0` on PyPI. The `1.0` API freeze shipped earlier than it
  should have. Several modules will deprecate in 1.x and be removed in 2.0.
- No third-party benchmarks against OPA exist yet. We plan to publish them
  during the 1.2.x cycle.
- The lifecycle indices (IFo/IFs/IFg/IDI) are implemented but
  under-documented; production produtization is planned for 1.4.0.
- The MCP server is functional today but is only positioned as a real
  authority surface for LLM agents from 1.5.0 onward.

Track all of this in [`drafts/ROADMAP.md`](https://github.com/marquesantero/cfa/blob/main/drafts/ROADMAP.md).
