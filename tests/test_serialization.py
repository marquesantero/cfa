"""Tests for CFA serialization — JSON roundtrip."""

from __future__ import annotations

import json

from cfa.types import (
    DatasetClassification,
    DatasetRef,
    DecisionState,
    ExecutionContext,
    KernelResult,
    PolicyAction,
    PolicyResult,
    SignatureConstraints,
    StateSignature,
    TargetLayer,
)


def _make_sig() -> StateSignature:
    return StateSignature(
        domain="fiscal",
        intent="reconciliation",
        target_layer=TargetLayer.SILVER,
        datasets=(
            DatasetRef(name="nfe", classification=DatasetClassification.HIGH_VOLUME, size_gb=4000),
            DatasetRef(name="clientes", classification=DatasetClassification.SENSITIVE, pii_columns=("cpf", "email")),
        ),
        constraints=SignatureConstraints(
            no_pii_raw=True, merge_key_required=True, enforce_types=True,
            partition_by=("processing_date",), max_cost_dbu=50.0,
        ),
        execution_context=ExecutionContext(
            policy_bundle_version="v1.0", catalog_snapshot_version="cat_v1",
            context_registry_version_id="ctx_001",
        ),
    )


class TestStateSignatureSerialization:
    def test_roundtrip(self):
        sig = _make_sig()
        d = sig.to_dict()
        sig2 = StateSignature.from_dict(d)
        assert sig2.domain == sig.domain
        assert sig2.intent == sig.intent
        assert sig2.target_layer == sig.target_layer
        assert len(sig2.datasets) == 2
        assert sig2.constraints.no_pii_raw == sig.constraints.no_pii_raw
        assert sig2.constraints.partition_by == sig.constraints.partition_by
        assert sig2.execution_context.policy_bundle_version == "v1.0"

    def test_json_roundtrip(self):
        sig = _make_sig()
        j = sig.to_json()
        sig2 = StateSignature.from_json(j)
        assert sig2.to_dict() == sig.to_dict()

    def test_minimal_signature(self):
        sig = StateSignature(
            domain="test", intent="test", target_layer=TargetLayer.BRONZE,
            datasets=(), constraints=SignatureConstraints(),
            execution_context=ExecutionContext(
                policy_bundle_version="v1", catalog_snapshot_version="v1",
                context_registry_version_id="v1",
            ),
        )
        d = sig.to_dict()
        sig2 = StateSignature.from_dict(d)
        assert sig2.domain == "test"
        assert sig2.target_layer == TargetLayer.BRONZE

    def test_serialization_preserves_hash(self):
        sig = _make_sig()
        j = sig.to_json()
        sig2 = StateSignature.from_json(j)
        assert sig.signature_hash == sig2.signature_hash


class TestPolicyResultSerialization:
    def test_to_dict(self):
        pr = PolicyResult(
            action=PolicyAction.APPROVE,
            faults=[],
            reasoning="All rules passed.",
        )
        d = pr.to_dict()
        assert d["action"] == "approve"
        assert d["faults"] == []

    def test_to_json(self):
        pr = PolicyResult(action=PolicyAction.BLOCK, reasoning="blocked")
        j = pr.to_json()
        data = json.loads(j)
        assert data["action"] == "block"


class TestKernelResultSerialization:
    def test_to_dict(self):
        sig = _make_sig()
        kr = KernelResult(intent_id="abc", state=DecisionState.APPROVED, signature=sig)
        d = kr.to_dict()
        assert d["intent_id"] == "abc"
        assert d["state"] == "approved"
        assert "signature" in d

    def test_to_json(self):
        kr = KernelResult(intent_id="xyz", state=DecisionState.BLOCKED, blocked_reason="test")
        j = kr.to_json()
        data = json.loads(j)
        assert data["state"] == "blocked"
        assert data["blocked_reason"] == "test"
