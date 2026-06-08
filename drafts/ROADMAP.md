# CFA — Plano de Correções e Crescimento

> Documento vivo. Última revisão: 2026-06-08. Owner: Antero Marques.
> Status: draft v1 — sujeito a iteração antes de virar plano de release.

---

## 0. Sumário executivo

CFA hoje está em **0.1.9**, alpha, mantenedor solo. Tem código de qualidade acima da média (534 testes, 83% cobertura, tipos imutáveis, hash chain real, zero deps no core), mas está em rota de colisão com OPA, LangSmith e Unity Catalog porque o pitch tenta cobrir os três simultaneamente sem vencer nenhum.

Este plano organiza a evolução em **três movimentos** (cunha → expansão → plataforma) ao longo de aproximadamente 18 meses, preservando o DNA distintivo e cortando ruído que dilui esse DNA. Cada movimento tem releases concretas, deliveráveis técnicos por release, critérios de saída mensuráveis e riscos identificados.

A próxima release (**0.2.0 — Foco**) faz a limpeza necessária para o DNA ser visível. A release seguinte (**0.3.0 — Primeira integração**) cria o primeiro caso de uso público inegável. A partir daí o projeto ganha direito de expandir.

---

## 1. Tese estratégica

### 1.1. O lugar que CFA ocupa

> CFA é o **gate de pré-execução tipado e verificável** entre quem pede uma escrita governada em dado (humano, agente, orquestrador) e o sistema que executa.

Esse seam — *pré-execução*, *dataset-aware*, *com remediação estruturada*, *com audit verificável offline* — não é ocupado por nenhuma das alternativas maduras:

- **OPA** é genérico, não conhece PII/partition/merge_key sem Rego de zero.
- **LangSmith / Patronus / Galileo** são pós-fato (observabilidade, eval).
- **Great Expectations / Soda** validam dado em repouso, não intenção.
- **Unity Catalog / Atlan / DataHub** são catálogos passivos, não decisores.
- **Open Lineage** é emissão de evento, não política.

### 1.2. DNA — as 5 primitivas distintivas

Qualquer evolução deve preservar e amplificar estas:

1. **Signature tipada e content-hashed.** Hash determinístico de (domain, intent, target_layer, datasets, constraints). Permite cache de decisão, replay e idempotência. Hoje em `cfa.types.StateSignature`.
2. **REPLAN como cidadão de primeira classe.** Decisão não é só yes/no — é `approve | replan(remediations) | block(reason)`. Caller pode aplicar remediação e reenviar. Hoje em `cfa.policy.PolicyResult` + `cfa.types.PolicyAction`.
3. **Cadeia SHA-256 verificável offline.** `verify_chain()` funciona sem rede, sem servidor, sem chave. Hoje em `cfa.audit.AuditTrail`.
4. **Catálogo operacional.** PII, classification, partition, merge_key são primitivas de regra, não metadados de busca. Hoje em `cfa.types.DatasetRef` + `cfa.policy.catalog`.
5. **Determinístico por default, LLM por opção.** A decisão é função pura de (signature, policy, catalog). LLM é normalizer plugável, nunca decisor. Hoje em `cfa.normalizer.base.NormalizerBackend`.

Qualquer release que dilua estas (ex.: tornar LLM obrigatório no path crítico, fazer audit depender de servidor remoto) está fora do plano.

### 1.3. Princípios operacionais

- **Determinismo no path crítico.** Mesma entrada → mesma decisão → mesmo hash.
- **Imutabilidade.** `frozen=True` em todo tipo de domínio; replan gera nova Signature.
- **Zero deps no core.** Extras (`yaml`, `otel`, `mcp`, `llm`, `dbt`, `airflow`) ficam em `[project.optional-dependencies]`.
- **API pública contractualizada.** Tudo exposto em `cfa.__init__.__getattr__` é parte do contrato e segue semver a partir de 1.0.
- **Honestidade nos deliveráveis.** Adapter listado é adapter que existe.
- **Documentação como código.** Toda decisão de arquitetura vira ADR em `docs/adr/`.

---

## 2. Visão dos três movimentos

| Movimento | Releases | Duração | Objetivo |
|-----------|----------|---------|----------|
| **I — Cunha** | 0.2.0 → 0.3.x | ~6-9 meses | Ser referência inegável em "pre-execution governance gate" |
| **II — Expansão lateral** | 0.4.0 → 0.7.x | ~9-12 meses | DNA se expressa nas adjacências (lifecycle, MCP, backends, state projection) |
| **III — Plataforma** | 1.0 → 1.x | 12+ meses | "CFA Protocol" — categoria nomeada, ecossistema, hosted version opcional |

