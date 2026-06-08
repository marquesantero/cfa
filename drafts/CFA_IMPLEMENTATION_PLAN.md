# CFA — Plano de Implementação: Fechando os Gaps

**Data:** 2026-06-06
**Objetivo:** Transformar o CFA de "biblioteca com ideias legais" em ferramenta de utilidade real e mensurável.

---

## Diagnóstico

O CFA tem **4 diferenciais que NENHUM dos 12 concorrentes possui:**

| # | Diferencial | Concorrentes que têm | Valor real |
|---|---|---|---|
| 1 | **Hash-chain audit trail** (SHA-256 imutável) | 0/12 | Compliance regulatório: provar o que aconteceu |
| 2 | **State projection** (I4: projeta estado pós-execução) | 0/12 | Rastreabilidade operacional entre execuções |
| 3 | **Lifecycle indices** (IFo/IFs/IFg/IDI) | 0/12 | Detectar degradação silenciosa de pipelines |
| 4 | **REPLAN** (estado intermediário entre allow/deny) | 0/12 | Correção automática sem intervenção humana |

Mas falta **tudo que torna esses diferenciais acessíveis** a quem não escreve Python.

---

## Plano de Implementação — 13 Sprints (90 dias)

### FASE A: Fundação para Adoção (Sprints 1-4, Dias 1-14)

```
OBJETIVO: Qualquer pessoa consegue instalar e usar CFA em 5 minutos.
ENTREGÁVEL: `pip install cfa && cfa evaluate "meu intent"`
```

---

#### Sprint 1: CLI — `cfa` command (Dias 1-3)

**Por que é #1:** Sem CLI, CFA só existe para devs Python. Com CLI, entra em CI/CD, scripts, e workflows de qualquer time.

**O que implementar:**

```
cfa evaluate "Join NFe with Clientes persist Silver"
  --catalog fiscal_catalog.yaml
  --policy-bundle prod-v1
  --backend pyspark
  --format json | table | summary

cfa validate --spec fiscal_governance.yaml
  --intent "agregar vendas"
  --exit-code    # retorna 1 se BLOCKED

cfa rules list
  --policy-bundle prod-v1
  --format table

cfa rules explain GOVERNANCE_RAW_PII_IN_PROTECTED_LAYER

cfa audit show --intent-id <id>
  --format json | markdown
  --output audit_report.md

cfa audit verify
  --check-integrity   # verifica hash chain

cfa taxonomy generate
  --spec fiscal_governance.yaml
  --output taxonomy.json

cfa taxonomy test-intents
  --spec fiscal_governance.yaml
  --count 10
  --output test_intents.txt

cfa backend list
  [pyspark] (built-in)

cfa init   # gera .cfa/ com config default + catalog exemplo
```

**Arquivos:**
- `src/cfa/cli/__init__.py` — entry point, argparser
- `src/cfa/cli/commands.py` — each command implementation
- `pyproject.toml` — `[project.scripts] cfa = "cfa.cli:main"`
- `src/cfa/cli/formatters.py` — table, json, summary output formatters

**Dependências:** Zero (argparse da stdlib)

**Testes:** Testar todo comando CLI com subprocess + captura de stdout/stderr

---

#### Sprint 2: Serialização (Dias 4-6)

**Por que é #2:** Sem serialização, não há como passar contratos entre sistemas (CLI→kernel, MCP→policy engine, CI→resultado).

**O que implementar:**

```python
# StateSignature JSON
sig = StateSignature(...)
json_str = sig.to_json()                    # {"domain": "fiscal", ...}
sig2 = StateSignature.from_json(json_str)    # reconstroi identico

# PolicyResult JSON  
pr = policy.evaluate(sig)
d = pr.to_dict()      # {"action": "approve", "faults": [...], ...}
j = pr.to_json()       # string JSON

# KernelResult JSON
kr = kernel.process(intent)
j = kr.to_json()       # serialização completa do resultado

# BehaviorTaxonomy JSON
t = taxonomy.to_dict()  # já existe! verificar se cobre tudo
```

