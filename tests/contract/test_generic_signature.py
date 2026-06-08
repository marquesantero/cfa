"""Tests for the hybrid generic surface on StateSignature.

ADR-0008 calls for a vertical-aware `StateSignature` with generic
mapping views. Phase 1b implements the hybrid form: typed fields stay
the primary storage; ``vertical`` is a new field defaulting to
``"data"``; ``payload`` and ``constraint_values`` are derived mapping
views the kernel can use without depending on the data-vertical shape.

These tests pin the contract so we don't accidentally regress on the
vertical field, hash semantics, or the mapping derivation.
"""

from __future__ import annotations

import pytest

from cfa.types import (
    DatasetClassification,
    DatasetRef,
    ExecutionContext,
    SignatureConstraints,
    StateSignature,
    TargetLayer,
)


def _build(vertical: str | None = None) -> StateSignature:
    kwargs: dict = dict(
        domain="fiscal",
        intent="reconciliation",
        target_layer=TargetLayer.SILVER,
        datasets=(
            DatasetRef(
                name="nfe",
                classification=DatasetClassification.HIGH_VOLUME,
                size_gb=4000.0,
                merge_keys=("nfe_id",),
            ),
            DatasetRef(
                name="clientes",
                classification=DatasetClassification.SENSITIVE,
                size_gb=0.5,
                pii_columns=("cpf", "email"),
                merge_keys=("cliente_id",),
            ),
        ),
        constraints=SignatureConstraints(
            no_pii_raw=True,
            merge_key_required=True,
            partition_by=("processing_date",),
            max_cost_dbu=50.0,
        ),
        execution_context=ExecutionContext("v1", "c1", "r1"),
    )
    if vertical is not None:
        kwargs["vertical"] = vertical
    return StateSignature(**kwargs)


class TestVerticalField:
    def test_defaults_to_data(self) -> None:
        sig = _build()
        assert sig.vertical == "data"

    def test_can_be_set_explicitly(self) -> None:
        sig = _build(vertical="agent")
        assert sig.vertical == "agent"

    def test_with_constraints_preserves_vertical(self) -> None:
        sig = _build(vertical="agent").with_constraints(no_pii_raw=False)
        assert sig.vertical == "agent"


class TestPayloadView:
    def test_payload_contains_target_layer_and_datasets(self) -> None:
        sig = _build()
        payload = sig.payload
        assert payload["target_layer"] == "silver"
        names = [d["name"] for d in payload["datasets"]]
        assert names == ["nfe", "clientes"]

    def test_payload_preserves_dataset_metadata(self) -> None:
        sig = _build()
        payload = sig.payload
        clientes = next(d for d in payload["datasets"] if d["name"] == "clientes")
        assert clientes["classification"] == "sensitive"
        assert clientes["pii_columns"] == ["cpf", "email"]
        assert clientes["merge_keys"] == ["cliente_id"]

    def test_payload_is_json_serializable(self) -> None:
        import json

        sig = _build()
        encoded = json.dumps(sig.payload)
        decoded = json.loads(encoded)
        assert decoded["target_layer"] == "silver"


class TestConstraintValuesView:
    def test_constraint_values_mirrors_dataclass(self) -> None:
        sig = _build()
        cv = sig.constraint_values
        assert cv["no_pii_raw"] is True
        assert cv["merge_key_required"] is True
        assert cv["partition_by"] == ["processing_date"]
        assert cv["max_cost_dbu"] == 50.0

    def test_constraint_values_is_json_serializable(self) -> None:
        import json

        sig = _build()
        encoded = json.dumps(sig.constraint_values)
        decoded = json.loads(encoded)
        assert decoded["no_pii_raw"] is True


class TestHashSemantics:
    def test_same_content_same_hash(self) -> None:
        sig1 = _build()
        sig2 = _build()
        assert sig1.signature_hash == sig2.signature_hash

    def test_different_vertical_different_hash(self) -> None:
        sig_data = _build(vertical="data")
        sig_agent = _build(vertical="agent")
        assert sig_data.signature_hash != sig_agent.signature_hash

    def test_hash_is_64_char_hex(self) -> None:
        sig = _build()
        h = sig.signature_hash
        assert len(h) == 64
        int(h, 16)  # raises if not hex


class TestSerialization:
    def test_to_dict_includes_vertical(self) -> None:
        sig = _build(vertical="agent")
        data = sig.to_dict()
        assert data["vertical"] == "agent"

    def test_from_dict_round_trip_preserves_vertical(self) -> None:
        sig = _build(vertical="infra")
        roundtrip = StateSignature.from_dict(sig.to_dict())
        assert roundtrip.vertical == "infra"
        assert roundtrip.signature_hash == sig.signature_hash

    def test_from_dict_without_vertical_defaults_to_data(self) -> None:
        """1.0/1.1-shaped JSON should still parse and carry vertical='data'."""
        data = {
            "domain": "fiscal",
            "intent": "reconciliation",
            "target_layer": "silver",
            "datasets": [{"name": "nfe", "classification": "high_volume"}],
            "constraints": {},
            "execution_context": {},
        }
        sig = StateSignature.from_dict(data)
        assert sig.vertical == "data"


class TestNonDataVerticalConstructionWorks:
    def test_agent_vertical_signature_round_trips(self) -> None:
        """Even though the typed shape today is data-flavored, a
        signature can be marked with a different vertical and survive
        serialization. Future verticals will extend the storage; the
        contract for vertical attribution is already stable."""
        sig = _build(vertical="agent")
        decoded = StateSignature.from_dict(sig.to_dict())
        assert decoded.vertical == "agent"
        assert decoded.signature_hash == sig.signature_hash
