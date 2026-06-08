"""cfa init — bootstrap CFA project with optional templates."""

from __future__ import annotations

import json
from pathlib import Path


TEMPLATES = {
    "fastapi": "FastAPI app with RuntimeGate guard — REST API with governance",
    "langgraph": "LangGraph agent node with @cfa_guard decorator",
    "dbt": "dbt models with CFA validation step in CI/CD",
    "mcp": "MCP server skeleton with CFA governance tools",
    "streaming-placeholder": "Structured Streaming stub — experimental, governance in v1.3",
}


def _generate_fastapi(dir_path: Path) -> None:
    (dir_path / "main.py").write_text("""\
from fastapi import FastAPI
from cfa.runtime import RuntimeGate

app = FastAPI(title="CFA-Governed API")
gate = RuntimeGate(catalog={})

@app.post("/pipeline")
@gate.guard("execute governed pipeline")
async def run_pipeline():
    return {"status": "approved", "gate_id": gate.gate_id}

@app.get("/health")
async def health():
    return {"cfa": "v1.0.0", "status": "ok"}
""", encoding="utf-8")

    (dir_path / "test_main.py").write_text("""\
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

def test_pipeline():
    resp = client.post("/pipeline")
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
""", encoding="utf-8")

    (dir_path / "requirements.txt").write_text("fastapi\nuvicorn\ncfa-kernel>=1.0.0\n", encoding="utf-8")


def _generate_langgraph(dir_path: Path) -> None:
    (dir_path / "agent.py").write_text("""\
from langgraph.graph import StateGraph
from cfa.adapters.langgraph import cfa_guard

class AgentState(dict):
    pass

@cfa_guard("join NFe with Clientes anonymize CPF and persist to Silver")
def governed_node(state: AgentState) -> AgentState:
    return {"status": "completed", "output": "governed execution ok"}

builder = StateGraph(AgentState)
builder.add_node("governed_step", governed_node)
builder.set_entry_point("governed_step")
graph = builder.compile()

if __name__ == "__main__":
    result = graph.invoke({})
    print(result)
""", encoding="utf-8")

    (dir_path / "test_agent.py").write_text("""\
from agent import governed_node

def test_governed_node():
    result = governed_node({})
    assert result["status"] == "completed"
""", encoding="utf-8")

    (dir_path / "requirements.txt").write_text("langgraph\ncfa-kernel>=1.0.0\n", encoding="utf-8")


def _generate_dbt(dir_path: Path) -> None:
    (dir_path / "models").mkdir(exist_ok=True)
    (dir_path / "models" / "fiscal_merge.sql").write_text("""\
-- dbt model: silver_fiscal_merge
-- CFA validation applies before deployment
{{ config(
    materialized='table',
    partition_by={'field': ['processing_date'], 'data_type': 'date'},
    unique_key=['nfe_id'],
) }}

WITH nfe AS (
    SELECT * FROM {{ ref('nfe_bronze') }}
),
clientes AS (
    SELECT
        sha2(cpf, 256) AS cpf_hash,
        sha2(nome, 256) AS nome_hash,
        endereco,
        cliente_id
    FROM {{ ref('clientes_bronze') }}
)
SELECT
    n.*,
    c.cpf_hash,
    c.nome_hash,
    c.endereco
FROM nfe n
LEFT JOIN clientes c ON n.cliente_id = c.cliente_id
""", encoding="utf-8")

    (dir_path / "cfa_check.py").write_text("""\
from cfa.policy.engine import PolicyEngine
from cfa.types import StateSignature, TargetLayer, DatasetRef, SignatureConstraints, ExecutionContext

sig = StateSignature(
    domain="fiscal", intent="reconciliation", target_layer=TargetLayer.SILVER,
    datasets=(
        DatasetRef(name="nfe_bronze"),
        DatasetRef(name="clientes_bronze", pii_columns=("cpf", "nome")),
    ),
    constraints=SignatureConstraints(no_pii_raw=True, merge_key_required=True, partition_by=("processing_date",)),
    execution_context=ExecutionContext(policy_bundle_version="prod-v1.0", catalog_snapshot_version="default", context_registry_version_id="ci"),
)

result = PolicyEngine().evaluate(sig)
assert result.action.value != "block", f"CFA blocked: {result.reasoning}"
print(f"CFA check passed: {result.action.value}")
""", encoding="utf-8")

    (dir_path / "requirements.txt").write_text("cfa-kernel>=1.0.0\n", encoding="utf-8")


