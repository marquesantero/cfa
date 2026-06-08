# ADR-0009: Vertical protocol and registry via entry points

* Status: accepted
* Date: 2026-06-08
* Tags: plugins, public-api, contracts

## Context and Problem Statement

A "vertical" in CFA is a domain that the kernel governs — data writes,
agent tool calls, infrastructure plans, financial transactions, schema
migrations, ML model deploys, mass-notification sends, anything where
the pattern *declare intent → decide → execute → audit* applies.

ADR-0007 places verticals at Layer 3. They must:

- be shippable inside `cfa-kernel` (the data vertical) or as separate
  pip-installable packages (`cfa-vertical-finance`);
- be discoverable by the kernel **without the kernel importing them**;
- expose a stable, minimal contract.

## Decision Drivers

- Third-party verticals must not require a PR in `cfa-kernel` to be
  usable.
- Discovery should be lazy — verticals are looked up when needed, not
  during `import cfa`.
- The protocol surface should be minimal. Smaller surface ↔ easier to
  implement and easier to keep stable.
- Verticals must be testable in isolation against a mock kernel.

## Decision

### The `Vertical` protocol

Lives at `cfa.core.vertical.Vertical`:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Vertical(Protocol):
    name: str  # globally unique, e.g., "data", "agent", "infra"

    def payload_schema(self) -> dict[str, Any]:
        """JSON Schema for StateSignature.payload in this vertical."""

    def constraints_schema(self) -> dict[str, Any]:
        """JSON Schema for StateSignature.constraints in this vertical."""

    def conditions(self) -> dict[str, ConditionFactory]:
        """Named condition functions this vertical contributes.
        Returned dict maps short name -> factory. Names are auto-prefixed
        by the vertical name on registration to avoid collisions."""

    def default_rules(self) -> list[PolicyRule]:
        """Default ruleset this vertical wants registered when active.
        May be empty."""

    def catalog_schema(self) -> dict[str, Any] | None:
        """Optional: JSON Schema for ground-truth catalog entries."""

    def backends(self) -> dict[str, BackendFactory]:
        """Optional: codegen / execution backends for this vertical.
        See ADR-0012 for per-vertical backend scoping."""
```

`runtime_checkable` is intentional — third parties can implement the
protocol structurally without inheriting from any base class, and the
registry validates conformance at registration time.

### The `VerticalRegistry`

A process-wide singleton (`cfa.core.vertical.VerticalRegistry.singleton()`)
that:

- accepts manual registration: `VerticalRegistry.register(MyVertical())`;
- discovers third-party verticals via Python entry points on first
  query;
- never instantiates a vertical at import time — only when looked up.

### Discovery via entry points

Third-party packages declare their vertical in `pyproject.toml`:

```toml
[project.entry-points."cfa.verticals"]
finance = "cfa_finance.vertical:FinanceVertical"
ml-deploy = "cfa_ml_deploy:MLDeployVertical"
```

`VerticalRegistry._discover_entry_points()` uses
`importlib.metadata.entry_points(group="cfa.verticals")`, loads each, and
instantiates it if it is callable. Discovery is idempotent and runs at
most once per process.

### Condition namespacing

Conditions returned by `vertical.conditions()` are auto-prefixed with the
vertical name when registered into the `ConditionRegistry` (see
ADR-0011). So a `pii_in_protected_layer` condition from
`cfa.verticals.data` becomes `data.pii_in_protected_layer` in YAML
bundles. This prevents collisions across verticals.

## Consequences

Positive:

- A vertical is a self-contained, testable unit. Its public surface is a
  single class implementing the protocol.
- Adding `cfa.verticals.agent` is the same shape as `cfa.verticals.data`
  — there is one canonical pattern.
- Entry points make third-party publishing trivial: pip install + a
  pyproject.toml stanza.

Negative:

- The protocol has six methods. Some verticals will return empty
  defaults for half of them. We accept the verbosity in favor of
  explicitness; a future `BaseVertical` ABC may provide default
  implementations.
- Misbehaving third-party verticals (raising during discovery, etc.)
  could degrade the registry. We mitigate with try/except around each
  entry-point load and a `warnings.warn` so the issue surfaces but
  doesn't crash the kernel.

## Alternatives considered

- **Inheritance instead of Protocol.** Rejected — Protocol allows
  structural typing and lets users implement verticals with libraries
  that already have their own base classes.
- **JSON manifest files instead of Python classes.** Rejected — most
  verticals will want at least condition factories implemented in
  Python; mixing a JSON manifest plus Python wiring is more friction.
- **No registry, explicit `KernelOrchestrator(vertical=…)`.** Rejected
  — works for one vertical at a time but doesn't compose for the
  multi-vertical case (e.g., a generic CLI processing both data and
  infra signatures in the same run).

## See also

- ADR-0007 — the layered architecture this fits into.
- ADR-0008 — what `payload_schema` and `constraints_schema` validate.
- ADR-0011 — how `conditions()` plugs into the policy engine.
- ADR-0012 — how `backends()` is scoped.
