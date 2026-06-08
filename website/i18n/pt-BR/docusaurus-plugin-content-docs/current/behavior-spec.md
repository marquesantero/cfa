---
sidebar_position: 14
---

# Behavior Spec

Especificações de Comportamento conectam políticas de governança escritas por humanos (em YAML ou linguagem natural) a regras de política CFA executáveis.

## YAML Behavior Spec

```yaml
behavior:
  name: fiscal_reconciliation
  description: |
    Pipeline deve:
    - anonimizar PII antes da Silver
    - aplicar merge_key em todas as escritas Silver
    - permanecer dentro do orçamento de shuffle (500MB)

  failure_modes:
    - code: raw_pii_in_silver
      label: "PII bruto na Silver"
      description: "Colunas de PII em escrita Silver sem anonimização."
      condition: pii_in_protected_layer
      severity: critical
      action: block
      target_layer: silver
      remediation:
        - "Aplicar sha256 nas colunas de PII"
        - "Habilitar restrição no_pii_raw"
```

## Gerar Taxonomia

```bash
cfa taxonomy generate --spec spec.yaml --output taxonomia.json
```

## Gerar Intenções de Teste

```bash
cfa taxonomy test-intents --spec spec.yaml --count 5
```

Gera intenções de teste para cada categoria de falha — útil para validar que as regras de política estão funcionando corretamente.

## API Python

### Carregar e sistematizar

```python
from cfa.behavior import BehaviorSpec, Systematizer

spec = BehaviorSpec.from_yaml("spec.yaml")
taxonomy, rules = Systematizer().systematize(spec)

print(f"Categorias: {taxonomy.category_count}")
print(f"Regras: {len(rules)}")

for rule in rules:
    print(f"  {rule.name}: {rule.fault_code} ({rule.severity.value})")
```

### Sistematizador com LLM

```python
from cfa.behavior.llm import OpenAISystematizerBackend
from cfa.behavior import Systematizer

backend = OpenAISystematizerBackend(model="gpt-4o-mini")
taxonomy, rules = Systematizer().systematize_from_nl(
    "Pipeline fiscal: anonimizar PII, exigir merge_key, particionar datasets > 100GB",
    backend=backend,
    target_layer="silver",
)
```