def _generate_mcp(dir_path: Path) -> None:
    (dir_path / "server.py").write_text("""\
\"\"\"CFA MCP Server — governance tools for AI agents.\"\"\"
import json, sys
from cfa.policy.engine import PolicyEngine
from cfa.types import (
    StateSignature, TargetLayer, DatasetRef,
    SignatureConstraints, ExecutionContext,
)

TOOLS = {
    "cfa_evaluate": "Evaluate a pipeline intent against governance rules.",
    "cfa_audit": "Verify audit trail integrity.",
}

def handle(method, params, req_id):
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": req_id, "result": {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "cfa-mcp", "version": "1.0.0"},
            "capabilities": {"tools": {}},
        }}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": [
            {"name": k, "description": v} for k, v in TOOLS.items()
        ]}}
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "not found"}}

if __name__ == "__main__":
    for line in sys.stdin:
        req = json.loads(line.strip())
        resp = handle(req.get("method"), req.get("params", {}), req.get("id"))
        if resp: print(json.dumps(resp), flush=True)
""", encoding="utf-8")

    (dir_path / "requirements.txt").write_text("cfa-kernel>=1.0.0\n", encoding="utf-8")


def _generate_streaming(dir_path: Path) -> None:
    (dir_path / "README.md").write_text("""\
# CFA Streaming Governance — Placeholder

⚠️ **Experimental** — Streaming governance arrives in CFA v1.3.

Current v1.0 supports batch and micro-batch execution.
For Spark Structured Streaming governance, check back later.

Track progress: https://github.com/marquesantero/cfa/issues
""", encoding="utf-8")

    (dir_path / "stub.py").write_text("""\
# Placeholder for CFA streaming governance
# Coming in v1.3 — see README.md
print("CFA streaming governance not yet available. Track progress at github.com/marquesantero/cfa")
""", encoding="utf-8")


_TEMPLATE_GENERATORS = {
    "fastapi": _generate_fastapi,
    "langgraph": _generate_langgraph,
    "dbt": _generate_dbt,
    "mcp": _generate_mcp,
    "streaming-placeholder": _generate_streaming,
}


def _base_cfa_files(dir_path: Path) -> None:
    cfg = (dir_path / "cfa.yaml")
    if not cfg.exists():
        cfg.write_text(
            "version: \"1.0\"\n"
            "storage:\n"
            "  backend: sqlite\n"
            "  path: cfa.db\n"
            "  retention_days: 90\n"
            "defaults:\n"
            "  catalog: catalog.json\n"
            "  policy_bundle: policy.yaml\n"
            "  backend: pyspark\n",
            encoding="utf-8",
        )

    cat = (dir_path / "catalog.json")
    if not cat.exists():
        cat.write_text(json.dumps({
            "nfe_bronze": {"type": "delta", "layer": "bronze", "size_gb": 50, "classification": "high_volume", "pii": False},
            "clientes_bronze": {"type": "delta", "layer": "bronze", "size_gb": 10, "classification": "sensitive", "pii": True, "pii_columns": ["cpf", "nome"]},
        }, indent=2), encoding="utf-8")

    pol = (dir_path / "policy.yaml")
    if not pol.exists():
        pol.write_text("""\
policy_bundle:
  version: "prod-v1.0"
  description: "Production governance rules"
  rules:
    - name: forbid_raw_pii
      condition: pii_in_protected_layer
      action: block
      fault_code: GOVERNANCE_RAW_PII
      severity: critical
      family: semantic
      message: "PII in protected layer without anonymization."
      remediation:
        - "Apply sha256 on PII columns"
    - name: require_merge_key
      condition: missing_merge_key
      action: block
      fault_code: CONTRACT_MISSING_MERGE_KEY
      severity: critical
      family: semantic
      message: "Silver/Gold write without merge key."
      remediation:
        - "Set merge_key_required=True"
""", encoding="utf-8")