**Arquivos:**
- `src/cfa/types.py` — adicionar `StateSignature.to_dict()`, `.from_dict()`, `.to_json()`, `.from_json()`
- `src/cfa/types.py` — adicionar `KernelResult.to_dict()`, `.to_json()`
- `src/cfa/policy.py` — adicionar `PolicyResult.to_dict()`, `.to_json()`

**Testes:** roundtrip (serialize→deserialize→compare), todos os campos opcionais

---

#### Sprint 3: Policy Bundles YAML/JSON (Dias 7-10)

**Por que é #3:** Política em Python = programação, não governança. Platform teams precisam versionar políticas como arquivos, separados do código.

**O que implementar:**

```yaml
# policies/prod-v1.yaml
policy_bundle:
  version: "prod-v1.0"
  description: "Production governance rules for fiscal ETL"
  last_updated: "2026-06-01"
  rules:
    - name: forbid_raw_pii_in_silver_or_gold
      condition: pii_in_protected_layer
      action: replan
      fault_code: GOVERNANCE_RAW_PII_IN_PROTECTED_LAYER
      severity: critical
      message: "PII detected without treatment in write to protected layer."
      remediation:
        - "Apply sha256() on PII columns before join"
        - "Or use drop() to remove sensitive columns"
    
    - name: require_merge_key_for_silver_gold
      condition: missing_merge_key
      action: block
      fault_code: CONTRACT_MISSING_MERGE_KEY
      severity: critical
      message: "Write to Silver/Gold without merge_key."
      remediation:
        - "Set constraints.merge_key_required=True"

    - name: require_partition_for_high_volume
      condition: missing_partition
      action: replan
      fault_code: FINOPS_MISSING_TEMPORAL_PREDICATE
      severity: high
      message: "High volume dataset without partition filter"
      min_size_gb: 1.0
      remediation:
        - "Add partition_by with temporal column"

  # Custom rules (callable Python — escape hatch)
  custom_rules: []
```

**Arquivos:**
- `src/cfa/policy_bundle.py` — `PolicyBundle` dataclass, YAML/JSON loader
- `src/cfa/policy.py` — estender `PolicyEngine` para aceitar `PolicyBundle`
- `policies/default-v1.yaml` — bundle padrão incluso no pacote
- `policies/finops-strict-v1.yaml` — bundle focado em custo
- `policies/compliance-strict-v1.yaml` — bundle para setor regulado

**Mapeamento condition string → lambda:**

```python
_CONDITION_REGISTRY = {
    "pii_in_protected_layer": lambda sig: (
        sig.writes_to_protected_layer and sig.contains_pii 
        and not sig.constraints.no_pii_raw
    ),
    "missing_merge_key": lambda sig: (
        sig.writes_to_protected_layer 
        and not sig.constraints.merge_key_required
    ),
    "missing_partition": lambda sig: (
        any(d.classification in (HIGH_VOLUME, SENSITIVE) for d in sig.datasets)
        and len(sig.constraints.partition_by) == 0
    ),
    ...  # mesmo mapeamento do behavior/systematizer.py
}
```

---

#### Sprint 4: Serialização + Rich Reporting Engine (Dias 11-17)

**Por que é crítico:** O audit trail e os índices de lifecycle são os diferenciais mais profundos do CFA, mas sem relatórios ricos são invisíveis. Um auditor ou gestor não vai ler JSON — precisa de HTML com gráficos, tabelas e chain of custody visual. Este sprint unifica os Sprints 2 (serialização) e 4 (audit export) + Sprint 9 (dashboard) em um sistema coeso de reporting que gera relatórios autossuficientes, prontos para qualquer ferramenta de visualização.

**Arquitetura do módulo de reporting:**