Cada movimento tem **critério de saída mensurável**. Não se passa para o próximo só porque o calendário virou. Se Movimento I não atingiu o critério em 9 meses, revisitamos a tese antes de seguir.

---

## 3. Movimento I — Cunha

### 3.1. Goal narrativo

Quando alguém perguntar "qual ferramenta usar para validar tipadamente uma escrita governada em Silver/Gold *antes* dela acontecer?" — a resposta padrão é CFA.

### 3.2. Critério de saída

Pelo menos **uma das seguintes** acontece publicamente:
- Issue de terceiro relatando uso em produção.
- Comparação em blog/post de terceiro que cita CFA ao lado de OPA/GE.
- PR não-trivial de contribuidor externo.
- ≥3 menções orgânicas (LinkedIn, X, Reddit, HN).
- ≥500 downloads/mês no PyPI por 2 meses consecutivos.

---

### 3.3. Release 0.2.0 — Foco

**Objetivo:** remover tudo que dilui o DNA. Reescrever pitch. Consolidar pacotes. Sem features novas.

**Duração estimada:** 1-2 semanas de trabalho dedicado.

#### 3.3.1. Trilha A — Cortes editoriais

| Item | Ação | Arquivo/local |
|------|------|---------------|
| Adapters falsos | Remover `langgraph.py`, `crewai.py`, `autogen.py`, `dspy.py`, `openai_agents.py`. Criar `docs/integrations/use-cfa-guard-with-frameworks.md` único, mostrando padrão de uso. | `src/cfa/adapters/` |
| Hero "Whitepaper" | Hero passa a ser demo de 20s em ASCII/code + CTA para Getting Started. Whitepaper vira link secundário. | `website/src/pages/index.tsx` |
| Letras gregas no marketing | Remover `(Φ, Γ, Π, Ω, Σ)` do whitepaper público (renomear para "Architecture Notes"). Mantém versão interna em `docs/internal/`. | `website/docs/whitepaper.md` |
| Versão "v1.0.0" no site | Padronizar tudo com `__version__` lido do package. Adicionar build hook no Docusaurus. | `website/src/`, `website/docs/api.md` |
| Tabela "✅/❌ Others" | Já removida no README, remover também em `website/docs/intro.md`. | `website/docs/intro.md:85-97` |
| Blog template Docusaurus | Apagar `website/blog/` inteiro. Substituir por 1 release notes da 0.2.0. | `website/blog/` |
| Docs de planejamento na raiz | Mover `CFA_IMPLEMENTATION_PLAN.md`, `CFA_MARKET_RESEARCH_2026.md`, `MANUAL_TESTING_GUIDE.md` para `drafts/`. Adicionar `.gitignore` para `cfa_test_results_*/`. | raiz do repo |
| Keywords PT-BR/fiscal hardcoded | Tirar `_DOMAIN_KEYWORDS` específicos do `RuleBasedNormalizerBackend`. Criar `examples/fiscal_pt_br_normalizer.py` mostrando como estender. | `src/cfa/normalizer/base.py:82-93` |
| Status alpha no site | Banner persistente "Alpha — APIs may change" em todas as páginas. | `website/src/theme/` |

#### 3.3.2. Trilha B — Consolidação de pacotes

Reduzir de **20 subpacotes para ~13** sem quebrar API pública (manter re-exports nos antigos com `DeprecationWarning`).

```text
ANTES (atual)                  →  DEPOIS (0.2.0)
─────────────────────────────────────────────────────────
core/                          →  core/                 (kernel + phases + types)
governance/                    →  REMOVIDO              (absorvido por policy/)
policy/                        →  policy/               (engine + bundle + rules + catalog)
validation/                    →  validate/             (renomeado, mais curto)
resolution/                    →  REMOVIDO              (absorvido por resolve/)
normalizer/                    →  resolve/              (renomeado: intent→signature)
audit/                         →  audit/                (sem mudança)
observability/                 →  obs/                  (renomeado, mais curto)
lifecycle/                     →  lifecycle/            (sem mudança)
execution/                     →  execution/            (sem mudança)
adapters/                      →  REMOVIDO              (vira pasta de docs)
backends/                      →  backends/             (sem mudança)
sandbox/                       →  sandbox/              (sem mudança)
cli/                           →  cli/                  (sem mudança)
storage/                       →  storage/              (sem mudança)
mcp/                           →  mcp/                  (sem mudança)
reporting/                     →  reporting/            (sem mudança)
runtime/                       →  runtime/              (sem mudança)
testing/                       →  testing/              (sem mudança)
behavior/                      →  behavior/             (sem mudança, candidato a fundir com resolve em 0.4)
```

