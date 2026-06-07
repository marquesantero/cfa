# CFA v0.1.0 — Manual Testing Guide

> **Objetivo:** Testar o CFA como um usuário real usaria, cobrindo cenários que testes automatizados não alcançam (terminal, browser, MCP real, workflows iterativos).

## Pré-requisitos

```bash
# PowerShell como admin — ativa script execution se necessário
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

# Instala CFA em modo editável
pip install -e ".[dev]"

# Verifica instalação
cfa --help
python -c "import cfa; print(cfa.__version__)"
# Deve imprimir: 0.1.0
```

---

## Jornada 1 — Primeiro Uso (15 min)

> **Persona:** Desenvolvedor Python que nunca usou CFA.  
> **Objetivo:** Experimentar a ferramenta em 5 minutos e gerar o primeiro relatório.

### 1.1 CLI básica

```bash
# Comando mais simples possível
cfa evaluate "teste de governanca"

# Deve mostrar uma tabela formatada com:
# ┌───────────────── CFA Evaluation Result ──────────────────┐
# │ State:  ✓ approved                                       │
# └──────────────────────────────────────────────────────────┘
```

**Check manual:**
- [ ] A tabela tem bordas bem desenhadas (sem caracteres quebrados)?
- [ ] O ícone ✓ aparece corretamente?
- [ ] O hash da assinatura aparece?

### 1.2 Formatos de saída

```bash
cfa evaluate "teste" --format json
cfa evaluate "teste" --format summary
cfa evaluate "teste" --format table
```

**Check manual:**
- [ ] JSON é válido e indentado?
- [ ] Summary é legível em uma linha?
- [ ] Table mostra todos os campos relevantes?

### 1.3 Ajuda dos comandos

```bash
cfa --help
cfa evaluate --help
cfa rules --help
cfa audit --help
cfa report --help
cfa taxonomy --help
cfa backend --help
```

**Check manual:**
- [ ] Cada comando lista TODAS as opções disponíveis?
- [ ] As descrições são claras?
- [ ] Subcomandos aparecem corretamente (ex: `cfa rules list`, `cfa rules explain`)?
- [ ] `cfa serve --help` mostra `--port` e `--metrics-port`?

### 1.4 Erros amigáveis

```bash
cfa rules explain CODIGO_INEXISTENTE
cfa backend list --format invalido
cfa evaluate
```

**Check manual:**
- [ ] Erro de código inexistente é claro ("Unknown fault code: ...")?
- [ ] Erro de formato inválido é claro?
- [ ] Comando sem argumento obrigatório mostra help?

### 1.5 Primeiro relatório HTML

```bash
cfa report execution --intent "Join NFe with Clientes and persist to Silver" --output report_teste.html

# Abre no browser
start report_teste.html
```

**Check manual (no browser):**
- [ ] O HTML abre sem erros?
- [ ] O título contém "CFA Execution Report"?
- [ ] Os gráficos Chart.js carregam (doughnut, bar)?
- [ ] A timeline mostra as fases do pipeline?
- [ ] As cores estão corretas (dark theme)?
- [ ] O cabeçalho mostra o estado com badge colorido?
- [ ] Tenta imprimir (Ctrl+P) — a versão de impressão é legível?

---

## Jornada 2 — Engenheiro de Dados (30 min)

> **Persona:** Engenheiro que governa um pipeline fiscal real.  
> **Objetivo:** Criar catálogo, definir políticas, validar intents, iterar.

### 2.1 Setup do projeto

```bash
mkdir cfa_demo
cd cfa_demo
cfa init
dir .cfa
```

**Check manual:**
- [ ] `.cfa/catalog.json` existe?
- [ ] `.cfa/governance_spec.yaml` existe?
- [ ] `.cfa/.gitignore` existe?

### 2.2 Criar catálogo realista

Crie `cfa_demo/meu_catalogo.json`:

```json
{
  "datasets": {
    "notas_fiscais": {
      "classification": "high_volume",
      "size_gb": 4000,
      "pii_columns": [],
      "partition_column": "data_emissao"
    },
    "cadastro_clientes": {
      "classification": "sensitive",
      "size_gb": 2.5,
      "pii_columns": ["cpf", "email", "telefone", "endereco"],
      "partition_column": "data_atualizacao"
    },
    "produtos": {
      "classification": "internal",
      "size_gb": 0.8,
      "pii_columns": []
    },
    "vendas_diarias": {
      "classification": "high_volume",
      "size_gb": 500,
      "pii_columns": [],
      "partition_column": "data_venda"
    }
  }
}
```

### 2.3 Validar intents seguros

```bash
cfa evaluate "Join notas_fiscais with cadastro_clientes and persist to Silver" --catalog meu_catalogo.json --format table
cfa evaluate "aggregate vendas_diarias by produto" --catalog meu_catalogo.json --format summary
cfa evaluate "Load produtos into Bronze" --catalog meu_catalogo.json --format json
```

**Check manual:**
- [ ] Intents que não envolvem PII passam (APPROVED)?
- [ ] O nome dos datasets do catálogo aparece no resultado?
- [ ] O `signature_hash` é consistente para o mesmo intent?

### 2.4 Testar cenários de violação

```bash
# PII sem proteção em camada protegida
cfa evaluate "Write cadastro_clientes with raw PII to Gold" --catalog meu_catalogo.json --format table

# Sem partition em high volume
cfa evaluate "Scan all notas_fiscais without date filter" --catalog meu_catalogo.json --format table
```

**Check manual:**
- [ ] O resultado mostra BLOCKED ou REPLAN?
- [ ] Os faults são listados com severidade?
- [ ] As remediações sugeridas são acionáveis?

### 2.5 Carregar e usar policy bundles

```bash
cfa rules list --policy-bundle v1.0

cfa evaluate "Join notas_fiscais with cadastro_clientes persist Silver" --catalog meu_catalogo.json --policy-bundle policies/compliance-strict-v1.yaml --format table

cfa evaluate "Join notas_fiscais with cadastro_clientes persist Silver" --catalog meu_catalogo.json --policy-bundle policies/finops-strict-v1.yaml --format table
```

**Check manual:**
- [ ] O bundle `compliance-strict-v1` é mais restritivo que o default?
- [ ] O bundle `finops-strict-v1` bloqueia mais por custo?
- [ ] O nome do bundle aparece na saída?

### 2.6 Explicar um fault

```bash
cfa rules explain GOVERNANCE_RAW_PII_IN_PROTECTED_LAYER
cfa rules explain FINOPS_MISSING_TEMPORAL_PREDICATE
cfa rules explain CONTRACT_MISSING_MERGE_KEY
```

**Check manual:**
- [ ] Cada explicação inclui: fault_code, rule name, action, severity, message, remediation?
- [ ] As remediações são passos concretos (não genéricos)?

---

## Jornada 3 — Compliance Officer (25 min)

> **Persona:** Auditor ou compliance officer que precisa de evidências para auditoria regulatória.  
> **Objetivo:** Gerar trilha de auditoria completa, verificar integridade, exportar evidências.

### 3.1 Executar pipeline governado com auditoria

```bash
cfa evaluate "Join notas_fiscais with cadastro_clientes and persist to Silver" --catalog meu_catalogo.json --format json --output resultado_auditado.json
type resultado_auditado.json
```

**Check manual:**
- [ ] O JSON contém `intent_id` (UUID)?
- [ ] O JSON contém `state`, `signature_hash`, `replan_count`?
- [ ] O JSON contém `faults` (array)?
- [ ] O JSON contém `policy_bundle`?

Anote o `intent_id` para usar nos próximos passos:
```bash
# Extrai o intent_id (PowerShell)
$INTENT_ID = (Get-Content resultado_auditado.json | ConvertFrom-Json).intent_id
Write-Output "Intent ID: $INTENT_ID"
```