```
src/cfa/reporting/
├── __init__.py          # API pública: ReportEngine, gerar_relatorio()
├── engine.py            # ReportEngine — orquestrador de geração
├── charts.py            # Preparação de dados para Chart.js (JSON configs)
├── templates.py         # Templates HTML inline (zero dependências)
│   ├── _base()          # Layout base: header, footer, CSS dark theme
│   ├── _chart_script()  # Script tag Chart.js CDN + renderização
│   ├── execution()      # Relatório de execução de pipeline
│   ├── audit()          # Relatório de audit trail com hash chain visual
│   ├── lifecycle()      # Dashboard de índices IFo/IFs/IFg/IDI
│   └── compliance()     # Resumo de conformidade
└── writer.py            # HTML writer com assets inline
```

**Quatro tipos de relatório:**

```bash
cfa report execution --intent-id abc123 --output report.html
cfa report audit     --intent-id abc123 --output audit.html
cfa report lifecycle --period 90d         --output lifecycle.html
cfa report compliance                     --output compliance.html
```

---

**Tipo 1: Relatório de Execução** (`cfa report execution`)

HTML autossuficiente (single-file, sem dependências externas exceto Chart.js CDN) contendo:

```
┌─────────────────────────────────────────────────────────┐
│  CFA Execution Report                                   │
│  ────────────────────────────────────────────────────   │
│                                                         │
│  Intent: "Join NFe with Clientes persist Silver"        │
│  Status: ✅ APPROVED_WITH_WARNINGS                      │
│  Signature Hash: 7f83b165...  |  Policy: prod-v1.0      │
│  Domain: fiscal  |  Layer: Silver  |  Datasets: 2       │
│                                                         │
│  ┌───────────── Pipeline Timeline ─────────────────┐    │
│  │ Formalize ✅ → Govern ⚠️ → Generate ✅ →        │    │
│  │ Execute ✅ → Validate ✅                        │    │
│  │                                                  │    │
│  │ ⚠️ Govern: replan applied                       │    │
│  │    + partition_by added (processing_date)        │    │
│  └──────────────────────────────────────────────────┘    │
│                                                         │
│  ┌─ Execution Metrics ──────────────────────────────┐   │
│  │ Rows: 1,200,000  |  Shuffle: 450 MB               │   │
│  │ Duration: 8.3s   |  Cost: 12.5 DBU                │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─ Policy Decisions Pie ──┐  ┌─ Fault Severity ────┐  │
│  │   [doughnut chart]       │  │   [pie chart]        │  │
│  └──────────────────────────┘  └─────────────────────┘  │
│                                                         │
│  ┌─ Fault Details ──────────────────────────────────┐   │
│  │ 🔴 CRITICAL: GOVERNANCE_RAW_PII_IN_PROTECTED      │   │
│  │    PII detected without treatment                  │   │
│  │    Remediation: Apply sha256(), Enable no_pii_raw  │   │
│  │ 🟡 WARNING: FINOPS_SENSITIVE_WITHOUT_PARTITION     │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  Chain Integrity: ✅ VERIFIED | 8 events | 0 tampered   │
└─────────────────────────────────────────────────────────┘
```

---

**Tipo 2: Relatório de Audit Trail** (`cfa report audit`)

Visualização blockchain-style da cadeia de hash com verificação de integridade:

```
┌─────────────────────────────────────────────────────────┐
│  CFA Audit Trail Report                                 │
│  ────────────────────────────────────────────────────   │
│  Intent ID: abc12345  |  Bundle: prod-v1.0              │
│  Chain Status: ✅ INTACT (8/8 events verified)           │
│                                                         │
│  ┌─ Hash Chain Visualization ───────────────────────┐   │
│  │                                                    │   │
│  │  [event_1] ──SHA256──▶ [event_2] ──SHA256──▶ ...  │   │
│  │  formalize              govern                     │   │
│  │  env consulted          policy evaluation          │   │
│  │  0xabc123...            0xdef456...                │   │
│  │     │                      │                       │   │
│  │     └──────────────────────┼───────────────────────│   │
│  │                            ↓                       │   │
│  │                      [event_3] ──▶ ... ──▶ [root] │   │
│  │                      formalize         0x789abc    │   │
│  └────────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─ Event Timeline ─────────────────────────────────┐   │
│  │ #  Timestamp           Phase      Outcome  Hash    │   │
│  │ 1  2026-06-06T14:30:01 formalize  ok       0xabc.. │   │
│  │ 2  2026-06-06T14:30:02 formalize  resolved 0xdef.. │   │
│  │ 3  2026-06-06T14:30:03 formalize  approved 0x789.. │   │
│  │ 4  2026-06-06T14:30:04 govern     replan   0x012.. │   │
│  │ ...                                                │   │
│  └────────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─ Export Options ──────────────────────────────────┐   │
│  │ [📋 Copy JSON] [📄 Download PDF] [🔗 Share Link]   │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

**Tipo 3: Lifecycle Dashboard** (`cfa report lifecycle`)

Dashboard completo de saúde dos pipelines com gráficos interativos:

```
┌─────────────────────────────────────────────────────────┐
│  CFA Lifecycle Dashboard                                │
│  ────────────────────────────────────────────────────   │
│  Period: Last 90 days  |  Pipelines tracked: 12         │
│  Skills promoted: 3  |  Watchlist: 2  |  Demoted: 1     │
│                                                         │
│  ┌─ Index Trends (90 days) ─────────────────────────┐   │
│  │                                                    │   │
│  │  IFo ──blue──  IFs ──purple──  IDI ──cyan---     │   │
│  │  IFg ──green── (stepped)                          │   │
│  │                                                    │   │
│  │  [multi-line Chart.js chart with 4 series]         │   │
│  │                                                    │   │
│  └────────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─ Cost Trend ───────────────┐ ┌─ Decisions ─────────┐  │
│  │ [line chart + budget line]  │ │ [doughnut chart]     │  │
│  └─────────────────────────────┘ └──────────────────────┘  │
│                                                         │
│  ┌─ Pipeline Skill States ───────────────────────────┐   │
│  │ Pipeline           IFo   IFs   IFg  IDI  State     │   │
│  │ fiscal_monthly     0.92  0.95  1.0  0.88 ACTIVE   │   │
│  │ customer_360       0.85  0.91  1.0  0.82 ACTIVE   │   │
│  │ sales_daily        0.72  0.88  0.0  0.55 WATCHLIST│   │
│  │ legacy_export      0.45  0.60  0.0  0.30 DEMOTED  │   │
│  └────────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─ Top Violations ──────────────────────────────────┐   │
│  │ [horizontal bar chart]                              │   │
│  └────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

**Tipo 4: Relatório de Compliance** (`cfa report compliance`)

Resumo consolidado para auditores e compliance officers:

```
┌─────────────────────────────────────────────────────────┐
│  CFA Compliance Report                                  │
│  ────────────────────────────────────────────────────   │
│  Generated: 2026-06-06T15:00:00Z                        │
│  Policy Bundle: prod-v1.0 (7 rules)                     │
│  Backend: pyspark                                       │
│                                                         │
│  ┌─ Governance Health ───────────────────────────────┐  │
│  │                                                    │  │
│  │  [gauge: 94%]  Governance Compliance Score         │  │
│  │                                                    │  │
│  │  Total Evaluations: 1,847                          │  │
│  │  Approved:  1,748 (94.6%)                          │  │
│  │  Replanned:    87 (4.7%)                           │  │
│  │  Blocked:      12 (0.6%)                           │  │
│  └────────────────────────────────────────────────────┘  │
│                                                         │
│  ┌─ Rules Summary ───────────────────────────────────┐   │
│  │ Rule                                    Action   Hits│   │
│  │ forbid_raw_pii_in_silver_or_gold       REPLAN    142│   │
│  │ require_merge_key_for_silver_gold      BLOCK       8│   │
│  │ require_partition_filter_for_high_vol  REPLAN     95│   │
│  └────────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─ PII Incidents ──────────────────────────────────┐   │
│  │ Total PII exposures prevented: 142                 │   │
│  │ Datasets with PII: 3 (clientes, funcionarios, RH)  │   │
│  └────────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─ Audit Trail Summary ────────────────────────────┐   │
│  │ Total audit events: 14,776                         │   │
│  │ Chain integrity: ✅ VERIFIED                       │   │
│  │ Storage backend: JSON Lines (audit.jsonl)          │   │
│  └────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

**Design decisions do reporting engine:**

| Decisão | Escolha | Justificativa |
|---|---|---|
| Formato | HTML único (single-file) | Zero dependências de servidor; abre em qualquer navegador |
| Gráficos | Chart.js via CDN | Bibliotecas Python de chart são pesadas; Chart.js é leve e interativo |
| CSS | Inline + dark theme | Profissional, imprimível, consistente |
| Dados | Embutidos no HTML como `<script>` JSON | Sem CORS, sem fetch, autossuficiente |
| Temas | Dark (default) + Light (toggle) | Ambos os modos para diferentes contextos |
| Impressão | CSS `@media print` otimizado | Auditores precisam imprimir |
| Dependências | ZERO no Python | Apenas stdlib; Chart.js carrega no browser |

**Arquivos:**
- `src/cfa/reporting/__init__.py` — API pública: `ReportEngine`, `generate_report()`
- `src/cfa/reporting/engine.py` — `ReportEngine` com `execution_report()`, `audit_report()`, `lifecycle_report()`, `compliance_report()`
- `src/cfa/reporting/charts.py` — `ChartConfig`, `lifecycle_trend_chart()`, `decisions_pie_chart()`, `faults_bar_chart()`, `cost_trend_chart()`, `severity_pie_chart()`
- `src/cfa/reporting/templates.py` — Templates HTML como string constants
- `src/cfa/reporting/writer.py` — `write_html()` com assets inline
- CLI: `cfa report generate --type execution|audit|lifecycle|compliance`

---

### FASE B: Ecossistema e Integração (Sprints 5-9, Dias 18-50)

```
OBJETIVO: CFA se integra com o ecossistema de AI agents e ferramentas existentes.
ENTREGÁVEL: Relatórios ricos em HTML + agentes consultam políticas CFA em tempo real.
```

---

#### Sprint 5: MCP Server (Dias 18-24)

**Por que é crítico:** MCP (Model Context Protocol) é o protocolo padrão para agentes AI acessarem ferramentas externas. Um MCP server do CFA permite que ChatGPT, Claude, Copilot, Cursor, Windsurf e qualquer agente compatível com MCP chame o PolicyEngine em tempo real.

**O que implementar:**

```
MCP Server CFA — Tools expostas:

1. cfa_evaluate_signature(signature_json: str) → PolicyResult
   "Avalia uma StateSignature contra o policy bundle ativo e retorna APPROVE/REPLAN/BLOCK."

2. cfa_describe_rules() → list[RuleInfo]
   "Lista todas as regras de política ativas com descrição e severidade."

3. cfa_explain_fault(fault_code: str) → FaultExplanation
   "Explica um código de falta: o que significa, por que ocorre, e como corrigir."

4. cfa_audit_check(intent_id: str) → AuditVerification
   "Verifica a integridade da cadeia de auditoria para uma intenção específica."

5. cfa_list_backends() → list[BackendInfo]
   "Lista os backends de codegen disponíveis com capabilities."
```

**Arquivos:**
- `src/cfa/mcp/__init__.py` — entry point do MCP server
- `src/cfa/mcp/server.py` — implementação do servidor MCP
- `src/cfa/mcp/tools.py` — implementação de cada tool
- `pyproject.toml` — `[project.scripts] cfa-mcp = "cfa.mcp:main"`
- `mcp.json` — configuração exemplo para Claude Desktop, Cursor, etc.

**Dependências:** `mcp` package (extras_require: `pip install cfa-kernel[mcp]`)

---

#### Sprint 6: Framework Adapters (Dias 25-32)

**Por que é crítico:** AI agents são o mercado que mais cresce. Sem adapters, CFA é irrelevante para 90% dos casos de uso emergentes.

**O que implementar — adapters FINOS (3-5 linhas para integrar):**

```python
# 1. LangGraph adapter
from cfa.adapters.langgraph import cfa_guard