Implementação: para cada pacote movido, deixar shim:

```python
# src/cfa/governance/__init__.py (mantido por 2 minor releases)
import warnings
warnings.warn("cfa.governance is deprecated; use cfa.policy", DeprecationWarning, stacklevel=2)
from cfa.policy import *  # noqa
```

#### 3.3.3. Trilha C — Reescrita de narrativa

Substituir README, `intro.md`, e homepage por linguagem operacional, sem letras gregas, sem "kernel para tudo". Modelo:

> **CFA** valida intenções de escrita governada antes da execução.
>
> Você descreve o que vai fazer como uma `StateSignature` tipada. CFA responde com `approve`, `replan(remediations)` ou `block(reason)`. Cada decisão entra numa cadeia SHA-256 verificável offline.
>
> Funciona como decorator Python, CLI, MCP tool, e integrações com dbt e Airflow (em breve).
>
> Não precisa de LLM. Não precisa de rede. Não substitui OPA — completa em casos dataset-aware.

Adicionar seção **"What CFA is not"** explícita:

- Não é um observability tool — use LangSmith/Phoenix para isso.
- Não é um catalog — use Unity Catalog/Atlan/DataHub para isso, e plugue catalog no CFA.
- Não é um data quality tool em repouso — use Great Expectations/Soda para isso.
- Não substitui OPA em casos genéricos de policy-as-code.

Adicionar página comparativa: `website/docs/compare.md`.

#### 3.3.4. Trilha D — Cache no decorator

[`CFAGuard._check`](src/cfa/adapters/__init__.py) instancia kernel completo a cada chamada. Corrigir:

```python
class CFAGuard:
    def __init__(self, ...):
        self._kernel: KernelOrchestrator | None = None
        ...

    def _get_kernel(self) -> KernelOrchestrator:
        if self._kernel is None:
            self._kernel = KernelOrchestrator(...)
        return self._kernel

    def _check(self, intent: str) -> None:
        result = self._get_kernel().process(intent)
        ...
```

Adicionar benchmark micro em `tests/perf/test_guard_overhead.py`: chamada decorada ≤ 5ms p99 com normalizer rule-based.

#### 3.3.5. Trilha E — ADRs

Criar `docs/adr/` com formato MADR:

- `0001-typed-signature-as-contract.md`
- `0002-sha256-hash-chain-offline-verifiable.md`
- `0003-replan-as-first-class.md`
- `0004-deterministic-by-default-llm-as-extra.md`
- `0005-package-consolidation-0.2.0.md`
- `0006-no-fake-adapters.md`

Cada ADR ≤2 páginas: contexto, decisão, consequências, alternativas consideradas.

#### 3.3.6. Critério de release 0.2.0

- [ ] Pacotes consolidados, todos os testes passando (mantém 534+).
- [ ] Adapters falsos removidos, doc honesto no lugar.
- [ ] README + intro + homepage reescritos.
- [ ] Site limpo: blog template removido, versão consistente, banner alpha.
- [ ] 6 ADRs publicados.
- [ ] CHANGELOG.md com migration notes (breaking + deprecations).
- [ ] Tag `v0.2.0` no GitHub, release no PyPI.
- [ ] Release notes em blog do site.

---

### 3.4. Release 0.3.0 — Primeira integração real

**Objetivo:** o primeiro caso de uso público inegável. Escolher **uma** integração e fazê-la com qualidade de referência.

**Duração estimada:** 2-4 semanas.

#### 3.4.1. A escolha: dbt check

dbt é a escolha racional para a primeira integração porque:

1. Tem manifest determinístico (`target/manifest.json`) → fácil derivar `StateSignature`.
2. CI-friendly (todo time dbt já tem CI).
3. Resolve dor real (dbt contracts cobrem schema, não governance).
4. ICP coincide com o que CFA já assume (lakehouse-shape, layers, partitions).
5. Não requer infra (Airflow exige rodar Airflow, Databricks exige cluster).

#### 3.4.2. Escopo técnico

