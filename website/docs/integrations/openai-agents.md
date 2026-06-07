---
sidebar_position: 3
---

# OpenAI Agents SDK Adapter

Add CFA governance to OpenAI Agents SDK tool functions with a single decorator.

---

## Installation

```bash
pip install cfa openai-agents
```

---

## Basic Usage

```python
from cfa.adapters.openai_agents import cfa_tool_guard

@cfa_tool_guard(policy_bundle="prod-v1")
def query_database(query: str) -> list[dict]:
    """Query the NFe database in Silver layer"""
    # Your tool logic — only executes if CFA approves
    return [{"id": 1, "value": 100}]
```

The decorator validates the intent (from the function's docstring) against CFA policy before the tool executes. If blocked, a `PermissionError` is raised.

---

## With the Agents SDK

```python
from agents import Agent, Runner
from cfa.adapters.openai_agents import cfa_tool_guard

@cfa_tool_guard("write aggregated results to Gold layer", policy_bundle="prod-v1")
def write_to_gold(data: list[dict]) -> str:
    return "Data written to Gold"

@cfa_tool_guard("query Silver layer for reconciliation", catalog=MY_CATALOG)
def query_silver(query: str) -> list[dict]:
    return [{"total": 5000}]

agent = Agent(
    name="Data Analyst",
    instructions="You help analyze fiscal data.",
    tools=[write_to_gold, query_silver],
)

result = Runner.run_sync(agent, "Reconcile NFe data and save results")
```

---

## Modes

| Mode | Behavior |
|------|----------|
| `block` (default) | Raises `PermissionError` if CFA blocks the tool |
| `warn` | Logs a warning but allows tool execution |
| `audit` | Silently records the evaluation for audit |

```python
@cfa_tool_guard("read from Bronze", mode="audit")
def read_bronze_data(query: str) -> list[dict]:
    ...
```

---

## With Explicit Intent String

```python
@cfa_tool_guard(
    "Join NFe with Clientes, anonymize PII, persist to Silver",
    catalog=CATALOG,
    policy_bundle="compliance-strict-v1",
    mode="block",
)
def sensitive_join_tool(params: dict) -> dict:
    ...
```

---

## Guarding Multiple Tools

```python
from cfa.adapters.openai_agents import cfa_tool_guard

POLICY = "compliance-strict-v1"

@cfa_tool_guard("read raw data from Bronze", policy_bundle=POLICY, mode="audit")
def read_raw(source: str) -> list[dict]:
    ...

@cfa_tool_guard("clean PII and write to Silver", policy_bundle=POLICY)
def clean_and_write(data: list[dict]) -> str:
    ...

@cfa_tool_guard("aggregate and publish to Gold", policy_bundle=POLICY, catalog=MY_CATALOG)
def aggregate_and_publish(metrics: dict) -> str:
    ...
```

---

## Handling Blocked Tools

```python
from agents import Agent, Runner
from cfa.adapters.openai_agents import cfa_tool_guard

@cfa_tool_guard("write raw PII to Gold", mode="block")
def unsafe_write(data: list[dict]) -> str:
    # This will never execute — CFA blocks it before the function body
    ...

try:
    unsafe_write([{"cpf": "123"}])
except PermissionError as e:
    print(f"Tool blocked by CFA: {e}")
    # The agent can fall back to a safe alternative
```

---

## Adapter Internals

The OpenAI Agents SDK adapter is 3 lines of code:

```python
"""OpenAI Agents SDK adapter — CFA governance for tool functions."""
from ..adapters import cfa_guard as _cfa_guard
cfa_tool_guard = _cfa_guard
```

All framework adapters share the same underlying `CFAGuard` class, wrapping any callable with CFA policy validation. The adapter simply exports it as `cfa_tool_guard` for semantic clarity within the OpenAI Agents ecosystem.