@cfa_guard(policy_bundle="prod-v1")
def my_agent_node(state):
    # se chegar aqui, passou pelo CFA
    ...

# 2. OpenAI Agents SDK adapter
from cfa.adapters.openai_agents import cfa_tool_guard

@cfa_tool_guard(policy="pii_strict")
async def query_database(sql: str) -> str:
    # CFA valida intenção antes da tool executar
    ...

# 3. CrewAI adapter
from cfa.adapters.crewai import cfa_crew_guard

@cfa_crew_guard(policy_bundle="prod-v1")
def my_crew_task():
    ...

# 4. AutoGen adapter
from cfa.adapters.autogen import cfa_agent_guard

# 5. DSPy adapter
from cfa.adapters.dspy import cfa_module_guard
```

**Arquivos:**
- `src/cfa/adapters/__init__.py`
- `src/cfa/adapters/base.py` — `CFAGuard` base class comum
- `src/cfa/adapters/langgraph.py`
- `src/cfa/adapters/openai_agents.py`
- `src/cfa/adapters/crewai.py`
- `src/cfa/adapters/autogen.py`
- `src/cfa/adapters/dspy.py`

---

#### Sprint 7: OpenTelemetry Export (Dias 33-37)

**Por que é importante:** OTel é o padrão da indústria. Permite que métricas do CFA apareçam em Grafana, Datadog, Honeycomb, Dynatrace. Sem isso, CFA é invisível.

**O que implementar:**

```python
# Cada fase do pipeline vira um span OTel
from cfa.otel import enable_otel, OTELConfig

enable_otel(OTELConfig(
    service_name="cfa-governance",
    exporter="otlp",  # ou "console"
    endpoint="http://localhost:4317",
))

# Resultado: spans hierárquicas
# cfa.pipeline
#   ├── cfa.formalize (normalize + confirm)
#   ├── cfa.govern (policy check + replan)
#   │   └── cfa.govern.replan (1 iteração)
#   ├── cfa.generate (plan + code + static validate)
#   ├── cfa.execute (sandbox + runtime)
#   └── cfa.validate (decision + lifecycle)

# Atributos em cada span:
# - cfa.phase = "govern"
# - cfa.decision = "approve"
# - cfa.signature_hash = "abc123"
# - cfa.faults = ["FINOPS_MISSING_TEMPORAL_PREDICATE"]
# - cfa.replan_count = 1
```

**Arquivos:**
- `src/cfa/otel.py` — `enable_otel()`, `OTELConfig`, instrumentação do pipeline
- Dependência: `opentelemetry-api` + `opentelemetry-sdk` (extras_require: `pip install cfa-kernel[otel]`)

---

#### Sprint 8: Notificações (Slack/Teams) + CI/CD (Dias 38-44)

**Por que é crítico:** Alertas de governança precisam chegar em quem opera. Sem notificação, decisões do PolicyEngine ficam invisíveis até a auditoria.

**O que implementar:**

```python
# No CLI
cfa evaluate "intent" --notify slack://webhook_url
cfa evaluate "intent" --notify teams://webhook_url
cfa evaluate "intent" --notify email://alerts@company.com

# No código
from cfa.notify import SlackNotifier, TeamsNotifier

notifier = SlackNotifier(webhook_url="https://hooks.slack.com/...")
kernel = KernelOrchestrator(notifier=notifier)
# → toda decisão BLOCK ou REPLAN envia mensagem formatada no Slack
```

**Mensagem Slack exemplo:**

```
🚫 CFA Governance — BLOCKED
Intent: "Write raw PII to Gold"
Policy: prod-v1.0
Faults: GOVERNANCE_RAW_PII_IN_PROTECTED_LAYER (critical)
Action: Execution blocked. PII detected without anonymization.

Remediation:
1. Apply sha256() on PII columns before join
2. Or use drop() to remove sensitive columns

Audit: abc12345 | Hash: 7f83b165
```

**CI/CD integration:**

```yaml
# .github/workflows/governance.yml
- name: CFA Governance Check
  uses: cfa/github-action@v1
  with:
    catalog: catalogs/prod.yaml
    policy-bundle: policies/prod-v1.yaml
    intent-file: intents/pipeline_intents.txt
