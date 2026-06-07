"""
Minimal Airflow DAG example for a CFA governance gate.

This file is a repository example, not a packaged Airflow provider.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
INTEGRATION_SRC = ROOT / "integrations" / "airflow-governance-gate" / "src"
if str(INTEGRATION_SRC) not in sys.path:
    sys.path.insert(0, str(INTEGRATION_SRC))

from governance_gate import GovernanceRequest, assert_allowed

try:
    from airflow import DAG
    from airflow.decorators import task
except ImportError:  # pragma: no cover
    DAG = None
    task = None


def _demo_request() -> GovernanceRequest:
    return GovernanceRequest(
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


if DAG is not None and task is not None:
    with DAG(
        dag_id="cfa_governance_gate_demo",
        start_date=datetime(2026, 1, 1),
        schedule=None,
        catchup=False,
        tags=["cfa", "governance"],
    ) as dag:

        @task
        def validate_governance():
            result = assert_allowed(_demo_request())
            return {
                "action": result.action.value,
                "reasoning": result.reasoning,
                "faults": [fault.code for fault in result.faults],
            }

        @task
        def run_pipeline():
            return "Execution placeholder: your real Spark or SQL task goes here."

        validate_governance() >> run_pipeline()
