---
sidebar_position: 2
---

# Adaptador LangGraph

Adicione governança CFA a nós de agentes LangGraph com um único decorator.

## Uso Básico

```python
from cfa.adapters.langgraph import cfa_guard

@cfa_guard("agregar vendas com PII protegido", policy_bundle="prod-v1")
def meu_no(state: dict) -> dict:
    ...
```

## Com Catálogo

```python
@cfa_guard("juntar NFe com Clientes para Silver",
           catalog=CATALOGO_PRODUCAO, strict=True)
def no_reconciliacao(state: dict) -> dict:
    ...
```

Cada nó decorado é validado pelo CFA antes da execução. Se a política bloquear a intenção, uma exceção `PermissionError` é lançada.