### 3.2 Verificar cadeia de auditoria

```bash
cfa audit show --id $INTENT_ID
cfa audit verify --id $INTENT_ID
cfa audit verify
```

**Check manual:**
- [ ] `audit show` mostra timeline de eventos?
- [ ] Cada evento tem: timestamp, phase, event_type, outcome?
- [ ] `audit verify` mostra "INTACT" ou "BROKEN"?
- [ ] O número de eventos é consistente com o que foi executado?

### 3.3 Gerar relatório de auditoria HTML

```bash
cfa report audit --intent-id $INTENT_ID --output auditoria_fiscal.html
start auditoria_fiscal.html
```

**Check manual (no browser):**
- [ ] O título é "CFA Audit Trail Report"?
- [ ] Mostra o intent_id?
- [ ] Mostra "Chain: INTACT" com badge verde?
- [ ] A tabela de eventos está completa?
- [ ] Os timestamps estão no formato ISO 8601?
- [ ] A cadeia de hash é visualizada?

### 3.4 Relatório de compliance

```bash
cfa report compliance --policy-bundle prod-v1.0 --output compliance_report.html
start compliance_report.html
```

**Check manual (no browser):**
- [ ] Mostra "Compliance Score" com percentual?
- [ ] Mostra gráfico doughnut de decisões?
- [ ] Mostra tabela de regras?
- [ ] Mostra total de eventos de auditoria?
- [ ] Mostra status da cadeia (INTACT/BROKEN)?

### 3.5 Prova de reprodutibilidade (I8)

```bash
# Executa o mesmo intent duas vezes
cfa evaluate "Join notas_fiscais with cadastro_clientes persist Silver" --catalog meu_catalogo.json --format json --output run1.json
cfa evaluate "Join notas_fiscais with cadastro_clientes persist Silver" --catalog meu_catalogo.json --format json --output run2.json

# Compara hashes (PowerShell)
$h1 = (Get-Content run1.json | ConvertFrom-Json).signature_hash
$h2 = (Get-Content run2.json | ConvertFrom-Json).signature_hash
Write-Output "Hash 1: $h1"
Write-Output "Hash 2: $h2"
Write-Output "Iguais? $($h1 -eq $h2)"
```

**Check manual:**
- [ ] Os hashes são idênticos?
- [ ] Isso prova que a mesma intenção produz a mesma assinatura (Invariante I8)?

---

## Jornada 4 — AI Developer (25 min)

> **Persona:** Desenvolvedor que está construindo um agente LangGraph.  
> **Objetivo:** Usar CFA como governance gate no agente, testar MCP server.

### 4.1 Governance guard via Python

Crie `cfa_demo/test_agent.py`:

```python
from cfa.adapters import cfa_guard
from cfa.policy import PolicyRule
from cfa.types import PolicyAction, FaultFamily, FaultSeverity

CATALOG = {
    "datasets": {
        "clientes": {
            "classification": "sensitive",
            "size_gb": 0.5,
            "pii_columns": ["cpf", "email"],
        }
    }
}

# Cenário 1: Intenção segura — o agente pode executar
@cfa_guard("Join NFe with Clientes and persist to Silver", catalog=CATALOG, mode="block")
def safe_agent_action(state):
    return {"status": "ok", "sql": "SELECT * FROM silver_fiscal"}

# Cenário 2: Intenção perigosa — CFA bloqueia
block_all = PolicyRule(
    name="block_dangerous", condition=lambda s: True, action=PolicyAction.BLOCK,
    fault_code="AGENT_BLOCKED", fault_family=FaultFamily.SEMANTIC,
    severity=FaultSeverity.CRITICAL, message="Dangerous action blocked by CFA.",
)

@cfa_guard("Write raw PII to production database", catalog=CATALOG, mode="block", policy_rules=[block_all])
def dangerous_agent_action(state):
    return {"status": "should not execute"}

# Testa
print("Teste 1 — ação segura:")
result = safe_agent_action({"user": "test"})
print(f"  Resultado: {result}")

print("\nTeste 2 — ação bloqueada:")
try:
    dangerous_agent_action({"user": "hacker"})
    print("  ERRO: deveria ter sido bloqueado!")
except PermissionError as e:
    print(f"  Bloqueado corretamente: {e}")
```

