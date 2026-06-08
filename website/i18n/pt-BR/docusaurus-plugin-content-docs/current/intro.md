---
sidebar_position: 1
---

# Introdução

:::info Tradução
A versão em inglês é a fonte canônica. Esta tradução pode estar atrás de
edições recentes feitas no original. Se algo parecer divergir, consulte
a versão em inglês ou abra uma [issue](https://github.com/marquesantero/cfa/issues).
:::

CFA é um gate de governança tipado e pré-execução para agentes de IA e
pipelines de dados.

Você declara o que pretende fazer como uma `StateSignature`. O CFA responde
`approve`, `replan(remediations)` ou `block(reason)` — deterministicamente —
e grava a decisão em uma cadeia SHA-256 verificável offline.

A versão atual no PyPI é `1.0.0`. A próxima release (`1.1.0`) é um ciclo
editorial: cortes, consolidação, shims de deprecação e site reescrito —
sem features novas. Veja o
[roadmap](https://github.com/marquesantero/cfa/blob/main/drafts/ROADMAP.md).

## O que o CFA faz

1. **Recebe um contrato.** Uma `StateSignature` (JSON, YAML ou linguagem
   natural passada por um normalizer).
2. **Valida o contrato.** Estrutura, enums, campos obrigatórios.
3. **Faz cross-reference com o catálogo.** Os datasets têm que existir com
   metadados correspondentes.
4. **Avalia políticas declarativas.** PII, FinOps, merge keys, partições,
   tetos de custo.
5. **Decide.** `approve` / `replan(remediations)` / `block(reason)`.
6. **Registra uma decisão auditável.** Cadeia SHA-256 mais hashes de
   artefato para catálogo, policy bundle e signature.
7. **Acompanha saúde de ciclo de vida.** Índices IFo, IFs, IFg, IDI por
   pipeline (documentação aprofundada em `docs/lifecycle-indices` quando
   1.4.0 chegar).

## O que o CFA **não é**

- **Não é uma ferramenta de observabilidade de LLM.** Decide antes da
  execução, não depois. Combine com LangSmith, Phoenix ou Patronus para
  traces e eval.
- **Não é um motor de política genérico.** Combine com OPA quando precisar
  de policy-as-code em infra, APIs e CI/CD. O CFA ganha quando as políticas
  são *dataset-aware* (PII, partição, classificação, merge key).
- **Não é um catálogo de dados.** Combine com Unity Catalog, Atlan ou
  DataHub para descoberta, lineage e controle de acesso. O CFA lê
  catálogos; não substitui.
- **Não é validação de dado em repouso.** Combine com Great Expectations
  ou Soda para expectativas sobre dado já escrito. O CFA decide antes da
  escrita.

Veja [Compare](./compare) para tabelas lado a lado.

## Instalação rápida

```bash
pip install cfa-kernel
cfa init
cfa evaluate "Join NFe with Clientes and persist to Silver" \
  --catalog .cfa/catalog.json
```

## As cinco primitivas

Estas são as partes do CFA deliberadamente distintivas. Não vão mudar
entre releases.

| Primitiva | Onde mora |
|-----------|-----------|
| `StateSignature` tipada e content-hashed | `cfa.types.StateSignature` |
| `REPLAN` como cidadão de primeira classe | `cfa.policy.PolicyResult` + `cfa.types.PolicyAction` |
| Cadeia SHA-256 verificável offline | `cfa.audit.AuditTrail.verify_chain()` |
| Catálogo operacional (PII, partição, classificação, merge_key como primitivas de regra) | `cfa.types.DatasetRef` + `cfa.policy.catalog` |
| Determinístico por default; LLM como normalizer opcional | `cfa.normalizer.base.NormalizerBackend` |

## Para onde ir agora

- **[Getting Started](./getting-started)** — instale e rode seu primeiro
  governance check.
- **[CLI Reference](./cli)** — todos os comandos `cfa`.
- **[Policy Bundles](./policy-bundles)** — regras YAML declarativas.
- **[Backends](./backends)** — geração de código PySpark, SQL, dbt.
- **[MCP Server](./mcp-server)** — exponha o CFA para agentes de IA.
- **[Architecture Notes](./architecture-notes)** — decisões de design.
- **[FAQ](./faq)**.
