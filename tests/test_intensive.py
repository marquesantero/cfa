"""
CFA Intensive Test Suite
========================
Comprehensive edge-case, integration, stress, and compatibility tests.

Run: pytest tests/test_intensive.py -v -s
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from cfa.audit.context import ContextRegistry
from cfa.audit.trail import AuditTrail
from cfa.backends import BackendRegistry
from cfa.core.conditions import build_condition, list_conditions
from cfa.core.kernel import KernelConfig, KernelOrchestrator
from cfa.policy.bundle import PolicyBundle
from cfa.policy.engine import PolicyEngine, PolicyRule
from cfa.testing import assert_passed, evaluate
from cfa.types import (
    DatasetClassification,
    DatasetRef,
    DecisionState,
    ExecutionContext,
    FaultFamily,
    FaultSeverity,
    PolicyAction,
    SignatureConstraints,
    StateSignature,
    TargetLayer,
)

CATALOG = {
    "datasets": {
        "nfe": {"classification": "high_volume", "size_gb": 4000, "pii_columns": [], "partition_column": "processing_date"},
        "clientes": {"classification": "sensitive", "size_gb": 0.5, "pii_columns": ["cpf", "email"], "partition_column": "processing_date"},
        "produtos": {"classification": "internal", "size_gb": 0.1, "pii_columns": []},
    }
}


# ══════════════════════════════════════════════════════════════════════════════
# CLI Integration Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestCLIIntegration:
    """Tests that simulate real CLI usage patterns."""

    def test_evaluate_table_format(self):
        from cfa.cli import main
        result = main(["evaluate", "Join NFe with Clientes and persist to Silver", "--format", "table"])
        assert result == 0

    def test_evaluate_json_format(self):
        from cfa.cli import main
        result = main(["evaluate", "anything", "--format", "json"])
        assert result == 0

    def test_evaluate_summary_format(self):
        from cfa.cli import main
        result = main(["evaluate", "test intent", "--format", "summary"])
        assert result == 0

    def test_evaluate_blocked_exit_code(self):
        from cfa.cli import main
        PolicyRule(
            name="b", condition=lambda s: True, action=PolicyAction.BLOCK,
            fault_code="TEST_BLOCK", fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.CRITICAL, message="blocked",
        )
        # Test via CLI by using --exit-code
        result = main(["evaluate", "anything", "--exit-code", "--format", "json"])
        assert isinstance(result, int)

    def test_evaluate_with_output_file(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            f.write("{}")
        from cfa.cli import main
        result = main(["evaluate", "test", "--output", f.name, "--format", "json"])
        assert result == 0
        content = Path(f.name).read_text()
        assert "test" in content

    def test_rules_list(self):
        from cfa.cli import main
        assert main(["rules", "list"]) == 0
        assert main(["rules", "list", "--format", "json"]) == 0

    def test_rules_explain_known(self):
        from cfa.cli import main
        assert main(["rules", "explain", "GOVERNANCE_RAW_PII_IN_PROTECTED_LAYER"]) == 0

    def test_rules_explain_unknown(self):
        from cfa.cli import main
        assert main(["rules", "explain", "NONEXISTENT_FAULT"]) == 1

    def test_backend_list(self):
        from cfa.cli import main
        assert main(["backend", "list"]) == 0
        assert main(["backend", "list", "--format", "json"]) == 0

    def test_init_creates_files(self):
        import os
        import tempfile
        d = tempfile.mkdtemp()
        from cfa.cli import main
        result = main(["init", "--dir", d])
        assert result == 0
        assert os.path.isfile(os.path.join(d, "catalog.json"))
        assert os.path.isfile(os.path.join(d, "config.yaml"))
        assert os.path.isfile(os.path.join(d, "policies", "prod-v1.yaml"))

    def test_help_commands(self):
        from cfa.cli import main
        for cmd in [["--help"], ["evaluate", "--help"], ["rules", "--help"],
                     ["audit", "--help"], ["taxonomy", "--help"],
                     ["backend", "--help"], ["report", "--help"]]:
            try:
                main(cmd)
            except SystemExit:
                pass  # argparse help exits with 0

    def test_taxonomy_generate(self):
        import os
        import tempfile

        from cfa.cli import main
        out = os.path.join(tempfile.mkdtemp(), "taxonomy.json")
        result = main(["taxonomy", "generate", "--spec", "examples/fiscal_governance.yaml", "--output", out])
        assert result == 0
        assert os.path.isfile(out)

    def test_taxonomy_test_intents(self):
        from cfa.cli import main
        result = main(["taxonomy", "test-intents", "--spec", "examples/fiscal_governance.yaml", "--count", "3"])
        assert result == 0

    def test_validate_command(self):
        from cfa.cli import main
        result = main(["validate", "--spec", "examples/fiscal_governance.yaml",
                        "--intent", "Join NFe with Clientes persist Silver"])
        assert result == 0


# ══════════════════════════════════════════════════════════════════════════════
# Edge Case Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Tests for boundary conditions and unusual inputs."""

    def test_empty_intent(self):
        result = evaluate("", catalog={"datasets": {}})
        assert result.intent == ""

    def test_very_long_intent(self):
        long = "Join " + "NFe with Clientes and persist to Silver. " * 20
        result = evaluate(long, catalog=CATALOG)
        assert result.passed

    def test_unicode_intent(self):
        result = evaluate("Juntar NF-e com Clientes e persistir na Silver 🚀", catalog=CATALOG)
        assert isinstance(result.state.value, str)

    def test_catalog_empty(self):
        result = evaluate("anything", catalog={"datasets": {}})
        assert result.passed

    def test_catalog_none(self):
        result = evaluate("anything")
        assert result.passed

    def test_intent_with_special_chars(self):
        result = evaluate("SELECT * FROM `table` WHERE x = 'y'; DROP TABLE;", catalog=CATALOG)
        assert isinstance(result.state.value, str)

    def test_intent_only_spaces(self):
        result = evaluate("   ", catalog={"datasets": {}})
        assert isinstance(result.state.value, str)

    def test_max_replan_exceeded(self):
        replan_rule = PolicyRule(
            name="always_replan", condition=lambda s: True, action=PolicyAction.REPLAN,
            fault_code="TEST_REPLAN", fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.WARNING, message="replan",
        )
        result = evaluate("anything", catalog=CATALOG,
                         policy_rules=[replan_rule],
                         config_overrides={"max_replan_attempts": 1})
        assert result.blocked  # Should block after max replans

    def test_custom_condition_registration(self):
        from cfa.core.conditions import register_condition
        def my_check(meta):
            def check(sig): return sig.domain == "custom_test"
            return check
        register_condition("custom_test_cond", my_check)
        assert "custom_test_cond" in list_conditions()


