"""Tests for cfa.runtime — production governance gate."""

from __future__ import annotations

import pytest

from cfa import GovernanceViolation, PolicyAction
from cfa.policy.engine import PolicyRule
from cfa.runtime import (
    GateConfig,
    GateResult,
    GateViolation,
    RuntimeGate,
    runtime_gate,
)
from cfa.types import DecisionState, FaultFamily, FaultSeverity

CATALOG = {
    "datasets": {
        "nfe": {
            "classification": "high_volume",
            "size_gb": 4000,
            "pii_columns": [],
            "partition_column": "processing_date",
        },
        "clientes": {
            "classification": "sensitive",
            "size_gb": 0.5,
            "pii_columns": ["cpf", "email"],
            "partition_column": "processing_date",
        },
    }
}


class TestGateConfig:
    def test_defaults(self):
        config = GateConfig()
        assert config.policy_bundle == "prod_v1.0"
        assert config.on_violation == GateViolation.BLOCK
        assert config.warnings_are_blocking is True

    def test_to_kernel_config(self):
        config = GateConfig(
            policy_bundle="custom_v2.0",
            backend="pyspark",
            warnings_are_blocking=False,
        )
        kc = config.to_kernel_config()
        assert kc.policy_bundle_version == "custom_v2.0"
        assert kc.backend == "pyspark"
        assert kc.warnings_are_blocking is False

    def test_audit_only_mode(self):
        config = GateConfig(on_violation=GateViolation.AUDIT_ONLY)
        assert config.on_violation == "audit_only"


class TestGateResult:
    def test_passed_result(self):
        result = GateResult(
            gate_id="g1",
            intent="safe intent",
            passed=True,
            state=DecisionState.APPROVED,
            signature_hash="abc123",
        )
        assert result.passed
        assert result.state == DecisionState.APPROVED

    def test_blocked_result(self):
        result = GateResult(
            gate_id="g1",
            intent="unsafe",
            passed=False,
            state=DecisionState.BLOCKED,
            blocked_reason="PII in protected layer",
            faults=["BEHAVIOR_RAW_PII"],
        )
        assert not result.passed
        assert result.blocked_reason == "PII in protected layer"


