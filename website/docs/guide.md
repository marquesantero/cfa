---
sidebar_position: 4
---

# Usage Guide

Complete workflow from intent to audit using CFA.

---

## Adoption Levels

CFA supports progressive adoption. You do not need to adopt everything at once.

| Level | What you use | What you get |
|-------|-------------|--------------|
| Governance only | `PolicyEngine` + `StateSignature` | Formal decision gate before pipeline execution |
| Governance + Resolution | Above + `IntentNormalizer` | Natural language requests converted into governed contracts |
| Partial kernel | Above + codegen + sandbox | Validation, controlled execution, and state projection |
| Full kernel | `KernelOrchestrator` | End-to-end governed execution flow |

---

## Level 1: Governance Only

Use CFA as a policy gate in front of an existing pipeline.

```python
from cfa.policy.engine import (
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
        max_cost_dbu=50.0,
    ),
    execution_context=ExecutionContext("v1.0", "catalog_2026", "ctx_1"),
)

result = PolicyEngine().evaluate(signature)

if result.is_blocked:
    raise RuntimeError(result.reasoning)
```

**Typical fit**: Airflow/Dagster pipelines, scripts materializing data into governed layers, systems needing policy gates before execution.

---

## Level 2: Governance + Resolution

Add intent resolution when you need semantic interpretation of natural-language requests.

```python
from cfa.normalizer.base import IntentNormalizer, MockNormalizerBackend

catalog = {
    "datasets": {
        "nfe": {"classification": "high_volume", "size_gb": 4000, "pii_columns": []},
        "clientes": {"classification": "sensitive", "size_gb": 0.5, "pii_columns": ["cpf", "email"]},
    }
}

normalizer = IntentNormalizer(backend=MockNormalizerBackend())
resolution = normalizer.normalize(
    raw_intent="Join NFe with Clientes and persist to Silver",
    environment_state={},
    catalog=catalog,
)

print(resolution.signature.domain)
print(resolution.confidence_score)
print(resolution.confirmation_mode.value)
```

**Confirmation modes**:
- `AUTO` — high confidence, low ambiguity, no protected risk
- `SOFT` — medium confidence, proceed with logging
- `HARD` — protected data in sensitive target, requires explicit approval
- `HUMAN_ESCALATION` — very low confidence or severe ambiguity

---

## Level 3: Partial Kernel

Use validation, code generation, and sandbox without full orchestration.

```python
from cfa.validation.static import StaticValidator
from cfa.core.codegen import GeneratedCode

validator = StaticValidator()
generated = GeneratedCode(
    plan_signature_hash="demo",
    intent_id="demo",
    language="pyspark",
    code="df.join(other, on='key').write.mode('overwrite').save('/silver/')",
)

result = validator.validate(generated, signature)
print(result.passed, result.fault_codes)
```

---

## Level 4: Full Kernel

End-to-end governed flow from natural language to execution outcome.

```python
from cfa import KernelOrchestrator, KernelConfig

kernel = KernelOrchestrator(
    catalog=my_catalog,
    config=KernelConfig(
        enable_planning=True,
        enable_codegen=True,
        enable_static_validation=True,
        enable_sandbox=True,
        enable_promotion=True,
    ),
)

result = kernel.process("Join NFe with Clientes and persist to Silver")
print(result.state.value)
print(f"Intent ID: {result.intent_id}")
print(f"Signature hash: {result.signature.signature_hash}")
print(f"Replans: {len(result.replan_history)}")
```

### Kernel Phases

```
context registry → normalization → confirmation → policy
→ planning → code generation → static validation
→ sandbox execution → runtime validation → partial execution
→ state projection → audit → lifecycle evaluation
```

---

## Using from CI/CD

```bash
cfa evaluate "Join NFe with Clientes persist Silver" \
    --catalog catalog.json \
    --policy-bundle policies/prod-v1.yaml \
    --exit-code
```

Exit code 1 if BLOCKED — suitable for GitHub Actions, GitLab CI, or any CI pipeline.

---

## Using as a Python Test

```python
from cfa.testing import evaluate, assert_passed

result = evaluate(
    "Join NFe with Clientes and persist to Silver",
    catalog=MY_CATALOG,
    backend="pyspark",
)
assert_passed(result)
```

---

## Custom Policy Bundles

Create `my-policy.yaml`:

```yaml
policy_bundle:
  version: "my-v1.0"
  description: "Custom governance rules"
  rules:
    - name: forbid_raw_pii_in_silver
      condition: pii_in_protected_layer
      action: replan
      fault_code: GOVERNANCE_RAW_PII_IN_PROTECTED_LAYER
      severity: critical
      family: semantic
      message: "PII detected without treatment in protected layer."
      remediation:
        - "Apply sha256() on PII columns before join"
```

```bash
cfa evaluate "intent" --policy-bundle my-policy.yaml
```

---

## Custom Backends

```python
from cfa.backends import BackendAdapter, BackendCapabilities, BackendRegistry

class MyBackend(BackendAdapter):
    def get_capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            backend_name="sql",
            supports_merge=True,
            supports_anonymization=False,
            supports_partition_overwrite=True,
        )

    def generate(self, plan):
        # Generate SQL from plan
        ...

BackendRegistry.singleton().register("sql", lambda: MyBackend())
```

```bash
cfa evaluate "intent" --backend sql
```

---

## Custom Conditions

```python
from cfa.core.conditions import register_condition, build_condition

def my_custom_check(meta):
    def check(sig):
        return sig.domain == "finance" and len(sig.datasets) > 5
    return check

register_condition("finance_large_join", my_custom_check)
```

---

## Lifecycle Monitoring

```python
from cfa.observability.promotion import PromotionEngine
from datetime import datetime, timezone

engine = PromotionEngine(policy=PromotionPolicy(min_executions=3))

engine.record_execution(ExecutionRecord(
    signature_hash="fiscal_reconciliation_abc123",
    timestamp=datetime.now(timezone.utc),
    success=True,
    cost_dbu=5.0,
    duration_seconds=30.0,
))

skill, scores = engine.evaluate("fiscal_reconciliation_abc123")
print(skill.state.value)  # candidate, active, watchlist, demoted, retired
print(scores.ifo, scores.ifs, scores.ifg, scores.idi)
```

---

## Audit Trail

```bash
# Show audit trail for an intent
cfa audit show --id abc12345

# Verify chain integrity
cfa audit verify

# Generate audit report
cfa report audit --intent-id abc12345 --output audit.html
```

---

## Next Steps

- **[CLI Reference](./cli)** — All `cfa` commands and options
- **[Policy Bundles](./policy-bundles)** — Declarative YAML policy rules
- **[MCP Server](./mcp-server)** — Expose CFA to AI agents
- **[Reporting](./reporting)** — Rich HTML reports
- **[Integrations](./integrations/airflow)** — Framework and orchestrator adapters