**Novo módulo:** `src/cfa/integrations/dbt/`

```
src/cfa/integrations/dbt/
├── __init__.py          # API pública: check(), derive_signature()
├── manifest.py          # Parser do target/manifest.json
├── signature.py         # ModelNode → StateSignature
├── cli.py               # Subcomando `cfa dbt check`
└── runner.py            # Orquestra: ler manifest → gerar sigs → policy → relatório
```

**CLI:**

```bash
cfa dbt check --project-dir ./my_dbt_project \
              --policy-bundle policies/prod-v1.yaml \
              --catalog .cfa/catalog.json \
              --fail-on block \
              --format json
```

**Comportamento:**
1. Lê `target/manifest.json` (executar `dbt parse` antes se não existe).
2. Para cada `node` materializado (table/incremental), deriva `StateSignature`:
   - `domain` ← schema do model
   - `intent` ← materialization type
   - `target_layer` ← inferido por convenção configurável (`mart_` → gold, `int_` → silver, etc.)
   - `datasets` ← refs + sources do model, casados com catálogo CFA
   - `constraints.partition_by` ← `partition_by` config do dbt
   - `constraints.merge_key_required` ← `unique_key` config
3. Roda `PolicyEngine.evaluate(sig)` em cada.
4. Emite relatório agregado (table/json/junit).
5. Exit code conforme `--fail-on`.

**Detalhes de qualidade:**
- Mapping configurável via `cfa.yaml` (`dbt.layer_mapping`).
- Suporte a `dbt-core` 1.7+ (manifest schema versionado).
- Cache de decisão por `model_hash` (se model não mudou, decisão reusada via signature_hash).
- Output formato JUnit XML para CI.

**Demo end-to-end:** `examples/dbt_demo/` com projeto dbt mínimo que provoca todos os 3 outcomes (approve, replan, block) + GitHub Action.

#### 3.4.3. Trilha paralela — Catalog auto-discovery

Para dbt check funcionar bem, CFA precisa entender catalog de fontes externas. Adicionar:

```python
from cfa.policy.catalog import Catalog

cat = Catalog.from_dbt_manifest("target/manifest.json")
cat = Catalog.from_unity_catalog(workspace_url=..., catalog_name=...)
cat = Catalog.from_json(".cfa/catalog.json")
cat = Catalog.merge(cat_a, cat_b)
```

Implementação só do `from_dbt_manifest` e `from_json` em 0.3.0. UC fica para 0.4+.

#### 3.4.4. Documentação

- `website/docs/integrations/dbt.md` — guia completo, 1500-2000 palavras.
- `website/docs/tutorials/governance-for-dbt-projects.md` — tutorial end-to-end.
- Atualizar README com seção "Use CFA in your dbt project".
- Screencast de 3min mostrando block → replan → approve.

#### 3.4.5. Critério de release 0.3.0

- [ ] `cfa dbt check` funcional em projeto dbt real (criar um para demo).
- [ ] ≥30 testes específicos do módulo dbt, ≥85% cobertura.
- [ ] Demo público no `examples/dbt_demo/`.
- [ ] GitHub Action funcionando no demo.
- [ ] Página de docs publicada.
- [ ] Post de release com video/gif demonstrativo.

---

### 3.5. Releases 0.3.x — Hardening

Pequenas releases de polish. Não introduzem categoria nova.

| Release | Conteúdo principal |
|---------|-------------------|
| 0.3.1 | Bug fixes pós-0.3.0; cobertura ≥85% global |
| 0.3.2 | Performance: bench p99 ≤5ms para gate path; profile e otimizar hot paths |
| 0.3.3 | Standalone audit verifier: binário Python `cfa-verify` que verifica chain sem dependência do resto. Útil para auditoria offline. |
| 0.3.4 | Catalog federation MVP: `Catalog.merge()` + suporte a UC (`from_unity_catalog`) |
| 0.3.5 | Estabilidade: 60 dias sem bug crítico aberto |

#### 3.5.1. Critério para fechar Movimento I

- Movimento I termina quando o **critério de saída de 3.2** é atingido.
- Antes disso, todas as releases ficam em 0.3.x. Não há 0.4.0 sem cunha plantada.

---

## 4. Movimento II — Expansão lateral

### 4.1. Goal narrativo

CFA deixa de ser "ferramenta para dbt check" e vira "categoria de governance pré-execução com 4 superfícies: CLI, decorator, MCP, integrações nativas (dbt, Airflow, Databricks)". DNA distintivo passa a se expressar fora do escopo inicial.

