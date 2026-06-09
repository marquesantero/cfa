# CFA — Plano de Correções e Crescimento

> Documento vivo. Última revisão: 2026-06-08. Owner: Antero Marques.
> Status: draft v1 — sujeito a iteração antes de virar plano de release.

---

## 0. Sumário executivo

CFA é uma camada de governança entre **intenção** e **execução** — tipada,
determinística, com remediação estruturada e audit chain SHA-256
verificável offline. Em 2026 (versão 1.1.0 no PyPI) o projeto consolidou
sua arquitetura como **plug-shaped**: kernel fechado, extensão por
contrato (`Vertical`, `Integration`, `DecisionSink` — ADR-0007 a 0012).

A pergunta estratégica não é "como viramos referência em 18 meses?" —
a janela de adoção da era IA fechou esse modelo. Frameworks viram febre
em meses e somem no semestre seguinte. Quem joga adoção-só morre com o
framework. Quem joga substrato-só fica invisível.

A resposta — formalizada em **ADR-0013** — é **dual-track**: toda
release ship dois deliverables em paralelo, um de **substrato** (algo
que sobrevive a 5 anos de churn) e um de **relevância** (algo útil neste
trimestre). A cadência alvo é **6-8 semanas por minor**, compatível com
o ritmo da era IA.

A próxima release (**1.2.0 — Protocol + dbt**) entrega:
- **Substrato:** `cfa-protocol v0.1` em repo separado — JSON Schema da
  signature, audit chain format, decision shape, conformance suite.
  Versionado independentemente do kernel. Qualquer linguagem pode
  implementar a spec.
- **Relevância:** `cfa dbt check` — lê `manifest.json`, deriva
  signatures por model, roda o policy bundle em CI. Demo público,
  GitHub Action, screencast, post.

A partir daí, cada minor segue a mesma estrutura — substrato +
relevância — até 2.0.0 que congela `cfa-protocol 1.0` como spec
estável.

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

## 2. Estratégia: substrato + relevância em paralelo

Em 2026 a janela de adoção encolheu de anos para semanas. Frameworks
viram febre e são abandonados no mesmo trimestre. Quem joga "vou
conquistar mindshare em 18 meses" perde o tabuleiro inteiro entre
turnos. Por outro lado, quem corre só atrás de framework do mês morre
com o framework.

A resposta — formalizada em [ADR-0013](../docs/adr/0013-protocol-over-product.md) —
é trabalhar dois eixos em cada release:

### Eixo Substrato (sobrevive a 5 anos)

O que sobrevive a ciclos de febre é **protocolo**, não framework.
SQLite, Postgres, Markdown, OAuth, HTTP, MCP — cada um é uma camada
que produtos implementam. Nenhum deles é o produto que ganhou.

O substrato de CFA é:

- **CFA Protocol spec** — JSON Schema da signature, formato da audit
  chain, schema da decisão, schema do policy bundle.
- **Versionamento independente** do código — `cfa-protocol 0.4` pode
  estar em uso enquanto `cfa-kernel-py 1.4.x` é uma implementação.
- **Implementações de referência em múltiplas linguagens** — Python
  (`cfa-kernel`), Go (`cfa-verify` para validar chains offline),
  TypeScript (signature builder para o ecossistema agent).
- **Estabilidade do kernel** — código escrito contra CFA em 2026
  continua rodando em 2030.

### Eixo Relevância (mostra valor neste trimestre)

O que coloca CFA na frente de gente real são **integrações úteis
agora**: dbt check em CI, Airflow operator, GitHub Action, MCP
authority pattern, dashboard live. Cada uma é manifestação do
substrato, descartável quando o framework morrer, sem afetar o core.

### Casamento dos dois eixos

Toda release ship as duas peças. A relevância traz pessoas. O
substrato dá motivo pra ficar:

| Release | Substrato | Relevância |
|---------|-----------|------------|
| 1.2.0 | CFA Protocol v0.1 spec publicado em repo separado | `cfa dbt check` em CI, demo público |
| 1.3.0 | Go binary `cfa-verify` standalone | Vertical `agent` + demo LLM via MCP |
| 1.4.0 | TypeScript signature builder | Airflow `CFAGateOperator` + DecisionSinks (Slack/OTel/PR) |
| 1.5.0 | Catalog Hub de verticais/integrações + conformance badge | Live dashboard polido + 2-3 case studies |
| 2.0.0 | CFA Protocol v1.0 stable + spec freeze + governance | Lifecycle indices produtizados, multi-vertical em produção |

