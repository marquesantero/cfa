"""DSPy adapter — CFA governance for DSPy modules.

Usage::

    from cfa.adapters.dspy import cfa_module_guard

    @cfa_module_guard("classify transactions with PII protected",
                       policy_bundle="prod-v1")
    class TransactionClassifier(dspy.Module):
        ...

The decorator is equivalent to ``cfa.adapters.cfa_guard``.
"""

from __future__ import annotations

from ..adapters import cfa_guard as _cfa_guard

cfa_module_guard = _cfa_guard
