"""CrewAI adapter — CFA governance for crew tasks.

Usage::

    from cfa.adapters.crewai import cfa_crew_guard

    @cfa_crew_guard("extract financial data from Silver layer",
                     policy_bundle="finops-strict-v1")
    def extract_task():
        ...

The decorator is equivalent to ``cfa.adapters.cfa_guard``.
"""

from __future__ import annotations

from ..adapters import cfa_guard as _cfa_guard

cfa_crew_guard = _cfa_guard
