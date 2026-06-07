"""AutoGen adapter — CFA governance for agent functions.

Usage::

    from cfa.adapters.autogen import cfa_agent_guard

    @cfa_agent_guard("analyze customer data without raw PII",
                      policy_bundle="compliance-strict-v1")
    def analyze(state):
        ...

The decorator is equivalent to ``cfa.adapters.cfa_guard``.
"""

from __future__ import annotations

from ..adapters import cfa_guard as _cfa_guard

cfa_agent_guard = _cfa_guard
