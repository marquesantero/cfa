---
sidebar_position: 1
---

# Introdução

:::info Tradução
A versão em inglês é a fonte canônica. Esta tradução pode estar atrás de
edições recentes feitas no original. Se algo parecer divergir, consulte
a versão em inglês ou abra uma [issue](https://github.com/marquesantero/cfa/issues).
:::

**Um gate de governança tipado e pré-execução para agentes de IA e
pipelines de dados.**

Você declara o que pretende fazer como uma `StateSignature`. O CFA
responde `approve`, `replan(remediations)` ou `block(reason)` —
deterministicamente — em **menos de 3 ms p99** num kernel quente, e
grava a decisão numa cadeia SHA-256 verificável offline com
`cfa audit verify`. Sem rede. Sem servidor. Sem chaves.

## Por que o CFA existe

Seis coisas concretas que o CFA faz hoje e nenhuma ferramenta vizinha
entrega junto:

### 1. Remediação estruturada, não apenas sim/não

Quando uma regra com fix possível falha, o CFA devolve o fix como dado.
O caller — agente LLM, passo de CI, humano — aplica e reenvia. O loop
de recuperação é parte do contrato, com limite de três tentativas, e
fica gravado na auditoria.

```json
{
  "action": "replan",
  "interventions": [
    "Set constraints.no_pii_raw=True",
    "Apply sha256() on PII columns before the join"
  ]
}
```

### 2. Cadeia de auditoria verificável offline

Cada decisão é um evento content-hashed encadeado numa cadeia SHA-256.
`cfa audit verify` reproduz a cadeia em qualquer máquina que tenha o
arquivo JSONL — sem vendor, sem servidor, sem chave de API, sem rede.

```bash
$ cfa audit verify --file audit.jsonl
OK · 1 274 events verified · last_hash=a4f3…6c01
```

### 3. Primitivas de política dataset-aware

Colunas PII, particionamento, classificação, merge keys, target layer
— primitivas de primeira classe, não metadados que você re-codifica
em Rego. Uma regra real cabe em seis linhas YAML.

### 4. Uma signature, três backends de produção

A mesma `StateSignature` aprovada gera código para **PySpark + Delta
Lake**, **SQL ANSI com `MERGE INTO`** ou **modelos dbt com schema.yml**.

### 5. Servidor MCP funcionando hoje

Qualquer agente compatível com MCP (Claude Desktop, Cursor, Continue,
LangGraph custom) chama o CFA antes de tocar produção. Cinco
ferramentas expostas via JSON-RPC.

### 6. Determinístico por padrão; LLM é opt-in

O path de decisão é função pura de `(signature, policy_bundle, catalog)`.
Mesma entrada → mesma decisão → mesmo hash, sempre, sem chamada de
rede. LLMs participam só na borda de entrada (intent → signature) e
apenas se você pedir via extra `[llm]`.

Cada uma dessas decisões tem ADR registrada em
[`docs/adr/`](https://github.com/marquesantero/cfa/tree/main/docs/adr).

## Instalação rápida

```bash
pip install cfa-kernel
cfa init
cfa evaluate "Join NFe with Clientes and persist to Silver" \
  --catalog .cfa/catalog.json
```

Para um gate de CI real, a forma decorator de quatro linhas:

```python
from cfa.adapters import cfa_guard

@cfa_guard("Join NFe with Clientes anonymize CPF persist Silver",
           policy_bundle="policies/prod-v1.yaml", catalog=CATALOG)
def my_pipeline(): ...
```

O decorator cacheia um único `KernelOrchestrator` por guard e adiciona
~2.4 ms p99 à sua chamada.

## Onde o CFA combina (em vez de substituir)

CFA **não** é ferramenta de observabilidade de LLM, motor de política
genérico, catálogo de dados, nem validação de dado em repouso. Combine
respectivamente com LangSmith / Phoenix / Patronus, OPA, Unity Catalog /
Atlan / DataHub, e Great Expectations / Soda.

Veja [Compare](./compare) para tabelas lado a lado.

## Para onde ir agora

- **[Getting Started](./getting-started)** — instale e rode seu primeiro
  governance check.
- **[CLI Reference](./cli)** — todos os comandos `cfa`.
- **[Policy Bundles](./policy-bundles)** — regras YAML declarativas.
- **[Backends](./backends)** — geração de código PySpark, SQL, dbt.
- **[MCP Server](./mcp-server)** — exponha o CFA para agentes de IA.
- **[Architecture Notes](./architecture-notes)** — decisões de design.
- **[FAQ](./faq)**.
