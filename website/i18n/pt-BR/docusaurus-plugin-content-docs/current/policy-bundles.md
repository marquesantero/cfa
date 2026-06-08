---
sidebar_position: 11
---

# Policy Bundles

Policy Bundles CFA são arquivos YAML/JSON versionados e carregáveis que definem regras de governança — separando definição de política do código.

## Por que Policy Bundles?

- **Separação de responsabilidades**: Times de plataforma/segurança definem políticas em YAML; times de dados referenciam por versão
- **Auditabilidade**: Cada execução registra qual versão do bundle estava ativa
- **Integração CI/CD**: `cfa policy validate policies/prod-v1.yaml`
- **Versionados**: Bundles possuem versões semânticas (ex: `prod-v1.0`)

## Bundles Integrados

CFA inclui 3 bundles no diretório `policies/`:

| Bundle | Foco | Regras | Severidade |
|--------|-------|-------|----------|
| `prod-v1.yaml` | Segurança e custo balanceados | 7 | Mista |
| `finops-strict-v1.yaml` | Controle de custo agressivo | 5 | Alta |
| `compliance-strict-v1.yaml` | Indústrias reguladas | 7 | Crítica |

## Schema YAML do Bundle

```yaml
policy_bundle:
  version: "prod-v1.0"
  description: "Regras de governança para produção"
  rules:
    - name: forbid_raw_pii
      condition: pii_in_protected_layer
      action: block
      fault_code: GOVERNANCE_RAW_PII
      severity: critical
      family: semantic
      message: "PII em camada protegida sem anonimização."
      remediation:
        - "Aplicar sha256 nas colunas de PII"
```

## Condições Disponíveis

| Condição | Descrição |
|----------|-----------|
| `pii_in_protected_layer` | PII em Silver/Gold sem anonimização |
| `pii_without_policy` | Dataset com PII sem política declarada |
| `missing_partition` | Dataset de alto volume sem partição |
| `sensitive_without_partition` | Dataset sensível sem partição |
| `missing_merge_key` | Escrita em Silver/Gold sem merge key |
| `enforce_types_disabled` | Verificação de tipos desabilitada |
| `cost_budget_exceeded` | Custo estimado excede orçamento |
| `schema_mismatch` | Schema não corresponde ao contrato |
| `unauthorized_gold_write` | Escrita não autorizada na camada Gold |
| `custom` | Condição definida pelo usuário |

## Carregando via Código

```python
from cfa.policy.bundle import PolicyBundle, list_available_bundles
from cfa.policy.engine import PolicyEngine

# Listar bundles disponíveis
for name in list_available_bundles():
    print(name)

# Carregar bundle de arquivo
bundle = PolicyBundle.from_yaml("policies/prod-v1.yaml")
engine = PolicyEngine(rules=bundle.rules, policy_bundle_version=bundle.version)

# Ou usar bundle built-in
engine = PolicyEngine(policy_bundle_version="prod-v1.0")
```

## Condições Customizadas

```python
from cfa.core.conditions import register_condition, build_condition

def verificar_orcamento(meta):
    limite = meta.get("max_dbu", 100)
    def check(sig):
        return sig.constraints.max_cost_dbu is not None and sig.constraints.max_cost_dbu > limite
    return check

register_condition("custom_budget", verificar_orcamento)
```

## Validando Bundles

```bash
cfa policy validate policies/prod-v1.yaml --format json
```

A validação verifica: condição registrada, enums válidos, códigos de fault duplicados, campos obrigatórios.
