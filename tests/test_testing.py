"""Tests for cfa.testing — pytest-native governance testing surface."""

from __future__ import annotations

import pytest

from cfa import PolicyAction
from cfa.policy.engine import PolicyRule
from cfa.sandbox import MockSandboxBackend
from cfa.testing import (
    assert_audit_intact,
    assert_blocked,
    assert_has_fault,
    assert_no_fault,
    assert_no_faults,
    assert_passed,
    assert_replan_attempted,
    evaluate,
)
from cfa.types import FaultFamily, FaultSeverity

# ── evaluate() integration tests ─────────────────────────────────────────────


class TestEvaluateBasic:
    def test_approves_safe_intent(self):
        result = evaluate(
            "Join NFe with Clientes and persist to Silver",
            catalog={
                "datasets": {
                    "nfe": {"classification": "high_volume", "size_gb": 4000, "pii_columns": []},
                    "clientes": {"classification": "sensitive", "size_gb": 0.5, "pii_columns": ["cpf"]},
                }
            },
        )
        assert_passed(result)
        assert_audit_intact(result)
        assert result.signature_hash != ""

    def test_passed_property(self):
        result = evaluate(
            "Join NFe with Clientes and persist to Silver",
            catalog={
                "datasets": {
                    "nfe": {"classification": "high_volume", "size_gb": 4000, "pii_columns": []},
                    "clientes": {"classification": "sensitive", "size_gb": 0.5, "pii_columns": ["cpf"]},
                }
            },
        )
        assert result.passed
        assert result.state.value in ("approved", "approved_with_warnings")

    def test_evaluation_result_repr(self):
        result = evaluate("Join NFe with Clientes and persist to Silver")
        rep = repr(result)
        assert "EvaluationResult" in rep
        assert result.state.value in rep

    def test_custom_backend_via_registry_name(self):
        result = evaluate(
            "Join NFe with Clientes and persist to Silver",
            backend="pyspark",
        )
        assert_passed(result)

    def test_custom_policy_rules_override_defaults(self):
        block_all = PolicyRule(
            name="block_everything",
            condition=lambda sig: True,
            action=PolicyAction.BLOCK,
            fault_code="TEST_BLOCK_ALL",
            fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.CRITICAL,
            message="Block all intents for testing.",
        )
        result = evaluate(
            "Join NFe with Clientes and persist to Silver",
            policy_rules=[block_all],
        )
        assert_blocked(result)
        assert_has_fault(result, "TEST_BLOCK_ALL")

    def test_replan_rule_converges(self):
        force_replan_once = PolicyRule(
            name="force_replan",
            condition=lambda sig: True,
            action=PolicyAction.REPLAN,
            fault_code="TEST_FORCE_REPLAN",
            fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.WARNING,
            message="Force replan for testing.",
        )
        never_block = PolicyRule(
            name="never_block",
            condition=lambda sig: True,
            action=PolicyAction.APPROVE,
            fault_code="TEST_NEVER_BLOCK",
            fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.INFO,
            message="Approve everything for testing.",
        )
        result = evaluate(
            "Join NFe with Clientes and persist to Silver",
            policy_rules=[force_replan_once, never_block],
        )
        assert result.replan_count > 0


# ── Fixture tests ────────────────────────────────────────────────────────────


class TestFixtures:
    def test_cfa_kernel_processes_intent(self, cfa_kernel):
        result = cfa_kernel.process("Join NFe with Clientes and persist to Silver")
        assert result.state.value in ("approved", "approved_with_warnings")

    def test_cfa_kernel_audit_has_events(self, cfa_kernel):
        result = cfa_kernel.process("Join NFe with Clientes and persist to Silver")
        assert len(result.audit_events) > 0

    def test_cfa_strict_kernel_processes(self, cfa_strict_kernel):
        result = cfa_strict_kernel.process(
            "Join NFe with Clientes and persist to Silver"
        )
        assert result.state.value in ("blocked", "approved", "approved_with_warnings")

    def test_cfa_noexec_kernel_skips_execution(self, cfa_noexec_kernel):
        result = cfa_noexec_kernel.process("Join NFe with Clientes and persist to Silver")
        assert result.state.value in (
            "approved",
            "approved_with_warnings",
            "promotion_candidate",
        )
        assert result.execution_plan is None
        assert result.generated_code is None

    def test_cfa_catalog_fixture(self, cfa_catalog):
        assert "nfe" in cfa_catalog["datasets"]
        assert "clientes" in cfa_catalog["datasets"]


# ── Assertion helper tests ──────────────────────────────────────────────────


