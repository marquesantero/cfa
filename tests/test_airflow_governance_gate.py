from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


def _load_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "integrations"
        / "airflow-governance-gate"
        / "src"
        / "governance_gate.py"
    )
    spec = spec_from_file_location("governance_gate", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_airflow_governance_gate_allows_valid_request():
    module = _load_module()
    request = module.GovernanceRequest(
        domain="fiscal",
        intent="reconciliation",
        target_layer="silver",
        datasets=(
            {
                "name": "nfe",
                "classification": "high_volume",
                "size_gb": 4000,
                "partition_column": "processing_date",
            },
            {
                "name": "clientes",
                "classification": "sensitive",
                "size_gb": 0.5,
                "pii_columns": ["cpf"],
                "partition_column": "processing_date",
            },
        ),
        no_pii_raw=True,
        merge_key_required=True,
        enforce_types=True,
        partition_by=("processing_date",),
        max_cost_dbu=50.0,
    )

    result = module.evaluate_request(request)
    assert result.action.value == "approve"


def test_airflow_governance_gate_blocks_invalid_request():
    module = _load_module()
    request = module.GovernanceRequest(
        domain="fiscal",
        intent="reconciliation",
        target_layer="silver",
        datasets=(
            {
                "name": "clientes",
                "classification": "sensitive",
                "size_gb": 0.5,
                "pii_columns": ["cpf"],
            },
        ),
        no_pii_raw=False,
        merge_key_required=False,
        enforce_types=False,
    )

    result = module.evaluate_request(request)
    assert result.action.value == "block"