Cadência **6 a 8 semanas por minor**. Em vez de "vai para o próximo
movimento depois de 9 meses", é "cada release entrega substrato +
relevância em 2 meses". Compatível com janela de adoção da era IA.

### Métricas

A métrica deixa de ser "stars no GitHub" e vira:

| Métrica antiga | Métrica nova |
|----------------|--------------|
| Downloads no PyPI | Implementações do protocolo em outras linguagens |
| Stars | Sistemas externos emitindo audit chains CFA-formatadas |
| Mentions em blogs | Citação em specs de outros projetos |
| Adopters nomeados | Verticais terceiros publicados |

Não se "passa pro próximo movimento" — se **avança o número da versão
do protocolo** sem quebrar implementadores. Isso é a definição de
substrato funcionando.

---

## 3. Releases (cadência 6-8 semanas, cada uma com substrato + relevância)

### 3.1. Onde estamos hoje

**1.1.0** já no PyPI. **Phase 0** (contratos de plugin) e **Phase 1a/1b**
(vertical de referência + signature genérica) na main, sem release nova
ainda — entrarão como **1.1.1** quando convier, ou direto na 1.2.0.

A partir daqui, **cada minor (1.2 → 2.0) entrega substrato + relevância
em paralelo**.

---

### 3.2. Release 1.2.0 — "Protocol + dbt"

**Janela:** ~6 semanas.

#### Substrate deliverable: `cfa-protocol` v0.1

Repo separado `marquesantero/cfa-protocol` contendo:

- `signature.schema.json` — JSON Schema canonical de `StateSignature`
  na forma vertical-aware (ADR-0008). Versionado independentemente
  de `cfa-kernel`.
- `audit-event.schema.json` — schema dos eventos da audit chain, com
  o algoritmo de canonicalização documentado (ADR-0002).
- `decision.schema.json` — formato do resultado da decisão
  (approve/replan/block + faults + interventions).
- `policy-bundle.schema.json` — formato do YAML policy bundle.
- `verticals/data.payload.schema.json` e
  `verticals/data.constraints.schema.json` — schemas do vertical
  data, importáveis por qualquer implementação.
- `conformance/` — suite de fixtures (~30 casos) que qualquer
  implementação roda para se declarar CFA-conformant.
- `examples/` — JSON canônico de uma signature + audit chain em
  cada vertical.
- README explicando: "Este repo é a spec. cfa-kernel é uma
  implementação. Qualquer linguagem pode implementar a spec."

Tag `v0.1.0` no `cfa-protocol`; spec viva mas não congelada.

#### Adoption deliverable: `cfa dbt check`

Módulo `cfa.integrations.dbt` shipped dentro do `cfa-kernel 1.2.0`,
implementando o contrato `Integration` da ADR-0010:

```bash
cfa dbt check --project-dir ./my_dbt_project \
              --policy-bundle policies/prod-v1.yaml \
              --catalog .cfa/catalog.json \
              --fail-on block \
              --format junit > test-results.xml
```

Lê `target/manifest.json`, deriva uma `StateSignature` (data vertical)
por model materializado, roda o policy bundle, emite resultado em
JUnit/JSON para CI. Saída zero-exit em approve, não-zero em block.

Inclui:

- Demo project público em `examples/dbt_demo/` que provoca os 3
  outcomes (approve, replan, block).
- GitHub Action template (`.github/workflows/cfa-check.yml`) que
  roda `cfa dbt check` em todo PR.
- Screencast 3min no homepage.
- Post de release no blog: "How to govern your dbt project with
  CFA in 5 minutes".

#### Critério de release

- [ ] `cfa-protocol` v0.1.0 publicado, README explicando spec vs
  implementação.
- [ ] `cfa-kernel 1.2.0` no PyPI; `cfa dbt check` rodando no demo
  project sem erro.
- [ ] Pelo menos um projeto público (mesmo que pessoal/sintético)
  com badge "Governed by CFA" e link para o action.
- [ ] Post no LinkedIn + 1 post no HN ou Reddit r/dataengineering.

---

### 3.3. Release 1.3.0 — "Portability + Agent Vertical"

**Janela:** ~6 semanas após 1.2.0.

#### Substrate deliverable: `cfa-verify` em Go

Binário standalone, ~5MB, sem dependência de Python ou rede:

```bash
cfa-verify audit-chain ./audit.jsonl
# OK · 1 274 events verified · last_hash=a4f3…6c01
# protocol_version=0.1

cfa-verify signature ./signature.json
# OK · vertical=data · hash matches
```

Implementa o protocolo `cfa-protocol 0.1` em Go. Distribuído como:

