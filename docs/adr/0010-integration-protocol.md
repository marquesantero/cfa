# ADR-0010: Integration protocol and DecisionSink

* Status: accepted
* Date: 2026-06-08
* Tags: plugins, public-api, contracts

## Context and Problem Statement

CFA's value at the edges is in *how* it plugs into real-world toolchains:

- dbt manifests, Airflow DAGs, GitHub PRs, Terraform plans, LangGraph
  state, Databricks Jobs, Kubernetes admission events — those are the
  inputs that should be turned into `StateSignature`s and run through
  the kernel.
- CI exits, PR comments, Slack messages, OTel spans, JIRA tickets,
  audit log appends — those are the outputs that should receive the
  kernel's decisions.

ADR-0007 places integrations at Layer 5. They depend on a vertical (for
the signature shape) and on the public kernel API (for the orchestrator
and types). They never touch the kernel internals.

We need two complementary protocols: one for **building** signatures
from external input, and one for **emitting** decisions to external
output.

## Decision Drivers

- A single integration must be small and focused — one input format,
  optionally one output channel.
- Integrations must be pip-installable separately and discovered by
  CFA via entry points (same mechanism as verticals).
- An integration must work with the public kernel API only — no
  internal imports.
- Decisions are *typed events*; the way they are surfaced (stdout, OTel,
  Slack) is a separate concern from the integration that produced the
  signature. They compose.

## Decision

### The `Integration` protocol

Lives at `cfa.core.integration.Integration`:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Integration(Protocol):
    name: str               # globally unique slug (e.g., "dbt-check")
    consumes: list[str]     # input format identifiers, e.g., ["dbt-manifest"]
    produces: str           # vertical name, e.g., "data"

    def build_signatures(self, raw: Any) -> list[StateSignature]:
        """Translate a tool-native input into one or more StateSignatures
        for the integration's target vertical."""

    def emit_decisions(self, results: list[KernelResult]) -> None:
        """Surface decisions back to the integration's natural channel —
        CI exit code, PR comment, Slack message, etc. Optional behavior:
        an integration that only consumes input may make this a no-op."""
```

### The `DecisionSink` protocol

Lives at `cfa.core.integration.DecisionSink`:

```python
@runtime_checkable
class DecisionSink(Protocol):
    name: str               # e.g., "stdout-json", "otel-span", "slack-webhook"

    def emit(self, result: KernelResult) -> None:
        """Send the decision event to this sink."""

    def flush(self) -> None:
        """Block until any buffered decisions are delivered. Optional."""
```

The kernel keeps a list of registered `DecisionSink`s and calls every
sink's `emit` after each phase produces a `KernelResult`. Sinks compose
freely — you can wire `stdout-json` + `otel-span` + `slack-webhook` in
the same process without any of them knowing about the others.

### The `IntegrationRegistry`

Singleton at `cfa.core.integration.IntegrationRegistry.singleton()`.
Same lazy entry-point discovery as `VerticalRegistry`:

```toml
[project.entry-points."cfa.integrations"]
dbt-check = "cfa_integrations.dbt:DbtCheckIntegration"
terraform-check = "cfa_terraform:TerraformCheckIntegration"

[project.entry-points."cfa.decision_sinks"]
slack = "cfa_integrations.slack:SlackWebhookSink"
otel = "cfa_integrations.otel:OtelSpanSink"
```

### Failure semantics

- An integration's `build_signatures` may raise
  `IntegrationInputError(loc, message)` to indicate a malformed input.
  The kernel CLI surfaces this with a clear pointer at the offending
  location and exits non-zero.
- A `DecisionSink.emit` failure is logged but does not abort the kernel.
  Decision processing must remain authoritative even if a downstream
  sink is unavailable. Sinks that require reliability can implement
  retries internally.

## Consequences

Positive:

- Each integration is one tiny pip package shipping one class with two
  methods.
- `DecisionSink` decouples *what a decision is* from *where it goes*.
  The same decision flows to OTel for observability and Slack for
  alerts without the kernel orchestrating either.
- The contract is small enough that a third party can land a working
  integration in an afternoon.

Negative:

- Sinks failing silently (only logged) is a deliberate trade-off. Teams
  that need at-least-once delivery for audit pipes should implement a
  sink backed by a durable queue and verify out-of-band.
- Distributing one process across many entry points complicates
  packaging metadata. We document the standard layout
  (`cfa-integrations-<tool>` pattern) in the extension guide.

## Alternatives considered

- **Single `Integration` interface that both builds signatures AND
  emits decisions.** Initially attractive but conflates two
  unrelated concerns. We split them so the same dbt integration can
  send decisions to multiple sinks.
- **Make sinks part of the orchestrator config rather than a registry.**
  Works for the CLI but not for the library-mode use case
  (third-party code wiring sinks programmatically). The registry
  shape covers both.
- **Use `logging.Handler` for sinks.** Reuses standard library plumbing
  but constrains payload shape to log records. Decisions carry
  structured data we'd lose. Worth providing a logging-handler sink as
  one of many sinks, not as the protocol itself.

## See also

- ADR-0007 — Layer 5 placement.
- ADR-0009 — verticals are the symmetric counterpart.
- ADR-0011 — sinks may include OTel spans, which depend on the
  condition namespacing rules in 0011.