### 4.2. Critério de saída

Pelo menos **três das seguintes**:
- ≥1 contribuidor externo com 5+ PRs aceitos.
- Aparece em comparação publicada por terceiro (Galileo, Maxim, Patronus blog, etc.).
- ≥5.000 downloads/mês no PyPI por 3 meses.
- ≥3 estudos de caso de empresas usando (mesmo que anonimizados).
- 2 integrações nativas em produção (dbt + Airflow ou dbt + Databricks).

---

### 4.3. Release 0.4.0 — Airflow operator

**Objetivo:** segunda integração nativa. Trazer de volta o que foi removido, agora bem feito.

**Escopo técnico:**

```python
# src/cfa/integrations/airflow/operators.py

from airflow.models import BaseOperator
from cfa.policy import PolicyEngine
from cfa.types import StateSignature

class CFAGateOperator(BaseOperator):
    """Gate de governance antes de executar tarefa downstream.

    Usage:
        gate = CFAGateOperator(
            task_id="govern_silver_join",
            signature_path="signatures/silver_join.json",
            policy_bundle="policies/prod-v1.yaml",
            catalog_path=".cfa/catalog.json",
            on_block="fail",  # fail | skip | warn
        )
        gate >> spark_job >> validation
    """
    ...

class CFAAuditEmitterOperator(BaseOperator):
    """Emite evento de audit após execução."""
    ...
```

**Inclui:**
- Provider package `apache-airflow-providers-cfa` (publicado em paralelo no PyPI).
- Hooks para conexão CFA (`CFAHook` usando `airflow connections`).
- 2 operators + 1 sensor (`CFAAuditChainSensor` para esperar decisão).
- Documentação completa em `website/docs/integrations/airflow.md`.
- Demo: DAG completo em `examples/airflow_demo/`.

**Compatibilidade:** Airflow 2.7+, 3.0+.

### 4.4. Release 0.5.0 — Lifecycle como diferencial

**Objetivo:** lifecycle indices (IFo/IFs/IFg/IDI) deixam de ser feature obscura e viram diferencial documentado.

**Trabalho:**

1. **Storage SQLite consolidado.** Hoje em `cfa.storage.sqlite`. Polir:
   - Schema migrations versionadas (`cfa storage migrate`).
   - Backup/restore commands.
   - Métricas: tamanho, query perf, retention status.

2. **Promotion engine produtizado.** Hoje em `cfa.observability.promotion`. Tornar:
   - Configurável por policy bundle (não só por código).
   - CLI: `cfa lifecycle promote`, `cfa lifecycle demote`, `cfa lifecycle list --state=watchlist`.
   - Dashboard HTML em `cfa report lifecycle`.

3. **Documentação formal dos índices.** Hoje fragmentado. Criar:
   - `website/docs/concepts/lifecycle-indices.md` — definição matemática + exemplo numérico.
   - ADR justificando cada índice.

4. **Métricas comparáveis.** Adicionar exemplo: "Como medir se sua pipeline X é promotable" com dados sintéticos.

**Critério:** alguém na comunidade entender o que IFo significa e como usar em produção sem precisar perguntar.

### 4.5. Release 0.6.0 — MCP como autoridade governante

**Objetivo:** o MCP server vira o **caso de uso definitivo para LLM agents**. Não como "CFA é uma tool que o agente usa", mas como "CFA é a autoridade que o agente consulta antes de agir".

**Trabalho:**

1. **Polish do MCP server existente.** Hoje em `cfa.mcp`. Adicionar:
   - Tool `cfa_propose_signature` — agente descreve em NL, CFA devolve signature tipada + confidence.
   - Tool `cfa_request_approval` — agente envia signature, CFA decide. Resposta inclui audit_event_hash.
   - Tool `cfa_verify_decision` — agente verifica se decisão prévia ainda é válida (hash chain check).
   - Streaming de eventos via MCP notifications.

2. **Padrão de uso documentado.** "Como construir um agente LangGraph que sempre pede aprovação CFA antes de escrita."

3. **Reference implementation.** `examples/llm_agent_with_cfa_gate/` com agente real (Claude/GPT) usando CFA via MCP.

4. **Server hosting docs.** Como rodar o MCP server em produção (uvicorn, gunicorn, Docker).

### 4.6. Release 0.7.0 — Backends estendidos