- GitHub release com binários para linux/darwin/windows
  (`cfa-verify-linux-amd64`, etc.)
- Single-file Homebrew formula.
- Imagem Docker `marquesantero/cfa-verify`.

Prova de portabilidade: você não precisa de Python para consumir
decisões CFA. Sobrevive ao dia que Python sair de moda.

#### Adoption deliverable: `cfa.verticals.agent` + demo LLM real

Vertical para tool calls de agente:

- `cfa.verticals.agent.AgentVertical` com payload
  `{"tool", "args", "caller", "session_id"}` e constraints
  `{"allowed_tools", "rate_limit_per_minute", "sensitive_fields"}`.
- Condições: `agent.tool_not_in_allowlist`,
  `agent.rate_limit_exceeded`, `agent.sensitive_field_in_args`.
- Bundle padrão `policies/agent-prod-v1.yaml`.

Plus demo end-to-end:

- Agente Claude (ou GPT) construído com LangGraph que usa CFA via
  MCP para validar **toda chamada de ferramenta** antes de
  executar.
- Cenário: "agente tenta deletar tabela em prod" → CFA `block`
  com remediation → audit event.
- Screencast 5min + blog post: "Stopping LLM agents from
  deleting production with CFA".

#### Critério de release

- [ ] `cfa-verify` rodando em Linux/macOS/Windows. Hash verification
  passa em audit chains geradas pelo Python kernel.
- [ ] `cfa.verticals.agent` registrado, condições disponíveis no
  registry, bundle de exemplo funcional.
- [ ] Demo agent + MCP + CFA gravado e publicado.

---

### 3.4. Release 1.4.0 — "Ecosystem + Infra Vertical"

**Janela:** ~6-8 semanas após 1.3.0.

#### Substrate deliverable: TypeScript signature builder + Catalog Hub MVP

- `npm install @cfa/protocol` — biblioteca TS que constroi e valida
  `StateSignature` contra os JSON Schemas. Sem dependência de
  servidor; trabalha contra `cfa-protocol 0.x`.
- `cfa-hub` (repo) — registry público de:
  - Verticais (data, agent, infra, third-party publicados).
  - Policy bundles compartilháveis (analogia com dbt packages).
  - DecisionSinks publicados.
- Site simples gerando catálogo navegável.

#### Adoption deliverable: Airflow operator + Slack/OTel/PR sinks

Pacote separado `apache-airflow-providers-cfa` ou
`cfa-int-airflow`:

- `CFAGateOperator` — bloqueia DAG quando o policy bundle dá block.
- `CFAAuditEmitterOperator` — emite audit event para o sink
  configurado.
- Hook de conexão + provider metadata.

Sinks publicados como pacotes separados:

- `cfa-sink-slack` — webhook Slack quando block/replan acontecem.
- `cfa-sink-otel` — spans OTel para Datadog/Honeycomb/Grafana.
- `cfa-sink-github-pr` — comenta no PR.

Plus `cfa.verticals.infra` com Terraform plan support:

- `cfa terraform check tfplan.json` — lê output JSON do `terraform
  plan` e roda o policy bundle.

#### Critério de release

- [ ] TS package no npm; signature roundtrip Python ⇄ TypeScript
  bate hash.
- [ ] `cfa-hub` no ar com pelo menos 3 verticais e 5 sinks
  catalogados.
- [ ] Airflow operator funcional em DAG real.
- [ ] `cfa terraform check` block em plan que viola política.

---

### 3.5. Release 1.5.0 — "Dashboard + Conformance"

**Janela:** ~6-8 semanas após 1.4.0.

#### Substrate deliverable: Conformance badge + protocol v0.5

- Repo `cfa-protocol` ganha runner standalone da conformance suite.
- Implementações que passam ganham badge:
  - `cfa-kernel-py` ✅ Conformance Level 3
  - `cfa-verify-go` ✅ Conformance Level 1 (verifier only)
  - `@cfa/protocol-ts` ✅ Conformance Level 2 (build + verify)
- Spec bump para `cfa-protocol 0.5` com estabilizações ganhas até aqui.

#### Adoption deliverable: Live dashboard + lifecycle produtizado

- `cfa serve --dashboard --port 8080` abre dashboard local:
  - Audit chain viewer (timeline + hash verification).
  - Decision metrics (replan rate por bundle, block reasons,
    latência p50/p99).
  - Lifecycle scoreboard (IFo/IFs/IFg/IDI por pipeline).
  - Policy rule explainer com remediação.
- `cfa lifecycle promote` / `demote` / `list` com bundle de promoção
  configurável.
