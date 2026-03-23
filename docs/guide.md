# CFA v2 -- Contextual Flux Architecture

## O que e

O CFA corrige 3 gaps de agentes e skills tradicionais:

| Gap | Problema | O que o CFA faz |
|-----|----------|-----------------|
| **Ambiguidade silenciosa** | LLM interpreta errado e executa com confianca | Formaliza a intencao em contrato tipado ANTES de executar |
| **Zero governanca** | Skill roda sem validar se pode (PII, custo, contrato) | Policy Engine valida regras declarativas antes da execucao |
| **Sem nocao de estado** | Ninguem sabe em que estado os dados ficaram | Context Registry mantem estado vivo, projetado apos cada execucao |

---

## 3 modulos independentes

O CFA e uma **biblioteca modular**. Cada modulo funciona sozinho. Use so o que precisa.

```
cfa.governance  -- Valida operacoes contra regras. Sem LLM, sem execucao.
cfa.resolution  -- Transforma linguagem natural em intencao tipada.
cfa.lifecycle   -- Monitora saude de pipelines com indices (IFo/IFs/IFg/IDI).
```

O pipeline completo (`KernelOrchestrator`) orquestra os 3 juntos. So use o pipeline completo quando precisar do fluxo inteiro.

---

## Modulo 1: cfa.governance

**Para que serve:** Validar operacoes de dados contra regras de governanca.

**Quando usar:** Voce ja tem um pipeline (Airflow, Dagster, script) e quer adicionar governanca ANTES de executar.

**O que NAO precisa:** LLM, cluster Spark, infraestrutura. Roda local, em memoria.

### Uso

```python
from cfa.governance import (
    PolicyEngine, StateSignature, TargetLayer,
    DatasetRef, DatasetClassification,
    SignatureConstraints, ExecutionContext,
)

# Declare o que seu pipeline faz
sig = StateSignature(
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
        partition_by=("processing_date",),
    ),
    execution_context=ExecutionContext("v1.0", "catalog_2026", "ctx_1"),
)

# Valide
engine = PolicyEngine()
result = engine.evaluate(sig)

if result.is_blocked:
    raise Exception(f"Bloqueado: {result.reasoning}")
# so entao executa seu pipeline
```

### 7 regras default

| Regra | Tipo | O que faz |
|-------|------|-----------|
| `forbid_raw_pii_in_silver_or_gold` | REPLAN | PII em camada protegida sem tratamento |
| `require_pii_anonymization_declaration` | BLOCK | Dataset com PII sem `no_pii_raw=True` |
| `require_partition_filter_for_high_volume` | REPLAN | High volume sem filtro de particao |
| `warn_on_sensitive_without_partition` | REPLAN | Sensitive sem particao declarada |
| `require_merge_key_for_silver_gold` | BLOCK | Silver/Gold sem merge key |
| `enforce_type_checking` | REPLAN | Camada protegida sem `enforce_types=True` |
| `enforce_cost_ceiling` | BLOCK | `max_cost_dbu` invalido |

### Adicionando regras customizadas

```python
from cfa.governance import PolicyRule, PolicyAction, FaultFamily, FaultSeverity

engine.add_rule(PolicyRule(
    name="fiscal_requer_particao_diaria",
    condition=lambda s: s.domain == "fiscal" and "processing_date" not in s.constraints.partition_by,
    action=PolicyAction.BLOCK,
    fault_code="FISCAL_SEM_PARTICAO",
    fault_family=FaultFamily.SEMANTIC,
    severity=FaultSeverity.CRITICAL,
    message="Pipeline fiscal deve ter particao por processing_date.",
))
```

### Static Validation (opcional)

Valida codigo PySpark contra tokens proibidos (collect, toPandas, crossJoin, import os).

```python
from cfa.governance import StaticValidator
from cfa.codegen import GeneratedCode

validator = StaticValidator()
result = validator.validate(generated_code, signature)
if not result.passed:
    print(result.fault_codes)
```

