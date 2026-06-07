---
sidebar_position: 12
---

# Servidor MCP

CFA expõe suas ferramentas de governança via **Model Context Protocol** (MCP), permitindo que qualquer agente de IA compatível com MCP (ChatGPT, Claude, Copilot, Cursor, Windsurf) consulte e aplique políticas CFA em tempo real.

## Início Rápido

```bash
pip install cfa-kernel[mcp]
cfa-mcp
```

Ou:

```bash
python -m cfa.mcp
```

## Configuração

Adicione ao seu cliente MCP:

```json
{
  "mcpServers": {
    "cfa": {
      "command": "python",
      "args": ["-m", "cfa.mcp"]
    }
  }
}
```

## Ferramentas Expostas

| Ferramenta | Descrição |
|-----------|-----------|
| `cfa_evaluate_signature` | Avalia uma StateSignature contra o policy bundle ativo |
| `cfa_describe_rules` | Lista todas as regras de política ativas |
| `cfa_explain_fault` | Explica um código de fault com detalhes e correção |
| `cfa_audit_check` | Verifica integridade da cadeia de auditoria |
| `cfa_list_backends` | Lista backends de geração de código registrados |

## Protocolo

Servidor JSON-RPC sobre stdio, zero dependências externas no core. Compatível com qualquer cliente MCP.
