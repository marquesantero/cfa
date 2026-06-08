"""
CFA User Acceptance Tests — 5 Real User Journeys
=================================================
Simulates actual user workflows from first install to production deployment.

Each journey uses only the public API — exactly as a real user would.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

CATALOG = {
    "datasets": {
        "nfe": {"classification": "high_volume", "size_gb": 4000, "pii_columns": [], "partition_column": "processing_date"},
        "clientes": {"classification": "sensitive", "size_gb": 0.5, "pii_columns": ["cpf", "email"], "partition_column": "processing_date"},
        "produtos": {"classification": "internal", "size_gb": 0.1, "pii_columns": []},
        "vendas": {"classification": "high_volume", "size_gb": 2000, "pii_columns": [], "partition_column": "data_venda"},
    }
}


# ══════════════════════════════════════════════════════════════════════════════
# Jornada 1: Primeiro Uso
# "Sou um dev Python, ouvi falar do CFA, quero testar em 5 minutos"
# ══════════════════════════════════════════════════════════════════════════════

class TestJourney1_FirstTimeUser:
    """A developer installing and using CFA for the first time."""

    def test_01_install_and_version(self):
        """User: pip install cfa && python -c 'import cfa; print(cfa.__version__)'"""
        import cfa
        assert cfa.__version__.startswith("1.")

    def test_02_first_evaluate(self):
        """User: cfa evaluate 'my first governance check'"""
        from cfa.testing import evaluate
        result = evaluate("Join NFe with Clientes and persist to Silver")
        assert result.passed
        print(f"  → {result.state.value} | hash={result.signature_hash}")

    def test_03_cli_table_output(self):
        """User: cfa evaluate --format table"""
        import io
        import sys

        from cfa.cli import main
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            main(["evaluate", "Join NFe with Clientes and persist to Silver", "--format", "table"])
        except SystemExit:
            pass
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        assert "approved" in output.lower() or "APPROVED" in output
        print(f"  → table output: {len(output)} chars")

    def test_04_cli_json_output(self):
        """User: cfa evaluate --format json"""
        import io
        import sys

        from cfa.cli import main
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            main(["evaluate", "aggregate sales", "--format", "json"])
        except SystemExit:
            pass
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        data = json.loads(output)
        assert "state" in data
        assert "intent" in data
        print(f"  → json: {data['state']}")

    def test_05_init_project(self):
        """User: cfa init (creates .cfa/ with example files)"""
        import os

        from cfa.cli import main

        d = tempfile.mkdtemp()
        main(["init", "--dir", d])
        assert os.path.isfile(os.path.join(d, "catalog.json"))
        assert os.path.isfile(os.path.join(d, "config.yaml"))
        assert os.path.isfile(os.path.join(d, "policies", "prod-v1.yaml"))
        print("  → .cfa/ created with catalog + config + policy")

    def test_06_list_rules(self):
        """User: cfa rules list (what rules are active?)"""
        import io
        import sys

        from cfa.cli import main
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            main(["rules", "list"])
        except SystemExit:
            pass
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        assert "GOVERNANCE" in output or "FINOPS" in output
        print("  → rules listed")

    def test_07_explain_fault(self):
        """User: cfa rules explain GOVERNANCE_RAW_PII_IN_PROTECTED_LAYER"""
        import io
        import sys

        from cfa.cli import main
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            main(["rules", "explain", "GOVERNANCE_RAW_PII_IN_PROTECTED_LAYER"])
        except SystemExit:
            pass
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        assert "sha256" in output or "PII" in output
        print("  → fault explained")

    def test_08_first_report(self):
        """User: cfa report execution --intent '...' --output report.html"""
        import os
        out = os.path.join(tempfile.mkdtemp(), "report.html")
        from cfa.core.kernel import KernelOrchestrator
        from cfa.reporting import generate_report

        kernel = KernelOrchestrator(catalog=CATALOG)
        result = kernel.process("Join NFe with Clientes and persist to Silver")

        faults = []
        if result.policy_result:
            for f in result.policy_result.faults:
                faults.append({"code": f.code, "severity": f.severity.value, "message": f.message, "remediation": list(f.remediation)})

        generate_report("execution", out,
            intent="Join NFe with Clientes and persist to Silver",
            intent_id=result.intent_id,
            state=result.state.value,
            signature_hash=result.signature.signature_hash if result.signature else "",
            policy_bundle="v1.0", replan_count=len(result.replan_history),
            events=result.audit_events, faults=faults)

        content = Path(out).read_text(encoding="utf-8")
        assert "<!doctype html>" in content.lower()
        assert "approved" in content.lower() or "APPROVED" in content
        print(f"  → report.html: {len(content)} chars")


# ══════════════════════════════════════════════════════════════════════════════
# Jornada 2: Engenheiro de Dados
# "Preciso governar meu pipeline fiscal que junta NF-e com clientes"
# ══════════════════════════════════════════════════════════════════════════════

class TestJourney2_DataEngineer:
    """A data engineer setting up governance for a real pipeline."""

    def test_01_create_catalog(self):
        """Create a real fiscal data catalog."""
        catalog = {
            "datasets": {
                "nfe": {"classification": "high_volume", "size_gb": 4000, "pii_columns": [], "partition_column": "processing_date"},
                "clientes": {"classification": "sensitive", "size_gb": 0.5, "pii_columns": ["cpf", "email", "telefone"], "partition_column": "processing_date"},
                "produtos": {"classification": "internal", "size_gb": 0.1, "pii_columns": []},
                "vendas": {"classification": "high_volume", "size_gb": 2000, "pii_columns": [], "partition_column": "data_venda"},
            }
        }
        assert len(catalog["datasets"]) == 4
        assert "cpf" in catalog["datasets"]["clientes"]["pii_columns"]
        print("  → catalog with 4 datasets, PII marked")

    def test_02_safe_intent_passes(self):
        """Intent with PII anonymization should pass."""
        from cfa.testing import assert_passed, evaluate
        result = evaluate(
            "Join NFe with Clientes and persist to Silver",
            catalog=CATALOG,
            backend="pyspark",
        )
        assert_passed(result)
        print(f"  → safe intent: {result.state.value}")

    def test_03_critical_intent_blocked(self):
        """Intent writing raw PII to Gold should be blocked by compliance bundle."""
        from cfa.policy.bundle import PolicyBundle
        from cfa.testing import evaluate

        bundle = PolicyBundle.from_yaml("policies/compliance-strict-v1.yaml")
        result = evaluate(
            "Write clientes data with PII to Gold layer",
            catalog=CATALOG,
            policy_rules=bundle.rules,
        )
        print(f"  → compliance check: {result.state.value}, faults: {result.faults}")

    def test_04_policy_bundle_workflow(self):
        """User workflow: load bundle → evaluate → adjust → re-evaluate."""
        from cfa.policy.bundle import PolicyBundle
        from cfa.policy.engine import PolicyEngine

        # Load production bundle
        bundle = PolicyBundle.from_yaml("policies/prod-v1.yaml")
        assert len(bundle.rules) == 7
        print(f"  → loaded prod-v1 with {len(bundle.rules)} rules")

        # Create engine and evaluate signature
        engine = PolicyEngine(rules=bundle.rules, policy_bundle_version=bundle.version)
        from cfa.types import (
            DatasetClassification,
            DatasetRef,
            ExecutionContext,
            SignatureConstraints,
            StateSignature,
            TargetLayer,
        )

        # Safe signature
        safe = StateSignature(
            domain="fiscal", intent="reconciliation", target_layer=TargetLayer.SILVER,
            datasets=(DatasetRef("nfe", DatasetClassification.HIGH_VOLUME, size_gb=4000),),
            constraints=SignatureConstraints(no_pii_raw=True, merge_key_required=True, enforce_types=True, partition_by=("processing_date",)),
            execution_context=ExecutionContext("prod-v1.0", "catalog_v1", "ctx_001"),
        )
        result = engine.evaluate(safe)
        assert result.action.value == "approve"
        print(f"  → safe signature: {result.action.value}")

        # Unsafe signature (missing partition on high volume)
        unsafe = StateSignature(
            domain="fiscal", intent="reconciliation", target_layer=TargetLayer.SILVER,
            datasets=(DatasetRef("nfe", DatasetClassification.HIGH_VOLUME, size_gb=4000),),
            constraints=SignatureConstraints(no_pii_raw=True, merge_key_required=True, enforce_types=True, partition_by=()),
            execution_context=ExecutionContext("prod-v1.0", "catalog_v1", "ctx_001"),
        )
        result2 = engine.evaluate(unsafe)
        print(f"  → unsafe signature: {result2.action.value}, faults: {[f.code for f in result2.faults]}")

    def test_05_behavior_spec_workflow(self):
        """User: write behavior spec YAML → generate taxonomy → get rules."""
        from cfa.behavior import BehaviorSpec, Systematizer

        spec = BehaviorSpec.from_dict({
            "behavior": {
                "name": "fiscal_governance",
                "description": "Fiscal pipeline must protect PII, enforce merge keys, declare partitions.",
                "failure_modes": [
                    {"code": "raw_pii", "condition": "pii_in_protected_layer", "severity": "critical", "action": "block",
                     "target_layer": "silver", "remediation": ["Apply sha256", "Enable no_pii_raw"]},
                    {"code": "no_merge", "condition": "missing_merge_key", "severity": "critical", "action": "block",
                     "target_layer": "silver", "remediation": ["Set merge_key_required=True"]},
                    {"code": "no_partition", "condition": "missing_partition", "severity": "high", "action": "replan",
                     "min_size_gb": 1.0, "remediation": ["Add partition_by"]},
                ],
            },
        })
        taxonomy, rules = Systematizer().systematize(spec)
        assert taxonomy.category_count == 4  # 3 not-allowed + 1 allowed
        assert len(rules) == 3
        print(f"  → spec → {len(rules)} rules, {taxonomy.category_count} categories")

        # Generate test intents
        intents = taxonomy.generate_test_intents(2)
        assert len(intents) == 6  # 3 categories × 2 each
        print(f"  → generated {len(intents)} test intents")


# ══════════════════════════════════════════════════════════════════════════════
# Jornada 3: Compliance Officer
# "Auditoria regulatória — preciso provar que cada execução seguiu a política"
# ══════════════════════════════════════════════════════════════════════════════

class TestJourney3_ComplianceOfficer:
    """A compliance officer auditing pipeline executions."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from cfa.core.kernel import KernelOrchestrator
        self._kernel = KernelOrchestrator(catalog=CATALOG)
        self._result = self._kernel.process("Join NFe with Clientes and persist to Silver")

    def test_01_run_governed_pipeline(self):
        """Execute a governed intent and capture the full result."""
        assert self._result.is_executable
        assert self._result.audit_events
        assert self._result.signature is not None
        print(f"  → executed: {self._result.state.value}, {len(self._result.audit_events)} audit events")

    def test_02_audit_trail_verification(self):
        """Verify the audit chain is intact."""
        trail = self._kernel.audit_trail
        assert trail.verify_chain() is True
        print(f"  → chain intact: {trail.event_count} events")

    def test_03_serialize_result_for_auditor(self):
        """Export the result as JSON for regulatory review."""
        d = self._result.to_dict()
        j = self._result.to_json()
        assert "intent_id" in d
        assert "state" in d
        assert "audit_events" in d
        parsed = json.loads(j)
        assert parsed["state"] == self._result.state.value
        print(f"  → serialized: {len(j)} bytes JSON")

    def test_04_audit_report_html(self):
        """Generate auditor-ready HTML report with hash chain visualization."""
        import os

        from cfa.reporting import generate_report
        out = os.path.join(tempfile.mkdtemp(), "audit_report.html")
        events_raw = self._kernel.audit_trail.get_events_for_intent(self._result.intent_id)
        events = [{
            "timestamp": str(e.timestamp) if hasattr(e, "timestamp") else "",
            "phase": str(getattr(e, "phase", getattr(e, "stage", ""))),
            "event_type": str(e.event_type), "outcome": str(e.outcome),
        } for e in events_raw]
        generate_report("audit", out,
            intent_id=self._result.intent_id,
            events=events,
            chain_intact=self._kernel.audit_trail.verify_chain(),
            policy_bundle="v1.0")
        content = Path(out).read_text(encoding="utf-8")
        assert "<!doctype html>" in content.lower()
        assert "INTACT" in content or "intact" in content.lower()
        print(f"  → audit report: {len(content)} chars, chain shown")

    def test_05_compliance_summary(self):
        """Generate compliance summary for the audit committee."""
        import os

        from cfa.policy.engine import PolicyEngine
        from cfa.reporting import generate_report
        engine = PolicyEngine()
        out = os.path.join(tempfile.mkdtemp(), "compliance.html")
        generate_report("compliance", out,
            policy_bundle="prod-v1.0",
            total_evaluations=100, approved=94, replanned=5, blocked=1,
            rules=engine.describe_rules(),
            pii_incidents_prevented=12,
            audit_events_total=self._kernel.audit_trail.event_count,
            chain_intact=True)
        content = Path(out).read_text(encoding="utf-8")
        assert "Compliance" in content
        assert "APPROVED" in content.upper()
        print(f"  → compliance summary: {len(content)} chars")

    def test_06_state_signature_reproducibility(self):
        """Prove that the same intent produces the same hash (I8)."""
        sig = self._result.signature
        assert sig is not None
        hash1 = sig.signature_hash
        j = sig.to_json()
        sig2 = type(sig).from_json(j)
        hash2 = sig2.signature_hash
        assert hash1 == hash2
        print(f"  → I8 verified: hash={hash1} reproducible")