```bash
python test_agent.py
```

**Check manual:**
- [ ] Ação segura executa e retorna resultado?
- [ ] Ação perigosa é bloqueada com `PermissionError`?
- [ ] A mensagem de erro contém "CFA blocked"?
- [ ] A mensagem de erro menciona o intent?

### 4.2 Testar MCP server (simulação local)

Crie `cfa_demo/test_mcp.py`:

```python
import json
from cfa.mcp import _handle_request

# Simula um cliente MCP chamando o servidor

# 1. Listar tools
resp = _handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
tools = [t["name"] for t in resp["result"]["tools"]]
print("Tools disponíveis:", tools)

# 2. Avaliar uma signature
sig = {
    "domain": "fiscal", "intent": "reconciliation", "target_layer": "silver",
    "datasets": [{"name": "nfe", "classification": "high_volume", "size_gb": 4000, "pii_columns": []}],
    "constraints": {"no_pii_raw": True, "merge_key_required": True, "enforce_types": True, "partition_by": ["processing_date"]},
    "execution_context": {"policy_bundle_version": "prod-v1.0", "catalog_snapshot_version": "v1", "context_registry_version_id": "ctx1"},
}
resp = _handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
    "params": {"name": "cfa_evaluate_signature", "arguments": {"signature": sig}}})
data = json.loads(resp["result"]["content"][0]["text"])
print(f"\nAvaliação: {data['action']} (passed={data['passed']})")

# 3. Explicar um fault
resp = _handle_request({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
    "params": {"name": "cfa_explain_fault", "arguments": {"fault_code": "GOVERNANCE_RAW_PII_IN_PROTECTED_LAYER"}}})
data = json.loads(resp["result"]["content"][0]["text"])
print(f"\nFault: {data['rule_name']}")
print(f"Severidade: {data['severity']}")
print(f"Remediação: {data['remediation']}")

# 4. Listar backends
resp = _handle_request({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
    "params": {"name": "cfa_list_backends", "arguments": {}}})
data = json.loads(resp["result"]["content"][0]["text"])
print(f"\nBackends: {[b['name'] for b in data['backends']]}")

# 5. Verificar auditoria
resp = _handle_request({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
    "params": {"name": "cfa_audit_check", "arguments": {}}})
data = json.loads(resp["result"]["content"][0]["text"])
print(f"\nAudit chain: {'INTACT' if data['chain_intact'] else 'BROKEN'}")
```

```bash
python test_mcp.py
```

**Check manual:**
- [ ] 5 tools listadas?
- [ ] `cfa_evaluate_signature` retorna `approve`?
- [ ] `cfa_explain_fault` retorna remediação com passos concretos?
- [ ] `cfa_list_backends` lista `pyspark`?
- [ ] `cfa_audit_check` retorna `chain_intact: true`?

### 4.3 Testar Framework Adapters

Crie `cfa_demo/test_adapters.py`:

```python
# Testa que todos os 5 adapters importam e são callable
from cfa.adapters.langgraph import cfa_guard as langgraph_guard
from cfa.adapters.openai_agents import cfa_tool_guard
from cfa.adapters.crewai import cfa_crew_guard
from cfa.adapters.autogen import cfa_agent_guard
from cfa.adapters.dspy import cfa_module_guard
from cfa.adapters import cfa_guard as universal_guard

adapters = {
    "LangGraph": langgraph_guard,
    "OpenAI Agents": cfa_tool_guard,
    "CrewAI": cfa_crew_guard,
    "AutoGen": cfa_agent_guard,
    "DSPy": cfa_module_guard,
    "Universal": universal_guard,
}

for name, adapter in adapters.items():
    assert callable(adapter), f"{name} adapter is not callable!"
    # Testa uso básico
    @adapter("safe test intent", mode="warn")
    def dummy(): return "ok"
    result = dummy()
    assert result == "ok"
    print(f"  ✓ {name} adapter funciona")

print("\nTodos os 6 adapters funcionam!")
```