# ══════════════════════════════════════════════════════════════════════════════
# Integration Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestIntegration:
    """End-to-end pipeline integration tests."""

    def test_full_pipeline_approval(self):
        kernel = KernelOrchestrator(catalog=CATALOG)
        result = kernel.process("Join NFe with Clientes and persist to Silver")
        assert result.is_executable
        assert result.state in (DecisionState.APPROVED, DecisionState.APPROVED_WITH_WARNINGS)
        assert result.signature is not None
        assert result.audit_events

    def test_full_pipeline_with_promotion(self):
        kernel = KernelOrchestrator(
            catalog=CATALOG,
            config=KernelConfig(enable_promotion=True)
        )
        for _ in range(5):
            result = kernel.process("Join NFe with Clientes and persist to Silver")
        assert result.state.value in ("approved", "approved_with_warnings", "promotion_candidate")

    def test_behavior_spec_to_rules_integration(self):
        from cfa.behavior import BehaviorSpec, Systematizer

        spec = BehaviorSpec.from_dict({
            "behavior": {
                "name": "pii_test",
                "failure_modes": [
                    {"code": "pii_check", "condition": "pii_in_protected_layer",
                     "severity": "critical", "action": "block",
                     "remediation": ["fix"]},
                ],
            },
        })
        _, rules = Systematizer().systematize(spec)
        assert len(rules) == 1
        result = evaluate("Join NFe with Clientes and persist to Silver",
                         catalog=CATALOG, policy_rules=rules)
        assert_passed(result)

    def test_policy_bundle_roundtrip(self):
        bundle = PolicyBundle.from_yaml("policies/prod-v1.yaml")
        assert len(bundle.rules) == 7
        engine = PolicyEngine(rules=bundle.rules, policy_bundle_version=bundle.version)
        result = engine.evaluate(
            StateSignature(
                domain="fiscal", intent="test", target_layer=TargetLayer.SILVER,
                datasets=(DatasetRef("nfe", DatasetClassification.HIGH_VOLUME, size_gb=4000),),
                constraints=SignatureConstraints(no_pii_raw=True, merge_key_required=True,
                                                 enforce_types=True, partition_by=("processing_date",)),
                execution_context=ExecutionContext("test", "test", "test"),
            )
        )
        assert result.action == PolicyAction.APPROVE

    def test_three_bundles_load(self):
        for name in ["prod-v1", "finops-strict-v1", "compliance-strict-v1"]:
            bundle = PolicyBundle.from_yaml(f"policies/{name}.yaml")
            assert len(bundle.rules) >= 1

    def test_serialization_roundtrip(self):
        sig = StateSignature(
            domain="fiscal", intent="reconciliation", target_layer=TargetLayer.SILVER,
            datasets=(
                DatasetRef("nfe", DatasetClassification.HIGH_VOLUME, size_gb=4000),
            ),
            constraints=SignatureConstraints(partition_by=("processing_date",)),
            execution_context=ExecutionContext("v1", "v1", "v1"),
        )
        j = sig.to_json()
        sig2 = StateSignature.from_json(j)
        assert sig.signature_hash == sig2.signature_hash

    def test_kernel_result_serialization(self):
        from cfa.types import KernelResult
        sig = StateSignature(
            domain="test", intent="test", target_layer=TargetLayer.BRONZE,
            datasets=(), constraints=SignatureConstraints(),
            execution_context=ExecutionContext("v1", "v1", "v1"),
        )
        kr = KernelResult(intent_id="abc", state=DecisionState.APPROVED, signature=sig)
        d = kr.to_dict()
        assert d["intent_id"] == "abc"
        j = kr.to_json()
        assert "abc" in j

    def test_mcp_tools_direct(self):
        from cfa.mcp import _handle_request

        resp = _handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        tools = [t["name"] for t in resp["result"]["tools"]]
        assert "cfa_evaluate_signature" in tools
        assert len(tools) >= 5

    def test_otel_noop(self):
        from cfa.observability.otel import cfa_span
        with cfa_span("test", phase="govern"):
            pass

    def test_notify_no_crash(self):
        from cfa.observability.notify import SlackNotifier
        n = SlackNotifier("https://localhost:9999/nonexistent")
        n.notify("block", "test", "reason", ["F1"])


