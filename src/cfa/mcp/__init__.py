"""
CFA MCP Server
==============
Model Context Protocol server exposing CFA governance tools to AI agents.

Tools exposed:
- cfa_evaluate_signature  — Evaluate a StateSignature against policy
- cfa_describe_rules      — List all active policy rules
- cfa_explain_fault       — Explain a fault code with remediation
- cfa_audit_check         — Verify audit chain integrity
- cfa_list_backends       — List registered codegen backends

Zero external dependencies — pure stdlib JSON-RPC over stdio.
Compatible with Claude Desktop, Cursor, Windsurf, Copilot, and any MCP client.

Usage:
    python -m cfa.mcp          # run as stdio server
    cfa-mcp                    # via console script (pip install)

Config (claude_desktop_config.json):
    {
      "mcpServers": {
        "cfa": {
          "command": "python", "args": ["-m", "cfa.mcp"]
        }
      }
    }
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

from cfa.policy.bundle import PolicyBundle
from cfa.policy.engine import PolicyEngine
from cfa.types import StateSignature

from ..backends import BackendRegistry

SERVER_NAME = "cfa-mcp"
SERVER_VERSION = "1.0.0"

# ── Auth ─────────────────────────────────────────────────────────────────────

_API_KEY = os.environ.get("CFA_MCP_API_KEY", "")

# ── Rate limiting (token bucket) ──────────────────────────────────────────────

_MAX_REQUESTS = int(os.environ.get("CFA_MCP_RATE_LIMIT", "60"))
_RATE_WINDOW = 60
_request_counts: dict[str, list[float]] = {}

def _check_rate_limit(tool_name: str) -> bool:
    now = time.time()
    window = _request_counts.setdefault(tool_name, [])
    window[:] = [t for t in window if now - t < _RATE_WINDOW]
    if len(window) >= _MAX_REQUESTS:
        return False
    window.append(now)
    return True

# ── Tool implementations ─────────────────────────────────────────────────────


def tool_evaluate_signature(args: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a StateSignature JSON against the active policy bundle."""
    sig_data = args.get("signature")
    if not sig_data:
        return {"error": "Missing required argument: signature"}

    try:
        from cfa.types import (
            DatasetClassification,
            DatasetRef,
            ExecutionContext,
            SignatureConstraints,
            TargetLayer,
        )
        layer_map = {"bronze": TargetLayer.BRONZE, "silver": TargetLayer.SILVER, "gold": TargetLayer.GOLD}
        cls_map = {
            "public": DatasetClassification.PUBLIC, "internal": DatasetClassification.INTERNAL,
            "sensitive": DatasetClassification.SENSITIVE, "high_volume": DatasetClassification.HIGH_VOLUME,
        }

        datasets = tuple(
            DatasetRef(
                name=d["name"],
                classification=cls_map.get(d.get("classification", "internal"), DatasetClassification.INTERNAL),
                size_gb=d.get("size_gb", 0.0),
                pii_columns=tuple(d.get("pii_columns", [])),
                partition_column=d.get("partition_column"),
            )
            for d in sig_data.get("datasets", [])
        )

        c = sig_data.get("constraints", {})
        constraints = SignatureConstraints(
            no_pii_raw=c.get("no_pii_raw", True),
            merge_key_required=c.get("merge_key_required", True),
            enforce_types=c.get("enforce_types", True),
            partition_by=tuple(c.get("partition_by", [])),
            max_cost_dbu=c.get("max_cost_dbu"),
        )

        ctx = sig_data.get("execution_context", {})
        execution_context = ExecutionContext(
            policy_bundle_version=ctx.get("policy_bundle_version", "mcp"),
            catalog_snapshot_version=ctx.get("catalog_snapshot_version", "mcp"),
            context_registry_version_id=ctx.get("context_registry_version_id", "mcp"),
        )

        signature = StateSignature(
            domain=sig_data.get("domain", ""),
            intent=sig_data.get("intent", ""),
            target_layer=layer_map.get(sig_data.get("target_layer", "silver"), TargetLayer.SILVER),
            datasets=datasets,
            constraints=constraints,
            execution_context=execution_context,
        )
    except Exception as e:
        return {"error": f"Invalid signature: {e}"}

    policy_bundle = args.get("policy_bundle", "")
    if policy_bundle:
        try:
            bundle = PolicyBundle.from_yaml(policy_bundle) if policy_bundle.endswith((".yaml", ".yml")) else PolicyBundle.from_json(policy_bundle)
            engine = PolicyEngine(rules=bundle.rules, policy_bundle_version=bundle.version)
        except Exception as e:
            return {"error": f"Failed to load policy bundle: {e}"}
    else:
        engine = PolicyEngine()

    result = engine.evaluate(signature)

    return {
        "action": result.action.value,
        "passed": result.action.value == "approve",
        "faults": [
            {
                "code": f.code,
                "severity": f.severity.value,
                "message": f.message,
                "remediation": list(f.remediation),
            }
            for f in result.faults
        ],
        "reasoning": result.reasoning,
        "replan_count": result.replan_count,
    }


