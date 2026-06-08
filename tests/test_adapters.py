"""Tests for cfa.adapters — universal governance guard.

Note: 0.2.0 removed the per-framework adapter shims (langgraph/crewai/autogen/
dspy/openai_agents). They were aliases of the same ``cfa_guard``. Use
``cfa.adapters.cfa_guard`` directly with any framework.
"""

from __future__ import annotations

import pytest

from cfa.adapters import CFAGuard, cfa_guard

CATALOG = {
    "datasets": {
        "nfe": {"classification": "high_volume", "size_gb": 4000, "pii_columns": []},
    }
}


class TestCFAGuard:
    def test_decorator_with_intent_passes(self):
        @cfa_guard("Join NFe with Clientes persist Silver", catalog=CATALOG)
        def safe_pipeline():
            return "ok"
        assert safe_pipeline() == "ok"

    def test_decorator_blocks_unsafe(self):
        from cfa.policy.engine import PolicyRule
        from cfa.types import FaultFamily, FaultSeverity, PolicyAction

        block_all = PolicyRule(
            name="block_all", condition=lambda sig: True, action=PolicyAction.BLOCK,
            fault_code="TEST_BLOCK", fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.CRITICAL, message="test",
        )
        @cfa_guard("anything", catalog=CATALOG, mode="block", policy_rules=[block_all])
        def blocked_pipeline():
            return "nope"

        with pytest.raises(PermissionError, match="CFA blocked"):
            blocked_pipeline()

    def test_warn_mode_allows(self):
        from cfa.policy.engine import PolicyRule
        from cfa.types import FaultFamily, FaultSeverity, PolicyAction

        block_all = PolicyRule(
            name="block_all", condition=lambda sig: True, action=PolicyAction.BLOCK,
            fault_code="TEST_BLOCK", fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.CRITICAL, message="test",
        )
        @cfa_guard("anything", catalog=CATALOG, mode="warn", policy_rules=[block_all])
        def warned_pipeline():
            return "still runs"
        assert warned_pipeline() == "still runs"

    def test_explicit_guard_method(self):
        guard = CFAGuard(catalog=CATALOG)

        @guard.guard("Join NFe with Clientes persist Silver")
        def my_fn():
            return 42
        assert my_fn() == 42

    def test_no_intent_uses_docstring(self):
        @cfa_guard(catalog=CATALOG)
        def my_safe_operation():
            """Join NFe with Clientes persist Silver"""
            return "safe"
        assert my_safe_operation() == "safe"

    def test_guard_caches_kernel_between_calls(self):
        """0.2.0: CFAGuard reuses a single KernelOrchestrator across calls."""
        guard = CFAGuard(catalog=CATALOG)

        @guard.guard("Join NFe with Clientes persist Silver")
        def call_once():
            return 1

        @guard.guard("Join NFe with Clientes persist Silver")
        def call_again():
            return 2

        call_once()
        call_again()
        # Internal cache populated after first call
        assert guard._kernel is not None
