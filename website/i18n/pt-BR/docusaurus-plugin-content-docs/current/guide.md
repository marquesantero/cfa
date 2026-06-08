---
sidebar_position: 4
---

# Guia de Uso

Fluxo completo da intenção à auditoria usando CFA.

---

## Níveis de Adoção

O CFA suporta adoção progressiva. Você não precisa adotar tudo de uma vez.

| Nível | O que usa | O que obtém |
|-------|-----------|-------------|
| Apenas governança | `PolicyEngine` + `StateSignature` | Gate formal de decisão antes da execução |
| Governança + Resolução | Acima + `IntentNormalizer` | Intenções em linguagem natural convertidas em contratos governados |
| Kernel parcial | Acima + codegen + sandbox | Validação, execução controlada e projeção de estado |
| Kernel completo | `KernelOrchestrator` | Fluxo de execução governada ponta a ponta |

---

## Nível 1: Apenas Governança

Use o CFA como um gate de políticas na frente de um pipeline existente.

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

**Uso típico**: pipelines Airflow/Dagster, scripts materializando dados em camadas governadas, sistemas que precisam de gate de políticas antes da execução.

---

## Nível 2: Governança + Resolução

Adicione resolução de intenções quando precisar de interpretação semântica de solicitações em linguagem natural.

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

**Modos de confirmação**:
- `AUTO` — alta confiança, baixa ambiguidade, sem risco protegido
- `SOFT` — confiança média, prossegue com logging
- `HARD` — dados protegidos em destino sensível, requer aprovação explícita
- `HUMAN_ESCALATION` — confiança muito baixa ou ambiguidade severa

---

## Nível 3: Kernel Parcial

Use validação, geração de código e sandbox sem orquestração completa.

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

## Nível 4: Kernel Completo

Fluxo governado ponta a ponta, de linguagem natural ao resultado da execução.

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

### Fases do Kernel

```
registro de contexto → normalização → confirmação → política
→ planejamento → geração de código → validação estática
→ execução no sandbox → validação em tempo real → execução parcial
→ projeção de estado → auditoria → avaliação de ciclo de vida
```

---

## Uso em CI/CD

```bash
cfa evaluate "Join NFe with Clientes persist Silver" \
    --catalog catalog.json \
    --policy-bundle policies/prod-v1.yaml \
    --exit-code
```

Exit code 1 se BLOCKED — compatível com GitHub Actions, GitLab CI ou qualquer pipeline CI.

---

## Uso como Teste Python

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

## Pacotes de Políticas Customizados

Crie `my-policy.yaml`:

```yaml
policy_bundle:
  version: "my-v1.0"
  description: "Regras de governança customizadas"
  rules:
    - name: forbid_raw_pii_in_silver
      condition: pii_in_protected_layer
      action: replan
      fault_code: GOVERNANCE_RAW_PII_IN_PROTECTED_LAYER
      severity: critical
      family: semantic
      message: "PII detectado sem tratamento em camada protegida."
      remediation:
        - "Aplique sha256() nas colunas PII antes do join"
```

```bash
cfa evaluate "intent" --policy-bundle my-policy.yaml
```

---

## Backends Customizados

```python
from cfa.backends import BackendAdapter, BackendCapabilities, BackendRegistry

class MeuBackend(BackendAdapter):
    def get_capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            backend_name="sql",
            supports_merge=True,
            supports_anonymization=False,
            supports_partition_overwrite=True,
        )

    def generate(self, plan):
        # Gera SQL a partir do plano
        ...

BackendRegistry.singleton().register("sql", lambda: MeuBackend())
```

```bash
cfa evaluate "intent" --backend sql
```

---

## Condições Customizadas

```python
from cfa.core.conditions import register_condition, build_condition

def minha_condicao(meta):
    def check(sig):
        return sig.domain == "finance" and len(sig.datasets) > 5
    return check

register_condition("finance_large_join", minha_condicao)
```

---

## Monitoramento de Ciclo de Vida

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

## Trilha de Auditoria

```bash
# Mostrar trilha de auditoria para uma intenção
cfa audit show --id abc12345

# Verificar integridade da cadeia
cfa audit verify

# Gerar relatório de auditoria
cfa report audit --intent-id abc12345 --output audit.html
```

---

## Próximos Passos

- **[Referência CLI](./cli)** — Todos os comandos e opções do `cfa`
- **[Pacotes de Políticas](./policy-bundles)** — Regras declarativas em YAML
- **[Servidor MCP](./mcp-server)** — Exponha o CFA para agentes de IA
- **[Relatórios](./reporting)** — Relatórios HTML ricos
- **[Integrações](./integrations/langgraph)** — Adaptadores para frameworks e orquestradores