def tool_describe_rules(args: dict[str, Any]) -> dict[str, Any]:
    """List all active policy rules."""
    policy_bundle = args.get("policy_bundle", "")
    if policy_bundle:
        try:
            bundle = PolicyBundle.from_yaml(policy_bundle) if policy_bundle.endswith((".yaml", ".yml")) else PolicyBundle.from_json(policy_bundle)
            engine = PolicyEngine(rules=bundle.rules, policy_bundle_version=bundle.version)
        except Exception as e:
            return {"error": f"Failed to load policy bundle: {e}"}
    else:
        engine = PolicyEngine()

    return {
        "policy_bundle_version": engine.policy_bundle_version,
        "rule_count": len(engine.rules),
        "rules": engine.describe_rules(),
    }


def tool_explain_fault(args: dict[str, Any]) -> dict[str, Any]:
    """Explain a fault code with details and remediation steps."""
    code = args.get("fault_code", "")
    if not code:
        return {"error": "Missing required argument: fault_code"}

    engine = PolicyEngine()
    for r in engine.rules:
        if r.fault_code == code:
            return {
                "fault_code": r.fault_code,
                "rule_name": r.name,
                "action": r.action.value,
                "severity": r.severity.value,
                "family": r.fault_family.value,
                "message": r.message,
                "remediation": list(r.remediation),
            }
    return {"error": f"Unknown fault code: {code}"}


def tool_audit_check(args: dict[str, Any]) -> dict[str, Any]:
    """Verify audit chain integrity."""
    from cfa.audit.trail import AuditTrail
    trail = AuditTrail()
    intent_id = args.get("intent_id", "")
    if intent_id:
        events = trail.get_events_for_intent(intent_id)
        chain_ok = trail.verify_chain()
        return {
            "intent_id": intent_id,
            "event_count": len(events),
            "chain_intact": chain_ok,
        }
    chain_ok = trail.verify_chain()
    return {
        "total_events": trail.event_count,
        "chain_intact": chain_ok,
    }


def tool_list_backends(args: dict[str, Any]) -> dict[str, Any]:
    """List registered codegen backends with capabilities."""
    registry = BackendRegistry.singleton()
    names = registry.list()
    backends: list[dict[str, Any]] = []
    for name in names:
        factory = registry.get(name)
        backend = factory()
        caps = backend.get_capabilities() if hasattr(backend, "get_capabilities") else None
        backends.append({
            "name": name,
            "supports_merge": caps.supports_merge if caps else False,
            "supports_anonymization": caps.supports_anonymization if caps else False,
            "supports_partition_overwrite": caps.supports_partition_overwrite if caps else False,
            "cost_model_available": caps.cost_model_available if caps else False,
            "supported_languages": caps.supported_languages if caps else [],
        })
    return {"backends": backends}


def tool_lifecycle_status(args: dict[str, Any]) -> dict[str, Any]:
    """Query lifecycle indices (IFo/IFs/IFg/IDI) for pipelines."""
    db_path = args.get("db_path", "")
    pipeline = args.get("pipeline", "")

    try:
        from cfa.storage import SqliteStorage
        store = SqliteStorage(db_path) if db_path else SqliteStorage()
    except Exception:
        return {"error": "Could not open storage. Provide db_path or ensure default exists."}

    try:
        rows = store._conn.execute(
            "SELECT * FROM skill_records WHERE name = ? ORDER BY computed_at DESC LIMIT 10",
            (pipeline,) if pipeline else ("%",),
        ).fetchall()
    except Exception:
        return {"skills": [], "note": f"No lifecycle data available{f' for {pipeline}' if pipeline else ''}"}

    skills = []
    for r in rows:
        skills.append({
            "name": r[1], "state": r[2],
            "ifo": r[3], "ifs": r[4], "ifg": r[5], "idi": r[6],
            "execution_count": r[7], "computed_at": r[16] if len(r) > 16 else "",
        })
    return {"skills": skills}


