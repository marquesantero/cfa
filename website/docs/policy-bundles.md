---
sidebar_position: 11
---

# Policy Bundles

CFA Policy Bundles are versioned, loadable YAML/JSON files that define governance rules — separating policy definition from code.

## Why Policy Bundles?

- **Separation of concerns**: Platform/security teams define policies in YAML; data teams reference them by version
- **Auditability**: Every execution records which bundle version was active
- **CI/CD integration**: `cfa validate --policy-bundle policies/prod-v1.yaml`
- **Versioned**: Bundles have semantic versions (e.g., `prod-v1.0`)

## Built-in Bundles

CFA ships with 3 bundles in the `policies/` directory:

| Bundle | Focus | Rules | Severity |
|--------|-------|-------|----------|
| `prod-v1.yaml` | Balanced safety & cost | 7 | Mixed |
| `finops-strict-v1.yaml` | Aggressive cost control | 5 | High |
| `compliance-strict-v1.yaml` | Regulated industries | 7 | Critical |

## Bundle YAML Schema

```yaml
policy_bundle:
  version: "prod-v1.0"
  description: "Production governance rules"
  last_updated: "2026-06-06"
  rules:
    - name: forbid_raw_pii_in_silver_or_gold
      condition: pii_in_protected_layer
      action: replan
      fault_code: GOVERNANCE_RAW_PII_IN_PROTECTED_LAYER
      severity: critical
      family: semantic
      message: "PII detected without treatment in write to protected layer."
      remediation:
        - "Apply sha256() on PII columns before join"
        - "Or use drop() to remove sensitive columns"
```

## Available Conditions

10 built-in conditions mapped to `StateSignature` checks:

| Condition | Trigger |
|-----------|---------|
| `pii_in_protected_layer` | PII in Silver/Gold without anonymization |
| `missing_merge_key` | Write to Silver/Gold without merge_key |
| `missing_partition` | High-volume dataset without partition filter |
| `sensitive_without_partition` | Sensitive dataset without partition |
| `enforce_types_disabled` | Type enforcement disabled on protected write |
| `pii_without_policy` | PII present without `no_pii_raw` constraint |
| `cost_budget_exceeded` | Cost exceeds configured ceiling |
| `schema_mismatch` | Output schema differs from contract |
| `unauthorized_gold_write` | Unauthorized Gold layer write |
| `custom` | User-defined condition |

## Custom Conditions

```python
from cfa.conditions import register_condition, build_condition

def my_custom_check(meta):
    def check(sig):
        return sig.domain == "finance" and len(sig.datasets) > 5
    return check

register_condition("finance_large_join", my_custom_check)
```

## Loading from Code

```python
from cfa.policy_bundle import PolicyBundle, list_available_bundles
from cfa.policy import PolicyEngine

# List available
bundles = list_available_bundles("policies/")

# Load and use
bundle = PolicyBundle.from_yaml("policies/prod-v1.yaml")
engine = PolicyEngine.from_bundle("policies/prod-v1.yaml")
```

## CLI Usage

```bash
cfa evaluate "intent" --policy-bundle policies/compliance-strict-v1.yaml
```