**Objetivo:** mostrar que arquitetura pluggable é séria.

**Trabalho:**

1. Backend Snowflake (SQL dialect-aware).
2. Backend BigQuery (SQL dialect-aware).
3. Backend Iceberg (via PySpark com Iceberg).
4. Refator do `BackendRegistry` para suportar versionamento de capabilities.
5. Documentação: "How to write your own backend" + ADR sobre contract.

### 4.7. Tracks paralelas no Movimento II

- **OpenLineage emit.** Audit events também emitidos como OpenLineage. Plug direto em Marquez, DataHub, Atlan.
- **Catalog federation completa.** UC, DataHub, Atlan como fontes.
- **State projection produtizada.** API para queries: "qual foi o estado da pipeline X em 2026-05-20?".
- **i18n real.** Documentação em pt-BR completa (não só fragmentos).

---

## 5. Movimento III — Plataforma

### 5.1. Goal narrativo

CFA vira **categoria nomeada**. Quando alguém escreve um post sobre AI governance em 2027, CFA aparece junto com OPA, LangSmith, Unity Catalog — não como alternativa, como peça complementar reconhecida.

### 5.2. Releases 1.0+ — esboço

| Marco | Conteúdo |
|-------|----------|
| **1.0.0** | API estabilizada. Semver estrito. Migration guide 0.x → 1.0. Audit do código por terceiro. |
| **1.1+** | **CFA Protocol** — spec versionada (JSON Schema + OpenAPI) que outras ferramentas podem implementar. Repo separado `cfa-protocol`. |
| **1.2+** | SDKs em outras linguagens. Go primeiro (alinha com OPA), TypeScript depois (alinha com agent frameworks). |
| **1.3+** | Hosted version opcional (`cfa.cloud` — nome a definir). Multi-tenant, RBAC, dashboard, alerting. Self-hostable também. |
| **1.4+** | CFA Catalog Hub — registry público de policy bundles compartilháveis (analogia com dbt packages, Helm charts). |

### 5.3. Como decidir se vai para Movimento III

Critério: Movimento II atingiu seu critério de saída + projeto tem **time** ou **comunidade ativa** que substitui time. Solo não fecha Movimento III com qualidade.

---

## 6. Trilhas transversais (todos os movimentos)

### 6.1. Testing

- **Manter** 534 testes como baseline mínimo.
- **Adicionar** suite de benchmarks em `tests/perf/` com baseline registrado.
- **Adicionar** golden tests: para cada release, gravar saída esperada de `cfa evaluate` em fixtures e testar contra. Detecta regressão semântica.
- **Adicionar** mutation testing (`mutmut`) em módulos críticos: `policy/engine.py`, `audit/trail.py`, `types.py`.
- **Meta:** cobertura ≥85% em módulos do core, ≥90% em `policy/`, `audit/`, `types.py`.

### 6.2. Documentation

- **ADR a cada decisão de arquitetura** — sem exceção a partir de 0.2.0.
- **Tutorial-driven docs** (Diátaxis): tutoriais → how-to → reference → explanation. Hoje só tem reference.
- **Versão por release.** Docusaurus versionado a partir de 0.3.0.
- **Reading paths**: "Sou DE", "Sou Platform", "Sou ML Engineer querendo governar agente" — três trilhas distintas no site.
- **Bilíngue real**: pt-BR completo a partir de 0.4.0.

### 6.3. Site

- **Hero operacional**, não acadêmico (já no 0.2.0).
- **Demo interativa** (terminal embedado rodando WASM?) a partir de 0.4.0.
- **Página comparativa** mantida atualizada: vs OPA, vs LangSmith, vs GE, vs UC.
- **Releases publicadas como posts** em vez de tag-only.
- **Métricas públicas**: GitHub Stars, downloads PyPI, latest version — todas no homepage.

### 6.4. Comunidade

| Fase | Investimento |
|------|--------------|
| 0.2.0-0.3.x | CHANGELOG público, CONTRIBUTING.md sério, issue templates, PR template, code of conduct ativo. |
| 0.4.0+ | GitHub Discussions ativo, label triage, "good first issue" curado. |
| 0.5.0+ | Discord/Matrix se houver tração. Não antes. |
| 1.0+ | Office hours, RFC process formal, governance da própria CFA (steering committee). |

### 6.5. CI/CD

