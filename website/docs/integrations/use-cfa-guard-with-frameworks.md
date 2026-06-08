---
sidebar_position: 1
---

# Use `cfa_guard` with any agent framework

CFA exposes a single, framework-agnostic decorator: `cfa.adapters.cfa_guard`.
It validates a declared intent against the active policy bundle before the
wrapped function runs. If the policy blocks the intent, the decorator raises
`PermissionError` (in `mode="block"`).

There is **no per-framework adapter**. The same decorator works in any Python
codebase — LangGraph nodes, CrewAI tasks, AutoGen agents, DSPy modules, OpenAI
Agents SDK tools, raw scripts, Airflow tasks, Lambda handlers, anything.

:::info Why no per-framework wrapper?

Prior CFA releases (`0.1.x`) shipped `cfa.adapters.langgraph`,
`cfa.adapters.crewai`, `cfa.adapters.autogen`, `cfa.adapters.dspy`, and
`cfa.adapters.openai_agents`. They were all identical re-exports of
`cfa_guard`. Shipping them as "integrations" implied framework-specific
behavior that did not exist.

`0.2.0` removed them. Real integrations (dbt, Airflow, MCP) live in
`cfa.integrations.*` and have framework-specific code. The agent-side guard
remains a single universal decorator.

:::

## Quick start

```python
from cfa.adapters import cfa_guard

CATALOG = {
    "datasets": {
        "nfe":      {"classification": "high_volume", "pii_columns": []},
        "clientes": {"classification": "sensitive",   "pii_columns": ["cpf"]},
    }
}

@cfa_guard("Join NFe with Clientes anonymize CPF persist Silver",
           catalog=CATALOG, mode="block")
def my_function():
    ...
```

## Modes

| `mode` | Behavior when policy blocks |
|--------|-----------------------------|
| `block` (default) | Raise `PermissionError`; the function does not run |
| `warn` | Log the decision; the function still runs |
| `audit` | Silently record the decision; the function still runs |

## LangGraph node

```python
from langgraph.graph import StateGraph
from cfa.adapters import cfa_guard

@cfa_guard("aggregate sales with PII protected",
           policy_bundle="prod-v1", catalog=CATALOG)
def governed_node(state: dict) -> dict:
    return {"status": "ok"}

builder = StateGraph(dict)
builder.add_node("governed_step", governed_node)
```

## CrewAI task

```python
from crewai import Task
from cfa.adapters import cfa_guard

@cfa_guard("extract financial data from Silver layer",
           policy_bundle="finops-strict-v1")
def extract_callable():
    ...

extract_task = Task(
    description="Extract Silver financials",
    expected_output="DataFrame",
    callable=extract_callable,
)
```

## AutoGen agent function

```python
from cfa.adapters import cfa_guard

@cfa_guard("query customer data with PII masked", policy_bundle="prod-v1")
def query_customers_tool(region: str) -> str:
    ...
```

Register `query_customers_tool` with any AutoGen agent as you normally would.

## DSPy module

```python
import dspy
from cfa.adapters import cfa_guard

class GovernedRetrieval(dspy.Module):
    @cfa_guard("retrieve fiscal data with classification filter")
    def forward(self, query: str):
        return self.retriever(query)
```

## OpenAI Agents SDK tool

```python
from cfa.adapters import cfa_guard

@cfa_guard("query customer data with PII masked", policy_bundle="prod-v1")
def query_customers(region: str) -> str:
    ...
```

Pass `query_customers` to the OpenAI Agents SDK as a tool function.

## Reusing a single guard

Each call to `cfa_guard(...)` constructs a `KernelOrchestrator` lazily and
caches it for subsequent invocations of the wrapped function. For multiple
guarded functions sharing the same configuration, instantiate `CFAGuard`
explicitly:

```python
from cfa.adapters import CFAGuard

guard = CFAGuard(policy_bundle="prod-v1", catalog=CATALOG, mode="block")

@guard.guard("aggregate sales")
def step_a(): ...

@guard.guard("publish to gold")
def step_b(): ...
```

`guard` reuses one `KernelOrchestrator` across both functions.

## API reference

- `cfa.adapters.cfa_guard(intent, *, policy_bundle, catalog, mode, **kwargs)` — the universal decorator.
- `cfa.adapters.CFAGuard(policy_bundle, catalog, backend, mode, **kernel_kwargs)` — the underlying class. Use directly when you want to reuse a single configured guard across multiple functions.

See [API Reference](../api) for full signatures.