---

## Modulo 2: cfa.resolution

**Para que serve:** Transformar linguagem natural em intencao tipada (StateSignature).

**Quando usar:** Usuarios nao-tecnicos pedem operacoes de dados e voce precisa entender O QUE eles querem antes de executar.

**O que precisa:** Um backend de NLP (LLM ou rule-based).

### Uso com mock (teste)

```python
from cfa.resolution import IntentNormalizer, MockNormalizerBackend

normalizer = IntentNormalizer(backend=MockNormalizerBackend())
resolution = normalizer.normalize(
    raw_intent="Join NFe com Clientes e persista na Silver",
    environment_state={},
    catalog=CATALOG,
)

sig = resolution.signature
print(sig.domain)            # "fiscal_data_processing"
print(sig.target_layer)      # TargetLayer.SILVER
print(sig.contains_pii)      # True
print(resolution.confidence_score)    # 0.75
print(resolution.confirmation_mode)   # ConfirmationMode.HARD
```

### Uso com LLM real

```python
from cfa.resolution import NormalizerBackend, NormalizerInput, NormalizerOutput

class ClaudeBackend(NormalizerBackend):
    def resolve(self, inp: NormalizerInput) -> NormalizerOutput:
        response = claude.messages.create(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": f"""
                Intent: {inp.raw_intent}
                Catalog: {inp.catalog}
                Retorne JSON: domain, intent, target_layer, datasets, constraints, confidence_score
            """}],
        )
        return NormalizerOutput(**json.loads(response.content[0].text))

normalizer = IntentNormalizer(backend=ClaudeBackend())
```

### Confirmation Orchestrator

Escalona automaticamente para aprovacao humana baseado no risco:

| Situacao | Modo |
|----------|------|
| Alta confianca, sem PII, nao e Gold | AUTO (passa direto) |
| Confianca media | SOFT |
| PII + Silver/Gold | HARD |
| Gold, ou confianca < 65% com PII, ou multiplas interpretacoes | HUMAN_ESCALATION |

---

## Modulo 3: cfa.lifecycle

**Para que serve:** Monitorar saude de pipelines e decidir quais promover/demover.

**Quando usar:** Voce tem pipelines recorrentes e quer saber quais sao estaveis, quais estao degradando, e quais aposentar.

**O que NAO precisa:** LLM, cluster. So precisa de metricas de execucao.

### Uso

```python
from cfa.lifecycle import PromotionEngine, PromotionPolicy, ExecutionRecord, SkillState
from datetime import datetime, timezone

engine = PromotionEngine(policy=PromotionPolicy(min_executions=5))

# Registre metricas de cada execucao
engine.record_execution(ExecutionRecord(
    signature_hash="meu_pipeline_abc",
    timestamp=datetime.now(timezone.utc),
    success=True,
    cost_dbu=5.0,
    duration_seconds=30.0,
))

# Avalie
skill, scores = engine.evaluate("meu_pipeline_abc")
print(f"Estado: {skill.state.value}")  # candidate -> active -> watchlist -> ...
print(f"IFo={scores.ifo:.2f} IFs={scores.ifs:.2f} IDI={scores.idi:.2f}")
```

### 4 indices

| Indice | O que mede | Formula |
|--------|-----------|---------|
| **IFo** | Fluidity operacional | (1 - latencia) x (1 - custo) x taxa_sucesso |
| **IFs** | Fidelidade semantica | schema_ok x sem_drift x sem_faults |
| **IFg** | Governanca (binario) | 1 se tudo ok, 0 se qualquer violacao |
| **IDI** | Drift de intencao | 1 - (replanejados / total) em 30 dias |

### Gate de promocao

```
Promote  <==  IFo >= 0.75  AND  IFs >= 0.90  AND  IFg = 1  AND  executions >= min
```

### Triggers de demotion

