# CFA v2

[![CI](https://github.com/marquesantero/cfa/actions/workflows/ci.yml/badge.svg)](https://github.com/marquesantero/cfa/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

**Contextual Flux Architecture** -- um kernel de execucao governada para sistemas de dados orientados por IA.

A maioria dos sistemas agenticos pula direto do prompt para a acao. O CFA coloca governanca, validacao e estado entre esses dois pontos: a intencao e formalizada em contrato tipado, avaliada contra regras, executada em sandbox, e o resultado e projetado de volta no estado do ambiente.

Em vez de perguntar _"qual agent ou skill deve agir?"_, o CFA pergunta _"qual mudanca de estado esta sendo pedida, sob quais restricoes, e ela pode ser executada com seguranca?"_

## 3 gaps que o CFA resolve

| Gap | O que acontece hoje | O que o CFA faz |
|-----|---------------------|-----------------|
| **Ambiguidade silenciosa** | LLM interpreta errado e executa com confianca | Formaliza a intencao em `StateSignature` antes de qualquer execucao |
| **Zero governanca** | Skill roda sem validar PII, custo, schema | `PolicyEngine` valida regras declarativas antes da execucao |
| **Sem modelo de estado** | Ninguem sabe em que estado os dados ficaram | `ContextRegistry` projeta e persiste estado apos cada execucao |

## Modular por design

Cada modulo funciona de forma independente. Use so o que precisa.

```
cfa.governance   Valida operacoes contra regras. Sem LLM, sem cluster.
cfa.resolution   Transforma linguagem natural em intencao tipada.
cfa.lifecycle    Monitora saude de pipelines com indices quantitativos.
```

O pipeline completo (`KernelOrchestrator`) orquestra os tres juntos quando voce precisa do fluxo inteiro.

---

## Instalacao

```bash
pip install -e .        # basico
pip install -e .[dev]   # com pytest
```

```bash
pytest -q               # 203 testes, <1s
```

---

## cfa.governance

Adiciona governanca a pipelines existentes. Funciona sem LLM, sem Spark, sem infraestrutura.

```python
from cfa.governance import (
    PolicyEngine, StateSignature, TargetLayer,
    DatasetRef, DatasetClassification,
    SignatureConstraints, ExecutionContext,
)

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

engine = PolicyEngine()
result = engine.evaluate(sig)

if result.is_blocked:
    raise Exception(f"Bloqueado: {result.reasoning}")
```

7 regras declarativas incluidas (PII, merge key, particao, custo, type enforcement). Regras customizadas sao funcoes `StateSignature -> bool`.

Tambem inclui `StaticValidator` para checar codigo PySpark contra tokens proibidos (collect, toPandas, crossJoin, import os).

## cfa.resolution

Transforma pedidos em linguagem natural em contratos tipados.

```python
from cfa.resolution import IntentNormalizer, MockNormalizerBackend

normalizer = IntentNormalizer(backend=MockNormalizerBackend())
resolution = normalizer.normalize(
    raw_intent="Join NFe com Clientes e persista na Silver",
    environment_state={},
    catalog=catalog,
)

sig = resolution.signature
# sig.domain, sig.target_layer, sig.contains_pii, resolution.confidence_score
```

O `MockNormalizerBackend` serve para testes. Para producao, implemente `NormalizerBackend` com seu LLM.

O `ConfirmationOrchestrator` escala automaticamente para aprovacao humana quando o risco e alto (PII em camada protegida, confianca baixa, multiplas interpretacoes).

## cfa.lifecycle

Monitora saude de pipelines recorrentes e decide quais promover ou aposentar.

```python
from cfa.lifecycle import PromotionEngine, PromotionPolicy, ExecutionRecord
from datetime import datetime, timezone

engine = PromotionEngine(policy=PromotionPolicy(min_executions=5))

engine.record_execution(ExecutionRecord(
    signature_hash="pipeline_fiscal_abc",
    timestamp=datetime.now(timezone.utc),
    success=True,
    cost_dbu=5.0,
    duration_seconds=30.0,
))

skill, scores = engine.evaluate("pipeline_fiscal_abc")
# skill.state: candidate -> active -> watchlist -> deprecated -> retired
# scores: ifo, ifs, ifg, idi
```

4 indices quantitativos:

| Indice | O que mede |
|--------|-----------|
| **IFo** | Fluidity operacional -- latencia, custo, taxa de sucesso |
| **IFs** | Fidelidade semantica -- schema, drift, faults |
| **IFg** | Governanca -- binario: 1 se tudo ok, 0 se qualquer violacao |
| **IDI** | Drift de intencao -- proporcao de replans em janela de 30 dias |

Gate de promocao: `IFo >= 0.75 AND IFs >= 0.90 AND IFg = 1`. Drift severo ou violacao de governanca causa demotion imediato.

---

## Pipeline completo

Quando voce precisa do fluxo inteiro -- da linguagem natural ate a projecao de estado:

```python
from cfa import KernelOrchestrator

kernel = KernelOrchestrator(catalog=catalog)
result = kernel.process("Join NFe com Clientes e persista na Silver")

print(result.state.value)  # approved / blocked / quarantined / rolled_back
```

Fluxo interno:

```
intent -> normalization -> confirmation -> policy -> planning -> codegen
-> static validation -> sandbox -> runtime validation -> partial execution
-> state projection -> audit -> lifecycle evaluation
```

Cada fase pode ser desabilitada via `KernelConfig`.

---

## Integracao com pipelines existentes

O caso de uso mais comum e adicionar governanca a um pipeline que ja existe:

```python
# Airflow
from airflow.decorators import task
from cfa.governance import PolicyEngine

@task
def validar(signature_dict: dict):
    result = PolicyEngine().evaluate(StateSignature(**signature_dict))
    if result.is_blocked:
        raise AirflowException(f"Bloqueado: {result.reasoning}")

# validar >> executar_spark
```

```python
# Script
from cfa.governance import PolicyEngine, StateSignature

sig = montar_signature(...)
result = PolicyEngine().evaluate(sig)
if result.is_blocked:
    sys.exit(f"Bloqueado: {result.reasoning}")

# execucao normal do seu pipeline
```

---

## Conceitos-chave

**StateSignature** -- contrato imutavel que captura dominio, intencao, datasets, restricoes e contexto de execucao. Tem hash SHA256 deterministico. Toda decisao do kernel parte de uma signature.

**ContextRegistry** -- modelo de estado persistente do ambiente. Nao e um log; e o estado corrente relevante para decisoes futuras. Aceita backends customizados (JSON, DB).

**Faults** -- falhas tipadas em 4 familias (semantic, static, runtime, environmental) em vez de excecoes genericas. Sao eventos, nao erros.

**Audit Trail** -- eventos append-only com hash chain SHA256 para deteccao de adulteracao. Cada evento referencia o hash do anterior.

---

## Estrutura

```
src/cfa/
  governance/         uso standalone: policy + validacao
  resolution/         uso standalone: NLP -> contrato tipado
  lifecycle/          uso standalone: indices + promocao

  types.py            StateSignature, Fault, enums
  policy.py           PolicyEngine, 7 regras declarativas
  normalizer.py       IntentNormalizer, ConfirmationOrchestrator
  planner.py          ExecutionPlanner (DAG)
  codegen.py          PySparkGenerator
  static_validation.py
  sandbox.py          SandboxExecutor
  runtime_validation.py
  partial_execution.py
  context.py          ContextRegistry (persistente)
  state_projection.py
  audit.py            AuditTrail (hash chain)
  indices.py          IFo, IFs, IFg, IDI
  promotion.py        PromotionEngine
  kernel.py           KernelOrchestrator

examples/             4 exemplos standalone e pipeline completo
tests/                203 testes
docs/                 whitepaper PT-BR e EN, guia de uso
```

---

## Limitacoes conhecidas

- O normalizer padrao e um mock deterministico -- producao precisa de um `NormalizerBackend` real
- Codegen e orientado a PySpark -- outros runtimes precisam de novos backends
- Persistencia usa JSON/JSONL -- ambientes de producao provavelmente vao querer um backend de banco
- Concorrencia e conservadora por design (single-writer)

## Proximo

- Backends de resolucao semantica para producao (LLM)
- Contratos mais ricos no planner (merge keys, target scopes)
- Adaptadores de execucao alem de PySpark
- Observabilidade no runtime

---

## Documentacao

- [Whitepaper PT-BR](./cfa-v2-whitepaper.html) / [EN](./docs/cfa-v2-whitepaper.en.html) -- referencia arquitetural completa
- [Guia de uso](./docs/guide.md) -- exemplos praticos e integracao
- [Exemplos](./examples/) -- scripts prontos para cada modulo
- [GitHub Pages](https://marquesantero.github.io/cfa/) -- pagina do projeto

## Contribuindo

Veja [`CONTRIBUTING.md`](./CONTRIBUTING.md). O projeto separa contribuicoes de arquitetura (whitepaper, invariantes) de implementacao (kernel, adapters, testes).

## Licenca

[MIT](./LICENSE)
