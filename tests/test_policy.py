"""Tests for CFA Policy Engine."""

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
from conftest import make_signature


class TestPolicyEngine:
    def test_approves_clean_signature(self):
        engine = PolicyEngine()
        result = engine.evaluate(make_signature())
        assert result.action == PolicyAction.APPROVE
        assert not result.faults

    def test_replans_missing_partition_for_high_volume(self):
        engine = PolicyEngine()
        result = engine.evaluate(make_signature(with_partition=False))
        assert result.action == PolicyAction.REPLAN
        assert any(f.code == "FINOPS_MISSING_TEMPORAL_PREDICATE" for f in result.faults)

    def test_blocks_pii_without_policy(self):
        engine = PolicyEngine()
        sig = StateSignature(
            domain="fiscal",
            intent="join",
            target_layer=TargetLayer.SILVER,
            datasets=(DatasetRef("clientes", DatasetClassification.SENSITIVE, pii_columns=("cpf",)),),
            constraints=SignatureConstraints(no_pii_raw=False),
            execution_context=ExecutionContext("v1", "c1", "r1"),
        )
        result = engine.evaluate(sig)
        assert result.action == PolicyAction.BLOCK
        assert any(f.code == "GOVERNANCE_PII_WITHOUT_POLICY" for f in result.faults)

    def test_blocks_missing_merge_key(self):
        engine = PolicyEngine()
        sig = make_signature(merge_key=False)
        result = engine.evaluate(sig)
        assert result.action == PolicyAction.BLOCK
        assert any(f.code == "CONTRACT_MISSING_MERGE_KEY" for f in result.faults)

    def test_replans_disabled_type_enforcement(self):
        engine = PolicyEngine()
        sig = make_signature(enforce_types=False)
        result = engine.evaluate(sig)
        assert result.action == PolicyAction.REPLAN
        assert any(f.code == "CONTRACT_TYPE_ENFORCEMENT_DISABLED" for f in result.faults)

    def test_blocks_after_max_replans(self):
        engine = PolicyEngine(max_replan_attempts=3)
        result = engine.evaluate(make_signature(with_partition=False), replan_count=3)
        assert result.action == PolicyAction.BLOCK
        assert any(f.code == "POLICY_MAX_REPLAN_EXCEEDED" for f in result.faults)

    def test_blocks_invalid_cost_ceiling(self):
        engine = PolicyEngine()
        sig = make_signature(max_cost_dbu=0)
        result = engine.evaluate(sig)
        assert result.action == PolicyAction.BLOCK
        assert any(f.code == "FINOPS_INVALID_COST_CEILING" for f in result.faults)

    def test_block_takes_precedence_over_replan(self):
        """When both BLOCK and REPLAN faults exist, BLOCK wins."""
        engine = PolicyEngine()
        sig = StateSignature(
            domain="fiscal",
            intent="join",
            target_layer=TargetLayer.SILVER,
            datasets=(
                DatasetRef("nfe", DatasetClassification.HIGH_VOLUME),
                DatasetRef("clientes", DatasetClassification.SENSITIVE, pii_columns=("cpf",)),
            ),
            constraints=SignatureConstraints(
                no_pii_raw=False,       # triggers BLOCK (PII without policy)
                partition_by=(),        # triggers REPLAN (missing partition)
            ),
            execution_context=ExecutionContext("v1", "c1", "r1"),
        )
        result = engine.evaluate(sig)
        assert result.action == PolicyAction.BLOCK

    def test_describe_rules(self):
        engine = PolicyEngine()
        rules = engine.describe_rules()
        assert len(rules) > 0
        assert all("name" in r and "fault_code" in r for r in rules)