def tool_compliance_check(args: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a pipeline intent against a named compliance bundle (EU AI Act, LGPD, etc.)."""
    intent = args.get("intent", "")
    bundle_name = args.get("bundle", "prod-v1")

    from cfa.core.kernel import KernelConfig, KernelOrchestrator

    catalog = args.get("catalog", {})
    kernel = KernelOrchestrator(
        catalog=catalog,
        config=KernelConfig(policy_bundle_version=bundle_name),
    )
    result = kernel.process(intent)

    return {
        "intent": intent,
        "bundle": bundle_name,
        "decision": result.state.value.upper(),
        "faults": [{"code": f.code, "severity": f.severity.value, "message": f.message} for f in result.policy_result.faults] if result.policy_result else [],
        "blocked_reason": result.blocked_reason,
        "signature_hash": result.signature.signature_hash if result.signature else "",
    }


# ── Tool registry ────────────────────────────────────────────────────────────

TOOLS = {
    "cfa_evaluate_signature": {
        "description": "Evaluate a StateSignature JSON against the active CFA policy bundle. Returns APPROVE, REPLAN, or BLOCK with faults and remediation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "signature": {"type": "object", "description": "StateSignature JSON with domain, intent, target_layer, datasets, constraints"},
                "policy_bundle": {"type": "string", "description": "Optional path to YAML/JSON policy bundle file"},
            },
            "required": ["signature"],
        },
        "handler": tool_evaluate_signature,
    },
    "cfa_describe_rules": {
        "description": "List all active CFA policy rules with descriptions and severities.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "policy_bundle": {"type": "string", "description": "Optional path to YAML/JSON policy bundle file"},
            },
        },
        "handler": tool_describe_rules,
    },
    "cfa_explain_fault": {
        "description": "Explain a CFA fault code: what it means, why it occurs, and how to fix it.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "fault_code": {"type": "string", "description": "Fault code to explain, e.g. GOVERNANCE_RAW_PII_IN_PROTECTED_LAYER"},
            },
            "required": ["fault_code"],
        },
        "handler": tool_explain_fault,
    },
    "cfa_audit_check": {
        "description": "Verify the integrity of the CFA audit trail hash chain.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "intent_id": {"type": "string", "description": "Optional: check audit trail for a specific intent ID"},
            },
        },
        "handler": tool_audit_check,
    },
    "cfa_list_backends": {
        "description": "List all registered CFA codegen backends with their capabilities.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
        "handler": tool_list_backends,
    },
    "cfa_lifecycle_status": {
        "description": "Query lifecycle indices (IFo/IFs/IFg/IDI) for governed pipelines from CFA storage.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "db_path": {"type": "string", "description": "Path to CFA SQLite database"},
                "pipeline": {"type": "string", "description": "Optional: filter by pipeline name"},
            },
        },
        "handler": tool_lifecycle_status,
    },
    "cfa_compliance_check": {
        "description": "Evaluate a pipeline intent against a compliance bundle (e.g., eu-ai-act-v1, lgpd-v1). Returns decision, faults, and block reason.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "intent": {"type": "string", "description": "Natural-language pipeline intent to evaluate"},
                "bundle": {"type": "string", "description": "Compliance bundle name (default: prod-v1)"},
                "catalog": {"type": "object", "description": "Optional: data catalog dict"},
            },
            "required": ["intent"],
        },
        "handler": tool_compliance_check,
    },
}


# ── JSON-RPC Server ──────────────────────────────────────────────────────────


def _rpc_error(id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}


def _rpc_response(id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id, "result": result}


def _handle_request(req: dict[str, Any]) -> dict[str, Any] | None:
    method = req.get("method", "")
    req_id = req.get("id")

    # Auth check (skip for initialize + ping)
    if _API_KEY and method not in ("initialize", "ping"):
        key = req.get("params", {}).get("_meta", {}).get("api_key", "")
        if key != _API_KEY:
            return _rpc_error(req_id, -32001, "Unauthorized: set CFA_MCP_API_KEY")

    if method == "initialize":
        return _rpc_response(req_id, {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "capabilities": {"tools": {}},
        })

    if method == "notifications/initialized":
        return None  # No response for notifications

    if method == "tools/list":
        tools_list = [
            {
                "name": name,
                "description": info["description"],
                "inputSchema": info["inputSchema"],
            }
            for name, info in TOOLS.items()
        ]
        return _rpc_response(req_id, {"tools": tools_list})

    if method == "tools/call":
        tool_name = req.get("params", {}).get("name", "")
        tool_args = req.get("params", {}).get("arguments", {})

        if not _check_rate_limit(tool_name):
            return _rpc_error(req_id, -32002, f"Rate limit exceeded: {_MAX_REQUESTS}/{_RATE_WINDOW}s per tool")

        tool = TOOLS.get(tool_name)
        if not tool:
            return _rpc_error(req_id, -32601, f"Unknown tool: {tool_name}")

        try:
            result = tool["handler"](tool_args)
            return _rpc_response(req_id, {
                "content": [{"type": "text", "text": json.dumps(result, indent=2, default=str)}]
            })
        except Exception as e:
            return _rpc_error(req_id, -32603, f"Tool error: {e}")

    if method == "ping":
        return _rpc_response(req_id, {})

    return _rpc_error(req_id, -32601, f"Method not found: {method}")


def serve() -> None:
    """Run the MCP server on stdio (stdin/stdout JSON-RPC)."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = _handle_request(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    serve()
