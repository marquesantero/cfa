"""Tests for CFA core types."""

from cfa.types import (
    AmbiguityLevel,
    ConfirmationMode,
    DecisionState,
    KernelResult,
    SemanticResolution,
    TargetLayer,
)
from conftest import make_signature


class TestStateSignature:
    def test_hash_is_deterministic(self):
        s1 = make_signature()
        s2 = make_signature()
        assert s1.signature_hash == s2.signature_hash

    def test_hash_changes_with_layer(self):
        s_silver = make_signature(target_layer=TargetLayer.SILVER)
        s_gold = make_signature(target_layer=TargetLayer.GOLD)
        assert s_silver.signature_hash != s_gold.signature_hash

    def test_pii_detection(self):
        assert not make_signature(include_pii=False).contains_pii
        assert make_signature(include_pii=True).contains_pii

    def test_protected_layer(self):
        assert make_signature(target_layer=TargetLayer.SILVER).writes_to_protected_layer
        assert make_signature(target_layer=TargetLayer.GOLD).writes_to_protected_layer
        assert not make_signature(target_layer=TargetLayer.BRONZE).writes_to_protected_layer

    def test_with_constraints_returns_new_signature(self):
        original = make_signature(with_partition=False)
        updated = original.with_constraints(partition_by=("processing_date",))
        assert original.constraints.partition_by == ()
        assert updated.constraints.partition_by == ("processing_date",)
        assert original.intent_id == updated.intent_id  # same intent

    def test_signature_is_frozen(self):
        sig = make_signature()
        try:
            sig.domain = "other"
            assert False, "Should not allow mutation"
        except AttributeError:
            pass


class TestSemanticResolution:
    def test_auto_mode_for_low_risk(self):
        sig = make_signature(target_layer=TargetLayer.BRONZE)
        res = SemanticResolution(
            signature=sig,
            confidence_score=0.92,
            ambiguity_level=AmbiguityLevel.LOW,
        )
        assert res.confirmation_mode == ConfirmationMode.AUTO

    def test_human_escalation_for_gold(self):
        sig = make_signature(target_layer=TargetLayer.GOLD)
        res = SemanticResolution(
            signature=sig,
            confidence_score=0.95,
            ambiguity_level=AmbiguityLevel.LOW,
        )
        assert res.confirmation_mode == ConfirmationMode.HUMAN_ESCALATION

    def test_hard_for_pii_in_protected_layer(self):
        sig = make_signature(target_layer=TargetLayer.SILVER, include_pii=True)
        res = SemanticResolution(
            signature=sig,
            confidence_score=0.90,
            ambiguity_level=AmbiguityLevel.LOW,
        )
        assert res.confirmation_mode == ConfirmationMode.HARD

    def test_soft_for_medium_confidence(self):
        sig = make_signature(target_layer=TargetLayer.BRONZE)
        res = SemanticResolution(
            signature=sig,
            confidence_score=0.72,
            ambiguity_level=AmbiguityLevel.LOW,
        )
        assert res.confirmation_mode == ConfirmationMode.SOFT

    def test_human_escalation_for_competing_interpretations(self):
        sig = make_signature(target_layer=TargetLayer.BRONZE)
        res = SemanticResolution(
            signature=sig,
            confidence_score=0.90,
            ambiguity_level=AmbiguityLevel.LOW,
            competing_interpretations=["interp_a", "interp_b"],
        )
        assert res.confirmation_mode == ConfirmationMode.HUMAN_ESCALATION


class TestKernelResult:
    def test_is_executable_when_approved(self):
        sig = make_signature()
        result = KernelResult(
            intent_id="test",
            state=DecisionState.APPROVED,
            signature=sig,
        )
        assert result.is_executable

    def test_not_executable_when_blocked(self):
        result = KernelResult(
            intent_id="test",
            state=DecisionState.BLOCKED,
        )
        assert not result.is_executable

    def test_add_event(self):
        result = KernelResult(intent_id="test", state=DecisionState.BLOCKED)
        result.add_event("stage_x", "type_y", "ok", extra="data")
        assert len(result.audit_events) == 1
        assert result.audit_events[0]["stage"] == "stage_x"
        assert result.audit_events[0]["extra"] == "data"