```

**Arquivos:**
- `src/cfa/notify.py` — `SlackNotifier`, `TeamsNotifier`, `WebhookNotifier`
- `.github/workflows/example-governance.yml` — GitHub Actions example
- `src/cfa/cli/commands.py` — adicionar `--notify` flag

---

#### Sprint 9: Lifecycle Dashboard Interativo (Dias 45-50)

**Por que é importante:** O Sprint 4 cobre relatórios estáticos por pipeline. Este sprint expande para um dashboard interativo multi-pipeline com filtros dinâmicos, comparação entre períodos e drill-down. Enquanto o reporting engine gera snapshots, o dashboard é a visão contínua.

**O que implementar:**

```bash
cfa dashboard serve
  --data-dir ./cfa_data/
  --port 8080
  # → servidor HTTP local com dashboard interativo:
  #   - Filtro por período (7d, 30d, 90d, custom)
  #   - Filtro por pipeline/signature_hash
  #   - Comparação A/B entre dois períodos
  #   - Drill-down: clique num pipeline → relatório de execução
  #   - Tabela de skills com ordenação por qualquer índice
  #   - Gráfico de tendências com zoom
  #   - Alertas visuais: pipelines em watchlist/demoted piscam

cfa dashboard export
  --output-dir ./dashboard/
  --period last_90_days
  # → exporta dashboard como HTML estático (mesmo motor do reporting engine)
```

**Arquivos:**
- `src/cfa/reporting/dashboard.py` — estende `ReportEngine` com multi-pipeline e interatividade
- `src/cfa/cli/dashboard.py` — comandos `serve` e `export`

---

### FASE C: Expansão e Maturidade (Sprints 10-13, Dias 46-90)

```
OBJETIVO: CFA atinge maturidade de produção com SDKs, case studies e comunidade.
```

---

#### Sprint 10: Prometheus Metrics + SDK TypeScript (Dias 51-60)

**Prometheus endpoint:**

```python
# cfa serve --metrics-port 9090
# → expõe métricas em /metrics:
cfa_policy_evaluations_total{decision="approve"} 1523
cfa_policy_evaluations_total{decision="replan"} 87
cfa_policy_evaluations_total{decision="block"} 12
cfa_replan_attempts_total 132
cfa_audit_chain_valid 1
cfa_audit_events_total 4582
cfa_lifecycle_index{pipeline="fiscal_monthly", index="ifo"} 0.92
cfa_lifecycle_index{pipeline="fiscal_monthly", index="idi"} 0.88
```

**Arquivos:**
- `src/cfa/metrics.py` — Prometheus metrics collector
- `src/cfa/cli/commands.py` — `cfa serve` command

#### Sprint 11: Case Study + Documentação Completa (Dias 61-70)

**Case study público:**
- Título: "How CFA prevented PII exposure in a fiscal reconciliation pipeline"
- Repositório separado: `cfa-fiscal-case-study`
- Código executável, dados sintéticos, pipeline completo
- Métricas antes/depois documentadas
- Artigo Medium/LinkedIn

**Documentação:**
- `docs/getting-started.md` — 5 minutos até o primeiro `cfa evaluate`
- `docs/concepts.md` — StateSignature, PolicyEngine, Replan, Lifecycle
- `docs/integrations/airflow.md` — Airflow governance gate
- `docs/integrations/langgraph.md` — LangGraph adapter
- `docs/integrations/mcp.md` — MCP server setup
- `docs/cli/reference.md` — referência completa da CLI
- `docs/policies/authoring.md` — como escrever policy bundles

#### Sprint 12: Testes de Integração End-to-End (Dias 71-80)

**Cenários end-to-end:**
1. CLI: `cfa init` → `cfa evaluate` → `cfa audit export` (fluxo completo)
2. CI/CD: GitHub Actions workflow que valida intents em PRs
3. MCP: Claude Desktop chamando `cfa_evaluate_signature` via MCP
4. LangGraph: agente com `@cfa_guard` bloqueando tool call inseguro
5. Airflow: DAG com governance gate pré-execução

#### Sprint 13: PyPI Release + Community Setup (Dias 81-90)

**Release v0.1.0:**
- `pip install cfa-kernel` (core)
- `pip install cfa-kernel[cli]` (CLI)
- `pip install cfa-kernel[mcp]` (MCP server)
- `pip install cfa-kernel[otel]` (OpenTelemetry)
- `pip install cfa-kernel[langgraph]` (LangGraph adapter)
- `pip install cfa-kernel[all]` (tudo)

**Community:**
- `cfa` package no PyPI
- Discord/Slack community
- GitHub Discussions ativo
- `good first issue` labels para contribuidores

---

## Matriz de Prioridades Consolidada

```
CRÍTICO (Sprints 1-4, Dias 1-17) — Sem isso, CFA é invisível
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Core (6 fases já prontas — 279 testes)
🔴 S1: CLI — cfa evaluate, cfa rules, cfa audit, cfa init
🔴 S2: Policy Bundles — YAML/JSON versionados, 3 bundles built-in
🔴 S3: MCP Server — 5 tools expostas para ChatGPT/Claude/Copilot
🔴 S4: Rich Reporting Engine — 4 tipos de relatório HTML com Chart.js
     ├── execution (pipeline timeline + métricas + gráficos)
     ├── audit (hash chain visual + event timeline)
     ├── lifecycle (dashboard IFo/IFs/IFg/IDI + cost trends)
     └── compliance (governance health + rules summary)

