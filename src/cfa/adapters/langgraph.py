"""LangGraph adapter — CFA governance for LangGraph agent nodes.

CFA validates the node's declared intent before every invocation. Usage::

    from cfa.adapters.langgraph import cfa_guard

    @cfa_guard("aggregate sales with PII protected", policy_bundle="prod-v1")
    def my_node(state: dict) -> dict:
        ...

The decorator works identically to ``cfa.adapters.cfa_guard``. It raises
``PermissionError`` when the policy blocks the intent (``mode="block"``).
"""

from __future__ import annotations

from ..adapters import cfa_guard as _cfa_guard

cfa_guard = _cfa_guard
