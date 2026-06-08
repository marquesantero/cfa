"""Deprecated since 1.1.0. Use ``cfa.adapters.cfa_guard`` directly.

This module remains as a shim re-exporting :func:`cfa.adapters.cfa_guard` so
existing imports keep working. It will be removed in CFA 2.0.0.

The previous per-framework adapter modules (``cfa.adapters.langgraph``,
``crewai``, ``autogen``, ``dspy``, ``openai_agents``) were all aliases of
the same ``cfa_guard`` decorator. Shipping them as separate "integrations"
implied framework-specific behavior that did not exist. The single
universal ``cfa_guard`` decorator works in any Python codebase.

Migration::

    # Before
    from cfa.adapters.langgraph import cfa_guard

    # After
    from cfa.adapters import cfa_guard
"""

from __future__ import annotations

import warnings

from cfa.adapters import cfa_guard as _cfa_guard

warnings.warn(
    "cfa.adapters.langgraph is deprecated since 1.1.0 and will be removed "
    "in 2.0.0. Import cfa_guard from cfa.adapters directly.",
    DeprecationWarning,
    stacklevel=2,
)

cfa_guard = _cfa_guard

__all__ = ["cfa_guard"]
