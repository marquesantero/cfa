"""Tests for CFA Code Generator."""

from cfa.codegen import PySparkGenerator
from cfa.planner import ExecutionPlanner
from cfa.types import TargetLayer
from conftest import make_signature


class TestPySparkGenerator:
    def _generate(self, **kwargs):
        planner = ExecutionPlanner()
        gen = PySparkGenerator()
        sig = make_signature(**kwargs)
        plan = planner.plan(sig)
        return gen.generate(plan)

    def test_generates_pyspark_code(self):
        result = self._generate()
        assert result.language == "pyspark"
        assert "SparkSession" in result.code
        assert result.line_count > 0

    def test_code_contains_filter_with_partition(self):
        result = self._generate(with_partition=True)
        assert ".filter(" in result.code

    def test_code_contains_sha256_for_pii(self):
        result = self._generate(include_pii=True)
        assert "sha2(" in result.code

    def test_code_contains_drop_for_pii(self):
        result = self._generate(include_pii=True)
        assert ".drop(" in result.code

    def test_code_contains_merge_for_silver(self):
        result = self._generate(target_layer=TargetLayer.SILVER)
        assert "DeltaTable" in result.code
        assert "merge(" in result.code

    def test_code_not_merge_for_bronze(self):
        result = self._generate(target_layer=TargetLayer.BRONZE)
        # Bronze uses overwrite, not merge
        assert "DeltaTable" not in result.code

    def test_code_contains_broadcast_for_join(self):
        from cfa.types import (
            DatasetClassification, DatasetRef, ExecutionContext,
            SignatureConstraints, StateSignature,
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
        planner = ExecutionPlanner()
        gen = PySparkGenerator()
        plan = planner.plan(sig)
        result = gen.generate(plan)
        assert "broadcast(" in result.code

    def test_step_code_map_populated(self):
        result = self._generate()
        assert len(result.step_code_map) > 0
        assert all(isinstance(v, str) for v in result.step_code_map.values())

    def test_deterministic_output(self):
        r1 = self._generate()
        r2 = self._generate()
        assert r1.code == r2.code