```bash
python test_adapters.py
```

**Check manual:**
- [ ] Todos os 6 adapters imprimem ✓?

---

## Jornada 5 — Platform Team (30 min)

> **Persona:** Time de plataforma que gerencia dezenas de pipelines.  
> **Objetivo:** CI/CD, métricas, observabilidade, notificações, dashboards.

### 5.1 Simulação de CI/CD

Crie `cfa_demo/ci_test.sh` (ou `.ps1`):

```powershell
# Simula um pipeline de CI validando intents
Write-Output "=== CFA Governance CI Check ==="

$INTENTS = @(
    "Join notas_fiscais with cadastro_clientes and persist to Silver",
    "aggregate vendas_diarias by produto",
    "Load produtos into Bronze"
)

$FAILED = 0
foreach ($intent in $INTENTS) {
    Write-Output "Checking: $intent"
    cfa evaluate $intent --catalog meu_catalogo.json --exit-code
    if ($LASTEXITCODE -ne 0) {
        Write-Output "  ❌ BLOCKED"
        $FAILED++
    } else {
        Write-Output "  ✓ PASSED"
    }
}

if ($FAILED -gt 0) {
    Write-Output "`n❌ CI FAILED: $FAILED blocked intents"
    exit 1
} else {
    Write-Output "`n✓ CI PASSED"
}
```

```powershell
.\ci_test.ps1
```

**Check manual:**
- [ ] Intents seguros passam (exit code 0)?
- [ ] O output mostra ✓ para cada intent?
- [ ] O resumo final mostra o total?

### 5.2 Métricas Prometheus

```bash
# Inicia servidor com métricas (em um terminal separado)
cfa serve --port 8765 --metrics-port 9090

# Em outro terminal, após algumas avaliações:
curl http://localhost:9090/metrics
```

**Check manual:**
- [ ] `/metrics` retorna texto no formato Prometheus?
- [ ] Contém `HELP` e `TYPE` lines?
- [ ] Contém `cfa_policy_evaluations_total`?
- [ ] Contém `cfa_replan_attempts_total`?
- [ ] Contém `cfa_audit_events_total`?
- [ ] `/health` retorna 200?

### 5.3 Dashboard interativo

```bash
cfa report lifecycle --period 90 --output dashboard_lifecycle.html
start dashboard_lifecycle.html

cfa report dashboard --period 30 --output dashboard_interativo.html
start dashboard_interativo.html
```

**Check manual (no browser):**
- [ ] O lifecycle dashboard mostra gráfico de tendências IFo?
- [ ] O dashboard interativo mostra tabela de skills?
- [ ] Os gráficos são interativos (hover mostra valores)?
- [ ] As cores são consistentes com o dark theme?
- [ ] A tabela de skills mostra estados (ACTIVE/WATCHLIST/DEMOTED) com badges coloridos?

### 5.4 Dashboard ao vivo

```bash
cfa serve --port 8765
```

**Check manual:**
- [ ] Abre o browser automaticamente?
- [ ] O dashboard carrega sem erros de console (F12)?
- [ ] A URL é `http://localhost:8765/...`?

### 5.5 Taxonomia e Behavior Spec

```bash
# Gera taxonomia a partir de spec YAML
cfa taxonomy generate --spec examples/fiscal_governance.yaml --output minha_taxonomia.json
type minha_taxonomia.json

# Gera intents de teste
cfa taxonomy test-intents --spec examples/fiscal_governance.yaml --count 3 --output meus_test_intents.txt
type meus_test_intents.txt

# Valida um intent contra a spec
cfa validate --spec examples/fiscal_governance.yaml --intent "Join NFe with Clientes persist Silver"
```