- **Hoje:** 4 workflows. Bom baseline.
- **0.2.0:** adicionar workflow de mutation testing (semanal), benchmark drift (toda PR), site link checker.
- **0.3.0:** matrix test (Python 3.11, 3.12, 3.13; com/sem extras yaml/mcp/llm).
- **0.4.0:** integration tests com dbt real e Airflow real (containers).
- **1.0:** auditoria externa de segurança antes de tag.

### 6.6. Releases e versionamento

- **0.x:** breaking changes permitidos em minor (0.2 → 0.3 pode quebrar). Documentar no CHANGELOG.
- **0.x:** deprecation warnings ≥2 minor releases antes de remoção.
- **1.0+:** semver estrito. Breaking só em major.
- **Cadence:** minor a cada 6-10 semanas, patches conforme necessário.
- **Calendário público.** Issue pinned com próximas releases planejadas.

### 6.7. Infraestrutura do repo

- **Branch model:** `main` sempre release-ready, feature branches via PR, `release/x.y` para hardening.
- **RFC process** (a partir de 0.3.0): mudanças que afetam API pública passam por RFC em `docs/rfcs/` com período de comentário.
- **Issue triage** semanal: 1h fixa por semana, labels consistentes.
- **Security:** `SECURITY.md` ativo, GPG signing de release tags a partir de 1.0.

---

## 7. Sprint detalhado da 0.2.0

Plano executável por categoria. Estimativas em dias de trabalho focado.

### Sprint 1 — Cortes editoriais (2-3 dias)

**Dia 1:**
- [ ] Remover adapters falsos. Substituir por `docs/integrations/use-cfa-guard-with-frameworks.md`.
- [ ] Atualizar `cfa.__init__` e `cfa.adapters.__init__` para não reexportar falsos.
- [ ] Rodar testes; consertar imports quebrados nos tests (`test_adapters.py`).
- [ ] Mover `CFA_IMPLEMENTATION_PLAN.md`, `CFA_MARKET_RESEARCH_2026.md`, `MANUAL_TESTING_GUIDE.md` para `drafts/`.
- [ ] Adicionar `cfa_test_results_*/` ao `.gitignore`, remover pastas existentes.

**Dia 2:**
- [ ] Reescrever `website/src/pages/index.tsx`. Hero operacional. Versão lida do package.
- [ ] Reescrever `website/docs/intro.md`. Linguagem operacional. Remover tabela ✅/❌.
- [ ] Reescrever README.md com mesmo tom. Adicionar "What CFA is not".
- [ ] Apagar `website/blog/` inteiro. Substituir por 1 post placeholder.

**Dia 3:**
- [ ] Remover letras gregas do whitepaper público. Mover whitepaper original para `docs/internal/`.
- [ ] Banner alpha no site (componente persistente).
- [ ] Criar `website/docs/compare.md` (vs OPA, vs LangSmith, vs GE, vs UC).
- [ ] Padronizar versão "0.2.0" em todos os arquivos textuais.

### Sprint 2 — Consolidação de pacotes (3-4 dias)

**Dia 4-5:**
- [ ] Renomear `cfa.validation` → `cfa.validate`. Deixar shim com deprecation.
- [ ] Renomear `cfa.observability` → `cfa.obs`. Shim.
- [ ] Renomear `cfa.normalizer` → `cfa.resolve`. Shim.
- [ ] Absorver `cfa.governance` em `cfa.policy`. Shim.
- [ ] Absorver `cfa.resolution` em `cfa.resolve`. Shim.
- [ ] Atualizar imports internos (script).
- [ ] Atualizar `cfa.__init__.__getattr__`.

**Dia 6:**
- [ ] Atualizar todos os `__init__.py` afetados.
- [ ] Rodar full test suite. Consertar imports.
- [ ] Atualizar README "Repository" tree.
- [ ] Atualizar `website/docs/api.md`.

**Dia 7:**
- [ ] Testar instalação a partir do PyPI wheel local: `pip install dist/*.whl` em venv limpo, verificar que todos shims funcionam.

### Sprint 3 — Refator técnico (2 dias)

**Dia 8:**
- [ ] Cache do `KernelOrchestrator` no `CFAGuard`.
- [ ] Tirar keywords PT-BR hardcoded do `RuleBasedNormalizerBackend`.
- [ ] Criar `examples/fiscal_pt_br_normalizer.py` como extensão.

**Dia 9:**
- [ ] Adicionar `tests/perf/test_guard_overhead.py` com baseline.
- [ ] Adicionar `tests/perf/test_evaluate_throughput.py`.
- [ ] Rodar e gravar baseline.

