"""Shared fixtures for CFA tests."""

import pytest

from cfa.types import (
    DatasetClassification,
    DatasetRef,
    ExecutionContext,
    SignatureConstraints,
    StateSignature,
    TargetLayer,
)


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
        "produtos": {
            "classification": "internal",
            "size_gb": 0.1,
            "pii_columns": [],
        },
    }
}


def make_signature(
    target_layer: TargetLayer = TargetLayer.SILVER,
    include_pii: bool = False,
    with_partition: bool = True,
    merge_key: bool = True,
    enforce_types: bool = True,
    no_pii_raw: bool = True,
    max_cost_dbu: float | None = None,
) -> StateSignature:
    datasets = [DatasetRef(name="nfe", classification=DatasetClassification.HIGH_VOLUME)]
    if include_pii:
        datasets.append(
            DatasetRef(
                name="clientes",
                classification=DatasetClassification.SENSITIVE,
                pii_columns=("cpf", "email"),
            )
        )
    return StateSignature(
        domain="fiscal",
        intent="reconciliation",
        target_layer=target_layer,
        datasets=tuple(datasets),
        constraints=SignatureConstraints(
            no_pii_raw=no_pii_raw,
            merge_key_required=merge_key,
            enforce_types=enforce_types,
            partition_by=("processing_date",) if with_partition else (),
            max_cost_dbu=max_cost_dbu,
        ),
        execution_context=ExecutionContext(
            policy_bundle_version="v1.0",
            catalog_snapshot_version="catalog_test",
            context_registry_version_id="v_test",
        ),
    )


@pytest.fixture
def catalog():
    return CATALOG


@pytest.fixture
def clean_signature():
    return make_signature()
