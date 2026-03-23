"""Tests for CFA Static Validation."""

from cfa.codegen import GeneratedCode
from cfa.static_validation import StaticValidator
from cfa.types import TargetLayer
from conftest import make_signature


def _make_code(code: str, sig_hash: str = "test") -> GeneratedCode:
    return GeneratedCode(
        plan_signature_hash=sig_hash,
        intent_id="test",
        language="pyspark",
        code=code,
    )


class TestForbiddenTokens:
    def test_blocks_collect(self):
        validator = StaticValidator()
        code = _make_code('df.collect()')
        sig = make_signature()
        result = validator.validate(code, sig)
        assert not result.passed
        assert "STATIC_FORBIDDEN_COLLECT" in result.fault_codes

    def test_blocks_topandas(self):
        validator = StaticValidator()
        code = _make_code('df.toPandas()')
        sig = make_signature()
        result = validator.validate(code, sig)
        assert not result.passed
        assert "STATIC_FORBIDDEN_TOPANDAS" in result.fault_codes

    def test_blocks_crossjoin(self):
        validator = StaticValidator()
        code = _make_code('df1.crossJoin(df2)')
        sig = make_signature()
        result = validator.validate(code, sig)
        assert not result.passed
        assert "STATIC_FORBIDDEN_CROSSJOIN" in result.fault_codes

    def test_blocks_os_import(self):
        validator = StaticValidator()
        # Test that importing the os module is blocked (security rule in static validator)
        code = _make_code('import os')
        sig = make_signature()
        result = validator.validate(code, sig)
        assert not result.passed
        assert "STATIC_FORBIDDEN_IMPORT_OS" in result.fault_codes

    def test_blocks_subprocess_import(self):
        validator = StaticValidator()
        code = _make_code('import subprocess')
        sig = make_signature()
        result = validator.validate(code, sig)
        assert not result.passed

    def test_passes_clean_code(self):
        validator = StaticValidator()
        code = _make_code(
            'df = spark.read.format("delta").load("nfe")\n'
            'df = df.filter(F.col("processing_date") >= "2026-01-01")\n'
            'from delta.tables import DeltaTable\n'
            'DeltaTable.forPath(spark, "silver").alias("t").merge(df.alias("s"), "t.k = s.k")'
        )
        sig = make_signature()
        result = validator.validate(code, sig)
        assert result.passed


class TestRequiredPatterns:
    def test_requires_filter_when_partition_declared(self):
        validator = StaticValidator()
        code = _make_code(
            'df = spark.read.load("nfe")\n'
            'from delta.tables import DeltaTable\n'
            'DeltaTable.forPath(spark, "silver").alias("t").merge(df.alias("s"), "t.k = s.k")'
        )
        sig = make_signature(with_partition=True)
        result = validator.validate(code, sig)
        assert not result.passed
        assert "STATIC_MISSING_PARTITION_FILTER" in result.fault_codes

    def test_no_filter_required_without_partition(self):
        validator = StaticValidator()
        code = _make_code(
            'df = spark.read.load("nfe")\n'
            'from delta.tables import DeltaTable\n'
            'DeltaTable.forPath(spark, "silver").alias("t").merge(df.alias("s"), "t.k = s.k")'
        )
        sig = make_signature(with_partition=False)
        result = validator.validate(code, sig)
        assert "STATIC_MISSING_PARTITION_FILTER" not in result.fault_codes

    def test_requires_merge_for_silver(self):
        validator = StaticValidator()
        code = _make_code(
            'df = spark.read.load("nfe")\n'
            'df = df.filter(F.col("date") >= "2026")\n'
            'df.write.mode("append").save("silver_nfe")'
        )
        sig = make_signature(target_layer=TargetLayer.SILVER)
        result = validator.validate(code, sig)
        assert not result.passed
        assert "STATIC_MISSING_MERGE_OPERATION" in result.fault_codes


class TestPIIValidation:
    def test_allows_pii_in_sha2_context(self):
        validator = StaticValidator()
        code = _make_code(
            'df = df.withColumn("cpf_hash", F.sha2(F.col("cpf").cast("string"), 256))\n'
            'df = df.drop("cpf")\n'
            'df = df.filter(F.col("date") >= "2026")\n'
            'from delta.tables import DeltaTable\n'
            'DeltaTable.forPath(spark, "silver").alias("t").merge(df.alias("s"), "t.k = s.k")'
        )
        sig = make_signature(include_pii=True)
        result = validator.validate(code, sig)
        assert "STATIC_RAW_PII_REFERENCE_CPF" not in result.fault_codes


class TestSchemaContract:
    def test_blocks_forbidden_column_in_output(self):
        validator = StaticValidator()
        code = _make_code('df = df.select("nfe_id", "cpf")\ndf.alias("cpf")')
        sig = make_signature()
        schema = {"forbidden_columns": ["cpf", "email"]}
        result = validator.validate(code, sig, schema_contract=schema)
        assert any("FORBIDDEN_COLUMN" in f.code for f in result.faults)


class TestIntegrationWithCodegen:
    def test_generated_code_passes_validation(self):
        """Code generated by PySparkGenerator should pass static validation."""
        from cfa.codegen import PySparkGenerator
        from cfa.planner import ExecutionPlanner

        planner = ExecutionPlanner()
        gen = PySparkGenerator()
        validator = StaticValidator()

        sig = make_signature(include_pii=True)
        plan = planner.plan(sig)
        code = gen.generate(plan)
        result = validator.validate(code, sig)

        assert result.passed, f"Generated code failed validation: {result.fault_codes}"