ALTO (Sprints 5-9, Dias 18-50) — Integração com ecossistema
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟡 S5: Serialização — StateSignature/PolicyResult/KernelResult JSON
🟡 S6: Framework Adapters — LangGraph, OpenAI Agents, CrewAI, AutoGen, DSPy
🟡 S7: OpenTelemetry — spans para cada fase do pipeline
🟡 S8: Notificações — Slack, Teams, email webhooks + CI/CD GitHub Actions
🟡 S9: Dashboard Interativo — multi-pipeline, filtros, comparação A/B

MÉDIO (Sprints 10-13, Dias 51-90) — Maturidade de produção
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 S10: Prometheus metrics endpoint + SDK TypeScript
🟢 S11: Case Study público + Documentação completa
🟢 S12: Testes E2E (CLI → CI/CD → MCP → LangGraph → Airflow)
🟢 S13: PyPI release v0.1.0 + Community setup
```
CRÍTICO (Semanas 1-6) — Sem isso, CFA é invisível
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Core (6 fases já prontas — 279 testes)
🔴 CLI: cfa evaluate, cfa rules, cfa audit, cfa init
🔴 Serialização: StateSignature, PolicyResult, KernelResult JSON
🔴 Policy Bundles: YAML/JSON carregáveis, versionados
🔴 Audit Export: JSON + Markdown (auditor-ready)
🔴 MCP Server: 5 tools expostas para agentes

ALTO (Semanas 7-12) — Integração com ecossistema
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟡 Framework Adapters: LangGraph, OpenAI Agents, CrewAI, AutoGen, DSPy
🟡 OpenTelemetry: spans para cada fase do pipeline
🟡 Notificações: Slack, Teams, email webhooks
🟡 CI/CD: GitHub Actions, GitLab CI templates
🟡 Lifecycle Dashboard: HTML estático

MÉDIO (Semanas 13-18) — Maturidade de produção
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 Prometheus metrics endpoint
🟢 SDK TypeScript
🟢 Case Study público
🟢 Documentação completa
🟢 PyPI release v0.1.0
```

---

## O que NÃO fazer

- ❌ UI complexa antes de CLI + MCP
- ❌ Port para Rust/Go antes de Python maduro
- ❌ Streaming/continuous antes de target-scope concurrency
- ❌ Substituir LangGraph/CrewAI — complementar
- ❌ Multi-tenant SaaS antes de single-tenant
- ❌ Branding/website antes de CLI funcionando
