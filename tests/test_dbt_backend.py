"""Tests for dbt backend code generation."""

from cfa.backends import BackendRegistry
from cfa.core.planner import (
    ExecutionPlanner,
)
from cfa.types import (
    DatasetClassification,
    DatasetRef,
    ExecutionContext,
    SignatureConstraints,
    StateSignature,
    TargetLayer,
)


def _sql_for(sig: StateSignature) -> str:
    plan = ExecutionPlanner().plan(sig)
    registry = BackendRegistry.singleton()
    backend = registry.get("dbt")()
    result = backend.generate(plan)
    return result.code


class TestDbtBackend:
    def test_registered_in_backend_registry(self):
        registry = BackendRegistry.singleton()
        assert "dbt" in registry.list()
        backend = registry.get("dbt")()
        caps = backend.get_capabilities()
        assert caps.backend_name == "dbt"
        assert caps.supports_merge is True

    def test_generates_dbt_config_block(self):
        sig = StateSignature(
            domain="fiscal", intent="reconciliation", target_layer=TargetLayer.SILVER,
            datasets=(
                DatasetRef("nfe", DatasetClassification.HIGH_VOLUME, merge_keys=("nfe_id",)),
            ),
            constraints=SignatureConstraints(partition_by=("processing_date",)),
            execution_context=ExecutionContext("v1", "c1", "r1"),
        )
        code = _sql_for(sig)
        assert "{{ config(" in code
        assert "materialized" in code
        assert "partition_by" in code
        assert "processing_date" in code

    def test_generates_schema_yml(self):
        sig = StateSignature(
            domain="fiscal", intent="reconciliation", target_layer=TargetLayer.SILVER,
            datasets=(
                DatasetRef("nfe", DatasetClassification.HIGH_VOLUME, merge_keys=("nfe_id",)),
                DatasetRef("clientes", DatasetClassification.SENSITIVE,
                           pii_columns=("cpf",), merge_keys=("cliente_id",)),
            ),
            constraints=SignatureConstraints(merge_key_required=True),
            execution_context=ExecutionContext("v1", "c1", "r1"),
        )
        code = _sql_for(sig)
        assert "version: 2" in code
        assert "models:" in code
        assert "not_null" in code
        assert "unique" in code

    def test_generates_ref_syntax(self):
        sig = StateSignature(
            domain="fiscal", intent="reconciliation", target_layer=TargetLayer.SILVER,
            datasets=(
                DatasetRef("nfe", DatasetClassification.HIGH_VOLUME, merge_keys=("nfe_id",)),
            ),
            constraints=SignatureConstraints(),
            execution_context=ExecutionContext("v1", "c1", "r1"),
        )
        code = _sql_for(sig)
        assert "{{ ref(" in code

    def test_generates_pii_anonymization_comment(self):
        sig = StateSignature(
            domain="fiscal", intent="ingest", target_layer=TargetLayer.SILVER,
            datasets=(
                DatasetRef("clientes", DatasetClassification.SENSITIVE,
                           pii_columns=("cpf", "email"), merge_keys=("cliente_id",)),
            ),
            constraints=SignatureConstraints(merge_key_required=True),
            execution_context=ExecutionContext("v1", "c1", "r1"),
        )
        code = _sql_for(sig)
        assert "ANONYMIZE" in code
        assert "cpf" in code.lower()

    def test_generates_merge_keys_as_uniqueness_tests(self):
        sig = StateSignature(
            domain="fiscal", intent="reconciliation", target_layer=TargetLayer.SILVER,
            datasets=(
                DatasetRef("nfe", DatasetClassification.HIGH_VOLUME,
                           merge_keys=("nfe_id", "processing_date")),
            ),
            constraints=SignatureConstraints(merge_key_required=True),
            execution_context=ExecutionContext("v1", "c1", "r1"),
        )
        code = _sql_for(sig)
        assert "dbt_utils.unique_combination_of_columns" in code
        assert "nfe_id" in code
        assert "processing_date" in code

    def test_forbidden_tokens_block_drop_table(self):
        from cfa.validate.static import StaticValidator

        backend = BackendRegistry.singleton().get("dbt")()
        validator = StaticValidator()
        sig = StateSignature(
            domain="fiscal", intent="ingest", target_layer=TargetLayer.SILVER,
            datasets=(
                DatasetRef("clientes", DatasetClassification.SENSITIVE, merge_keys=("id",)),
            ),
            constraints=SignatureConstraints(merge_key_required=False),
            execution_context=ExecutionContext("v1", "c1", "r1"),
        )
        plan = ExecutionPlanner().plan(sig)
        code = backend.generate(plan)
        result = validator.validate(code, sig, backend=backend)
        assert result.passed

    def test_forbidden_tokens_block_dangerous_sql(self):
        from cfa.core.codegen import GeneratedCode
        from cfa.validate.static import StaticValidator

        backend = BackendRegistry.singleton().get("dbt")()
        validator = StaticValidator()
        sig = StateSignature(
            domain="fiscal", intent="ingest", target_layer=TargetLayer.SILVER,
            datasets=(),
            constraints=SignatureConstraints(),
            execution_context=ExecutionContext("v1", "c1", "r1"),
        )
        code = GeneratedCode(
            plan_signature_hash="hash", intent_id="id",
            language="dbt",
            code="DROP TABLE clientes",
        )
        result = validator.validate(code, sig, backend=backend)
        assert not result.passed
        assert "STATIC_DBT_DROP_TABLE" in result.fault_codes
