---
sidebar_position: 14
---

# Behavior Spec

Behavior Specifications bridge human-written governance policies (in YAML or natural language) to executable CFA policy rules — inspired by ASSERT's systematization approach.

## YAML Behavior Spec

```yaml
behavior:
  name: fiscal_reconciliation
  description: |
    Pipeline must:
    - anonymize PII before Silver
    - enforce merge_key on all Silver writes
    - stay within shuffle budget (500MB)

  failure_modes:
    - code: raw_pii_in_silver
      label: Raw PII in Silver
      description: PII columns in Silver write without anonymization
      condition: pii_in_protected_layer
      severity: critical
      action: block
      target_layer: silver
      remediation:
        - Apply sha256() on all PII columns
        - Enable no_pii_raw constraint
```

## Systematizer

```python
from cfa.behavior import BehaviorSpec, Systematizer

spec = BehaviorSpec.from_yaml("fiscal_governance.yaml")
taxonomy, rules = Systematizer().systematize(spec)

# Use generated rules
from cfa import KernelOrchestrator
kernel = KernelOrchestrator(policy_rules=rules)
```

## LLM-Assisted (Optional)

```python
from cfa.behavior.llm import OpenAISystematizerBackend
from cfa.behavior import Systematizer

backend = OpenAISystematizerBackend(model="gpt-4o-mini")
taxonomy, rules = Systematizer().systematize_from_nl(
    "Pipeline must protect PII, enforce merge keys, and stay within budget.",
    backend=backend,
)
```

## CLI

```bash
cfa taxonomy generate --spec fiscal_governance.yaml --output taxonomy.json
cfa taxonomy test-intents --spec fiscal_governance.yaml --count 5
```
