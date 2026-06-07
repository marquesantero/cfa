---
sidebar_position: 3
---

# Adaptador OpenAI Agents SDK

Adicione governança CFA a funções de ferramenta do OpenAI Agents SDK com um único decorator.

## Uso Básico

```python
from cfa.adapters.openai_agents import cfa_tool_guard

@cfa_tool_guard("consultar dados de clientes com PII mascarado",
                policy_bundle="prod-v1")
def consultar_clientes(regiao: str) -> str:
    ...
```

O decorator é equivalente ao `cfa.adapters.cfa_guard`. Antes de cada chamada de ferramenta, o CFA valida a intenção declarada contra o policy bundle ativo.