def cmd_init(args) -> int:
    if args.list:
        print("Available templates:")
        for name, desc in TEMPLATES.items():
            print(f"  {name:<25s} {desc}")
        print(f"\nUsage: cfa init --template <name>")
        return 0

    template = args.template
    dir_path = Path(args.dir if args.dir else ".")

    if template:
        if template not in _TEMPLATE_GENERATORS:
            print(f"Unknown template: {template}")
            print(f"Available: {', '.join(TEMPLATES)}")
            print(f"Use: cfa init --list")
            return 1

        dir_path.mkdir(parents=True, exist_ok=True)
        _base_cfa_files(dir_path)
        _TEMPLATE_GENERATORS[template](dir_path)

        print(f"CFA project initialized with template '{template}' in {dir_path}/")
        print(f"  cfa.yaml            — CFA configuration")
        print(f"  catalog.json        — data catalog")
        print(f"  policy.yaml         — governance policy bundle")
        return 0

    # Default: classic init (no template)
    cfa_dir = Path(args.dir or ".cfa")
    cfa_dir.mkdir(exist_ok=True)
    (cfa_dir / "policies").mkdir(exist_ok=True)

    example_catalog = {
        "datasets": {
            "nfe": {"classification": "high_volume", "size_gb": 4000, "pii_columns": [],
                     "partition_column": "processing_date", "merge_keys": ["nfe_id"]},
            "clientes": {"classification": "sensitive", "size_gb": 0.5,
                          "pii_columns": ["cpf", "email"], "partition_column": "processing_date",
                          "merge_keys": ["cliente_id"]},
        }
    }

    (cfa_dir / "catalog.json").write_text(json.dumps(example_catalog, indent=2), encoding="utf-8")

    prod_policy = {
        "policy_bundle": {
            "version": "prod-v1.0",
            "description": "Production governance rules",
            "rules": [
                {"name": "forbid_raw_pii", "condition": "pii_in_protected_layer",
                 "action": "block", "fault_code": "GOVERNANCE_RAW_PII", "severity": "critical",
                 "family": "semantic", "message": "PII in protected layer without anonymization.",
                 "remediation": ["Apply sha256 on PII columns"]},
                {"name": "require_partition", "condition": "missing_partition",
                 "action": "replan", "fault_code": "FINOPS_MISSING_PARTITION", "severity": "high",
                 "family": "semantic", "message": "High-volume dataset without partition.",
                 "remediation": ["Add partition_by column"]},
                {"name": "require_merge_key", "condition": "missing_merge_key",
                 "action": "block", "fault_code": "CONTRACT_MISSING_MERGE_KEY", "severity": "critical",
                 "family": "semantic", "message": "Silver/Gold write without merge key.",
                 "remediation": ["Set merge_key_required=True"]},
            ],
        }
    }
    (cfa_dir / "policies" / "prod-v1.yaml").write_text(
        json.dumps(prod_policy, indent=2), encoding="utf-8"
    )

    config = (
        "# CFA Configuration\n"
        "version: \"1.0\"\n"
        "\n"
        "storage:\n"
        "  backend: sqlite\n"
        "  path: cfa.db\n"
        "  retention_days: 90\n"
        "\n"
        "defaults:\n"
        f"  catalog: {cfa_dir / 'catalog.json'}\n"
        f"  policy_bundle: {cfa_dir / 'policies' / 'prod-v1.yaml'}\n"
        "  backend: pyspark\n"
    )
    (cfa_dir / "config.yaml").write_text(config, encoding="utf-8")

    (cfa_dir / ".gitignore").write_text("*\n!.gitignore\n", encoding="utf-8")

    print(f"CFA initialized in {cfa_dir}/")
    print("  config.yaml          — CFA configuration")
    print("  catalog.json         — example data catalog")
    print("  policies/prod-v1.yaml — production policy bundle")
    print(f"\nTemplates: cfa init --list")
    print(f"Example:   cfa init --template fastapi -d my_project")
    return 0