class TestRuntimeGate:
    def test_validate_safe_intent(self):
        gate = RuntimeGate(catalog=CATALOG)
        result = gate.validate("Join NFe with Clientes and persist to Silver")
        assert result.passed
        assert result.gate_id == gate.gate_id

    def test_validate_block_on_unsafe(self):
        block_all = PolicyRule(
            name="block_everything",
            condition=lambda sig: True,
            action=PolicyAction.BLOCK,
            fault_code="TEST_ALWAYS_BLOCK",
            fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.CRITICAL,
            message="Block all intents for testing.",
        )
        gate = RuntimeGate(
            config=GateConfig(on_violation=GateViolation.BLOCK),
            catalog=CATALOG,
            policy_rules=[block_all],
        )
        with pytest.raises(GovernanceViolation) as exc_info:
            gate.validate("any intent will be blocked")
        assert "Governance violation" in str(exc_info.value)

    def test_validate_warn_on_unsafe(self):
        gate = RuntimeGate(
            config=GateConfig(on_violation=GateViolation.WARN),
            catalog=CATALOG,
        )
        result = gate.validate(
            "Join NFe with Clientes and persist to Silver"
        )
        assert isinstance(result, GateResult)

    def test_validate_audit_only_never_blocks(self):
        gate = RuntimeGate(
            config=GateConfig(on_violation=GateViolation.AUDIT_ONLY),
            catalog=CATALOG,
        )
        result = gate.validate(
            "Join NFe with Clientes and persist to Silver"
        )
        assert isinstance(result, GateResult)

    def test_scope_context_manager(self):
        gate = RuntimeGate(catalog=CATALOG)
        gate.validate("Join NFe with Clientes and persist to Silver")
        with gate.scope("test_scope"):
            gate.record_metrics(rows=100, shuffle_mb=5, cost_dbu=1.0)
        assert gate._kernel.audit_trail.event_count > 0

    def test_scope_handles_exception_gracefully(self):
        gate = RuntimeGate(catalog=CATALOG)
        try:
            with gate.scope("test_error"):
                raise ValueError("pipeline failure")
        except ValueError:
            pass
        assert gate._kernel.audit_trail.event_count > 0

    def test_record_metrics(self):
        gate = RuntimeGate(catalog=CATALOG)
        gate.validate("Join NFe with Clientes and persist to Silver")
        gate.record_metrics(rows=5000, shuffle_mb=250, cost_dbu=3.5, duration_seconds=12.0)
        assert gate._kernel.audit_trail.event_count > 0

    def test_record_metrics_no_validation(self):
        gate = RuntimeGate(catalog=CATALOG)
        gate.record_metrics(rows=100, shuffle_mb=10)
        # Should not crash even without prior validate()
        assert True

    def test_gate_id_is_unique(self):
        gate1 = RuntimeGate()
        gate2 = RuntimeGate()
        assert gate1.gate_id != gate2.gate_id

    def test_guard_decorator(self):
        gate = RuntimeGate(catalog=CATALOG)

        @gate.guard("Join NFe with Clientes and persist to Silver")
        def safe_pipeline():
            return "done"

        result = safe_pipeline()
        assert result == "done"

    def test_guard_decorator_blocks_unsafe(self):
        block_all = PolicyRule(
            name="block_everything",
            condition=lambda sig: True,
            action=PolicyAction.BLOCK,
            fault_code="TEST_ALWAYS_BLOCK",
            fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.CRITICAL,
            message="Block all intents for testing.",
        )
        gate = RuntimeGate(
            config=GateConfig(on_violation=GateViolation.BLOCK),
            catalog=CATALOG,
            policy_rules=[block_all],
        )

        @gate.guard("any intent")
        def unsafe_pipeline():
            return "should not reach"

        with pytest.raises(GovernanceViolation):
            unsafe_pipeline()

    def test_gate_result_contains_execution_id(self):
        gate = RuntimeGate(catalog=CATALOG)
        result = gate.validate("Join NFe with Clientes and persist to Silver")
        assert result.execution_id != ""

    def test_gate_result_faults(self):
        gate = RuntimeGate(
            config=GateConfig(on_violation=GateViolation.WARN),
            catalog=CATALOG,
        )
        result = gate.validate("Join NFe with Clientes and persist to Silver")
        assert isinstance(result.faults, list)


class TestRuntimeGateDecorator:
    def test_standalone_decorator_passes(self):
        @runtime_gate(
            "Join NFe with Clientes and persist to Silver",
            catalog=CATALOG,
        )
        def safe_pipeline():
            return "ok"

        result = safe_pipeline()
        assert result == "ok"

    def test_standalone_decorator_blocks(self):
        block_all = PolicyRule(
            name="block_everything",
            condition=lambda sig: True,
            action=PolicyAction.BLOCK,
            fault_code="TEST_ALWAYS_BLOCK",
            fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.CRITICAL,
            message="Block all intents for testing.",
        )

        @runtime_gate(
            "any intent",
            catalog=CATALOG,
            policy_rules=[block_all],
            on_violation="block",
        )
        def unsafe_pipeline():
            return "should not reach"

        with pytest.raises(GovernanceViolation):
            unsafe_pipeline()


class TestGovernanceViolation:
    def test_exception_attributes(self):
        exc = GovernanceViolation(
            gate_id="g1",
            intent="bad intent",
            reason="PII violation",
            faults=["BEHAVIOR_RAW_PII", "CONTRACT_MISSING_MERGE_KEY"],
        )
        assert exc.gate_id == "g1"
        assert exc.intent == "bad intent"
        assert len(exc.faults) == 2
        assert "PII violation" in str(exc)