class TestAssertionHelpers:
    def test_assert_passed_raises_when_blocked(self):
        block_all = PolicyRule(
            name="block_everything",
            condition=lambda sig: True,
            action=PolicyAction.BLOCK,
            fault_code="TEST_BLOCK_ALL",
            fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.CRITICAL,
            message="Block all intents for testing.",
        )
        result = evaluate(
            "Join NFe with Clientes and persist to Silver",
            policy_rules=[block_all],
        )
        with pytest.raises(AssertionError):
            assert_passed(result)

    def test_assert_blocked_raises_when_passed(self):
        result = evaluate("Join NFe with Clientes and persist to Silver")
        with pytest.raises(AssertionError):
            assert_blocked(result)

    def test_assert_no_faults_on_clean_intent(self):
        result = evaluate("Join NFe with Clientes and persist to Silver")
        assert_no_faults(result)

    def test_assert_has_fault_detects_block(self):
        block_all = PolicyRule(
            name="block_everything",
            condition=lambda sig: True,
            action=PolicyAction.BLOCK,
            fault_code="TEST_BLOCK_ALL",
            fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.CRITICAL,
            message="Block all intents for testing.",
        )
        result = evaluate(
            "Join NFe with Clientes and persist to Silver",
            policy_rules=[block_all],
        )
        assert_has_fault(result, "TEST_BLOCK_ALL")

    def test_assert_no_fault_raises_when_present(self):
        block_all = PolicyRule(
            name="block_everything",
            condition=lambda sig: True,
            action=PolicyAction.BLOCK,
            fault_code="TEST_BLOCK_ALL",
            fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.CRITICAL,
            message="Block all intents for testing.",
        )
        result = evaluate(
            "Join NFe with Clientes and persist to Silver",
            policy_rules=[block_all],
        )
        with pytest.raises(AssertionError):
            assert_no_fault(result, "TEST_BLOCK_ALL")

    def test_assert_audit_intact_on_clean_result(self):
        result = evaluate("Join NFe with Clientes and persist to Silver")
        assert_audit_intact(result)

    def test_assert_replan_attempted_on_replan(self):
        force_replan_once = PolicyRule(
            name="force_replan",
            condition=lambda sig: True,
            action=PolicyAction.REPLAN,
            fault_code="TEST_FORCE_REPLAN",
            fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.WARNING,
            message="Force replan for testing.",
        )
        never_block = PolicyRule(
            name="never_block",
            condition=lambda sig: True,
            action=PolicyAction.APPROVE,
            fault_code="TEST_APPROVE",
            fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.INFO,
            message="Approve everything for testing.",
        )
        result = evaluate(
            "Join NFe with Clientes and persist to Silver",
            policy_rules=[force_replan_once, never_block],
        )
        assert_replan_attempted(result)


# ── Marker tests ─────────────────────────────────────────────────────────────


@pytest.mark.cfa_governance
class TestMarkers:
    def test_governance_marker_works(self, cfa_kernel):
        result = cfa_kernel.process("Join NFe with Clientes and persist to Silver")
        assert result.state.value in ("approved", "approved_with_warnings")

    @pytest.mark.cfa_policy("finops_strict")
    def test_policy_marker_works(self, cfa_kernel):
        result = cfa_kernel.process("aggregate NFe")
        assert result.state.value in ("approved", "approved_with_warnings", "blocked")

    @pytest.mark.cfa_audit
    def test_audit_marker_works(self, cfa_kernel):
        result = cfa_kernel.process("Join NFe with Clientes and persist to Silver")
        assert len(result.audit_events) > 0

    @pytest.mark.cfa_backend("pyspark")
    def test_backend_marker_works(self, cfa_kernel):
        result = cfa_kernel.process("Join NFe with Clientes and persist to Silver")
        assert result.state.value in ("approved", "approved_with_warnings")


# ── Edge cases ────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_intent_string(self):
        result = evaluate("", catalog={"datasets": {}})
        assert result.intent == ""

    def test_single_word_intent(self):
        result = evaluate("reconcile", catalog={"datasets": {}})
        assert isinstance(result.state.value, str)

    def test_evaluate_with_sandbox_override(self):
        sandbox = MockSandboxBackend()
        result = evaluate(
            "Join NFe with Clientes and persist to Silver",
            sandbox=sandbox,
        )
        assert_passed(result)

    def test_evaluate_with_schema_contract(self):
        result = evaluate(
            "Join NFe with Clientes and persist to Silver",
            schema_contract={"columns": ["nfe_id", "cpf_hash", "processing_date"]},
        )
        assert_passed(result)

    def test_evaluate_with_config_overrides(self):
        result = evaluate(
            "Join NFe with Clientes and persist to Silver",
            config_overrides={"max_replan_attempts": 5},
        )
        assert_passed(result)

    def test_audit_chain_properties(self):
        result = evaluate("Join NFe with Clientes and persist to Silver")
        assert result.audit_chain.intact
        assert result.audit_chain.event_count > 0