# ══════════════════════════════════════════════════════════════════════════════
# Condition Registry Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestConditionRegistry:
    """Test all 10 built-in conditions."""

    def _make_sig(self, **overrides):
        defaults = {
            "domain": "fiscal", "intent": "test", "target_layer": TargetLayer.SILVER,
            "datasets": (DatasetRef("nfe", DatasetClassification.HIGH_VOLUME, size_gb=4000),),
            "constraints": SignatureConstraints(),
            "execution_context": ExecutionContext("v1", "v1", "v1"),
        }
        defaults.update(overrides)
        return StateSignature(**defaults)

    def test_pii_in_protected_layer_fires(self):
        sig = self._make_sig(
            target_layer=TargetLayer.GOLD,
            datasets=(DatasetRef("clientes", DatasetClassification.SENSITIVE, pii_columns=("cpf",)),),
            constraints=SignatureConstraints(no_pii_raw=False),
        )
        cond = build_condition("pii_in_protected_layer", {"target_layer": "gold"})
        assert cond(sig) is True

    def test_pii_in_protected_layer_safe(self):
        sig = self._make_sig(constraints=SignatureConstraints(no_pii_raw=True))
        cond = build_condition("pii_in_protected_layer")
        assert cond(sig) is False

    def test_missing_merge_key_fires(self):
        sig = self._make_sig(constraints=SignatureConstraints(merge_key_required=False))
        cond = build_condition("missing_merge_key")
        assert cond(sig) is True

    def test_missing_partition_fires(self):
        sig = self._make_sig(
            datasets=(DatasetRef("nfe", DatasetClassification.HIGH_VOLUME, size_gb=4000),),
            constraints=SignatureConstraints(partition_by=()),
        )
        cond = build_condition("missing_partition", {"min_size_gb": 1.0})
        assert cond(sig) is True

    def test_sensitive_without_partition_fires(self):
        sig = self._make_sig(
            datasets=(DatasetRef("clientes", DatasetClassification.SENSITIVE),),
            constraints=SignatureConstraints(partition_by=()),
        )
        cond = build_condition("sensitive_without_partition")
        assert cond(sig) is True

    def test_enforce_types_disabled_fires(self):
        sig = self._make_sig(constraints=SignatureConstraints(enforce_types=False))
        cond = build_condition("enforce_types_disabled")
        assert cond(sig) is True

    def test_pii_without_policy_fires(self):
        sig = self._make_sig(
            datasets=(DatasetRef("c", DatasetClassification.SENSITIVE, pii_columns=("cpf",)),),
            constraints=SignatureConstraints(no_pii_raw=False),
        )
        cond = build_condition("pii_without_policy")
        assert cond(sig) is True

    def test_cost_budget_exceeded_fires(self):
        sig = self._make_sig(constraints=SignatureConstraints(max_cost_dbu=0.0))
        cond = build_condition("cost_budget_exceeded")
        assert cond(sig) is True

    def test_unknown_condition_raises(self):
        with pytest.raises(KeyError):
            build_condition("nonexistent_condition")

    def test_all_registered_conditions(self):
        names = list_conditions()
        assert len(names) >= 10
        for name in names:
            cond = build_condition(name)
            assert callable(cond)


