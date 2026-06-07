"""OpenAI Agents SDK adapter — CFA governance for tool functions.

Usage::

    from cfa.adapters.openai_agents import cfa_tool_guard

    @cfa_tool_guard("query customer data with PII masked", policy_bundle="prod-v1")
    def query_customers(region: str) -> str:
        ...

The decorator is equivalent to ``cfa.adapters.cfa_guard``. Before every tool
call, CFA validates the declared intent against the active policy bundle.
"""

from __future__ import annotations

from ..adapters import cfa_guard as _cfa_guard

cfa_tool_guard = _cfa_guard
