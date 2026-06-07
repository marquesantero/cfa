---
sidebar_position: 2
---

# LangGraph Adapter

Add CFA governance to LangGraph agent nodes with a single decorator.

---

## Installation

```bash
pip install cfa
```

---

## Basic Usage

```python
from cfa.adapters.langgraph import cfa_guard

@cfa_guard(policy_bundle="prod-v1")
def my_agent_node(state: dict) -> dict:
    """Join NFe with Clientes and persist to Silver"""
    # Your node logic — only executes if CFA approves
    return {"result": "processed"}
```

The decorator intercepts execution and validates the intent (derived from the function's docstring or name) against CFA policy before the node runs. If blocked, a `PermissionError` is raised.

---

## With Explicit Intent

```python
from cfa.adapters.langgraph import cfa_guard

@cfa_guard("aggregate sales data by region and persist to Gold", policy_bundle="finops-strict-v1")
def sales_aggregation_node(state: dict) -> dict:
    ...
```

---

## With a Catalog

```python
from cfa.adapters.langgraph import cfa_guard

CATALOG = {
    "datasets": {
        "nfe": {"classification": "high_volume", "size_gb": 4000, "pii_columns": []},
        "clientes": {"classification": "sensitive", "size_gb": 0.5, "pii_columns": ["cpf", "email"]},
    }
}

@cfa_guard("Join NFe with Clientes", catalog=CATALOG, policy_bundle="prod-v1")
def my_node(state: dict) -> dict:
    ...
```

---

## Modes

| Mode | Behavior |
|------|----------|
| `block` (default) | Raises `PermissionError` if CFA blocks the intent |
| `warn` | Logs a warning but allows execution to continue |
| `audit` | Records the evaluation silently without blocking |

```python
@cfa_guard("write to Silver", mode="warn")
def non_critical_node(state: dict) -> dict:
    ...
```

---

## LangGraph Graph Example

```python
from langgraph.graph import StateGraph
from cfa.adapters.langgraph import cfa_guard

class AgentState(dict):
    pass

@cfa_guard("fetch data from Bronze layer", policy_bundle="prod-v1")
def fetch_node(state: AgentState) -> AgentState:
    return {"data": "fetched"}

@cfa_guard("transform and write to Silver", policy_bundle="prod-v1")
def transform_node(state: AgentState) -> AgentState:
    return {"data": "transformed"}

@cfa_guard("aggregate and write to Gold", catalog=MY_CATALOG)
def aggregate_node(state: AgentState) -> AgentState:
    return {"data": "aggregated"}

graph = StateGraph(AgentState)
graph.add_node("fetch", fetch_node)
graph.add_node("transform", transform_node)
graph.add_node("aggregate", aggregate_node)
graph.add_edge("fetch", "transform")
graph.add_edge("transform", "aggregate")
graph.set_entry_point("fetch")
app = graph.compile()
```

---

## Integration with Conditional Edges

```python
from cfa.policy.engine import PolicyEngine

def route_after_gate(state: AgentState) -> str:
    engine = PolicyEngine()
    result = engine.evaluate(build_signature_from_state(state))
    if result.is_blocked:
        return "quarantine"
    return "execute"

graph.add_conditional_edges("gate", route_after_gate, {
    "execute": "pipeline",
    "quarantine": "alert_ops",
})
```

---

## Adapter Internals

The LangGraph adapter is 3 lines of code:

```python
"""LangGraph adapter — CFA governance for LangGraph agent nodes."""
from ..adapters import cfa_guard as _cfa_guard
cfa_guard = _cfa_guard
```

All framework adapters share the same underlying `CFAGuard` class, which wraps any callable with CFA policy validation. Each adapter simply re-exports it under a framework-appropriate name.