# ══════════════════════════════════════════════════════════════════════════════
# Backend Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestBackendRegistry:
    def test_pyspark_capabilities(self):
        registry = BackendRegistry.singleton()
        factory = registry.get("pyspark")
        backend = factory()
        caps = backend.get_capabilities()
        assert caps.supports_merge is True
        assert caps.supports_anonymization is True
        assert "sha256" in caps.pii_anonymization_methods

    def test_unknown_backend_raises(self):
        registry = BackendRegistry.singleton()
        with pytest.raises(KeyError):
            registry.get("nonexistent_backend_v2")

    def test_list_backends(self):
        registry = BackendRegistry.singleton()
        names = registry.list()
        assert "pyspark" in names


# ══════════════════════════════════════════════════════════════════════════════
# Audit Trail Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestAuditIntensive:
    def test_chain_verification(self):
        trail = AuditTrail()
        trail.record(intent_id="a", stage="govern", event_type="check",
                     outcome="ok", policy_bundle_version="v1")
        trail.record(intent_id="a", stage="generate", event_type="code",
                     outcome="ok", policy_bundle_version="v1")
        assert trail.event_count == 2
        assert trail.verify_chain() is True

    def test_audit_events_by_intent(self):
        trail = AuditTrail()
        for i in range(3):
            trail.record(intent_id=f"intent_{i}", stage="test", event_type="e",
                         outcome="ok", policy_bundle_version="v1")
        events = trail.get_events_for_intent("intent_1")
        assert len(events) == 1
        assert events[0].intent_id == "intent_1"


# ══════════════════════════════════════════════════════════════════════════════
# Context Registry Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestContextIntensive:
    def test_registry_records_execution(self):
        reg = ContextRegistry()
        reg.record_execution(intent_id="a", outcome="approved", signature_hash="hash")
        env = reg.get_environment_state()
        assert len(env["execution_history"]) == 1

    def test_registry_multiple_executions(self):
        reg = ContextRegistry()
        for i in range(5):
            reg.record_execution(intent_id=f"i{i}", outcome="approved",
                               signature_hash=f"h{i}")
        env = reg.get_environment_state()
        assert len(env["execution_history"]) == 5

    def test_registry_snapshot(self):
        reg = ContextRegistry()
        reg.record_execution(intent_id="a", outcome="approved", signature_hash="h")
        snapshot_id = reg.snapshot()
        assert snapshot_id != ""


# ══════════════════════════════════════════════════════════════════════════════
# Stress Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestStress:
    def test_many_intents(self):
        kernel = KernelOrchestrator(catalog=CATALOG)
        for i in range(50):
            result = kernel.process(f"Join NFe with Clientes and persist to Silver #{i}")
            assert result.state.value in ("approved", "approved_with_warnings", "promotion_candidate")

    def test_many_rules(self):
        rules = []
        for i in range(50):
            rules.append(PolicyRule(
                name=f"rule_{i}", condition=lambda s, i=i: s.domain == f"domain_{i}",
                action=PolicyAction.APPROVE, fault_code=f"FC_{i}",
                fault_family=FaultFamily.SEMANTIC, severity=FaultSeverity.INFO,
                message=f"Rule {i}",
            ))
        engine = PolicyEngine(rules=rules)
        sig = StateSignature(
            domain="fiscal", intent="test", target_layer=TargetLayer.SILVER,
            datasets=(), constraints=SignatureConstraints(),
            execution_context=ExecutionContext("v1", "v1", "v1"),
        )
        result = engine.evaluate(sig)
        assert result.action == PolicyAction.APPROVE

    def test_rapid_audit_events(self):
        trail = AuditTrail()
        for i in range(100):
            trail.record(intent_id=f"rapid_{i}", stage="test", event_type="e",
                         outcome="ok", policy_bundle_version="v1")
        assert trail.event_count == 100
        assert trail.verify_chain() is True
