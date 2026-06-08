# ADR-0011: `ConditionRegistry` as the canonical way to attach policy rules

* Status: accepted
* Date: 2026-06-08
* Tags: policy, plugins, contracts

## Context and Problem Statement

Today `cfa.policy.PolicyRule.condition` is `Callable[[StateSignature], bool]`,
and the shipped `build_default_ruleset()` constructs rules with inline
lambdas. YAML policy bundles already reference named conditions
(`condition: pii_in_protected_layer`), which are looked up via
`cfa.core.conditions.build_condition`. So we have **two attachment
mechanisms** in production:

1. Inline Python lambdas (used by `build_default_ruleset` and by tests).
2. Named conditions resolved at YAML bundle load time.

This duplication has direct costs:

- Verticals can only ship YAML-style rules cleanly because inline
  lambdas would require importing Python from the bundle.
- Audit clarity suffers — a YAML bundle is self-describing, an inline
  lambda is not.
- A condition can drift between its Python implementation and the YAML
  rule that references it.

## Decision Drivers

- Every condition has exactly one canonical form: a named function in
  the `ConditionRegistry`.
- YAML bundles are the canonical rule format. Python rules can still
  use the same conditions via the registry.
- Verticals contribute conditions via `Vertical.conditions()`
  (ADR-0009). The kernel auto-prefixes them with the vertical name to
  avoid collisions.
- Backward compatibility for 1.x callers that construct `PolicyRule`
  with inline lambdas — deprecated but still functional.

## Decision

### One registry, namespaced

`cfa.core.conditions.ConditionRegistry` is the single source of truth.
It maps fully-qualified names (e.g., `data.pii_in_protected_layer`,
`infra.blast_radius_above`) to factories that build a callable taking
a `StateSignature` and returning a bool.

```python
from cfa.core.conditions import ConditionRegistry

ConditionRegistry.singleton().register(
    name="data.pii_in_protected_layer",
    factory=build_pii_in_protected_layer,
    doc="Fires when datasets carry PII columns and the target layer is "
        "silver or gold and no_pii_raw is False.",
    expected_params={},  # static parameters from YAML config
)
```

Conditions registered by `Vertical.conditions()` are auto-prefixed at
registration time:

```python
# Inside cfa.verticals.data.__init__
class DataVertical(Vertical):
    name = "data"
    def conditions(self):
        return {
            "pii_in_protected_layer": build_pii_in_protected_layer,
            "high_volume_without_partition": build_high_volume_without_partition,
            ...
        }
# Becomes registered as data.pii_in_protected_layer, etc.
```

### YAML stays the canonical rule format

A `PolicyBundle` YAML references conditions by their fully-qualified
name. The bundle loader resolves them via the registry. Any rule whose
condition is not registered is rejected at load time with a clear
error pointing at the YAML location.

### Deprecation path for inline lambdas

`PolicyRule(condition=<lambda>)` continues to work in 1.x with a
`DeprecationWarning`:

```
DeprecationWarning: PolicyRule was constructed with an inline callable
condition. In 2.0 this will be removed. Register the condition in
ConditionRegistry and reference it by name. See ADR-0011.
```

`PolicyRule(condition="data.pii_in_protected_layer")` is the new
preferred form — a string identifying a registered condition.
`PolicyRule.evaluate()` looks the callable up at evaluation time.

The shipped `build_default_ruleset()` is rewritten to use the registry
form; the inline-lambda support is left as a temporary 1.x compatibility
surface.

### Discovery semantics

The registry is queried at three points:

1. **At policy bundle load time.** Every named condition referenced in
   YAML must exist. Missing conditions abort the load with a typed error.
2. **At policy evaluation time.** A `PolicyRule` carrying a string
   condition looks the callable up. Hot path; cached after first
   resolution.
3. **At CLI introspection time.** `cfa rules list --available-conditions`
   prints every registered condition with its docstring. Lets bundle
   authors discover what's available without grep.

### Parameterized conditions

Some conditions need parameters (e.g., `blast_radius_above` needs a
threshold). The registry's factory pattern handles this — YAML carries
the parameters:

```yaml
- name: terraform_blast_radius
  condition: infra.blast_radius_above
  condition_params:
    max_resources: 50
    forbidden_resources: ["aws_db_instance.production_db"]
  action: block
```

The factory receives `condition_params` and returns the bound predicate.

## Consequences

Positive:

- One place to look for "what conditions exist?". One YAML format.
- Verticals contribute conditions without changing the policy engine.
- Tests can introspect the registry to assert that every shipped
  condition has at least one rule that references it (catches dead
  conditions).
- `cfa rules list --available-conditions` becomes a useful authoring
  aid.

Negative:

- The deprecation cycle for inline-lambda rules adds a temporary
  warning that some library users will see. Documented in CHANGELOG
  for whichever release flips the switch.
- Verticals must be careful not to ship conditions that collide with
  another vertical's. The namespacing (vertical name as prefix)
  prevents accidental collisions; deliberate collisions (two verticals
  registering the same prefixed name) raise.
- Parameterized conditions add complexity. Existing inline lambdas
  closed over Python-level constants; the registry form requires
  threading parameters through YAML. We accept the tradeoff for
  uniformity.

## Alternatives considered

- **Allow YAML bundles to embed Python lambdas (via `eval`).** Hard no
  for security and audit reasons.
- **Generate Python code from YAML at bundle load.** Possible but
  hides the rule semantics inside generated code. The registry approach
  keeps the rule transparent.
- **Drop YAML and require Python rule definitions.** Reduces auditor
  comprehension. YAML stays the canonical input.

## See also

- ADR-0009 (verticals contribute conditions through this registry).
- ADR-0010 (integrations may also register conditions if they ship
  rule sets — rare but supported).
- `cfa.core.conditions` module (the existing partial implementation
  this ADR formalizes).