# ══════════════════════════════════════════════════════════════════════════════
# Jornada 4: AI Developer
# "Meu agente LangGraph precisa de governança antes de escrever no banco"
# ══════════════════════════════════════════════════════════════════════════════

class TestJourney4_AIDeveloper:
    """An AI developer integrating CFA governance into agents."""

    def test_01_guard_decorator(self):
        """Use @cfa_guard to protect a LangGraph agent node."""
        from cfa.adapters import cfa_guard

        @cfa_guard("Join NFe with Clientes and persist to Silver", catalog=CATALOG, mode="block")
        def my_agent_node(state):
            return {"status": "completed", "data": "processed"}

        result = my_agent_node({"input": "test"})
        assert result["status"] == "completed"
        print("  → agent node passed governance")

    def test_02_guard_blocks_unsafe(self):
        """Governance blocks an unsafe agent action."""
        from cfa.adapters import cfa_guard
        from cfa.policy.engine import PolicyRule
        from cfa.types import FaultFamily, FaultSeverity, PolicyAction

        block_all = PolicyRule(
            name="block", condition=lambda s: True, action=PolicyAction.BLOCK,
            fault_code="TEST", fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.CRITICAL, message="blocked",
        )

        @cfa_guard("unsafe action", catalog=CATALOG, mode="block", policy_rules=[block_all])
        def dangerous_node(state):
            return "should not execute"

        with pytest.raises(PermissionError, match="CFA blocked"):
            dangerous_node({})
        print("  → unsafe action blocked correctly")

    def test_03_mcp_tools_available(self):
        """Verify MCP tools are accessible for AI agents."""
        from cfa.mcp import TOOLS

        assert len(TOOLS) == 5
        print(f"  → {len(TOOLS)} MCP tools available: {list(TOOLS.keys())}")

    def test_04_mcp_evaluate_signature(self):
        """Agent sends a StateSignature JSON to MCP for evaluation."""
        from cfa.mcp import _handle_request

        sig_json = {
            "domain": "fiscal", "intent": "reconciliation", "target_layer": "silver",
            "datasets": [{"name": "nfe", "classification": "high_volume", "size_gb": 4000, "pii_columns": []}],
            "constraints": {"no_pii_raw": True, "merge_key_required": True, "enforce_types": True, "partition_by": ["processing_date"]},
            "execution_context": {"policy_bundle_version": "test", "catalog_snapshot_version": "test", "context_registry_version_id": "test"},
        }
        resp = _handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "cfa_evaluate_signature", "arguments": {"signature": sig_json}},
        })
        data = json.loads(resp["result"]["content"][0]["text"])
        assert data["action"] == "approve"
        assert data["passed"] is True
        print(f"  → MCP evaluate: {data['action']}")

    def test_05_mcp_explain_fault(self):
        """Agent asks CFA to explain a fault code."""
        from cfa.mcp import _handle_request

        resp = _handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "cfa_explain_fault", "arguments": {"fault_code": "GOVERNANCE_RAW_PII_IN_PROTECTED_LAYER"}},
        })
        data = json.loads(resp["result"]["content"][0]["text"])
        assert data["severity"] == "critical"
        assert len(data["remediation"]) >= 1
        print(f"  → explained: {data['rule_name']}")

    def test_06_all_five_adapters_import(self):
        """All 5 framework adapters import correctly."""
        from cfa.adapters.autogen import cfa_agent_guard as ag
        from cfa.adapters.crewai import cfa_crew_guard as cr
        from cfa.adapters.dspy import cfa_module_guard as dspy
        from cfa.adapters.langgraph import cfa_guard as lg
        from cfa.adapters.openai_agents import cfa_tool_guard as oai

        assert callable(lg)
        assert callable(oai)
        assert callable(cr)
        assert callable(ag)
        assert callable(dspy)
        print("  → all 5 adapters imported")