- 2-3 case studies escritos (mesmo que pessoais/sintéticos
  inicialmente).

#### Critério de release

- [ ] Conformance badge implementado, ao menos 2 implementações
  certificadas.
- [ ] Dashboard rodando local com audit chain real.
- [ ] Lifecycle CLI funcional em pelo menos 1 projeto exemplo.

---

### 3.6. Release 2.0.0 — "Spec freeze + ecosystem"

**Janela:** ~6 meses após 1.5.0 (ou quando 5 implementações
terceiras existirem, o que vier primeiro).

#### Substrate deliverable: `cfa-protocol 1.0` stable

- Spec freeze. A partir daqui breaking changes só com `cfa-protocol
  2.0`.
- Governance lightweight: RFC process no repo `cfa-protocol`,
  janela de comentário de 14 dias por proposta.
- Third-party security audit do `cfa-kernel`.
- Migration guide 1.x → 2.0 para implementadores.

#### Adoption deliverable: ecossistema declarado

- Multi-vertical em produção (mínimo data + agent ou data + infra
  em projeto real).
- 3+ verticais terceiros publicados no Catalog Hub.
- Hosted version opcional (`cfa.cloud` — nome a definir) — não
  obrigatório para nada; quem quer self-host roda o mesmo binário.
- Reference de "como ferramenta X usa CFA": pelo menos 1 caso
  publicado de fora.

#### Critério de release

- [ ] `cfa-protocol 1.0.0` tag estável.
- [ ] Auditoria externa concluída.
- [ ] Ao menos 5 implementações da spec (Python kernel, Go verifier,
  TS builder, mais 2 — internas ou externas).
## 6. Trilhas transversais (todos os movimentos)

### 6.1. Testing

- **Manter** 534 testes como baseline mínimo.
- **Adicionar** suite de benchmarks em `tests/perf/` com baseline registrado.
- **Adicionar** golden tests: para cada release, gravar saída esperada de `cfa evaluate` em fixtures e testar contra. Detecta regressão semântica.
- **Adicionar** mutation testing (`mutmut`) em módulos críticos: `policy/engine.py`, `audit/trail.py`, `types.py`.
- **Meta:** cobertura ≥85% em módulos do core, ≥90% em `policy/`, `audit/`, `types.py`.

### 6.2. Documentation

- **ADR a cada decisão de arquitetura** — sem exceção a partir de 1.1.0.
- **Tutorial-driven docs** (Diátaxis): tutoriais → how-to → reference → explanation. Hoje só tem reference.
- **Versão por release.** Docusaurus versionado a partir de 1.2.0.
- **Reading paths**: "Sou DE", "Sou Platform", "Sou ML Engineer querendo governar agente" — três trilhas distintas no site.
- **Bilíngue real**: pt-BR completo a partir de 1.3.0.

### 6.3. Site

- **Hero operacional**, não acadêmico (já no 1.1.0).
- **Demo interativa** (terminal embedado rodando WASM?) a partir de 1.3.0.
- **Página comparativa** mantida atualizada: vs OPA, vs LangSmith, vs GE, vs UC.
- **Releases publicadas como posts** em vez de tag-only.
- **Métricas públicas**: GitHub Stars, downloads PyPI, latest version — todas no homepage.

### 6.4. Comunidade

| Fase | Investimento |
|------|--------------|
| 1.1.0-1.2.x | CHANGELOG público, CONTRIBUTING.md sério, issue templates, PR template, code of conduct ativo. |
| 1.3.0+ | GitHub Discussions ativo, label triage, "good first issue" curado. |
| 1.4.0+ | Discord/Matrix se houver tração. Não antes. |
| 1.0+ | Office hours, RFC process formal, governance da própria CFA (steering committee). |

### 6.5. CI/CD

- **Hoje:** 4 workflows. Bom baseline.
- **1.1.0:** adicionar workflow de mutation testing (semanal), benchmark drift (toda PR), site link checker.
- **1.2.0:** matrix test (Python 3.11, 3.12, 3.13; com/sem extras yaml/mcp/llm).
- **1.3.0:** integration tests com dbt real e Airflow real (containers).
- **2.0:** auditoria externa de segurança antes de tag.

### 6.6. Releases e versionamento

- **1.x:** semver estrito. Breaking changes só em major (2.0). Deprecation warnings ≥2 minor releases antes de remoção em major.
- **Cadence:** minor a cada 6-10 semanas, patches conforme necessário.
- **Calendário público.** Issue pinned com próximas releases planejadas.