### Sprint 4 — ADRs + CHANGELOG + release (1-2 dias)

**Dia 10:**
- [ ] Escrever 6 ADRs em `docs/adr/`.
- [ ] Escrever CHANGELOG.md com migration notes.
- [ ] Escrever release notes em `website/blog/`.

**Dia 11:**
- [ ] Bump versão para `0.2.0` em `pyproject.toml`, `cfa/__init__.py`, site.
- [ ] PR final. Self-review.
- [ ] Tag `v0.2.0`, publicar no PyPI, criar GitHub release.
- [ ] Post no LinkedIn/X anunciando.

**Total estimado:** ~11 dias de trabalho focado, executável em 3-4 semanas calendário considerando outras obrigações.

---

## 8. Riscos e mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Mantenedor solo perde tração antes do critério de saída do Movimento I | Alta | Alto | Calendário público de releases força disciplina. Cortes do 0.2.0 reduzem superfície sustentável. |
| Adopters externos não aparecem mesmo após 0.3.0 | Média | Alto | Revisitar tese antes de Movimento II. Talvez nicho seja menor do que se imagina. |
| OPA/UC lança feature que sobrepõe CFA | Média | Médio | DNA distintivo (REPLAN + signature hash + audit offline) protege. Diferencial vai além de feature list. |
| LangChain/Databricks copia ideia em produto deles | Baixa | Alto | Já estamos em open source MIT. Mover rápido para CFA Protocol em 1.0 ajuda. |
| Refator de consolidação quebra usuários existentes | Baixa | Médio | Shims com deprecation warnings por 2 minor releases. CHANGELOG explícito. Versão 0.x permite. |
| Performance regression no path crítico | Baixa | Alto | Benchmarks em CI a partir do 0.3.0. PRs com regressão >10% bloqueadas. |
| Churn de API entre 0.x perde first adopters | Média | Médio | Deprecation policy clara. Migration scripts quando viável. |

---

## 9. Operacional

### 9.1. Branch e PR

- `main` é release-ready. Sempre verde.
- Feature work em `feature/<short-name>`.
- Releases em `release/0.x` quando entrar em hardening.
- PRs exigem: CI verde, 1 self-review documentado em comment, CHANGELOG entry (a partir de 0.3).

### 9.2. RFC process (a partir de 0.3.0)

Mudanças que afetam:
- API pública de `cfa.__init__.__getattr__`
- Formato de `StateSignature` serializada
- Formato de policy bundle YAML
- Audit event schema

Passam por RFC:
1. Issue com label `rfc`.
2. PR em `docs/rfcs/` com markdown ≥3 dias antes de implementação.
3. Período de comentários ≥7 dias (≥3 dias para correções).
4. Decisão registrada na issue, RFC marcada `accepted | rejected | superseded`.

### 9.3. Cadência de release

- 0.2.0: junho 2026 (target).
- 0.3.0: setembro 2026.
- 0.3.x: nov 2026, jan 2027.
- 0.4.0: março 2027.

Se calendário escorrega, escorrega — mas comunicar publicamente cada slip.

### 9.4. Métricas internas a acompanhar

- Test count, coverage %, mutation score.
- PyPI downloads (semanal).
- GitHub stars/forks/contributors (semanal).
- Tempo de release (commit → PyPI).
- Open issue age (mediana).
- p99 latency do gate path.

Dashboard simples em `metrics.md` (markdown atualizado por script no CI).

---

## 10. O que NÃO está neste plano

Para evitar deriva:

- Hosted version comercial (talvez Movimento III, talvez nunca).
- Suporte enterprise pago.
- Funding/captação.
- Conferência própria.
- Migração para outra linguagem.
- Reescrita de Rego (não vai acontecer, OPA já tem).
- Suporte a streaming (Kafka/Flink) antes do 1.0.

Se entrar pressão para qualquer um destes, registrar em `docs/non-goals.md` com data e razão para reabrir.

---

## 11. Próximos passos imediatos

Depois deste plano aprovado:

1. Você comenta/edita este documento.
2. Convertemos os itens da 0.2.0 em issues do GitHub com labels `release-0.2.0`.
3. Criamos milestone `0.2.0` no GitHub com data target.
4. Começamos Sprint 1.

---

*Fim do documento. Versionado em `drafts/ROADMAP.md` — edite e iterate aqui antes de promover para `docs/roadmap.md` público.*