| Trigger | Acao |
|---------|------|
| IDI < 0.50 (drift severo) | Demotion imediato |
| IFg < 1 (violacao de governanca) | Demotion imediato |
| IDI < 0.75 (drift moderado) | Watchlist |
| IFs abaixo do threshold | Watchlist |
| Inatividade prolongada | Deprecated |
| Catalogo incompativel | Retired |

### Mass demotion (bug recovery)

```python
# Se descobrir bug na versao que promoveu skills
demoted = engine.demote_by_system_version("cfa_v2.0", "Bug na logica de promocao")
```

---

## Pipeline completo (KernelOrchestrator)

So use quando precisar de TUDO junto: linguagem natural -> governanca -> planejamento -> codegen -> execucao -> projecao -> lifecycle.

```python
from cfa import KernelOrchestrator, KernelConfig

kernel = KernelOrchestrator(catalog=CATALOG)
result = kernel.process("Join NFe com Clientes e persista na Silver")

print(result.state.value)           # approved / blocked / quarantined / ...
print(result.signature.signature_hash)
print(result.execution_plan.step_count)
print(result.generated_code.code)
print(result.sandbox_result.aggregate_metrics.rows_output)
```

### Desabilitando fases

```python
kernel = KernelOrchestrator(
    catalog=CATALOG,
    config=KernelConfig(
        enable_planning=False,           # sem plano de execucao
        enable_codegen=False,            # sem geracao de codigo
        enable_static_validation=False,  # sem validacao estatica
        enable_sandbox=False,            # sem execucao
        enable_promotion=False,          # sem lifecycle
    ),
)
# Agora funciona so como: normalizer -> policy -> decisao
```

---

## Integrando com pipeline existente

### Airflow

```python
from airflow.decorators import task
from cfa.governance import PolicyEngine

engine = PolicyEngine()

@task
def validar_governanca(signature_dict: dict):
    sig = StateSignature(**signature_dict)
    result = engine.evaluate(sig)
    if result.is_blocked:
        raise AirflowException(f"Bloqueado: {result.reasoning}")

@task
def executar_spark(config: dict):
    # seu codigo Spark atual, inalterado
    ...

# DAG: validar_governanca >> executar_spark
```

### Script existente

```python
from cfa.governance import PolicyEngine, StateSignature, ...

def meu_pipeline():
    sig = montar_signature(...)  # declara o que o pipeline faz

    # Governanca
    result = PolicyEngine().evaluate(sig)
    if result.is_blocked:
        return f"Bloqueado: {result.reasoning}"

    # Execucao normal
    spark.read("nfe").join(spark.read("clientes")).write("silver")
```

---

## Estrutura do projeto

```
src/cfa/
  governance/        <-- uso standalone: validacao + policy
    __init__.py
  resolution/        <-- uso standalone: NLP -> intencao tipada
    __init__.py
  lifecycle/         <-- uso standalone: indices + promocao
    __init__.py

  types.py           fundacao: StateSignature, Fault, enums
  policy.py          Policy Engine (7 regras)
  normalizer.py      Intent Normalizer + Confirmation
  planner.py         Execution Planner (DAG)
  codegen.py         PySpark Generator
  static_validation.py  Static Validation
  sandbox.py         Sandbox Executor
  runtime_validation.py  Runtime Validation
  partial_execution.py   Failure policies
  context.py         Context Registry (persistente)
  state_projection.py  State Projection Protocol
  audit.py           Audit Trail (hash chain)
  indices.py         IFo, IFs, IFg, IDI
  promotion.py       Promotion/Demotion Engine
  kernel.py          KernelOrchestrator (orquestra tudo)

examples/
  standalone_governance.py   <-- use so governanca
  standalone_resolution.py   <-- use so resolucao
  standalone_lifecycle.py    <-- use so lifecycle
  full_pipeline.py           <-- pipeline completo

tests/               201 testes
```