### 6.7. Infraestrutura do repo

- **Branch model:** `main` sempre release-ready, feature branches via PR, `release/x.y` para hardening.
- **RFC process** (a partir de 1.2.0): mudanças que afetam API pública passam por RFC em `docs/rfcs/` com período de comentário.
- **Issue triage** semanal: 1h fixa por semana, labels consistentes.
- **Security:** `SECURITY.md` ativo, GPG signing de release tags a partir de 2.0.

---

## 7. Sprint detalhado da 1.1.0

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
- [ ] Padronizar versão "1.1.0" em todos os arquivos textuais.

### Sprint 2 — Consolidação de pacotes (2-3 dias)

Sem shims: 1.0.0 não tem usuário externo, então renames diretos.

**Dia 4:**
- [ ] Renomear `cfa.normalizer` → `cfa.resolve` (move + atualiza imports).
- [ ] Absorver `cfa.resolution` em `cfa.resolve`.
- [ ] Absorver `cfa.governance` em `cfa.policy`.

**Dia 5:**
- [ ] Renomear `cfa.validation` → `cfa.validate`.
- [ ] Renomear `cfa.observability` → `cfa.obs`.
- [ ] Atualizar `cfa.__init__.__getattr__` e demais `__init__.py` afetados.

**Dia 6:**
- [ ] Rodar full test suite. Consertar imports.
- [ ] Atualizar README "Repository" tree.
- [ ] Atualizar `website/docs/api.md` e i18n pt-BR equivalente.
- [ ] Testar instalação a partir do wheel local: `pip install dist/*.whl` em venv limpo.

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
- [ ] Bump versão para `1.1.0` em `pyproject.toml`, `cfa/__init__.py`, site.
- [ ] PR final. Self-review.
- [ ] Tag `v1.1.0`, publicar no PyPI, criar GitHub release.
- [ ] Post no LinkedIn/X anunciando.

**Total estimado:** ~11 dias de trabalho focado, executável em 3-4 semanas calendário considerando outras obrigações.

---

## 8. Riscos e mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Mantenedor solo perde tração antes de 1.4.0 | Alta | Alto | Cadência 6-8 semanas pública. Em release de baixa energia, ship apenas a peça de substrato (não a de adoção); o protocolo continua avançando. |
| Adoption deliverable (cfa dbt check etc.) não traz adopters | Média | Alto | O substrato deliverable da mesma release segue valendo. Re-segmentar adoção para outro framework no próximo ciclo sem mudar protocolo. |
| OPA/UC lança feature que sobrepõe CFA | Média | Médio | Substrato (protocolo aberto) é defesa estrutural. Quando feature copiada vira commodity, o que sobra é o formato compartilhado. |
| LangChain/Databricks/MCP-server-da-vez muda spec ou desaparece | Alta | Médio | Integrações são plug-shaped (ADR-0010). Quando o framework morre só morre a integration, não o kernel. |
| Refator quebra implementadores do protocolo após 1.5.0 | Média | Alto | Conformance suite + versionamento independente do protocolo. Qualquer breaking change vira `cfa-protocol 2.0`, kernel continua na faixa anterior por overlap. |
| Performance regression no path crítico | Baixa | Alto | Benchmarks em CI; regressão >10% bloqueia PR. |
| Spec não atrai segunda implementação | Média | Médio | Ship Go + TS implementations a partir da 1.3/1.4 nós mesmos. Provar portabilidade não pode depender de terceiros aparecerem. |
| Janela de adoção AI-era fecha antes da 1.3.0 | Média | Médio | Cada release entrega substrato útil mesmo se a adoção for zero. Substrato sobrevive ao fim de qualquer onda. |

---

## 9. Operacional

### 9.1. Branch e PR

- `main` é release-ready. Sempre verde.
- Feature work em `feature/<short-name>`.
- Releases em `release/1.x` quando entrar em hardening.
- PRs exigem: CI verde, 1 self-review documentado em comment, CHANGELOG entry (a partir de 0.3).

### 9.2. RFC process (a partir de 1.2.0)

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

- 1.1.0: junho 2026 (target).
- 1.2.0: setembro 2026.
- 1.2.x: nov 2026, jan 2027.
- 1.3.0: março 2027.

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
2. Convertemos os itens da 1.1.0 em issues do GitHub com labels `release-1.1.0`.
3. Criamos milestone `1.1.0` no GitHub com data target.
4. Começamos Sprint 1.

---

*Fim do documento. Versionado em `drafts/ROADMAP.md` — edite e iterate aqui antes de promover para `docs/roadmap.md` público.*