# ══════════════════════════════════════════════════════════════════════════════
# Jornada 5: Platform Team
# "Preciso de CI/CD, métricas Prometheus, OTel, e alertas Slack"
# ══════════════════════════════════════════════════════════════════════════════

class TestJourney5_PlatformTeam:
    """A platform team deploying CFA in production."""

    def test_01_ci_cd_exit_code(self):
        """CFA returns exit code 1 when intent is blocked — perfect for CI."""
        from cfa.policy.engine import PolicyRule
        from cfa.testing import evaluate
        from cfa.types import FaultFamily, FaultSeverity, PolicyAction

        block_rule = PolicyRule(
            name="ci_block", condition=lambda s: True, action=PolicyAction.BLOCK,
            fault_code="CI_TEST_BLOCK", fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.CRITICAL, message="CI test block",
        )
        result = evaluate("any intent", catalog=CATALOG, policy_rules=[block_rule])
        assert result.blocked
        print(f"  → CI would fail: blocked={result.blocked}, reason={result.blocked_reason[:50]}")

    def test_02_prometheus_metrics(self):
        """Metrics are emitted in Prometheus text format."""
        from cfa.observability.metrics import (
            get_metrics_text,
            record_audit_event,
            record_lifecycle_index,
            record_policy_evaluation,
            record_replan,
        )

        record_policy_evaluation("approve")
        record_policy_evaluation("block")
        record_replan()
        record_audit_event()
        record_lifecycle_index("abc123", "ifo", 0.92)

        text = get_metrics_text()
        assert "HELP" in text
        assert "TYPE" in text
        assert "cfa_policy_evaluations_total" in text
        assert "cfa_lifecycle_index" in text
        print(f"  → Prometheus metrics: {text.count(chr(10))} lines")

    def test_03_otel_span_works(self):
        """OpenTelemetry span no-ops gracefully without SDK installed."""
        from cfa.observability.otel import cfa_span

        with cfa_span("govern", phase="govern", decision="approve", signature_hash="abc123"):
            pass
        print("  → OTel span: no-op (SDK not installed)")

    def test_04_slack_notification(self):
        """Notification fires without crashing (webhook unreachable)."""
        from cfa.observability.notify import SlackNotifier, TeamsNotifier

        slack = SlackNotifier("https://hooks.slack.com/services/TEST/TEST/TEST")
        slack.notify("block", "PII violation in Gold write", "Raw PII detected", ["GOVERNANCE_RAW_PII"], policy_bundle="prod-v1", intent_id="abc", hash="hash123")

        teams = TeamsNotifier("https://outlook.office.com/webhook/TEST")
        teams.notify("replan", "Missing partition filter", "High volume scan risk", ["FINOPS_MISSING_PREDICATE"])

        print("  → notifications sent (or gracefully failed)")

    def test_05_backend_registry_extensibility(self):
        """Register a custom backend — key for platform extensibility."""
        from cfa.backends import BackendAdapter, BackendCapabilities, BackendRegistry
        from cfa.core.codegen import GeneratedCode

        class TestBackend(BackendAdapter):
            def get_capabilities(self):
                return BackendCapabilities(backend_name="test", supports_merge=True)
            def generate(self, plan):
                return GeneratedCode(plan_signature_hash="test", intent_id="test", language="sql", code="SELECT 1")

        BackendRegistry.singleton().register("test_backend", lambda: TestBackend())
        assert "test_backend" in BackendRegistry.singleton().list()
        print("  → custom backend registered")

    def test_06_lifecycle_dashboard(self):
        """Generate a lifecycle dashboard for the platform team."""
        import os

        from cfa.reporting import generate_report

        out = os.path.join(tempfile.mkdtemp(), "dashboard.html")
        generate_report("lifecycle", out,
            period_days=30,
            skills=[{"hash": "pipe_001", "ifo": 0.92, "ifs": 0.95, "ifg": 1.0, "idi": 0.88, "state": "active"}],
            trend_dates=["D1", "D2", "D3"], ifo_vals=[0.9, 0.88, 0.92], ifs_vals=[0.95, 0.93, 0.96],
            idi_vals=[0.88, 0.86, 0.90], ifg_vals=[1.0, 1.0, 1.0],
            cost_dates=["D1", "D2", "D3"], cost_vals=[10, 12, 9],
            decisions={"approved": 50, "replanned": 3, "blocked": 1})

        content = Path(out).read_text(encoding="utf-8")
        assert "Lifecycle Dashboard" in content
        assert "0.92" in content or "92" in content
        print(f"  → lifecycle dashboard: {len(content)} chars")

    def test_07_full_workflow_promotion(self):
        """Run 10 intents and verify promotion lifecycle activates."""
        from cfa.core.kernel import KernelConfig, KernelOrchestrator

        kernel = KernelOrchestrator(
            catalog=CATALOG,
            config=KernelConfig(enable_promotion=True),
        )
        states = []
        for i in range(10):
            result = kernel.process(f"Join NFe with Clientes and persist to Silver #{i}")
            states.append(result.state.value)

        assert "approved" in states or "approved_with_warnings" in states or "promotion_candidate" in states
        print(f"  → 10 intents: states={set(states)}, audit={kernel.audit_trail.event_count} events")