**Check manual:**
- [ ] Taxonomia JSON contém `allowed` e `not_allowed`?
- [ ] Cada failure mode tem `condition_type` válido?
- [ ] Test intents cobrem todas as categorias de failure?
- [ ] `cfa validate` retorna ✓ PASSED para intent seguro?

### 5.6 Backends registrados

```bash
cfa backend list
cfa backend list --format json
```

**Check manual:**
- [ ] Lista `pyspark` como built-in?
- [ ] Mostra capabilities (merge, anonymize)?

---

## Jornada 6 — Testes de Stress e Robustez (20 min)

> **Objetivo:** Garantir que o CFA não quebra sob condições extremas.

### 6.1 Muitas regras

```python
# Crie cfa_demo/stress_rules.py
from cfa.policy import PolicyRule, PolicyEngine
from cfa.types import *

rules = []
for i in range(200):
    rules.append(PolicyRule(
        name=f"rule_{i}", condition=lambda s: True, action=PolicyAction.APPROVE,
        fault_code=f"FC_{i}", fault_family=FaultFamily.SEMANTIC,
        severity=FaultSeverity.INFO, message=f"Rule {i}",
    ))

engine = PolicyEngine(rules=rules)
sig = StateSignature(domain="test", intent="test", target_layer=TargetLayer.SILVER,
    datasets=(), constraints=SignatureConstraints(),
    execution_context=ExecutionContext("v1", "v1", "v1"))

result = engine.evaluate(sig)
print(f"200 rules evaluated: {result.action.value} in {len(result.faults)} faults")
assert result.action == PolicyAction.APPROVE
print("✓ Stress test passed")
```

```bash
python stress_rules.py
```

**Check manual:**
- [ ] 200 regras avaliam em menos de 0.5 segundos?

### 6.2 Muitos intents

```bash
# PowerShell: 50 intents em sequência
1..50 | ForEach-Object {
    cfa evaluate "intent $_" --format summary
}
```

**Check manual:**
- [ ] Todos os 50 executam sem erro?
- [ ] O tempo total é aceitável (< 10 segundos)?

### 6.3 Intents com caracteres especiais

```bash
cfa evaluate "SELECT * FROM `"users`" WHERE name = 'João'; -- SQL injection" --format table
cfa evaluate "日本語のテスト" --format json
cfa evaluate "🚀 deploy to production 🔥" --format summary
```

**Check manual:**
- [ ] Caracteres SQL não quebram o parser?
- [ ] Unicode (japonês) funciona?
- [ ] Emojis não quebram a saída?

---

## Checklist Final

Ao final de todas as 6 jornadas, verifique:

- [ ] **CLI:** Todos os 9 comandos funcionam com `--help`
- [ ] **Formatos:** table, json, summary funcionam em todos os comandos
- [ ] **Relatórios:** 5 tipos de HTML abrem no browser sem erros
- [ ] **Gráficos:** Chart.js carrega em todos os relatórios
- [ ] **MCP:** 5 tools respondem corretamente
- [ ] **Adapters:** 6 adapters importam e funcionam
- [ ] **Bundles:** 3 bundles YAML carregam
- [ ] **Métricas:** Prometheus `/metrics` endpoint responde
- [ ] **OTel:** Span no-op não quebra
- [ ] **Notificações:** Slack/Teams não crasham
- [ ] **Auditoria:** Hash chain verificável
- [ ] **Reprodutibilidade:** Mesmo intent → mesmo hash (I8)
- [ ] **Stress:** 200 regras, 50 intents, Unicode, SQL injection
- [ ] **CI/CD:** `--exit-code` funciona para pipeline scripts
- [ ] **Dashboard:** `cfa serve` inicia servidor HTTP

---

## Reportando Problemas

Para cada teste que falhar, anote:
1. Comando executado
2. Saída esperada vs. saída real
3. Mensagem de erro completa
4. Ambiente (Windows/Linux, Python version)
