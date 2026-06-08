"""Tests for cfa.mcp — MCP server JSON-RPC logic."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SRC = str(Path(__file__).resolve().parents[1] / "src")
sys.path.insert(0, SRC)


def _call(method: str, params: dict | None = None, req_id: int = 1) -> dict:
    """Simulate a JSON-RPC call to the MCP server."""
    from cfa.mcp import _handle_request
    req = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}
    return _handle_request(req) or {}


class TestMCPServerLogic:
    def test_initialize(self):
        resp = _call("initialize")
        assert resp["result"]["serverInfo"]["name"] == "cfa-mcp"
        assert resp["result"]["protocolVersion"] == "2024-11-05"
        assert "tools" in resp["result"]["capabilities"]

    def test_ping(self):
        resp = _call("ping")
        assert resp["result"] == {}

    def test_unknown_method(self):
        resp = _call("nonexistent")
        assert "error" in resp
        assert resp["error"]["code"] == -32601

    def test_notification_no_response(self):
        resp = _call("notifications/initialized")
        assert resp == {}


class TestTools:
    def test_lists_all_tools(self):
        resp = _call("tools/list")
        tools = resp["result"]["tools"]
        names = {t["name"] for t in tools}
        assert names == {
            "cfa_evaluate_signature", "cfa_describe_rules",
            "cfa_explain_fault", "cfa_audit_check", "cfa_list_backends",
            "cfa_lifecycle_status", "cfa_compliance_check",
        }

    def test_each_tool_has_schema(self):
        resp = _call("tools/list")
        for tool in resp["result"]["tools"]:
            assert "description" in tool
            assert "inputSchema" in tool


class TestDescribeRules:
    def test_returns_rules(self):
        resp = _call("tools/call", {"name": "cfa_describe_rules", "arguments": {}})
        data = json.loads(resp["result"]["content"][0]["text"])
        assert data["rule_count"] >= 1
        assert len(data["rules"]) >= 1

    def test_with_policy_bundle_file(self):
        bundle = str(Path(__file__).resolve().parents[1] / "policies" / "prod-v1.yaml")
        resp = _call("tools/call", {"name": "cfa_describe_rules", "arguments": {"policy_bundle": bundle}})
        data = json.loads(resp["result"]["content"][0]["text"])
        assert data["policy_bundle_version"] == "prod-v1.0"


class TestExplainFault:
    def test_known_fault(self):
        resp = _call("tools/call", {"name": "cfa_explain_fault", "arguments": {"fault_code": "GOVERNANCE_RAW_PII_IN_PROTECTED_LAYER"}})
        data = json.loads(resp["result"]["content"][0]["text"])
        assert data["severity"] == "critical"
        assert len(data["remediation"]) >= 1

    def test_unknown_fault(self):
        resp = _call("tools/call", {"name": "cfa_explain_fault", "arguments": {"fault_code": "NOPE"}})
        data = json.loads(resp["result"]["content"][0]["text"])
        assert "error" in data


class TestEvaluateSignature:
    def test_missing_signature(self):
        resp = _call("tools/call", {"name": "cfa_evaluate_signature", "arguments": {}})
        data = json.loads(resp["result"]["content"][0]["text"])
        assert "error" in data

    def test_valid_clean_signature(self):
        resp = _call("tools/call", {"name": "cfa_evaluate_signature", "arguments": {"signature": {
            "domain": "fiscal", "intent": "test", "target_layer": "silver",
            "datasets": [{"name": "nfe", "classification": "high_volume", "size_gb": 4000, "pii_columns": []}],
            "constraints": {"no_pii_raw": True, "merge_key_required": True, "enforce_types": True, "partition_by": ["processing_date"]},
            "execution_context": {"policy_bundle_version": "test", "catalog_snapshot_version": "test", "context_registry_version_id": "test"},
        }}})
        data = json.loads(resp["result"]["content"][0]["text"])
        assert data["action"] == "approve"
        assert data["passed"] is True

    def test_invalid_signature(self):
        resp = _call("tools/call", {"name": "cfa_evaluate_signature", "arguments": {"signature": "not_a_dict"}})
        data = json.loads(resp["result"]["content"][0]["text"])
        assert "error" in data


class TestAuditCheck:
    def test_returns_chain_status(self):
        resp = _call("tools/call", {"name": "cfa_audit_check", "arguments": {}})
        data = json.loads(resp["result"]["content"][0]["text"])
        assert "chain_intact" in data


class TestListBackends:
    def test_lists_backends(self):
        resp = _call("tools/call", {"name": "cfa_list_backends", "arguments": {}})
        data = json.loads(resp["result"]["content"][0]["text"])
        assert len(data["backends"]) >= 3
        names = [b["name"] for b in data["backends"]]
        assert "pyspark" in names
        assert "sql" in names
        assert "dbt" in names


class TestErrorHandling:
    def test_missing_tool_name(self):
        resp = _call("tools/call", {"arguments": {}})
        assert "error" in resp

    def test_unknown_tool(self):
        resp = _call("tools/call", {"name": "nonexistent_tool", "arguments": {}})
        assert "error" in resp
