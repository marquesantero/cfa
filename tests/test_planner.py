"""Tests for CFA Execution Planner."""

import pytest

from cfa.planner import (
    ConsistencyUnit,
    ExecutionPlan,
    ExecutionPlanner,
    ExecutionStep,
    StepType,
    WriteMode,
)
from cfa.types import TargetLayer
from conftest import make_signature


class TestExecutionPlanner:
    def test_plan_has_extract_and_load(self):
        planner = ExecutionPlanner()
        sig = make_signature()
        plan = planner.plan(sig)
        types = [s.step_type for s in plan.steps]
        assert StepType.EXTRACT in types
        assert StepType.LOAD in types

    def test_plan_includes_anonymize_for_pii(self):
        planner = ExecutionPlanner()
        sig = make_signature(include_pii=True)
        plan = planner.plan(sig)
        anon_steps = [s for s in plan.steps if s.step_type == StepType.ANONYMIZE]
        assert len(anon_steps) > 0
        assert anon_steps[0].config["strategy"] == "sha256"

    def test_plan_no_anonymize_without_pii(self):
        planner = ExecutionPlanner()
        sig = make_signature(include_pii=False)
        plan = planner.plan(sig)
        anon_steps = [s for s in plan.steps if s.step_type == StepType.ANONYMIZE]
        assert len(anon_steps) == 0

    def test_plan_includes_join_for_reconciliation(self):
        planner = ExecutionPlanner()
        sig = make_signature(include_pii=True)  # 2 datasets + reconciliation intent
        plan = planner.plan(sig)
        join_steps = [s for s in plan.steps if s.step_type == StepType.JOIN]
        assert len(join_steps) == 1

    def test_plan_uses_broadcast_for_size_mismatch(self):
        planner = ExecutionPlanner()
        sig = make_signature(include_pii=True)  # nfe=0GB, clientes=0GB by default
        # Need to create a signature with actual size difference
        from cfa.types import (
            DatasetClassification, DatasetRef, ExecutionContext,
            SignatureConstraints, StateSignature, TargetLayer,
        )
        sig = StateSignature(
            domain="fiscal",
            intent="reconciliation_and_persist",
            target_layer=TargetLayer.SILVER,
            datasets=(
                DatasetRef("nfe", DatasetClassification.HIGH_VOLUME, size_gb=4000),
                DatasetRef("clientes", DatasetClassification.SENSITIVE, size_gb=0.5, pii_columns=("cpf",)),
            ),
            constraints=SignatureConstraints(partition_by=("processing_date",)),
            execution_context=ExecutionContext("v1", "c1", "r1"),
        )
        plan = planner.plan(sig)
        join_steps = [s for s in plan.steps if s.step_type == StepType.JOIN]
        assert join_steps[0].config["type"] == "broadcast"

    def test_plan_uses_merge_for_silver(self):
        planner = ExecutionPlanner()
        sig = make_signature(target_layer=TargetLayer.SILVER)
        plan = planner.plan(sig)
        assert plan.write_mode == WriteMode.MERGE

    def test_plan_uses_overwrite_partition_for_bronze(self):
        planner = ExecutionPlanner()
        sig = make_signature(target_layer=TargetLayer.BRONZE)
        plan = planner.plan(sig)
        assert plan.write_mode == WriteMode.OVERWRITE_PARTITION

    def test_plan_selects_partition_consistency_unit(self):
        planner = ExecutionPlanner()
        sig = make_signature(with_partition=True)
        plan = planner.plan(sig)
        assert plan.consistency_unit == ConsistencyUnit.PARTITION

    def test_plan_selects_dataset_consistency_unit_without_partition(self):
        planner = ExecutionPlanner()
        sig = make_signature(with_partition=False)
        plan = planner.plan(sig)
        assert plan.consistency_unit == ConsistencyUnit.DATASET

    def test_plan_extract_has_partition_filter(self):
        planner = ExecutionPlanner()
        sig = make_signature(with_partition=True)
        plan = planner.plan(sig)
        extract_steps = [s for s in plan.steps if s.step_type == StepType.EXTRACT]
        assert extract_steps[0].config.get("filter") is not None

    def test_plan_signature_hash_matches(self):
        planner = ExecutionPlanner()
        sig = make_signature()
        plan = planner.plan(sig)
        assert plan.signature_hash == sig.signature_hash


class TestExecutionPlan:
    def test_topological_sort(self):
        steps = [
            ExecutionStep(id="load", step_type=StepType.LOAD, depends_on=("extract",)),
            ExecutionStep(id="extract", step_type=StepType.EXTRACT),
        ]
        plan = ExecutionPlan(
            signature_hash="test",
            intent_id="test",
            steps=steps,
            consistency_unit=ConsistencyUnit.DATASET,
            write_mode=WriteMode.MERGE,
        )
        order = plan.execution_order()
        assert order[0].id == "extract"
        assert order[1].id == "load"

    def test_cyclic_dependency_raises(self):
        steps = [
            ExecutionStep(id="a", step_type=StepType.EXTRACT, depends_on=("b",)),
            ExecutionStep(id="b", step_type=StepType.LOAD, depends_on=("a",)),
        ]
        plan = ExecutionPlan(
            signature_hash="test",
            intent_id="test",
            steps=steps,
            consistency_unit=ConsistencyUnit.DATASET,
            write_mode=WriteMode.MERGE,
        )
        with pytest.raises(ValueError, match="Cyclic"):
            plan.execution_order()

    def test_to_dict(self):
        planner = ExecutionPlanner()
        sig = make_signature()
        plan = planner.plan(sig)
        d = plan.to_dict()
        assert "steps" in d
        assert "signature_hash" in d
        assert all("id" in s for s in d["steps"])
