"""Tests for SQL backend code generation."""

from cfa.backends import BackendRegistry
from cfa.core.planner import (
    ExecutionPlan,
    WriteMode,
)
from cfa.types import (
    DatasetClassification,
    DatasetRef,
    ExecutionContext,
    SignatureConstraints,
    StateSignature,
    TargetLayer,
)


def _plan_from_signature(sig: StateSignature) -> ExecutionPlan:
    from cfa.core.planner import ExecutionPlanner
    return ExecutionPlanner().plan(sig)


def _sql_for(sig: StateSignature) -> str:
    plan = _plan_from_signature(sig)
    registry = BackendRegistry.singleton()
    factory = registry.get("sql")
    backend = factory()
    result = backend.generate(plan)
    return result.code


class TestSqlBackend:
    def test_generates_sql_language(self):
        sig = StateSignature(
            domain="test", intent="ingest", target_layer=TargetLayer.BRONZE,
            datasets=(
                DatasetRef("nfe", DatasetClassification.HIGH_VOLUME, merge_keys=("nfe_id",)),
            ),
            constraints=SignatureConstraints(),
            execution_context=ExecutionContext("v1", "c1", "r1"),
        )
        plan = _plan_from_signature(sig)
        registry = BackendRegistry.singleton()
        backend = registry.get("sql")()
        result = backend.generate(plan)
        assert result.language == "sql"
        assert "-- Step:" in result.code
        assert "-- LOAD:" in result.code

    def test_generates_extract(self):
        sig = StateSignature(
            domain="test", intent="ingest", target_layer=TargetLayer.BRONZE,
            datasets=(
                DatasetRef("clientes", DatasetClassification.SENSITIVE, merge_keys=("cliente_id",)),
            ),
            constraints=SignatureConstraints(),
            execution_context=ExecutionContext("v1", "c1", "r1"),
        )
        code = _sql_for(sig)
        assert "-- EXTRACT:" in code
        assert "FROM" in code
        assert "clientes" in code.lower()

    def test_generates_join_for_reconciliation(self):
        sig = StateSignature(
            domain="fiscal", intent="reconciliation", target_layer=TargetLayer.SILVER,
            datasets=(
                DatasetRef("nfe", DatasetClassification.HIGH_VOLUME, merge_keys=("nfe_id",)),
                DatasetRef("clientes", DatasetClassification.SENSITIVE, merge_keys=("cliente_id",)),
            ),
            constraints=SignatureConstraints(merge_key_required=True),
            execution_context=ExecutionContext("v1", "c1", "r1"),
        )
        code = _sql_for(sig)
        assert "JOIN" in code
        assert "nfe_id" in code

    def test_generates_merge_load_for_silver(self):
        sig = StateSignature(
            domain="fiscal", intent="reconciliation", target_layer=TargetLayer.SILVER,
            datasets=(
                DatasetRef("nfe", DatasetClassification.HIGH_VOLUME, merge_keys=("nfe_id",)),
                DatasetRef("clientes", DatasetClassification.SENSITIVE, merge_keys=("cliente_id",)),
            ),
            constraints=SignatureConstraints(merge_key_required=True),
            execution_context=ExecutionContext("v1", "c1", "r1"),
        )
        code = _sql_for(sig)
        assert "MERGE INTO" in code
        assert "WHEN MATCHED" in code
        assert "WHEN NOT MATCHED" in code

    def test_generates_insert_overwrite_for_partition(self):
        sig = StateSignature(
            domain="test", intent="ingest", target_layer=TargetLayer.BRONZE,
            datasets=(
                DatasetRef("vendas", DatasetClassification.HIGH_VOLUME, merge_keys=("id",)),
            ),
            constraints=SignatureConstraints(partition_by=("data_venda",)),
            execution_context=ExecutionContext("v1", "c1", "r1"),
        )
        plan = _plan_from_signature(sig)
        plan.write_mode = WriteMode.OVERWRITE_PARTITION
        registry = BackendRegistry.singleton()
        backend = registry.get("sql")()
        result = backend.generate(plan)
        assert "INSERT OVERWRITE" in result.code
        assert "PARTITION" in result.code

    def test_generates_anonymization_comments(self):
        sig = StateSignature(
            domain="test", intent="ingest", target_layer=TargetLayer.SILVER,
            datasets=(
                DatasetRef("clientes", DatasetClassification.SENSITIVE,
                           pii_columns=("cpf", "email"), merge_keys=("cliente_id",)),
            ),
            constraints=SignatureConstraints(merge_key_required=True),
            execution_context=ExecutionContext("v1", "c1", "r1"),
        )
        code = _sql_for(sig)
        assert "ANONYMIZE" in code
        assert "cpf" in code.lower() or "SHA256" in code

    def test_registered_in_backend_registry(self):
        registry = BackendRegistry.singleton()
        assert "sql" in registry.list()
        factory = registry.get("sql")
        backend = factory()
        caps = backend.get_capabilities()
        assert caps.backend_name == "sql"
        assert caps.supports_merge is True
        assert "sql" in caps.supported_languages
