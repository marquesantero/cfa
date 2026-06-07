---
sidebar_position: 1
---

# CFA v0.1.6

Execução governada para agentes de IA e sistemas de dados.

## O que é CFA?

CFA é uma camada de governança que valida transições de estado antes da execução. Atua como um motor de decisão agnóstico:

1. **Recebe um contrato** — `StateSignature` (JSON, YAML ou linguagem natural)
2. **Valida o contrato** — estrutura, enums, campos obrigatórios
3. **Referência cruzada com catálogo** — datasets devem existir com metadados correspondentes
4. **Avalia políticas declarativas** — PII, FinOps, merge keys, partições, custos
5. **Decide** — `approve` / `replan` (com correções sugeridas) / `block`
6. **Registra decisão auditável** — cadeia de hash SHA-256, hashes de artefatos
7. **Acompanha saúde do ciclo de vida** — índices IFo, IFs, IFg, IDI por pipeline

## Instalação Rápida

```bash
pip install cfa-kernel
cfa init
cfa evaluate "Juntar NFe com Clientes e persistir na Silver" --catalog .cfa/catalog.json
```

## Conceitos principais

### StateSignature

O contrato universal. Qualquer sistema — CLI, API, agente, orquestrador — pode produzir um:

```json
{
  "domain": "fiscal",
  "intent": "reconciliation",
  "target_layer": "silver",
  "datasets": [
    {"name": "nfe", "classification": "high_volume", "pii_columns": [], "merge_keys": ["nfe_id"]}
  ],
  "constraints": {"no_pii_raw": true, "merge_key_required": true, "partition_by": ["processing_date"]},
  "execution_context": {"policy_bundle_version": "prod-v1.0", "catalog_snapshot_version": "v1", "context_registry_version_id": "ctx1"}
}
```

### Policy bundles

YAML declarativo. Sem código para definir regras de governança:

```yaml
policy_bundle:
  version: "prod-v1.0"
  rules:
    - name: forbid_raw_pii
      condition: pii_in_protected_layer
      action: block
      fault_code: GOVERNANCE_RAW_PII
      severity: critical
      message: "PII em camada protegida sem anonimização."
      remediation:
        - "Aplicar sha256 nas colunas de PII antes da operação"
```

### Saída da decisão

Toda decisão é estruturada e versionada:

```json
{
  "schema_version": "cfa.policy_check.v1",
  "decision_id": "...",
  "signature_hash": "...",
  "catalog_hash": "...",
  "policy_bundle_hash": "...",
  "action": "block",
  "passed": false,
  "faults": [{"code": "GOVERNANCE_RAW_PII", "severity": "critical", "remediation": [...]}],
  "audit_event_hash": "..."
}
```

## Diferenciais

| Funcionalidade | CFA | Outros |
|---------|-----|--------|
| Trilha de auditoria SHA-256 (tamper-evident) | ✅ | ❌ |
| Hash de artefatos (catálogo + política + assinatura) | ✅ | ❌ |
| REPLAN com intervenções automáticas | ✅ | ❌ |
| Índices de ciclo de vida (IFo/IFs/IFg/IDI) | ✅ | ❌ |
| Agnóstico de backend (PySpark, SQL, dbt) | ✅ | ❌ |
| Protocolo MCP para agentes de IA | ✅ | ❌ |
| Armazenamento SQLite com gestão de retenção | ✅ | ❌ |
| Arquivo de configuração com auto-descoberta | ✅ | ❌ |
| Zero dependências runtime (core) | ✅ | ❌ |

## Próximos passos

- **[Primeiros Passos](./getting-started)** — Instale e execute sua primeira verificação
- **[Referência CLI](./cli)** — Todos os comandos `cfa`
- **[Policy Bundles](./policy-bundles)** — Regras de política YAML declarativas
- **[Backends](./backends)** — Geração de código PySpark, SQL, dbt
- **[Servidor MCP](./mcp-server)** — Exponha CFA para agentes de IA
- **[Relatórios](./reporting)** — Relatórios HTML e dashboards
- **[Notas de Arquitetura](./architecture-notes)** — Decisões de design e trade-offs
