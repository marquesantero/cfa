"""
CFA Testing — pytest-native governance testing
===============================================
Write governance tests as pytest functions with minimal boilerplate.

Quickstart:
    from cfa.testing import evaluate, assert_passed

    def test_my_pipeline():
        result = evaluate("agregar vendas com PII protegido")
        assert_passed(result)

Fixtures:
    from cfa.testing import cfa_kernel, cfa_catalog

    def test_with_fixture(cfa_kernel):
        result = cfa_kernel.process("intent text")
        assert result.state.value == "approved"

Markers:
    import pytest

    @pytest.mark.cfa_governance
    @pytest.mark.cfa_policy("finops_strict")
    def test_cost_limits(cfa_kernel):
        ...
"""

from __future__ import annotations

from .asserts import (
    assert_audit_intact,
    assert_blocked,
    assert_has_fault,
    assert_no_fault,
    assert_no_faults,
    assert_passed,
    assert_replan_attempted,
)
from .evaluate import AuditChain, EvaluationResult, evaluate
from .fixtures import cfa_catalog, cfa_kernel, cfa_noexec_kernel, cfa_strict_kernel
from .markers import _register_markers

__all__ = [
    "evaluate",
    "EvaluationResult",
    "AuditChain",
    "cfa_kernel",
    "cfa_catalog",
    "cfa_strict_kernel",
    "cfa_noexec_kernel",
    "assert_passed",
    "assert_blocked",
    "assert_audit_intact",
    "assert_no_faults",
    "assert_no_fault",
    "assert_has_fault",
    "assert_replan_attempted",
    "_register_markers",
]
