"""
Minimal helper for validating a CFA governance gate inside an orchestrated job.

This module intentionally imports only the narrow core pieces it needs
instead of the broader `cfa.governance` convenience surface. That keeps the
integration lightweight and avoids pulling execution-oriented modules that are
not needed for a simple policy gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cfa.policy import PolicyEngine
from cfa.types import (
    DatasetClassification,
    DatasetRef,
    ExecutionContext,
    PolicyAction,
    SignatureConstraints,
    StateSignature,
    TargetLayer,
)


@dataclass(frozen=True)
class GovernanceRequest:
    domain: str
    intent: str
    target_layer: str
    datasets: tuple[dict, ...]
    no_pii_raw: bool = True
    merge_key_required: bool = True
    enforce_types: bool = True
    partition_by: tuple[str, ...] = ()
    max_cost_dbu: float | None = None
    policy_bundle_version: str = "v1.0"
    catalog_snapshot_version: str = "catalog_default"
    context_registry_version_id: str = "airflow_local"


def _build_signature(request: GovernanceRequest) -> StateSignature:
    classification_map = {
        "public": DatasetClassification.PUBLIC,
        "internal": DatasetClassification.INTERNAL,
        "sensitive": DatasetClassification.SENSITIVE,
        "high_volume": DatasetClassification.HIGH_VOLUME,
    }

    layer_map = {
        "bronze": TargetLayer.BRONZE,
        "silver": TargetLayer.SILVER,
        "gold": TargetLayer.GOLD,
    }

    return StateSignature(
        domain=request.domain,
        intent=request.intent,
        target_layer=layer_map[request.target_layer],
        datasets=tuple(
            DatasetRef(
                name=item["name"],
                classification=classification_map[item.get("classification", "internal")],
                size_gb=item.get("size_gb", 0.0),
                pii_columns=tuple(item.get("pii_columns", [])),
                partition_column=item.get("partition_column"),
            )
            for item in request.datasets
        ),
        constraints=SignatureConstraints(
            no_pii_raw=request.no_pii_raw,
            merge_key_required=request.merge_key_required,
            enforce_types=request.enforce_types,
            partition_by=request.partition_by,
            max_cost_dbu=request.max_cost_dbu,
        ),
        execution_context=ExecutionContext(
            policy_bundle_version=request.policy_bundle_version,
            catalog_snapshot_version=request.catalog_snapshot_version,
            context_registry_version_id=request.context_registry_version_id,
        ),
    )


def evaluate_request(request: GovernanceRequest):
    return PolicyEngine().evaluate(_build_signature(request))


def assert_allowed(request: GovernanceRequest):
    result = evaluate_request(request)
    if result.action == PolicyAction.BLOCK:
        raise RuntimeError(f"CFA governance blocked execution: {result.reasoning}")
    return result
