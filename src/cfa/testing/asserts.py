"""
CFA Testing — assertion helpers
===============================
Custom assertion functions for governance test results.

Usage:
    from cfa.testing import evaluate, assert_passed, assert_audit_intact

    def test_my_intent():
        result = evaluate("agregar vendas com PII protegido")
        assert_passed(result)
        assert_audit_intact(result)
        assert_no_fault(result, "GOVERNANCE_RAW_PII_IN_PROTECTED_LAYER")
"""

from __future__ import annotations

from .evaluate import EvaluationResult


def assert_passed(result: EvaluationResult, *, message: str = "") -> None:
    """Assert that the evaluation passed (approved or approved_with_warnings)."""
    msg = message or (
        f"Expected evaluation to pass, got state={result.state.value}. "
        f"Blocked reason: {result.blocked_reason}"
    )
    assert result.passed, msg


def assert_blocked(result: EvaluationResult, *, reason_contains: str = "", message: str = "") -> None:
    """Assert that the evaluation was blocked, optionally checking the reason."""
    msg = message or f"Expected evaluation to be blocked, got state={result.state.value}."
    assert result.blocked, msg
    if reason_contains:
        assert reason_contains.lower() in result.blocked_reason.lower(), (
            f"Expected blocked reason to contain '{reason_contains}', "
            f"got: {result.blocked_reason}"
        )


def assert_audit_intact(result: EvaluationResult, *, message: str = "") -> None:
    """Assert that the audit chain has events and is intact."""
    msg = message or "Expected audit chain to have events."
    assert result.audit_chain.event_count > 0, msg
    assert result.audit_chain.intact, "Audit chain integrity check failed."


def assert_no_faults(result: EvaluationResult, *, message: str = "") -> None:
    """Assert that the evaluation produced no faults."""
    msg = message or (
        f"Expected no faults, got {len(result.faults)}: {result.faults}"
    )
    assert len(result.faults) == 0, msg


def assert_no_fault(result: EvaluationResult, fault_code: str, *, message: str = "") -> None:
    """Assert that a specific fault code is NOT present."""
    msg = message or (
        f"Expected fault '{fault_code}' to be absent, "
        f"but it was found. All faults: {result.faults}"
    )
    assert fault_code not in result.faults, msg


def assert_has_fault(result: EvaluationResult, fault_code: str, *, message: str = "") -> None:
    """Assert that a specific fault code IS present."""
    msg = message or (
        f"Expected fault '{fault_code}' to be present, "
        f"but it was not found. All faults: {result.faults}"
    )
    assert fault_code in result.faults, msg


def assert_replan_attempted(result: EvaluationResult, *, message: str = "") -> None:
    """Assert that at least one replan was attempted."""
    msg = message or "Expected at least one replan attempt."
    assert result.replan_count > 0, msg
