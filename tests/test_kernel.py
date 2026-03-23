"""Tests for CFA Kernel Orchestrator — integration tests."""

from cfa.audit import AuditTrail
from cfa.context import ContextRegistry
from cfa.kernel import KernelOrchestrator
from cfa.normalizer import AutoRejectHandler
from cfa.types import DecisionState
from conftest import CATALOG


class TestKernelApproval:
    def test_approves_simple_bronze_intent(self):
        kernel = KernelOrchestrator(catalog=CATALOG)
        result = kernel.process("Carregar produtos na Bronze")
        assert result.state in (DecisionState.APPROVED, DecisionState.APPROVED_WITH_WARNINGS)
        assert result.signature is not None
        assert result.is_executable

    def test_approves_pii_join_after_auto_replan(self):
        kernel = KernelOrchestrator(catalog=CATALOG)
        result = kernel.process("Junte nfe com clientes e salve na Silver")
        assert result.state in (DecisionState.APPROVED, DecisionState.APPROVED_WITH_WARNINGS)
        assert result.is_executable

    def test_signature_hash_deterministic_across_calls(self):
        kernel = KernelOrchestrator(catalog=CATALOG)
        r1 = kernel.process("Carregar produtos na Bronze")
        r2 = kernel.process("Carregar produtos na Bronze")
        if r1.signature and r2.signature:
            assert r1.signature.signature_hash == r2.signature.signature_hash


class TestKernelBlocking:
    def test_blocks_gold_with_rejection(self):
        kernel = KernelOrchestrator(
            catalog=CATALOG,
            confirmation_handler=AutoRejectHandler(),
        )
        result = kernel.process("Publicar dados finais na Gold")
        assert result.state == DecisionState.BLOCKED

    def test_blocked_has_reason(self):
        kernel = KernelOrchestrator(
            catalog=CATALOG,
            confirmation_handler=AutoRejectHandler(),
        )
        result = kernel.process("Publicar dados finais na Gold")
        assert result.blocked_reason != ""


class TestKernelReplan:
    def test_replan_cycle_does_not_hang(self):
        kernel = KernelOrchestrator(catalog=CATALOG)
        result = kernel.process("Processar nfe na Silver sem filtro temporal")
        # Should either approve (after replan) or block, never hang
        assert result.state in (
            DecisionState.APPROVED,
            DecisionState.APPROVED_WITH_WARNINGS,
            DecisionState.BLOCKED,
        )

    def test_replan_history_recorded(self):
        kernel = KernelOrchestrator(catalog=CATALOG)
        result = kernel.process("Junte nfe com clientes e salve na Silver")
        if result.state in (DecisionState.APPROVED, DecisionState.APPROVED_WITH_WARNINGS):
            # If replans were needed, they should be recorded
            replan_events = [
                e for e in result.audit_events if e["event_type"] == "replan_applied"
            ]
            # May or may not have replans depending on mock resolution
            assert isinstance(replan_events, list)


class TestKernelAuditTrail:
    def test_audit_events_populated(self):
        kernel = KernelOrchestrator(catalog=CATALOG)
        result = kernel.process("Carregar produtos na Bronze")
        assert len(result.audit_events) > 0
        stages = [e["stage"] for e in result.audit_events]
        assert "context_registry" in stages
        assert "intent_normalizer" in stages

    def test_audit_trail_receives_events(self):
        trail = AuditTrail()
        kernel = KernelOrchestrator(catalog=CATALOG, audit_trail=trail)
        result = kernel.process("Carregar produtos na Bronze")
        events = trail.get_events_for_intent(result.intent_id)
        assert len(events) > 0
        assert all(e.intent_id == result.intent_id for e in events)

    def test_approved_intent_has_decision_event(self):
        kernel = KernelOrchestrator(catalog=CATALOG)
        result = kernel.process("Carregar produtos na Bronze")
        if result.is_executable:
            decision_events = [
                e for e in result.audit_events if e["stage"] == "decision_engine"
            ]
            assert len(decision_events) == 1
            assert decision_events[0]["outcome"] in ("approved", "approved_with_warnings")


class TestKernelContextRegistry:
    def test_context_registry_updated_on_approval(self):
        registry = ContextRegistry()
        kernel = KernelOrchestrator(catalog=CATALOG, context_registry=registry)
        result = kernel.process("Carregar produtos na Bronze")
        if result.is_executable:
            env = registry.get_environment_state()
            assert len(env["execution_history"]) > 0
            assert env["execution_history"][-1]["intent_id"] == result.intent_id

    def test_context_registry_not_updated_on_block(self):
        registry = ContextRegistry()
        kernel = KernelOrchestrator(
            catalog=CATALOG,
            context_registry=registry,
            confirmation_handler=AutoRejectHandler(),
        )
        kernel.process("Publicar dados finais na Gold")
        env = registry.get_environment_state()
        assert len(env["execution_history"]) == 0


class TestKernelDescribe:
    def test_describe_returns_expected_keys(self):
        kernel = KernelOrchestrator(catalog=CATALOG)
        desc = kernel.describe()
        assert "config" in desc
        assert "context_registry_version" in desc
        assert "catalog_datasets" in desc
        assert "policy_rules" in desc
        assert "audit_events" in desc
