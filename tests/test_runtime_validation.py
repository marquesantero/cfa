"""Tests for CFA Runtime Validation."""

from cfa.runtime_validation import RuntimeThresholds, RuntimeValidationResult, RuntimeValidator
from cfa.sandbox import ExecutionMetrics, SandboxOutcome, SandboxResult, StepOutcome, StepResult
from conftest import make_signature


def _make_sandbox_result(
    rows: int = 100_000,
    shuffle_mb: float = 50.0,
    cost_dbu: float = 5.0,
    null_ratio: float = 0.01,
    schema: list[str] | None = None,
    outcome: SandboxOutcome = SandboxOutcome.COMPLETED,
) -> SandboxResult:
    schema = schema or ["nfe_id", "cpf_hash", "processing_date"]
    null_counts = {col: int(rows * null_ratio) for col in schema}
    metrics = ExecutionMetrics(
        rows_output=rows,
        shuffle_bytes=int(shuffle_mb * 1024 * 1024),
        cost_dbu=cost_dbu,
        duration_seconds=2.5,
        null_counts=null_counts,
        output_schema=schema,
    )
    return SandboxResult(
        outcome=outcome,
        step_results=[StepResult(step_id="test_step", outcome=StepOutcome.SUCCESS, metrics=metrics)],
        aggregate_metrics=metrics,
    )


class TestRuntimeValidatorCardinality:
    def test_passes_within_bounds(self):
        validator = RuntimeValidator(RuntimeThresholds(min_rows=1000, max_rows=200_000))
        result = validator.validate(_make_sandbox_result(rows=100_000), make_signature())
        assert result.passed
        assert "RUNTIME_CARDINALITY_BELOW_MINIMUM" not in result.fault_codes

    def test_blocks_below_minimum(self):
        validator = RuntimeValidator(RuntimeThresholds(min_rows=200_000))
        result = validator.validate(_make_sandbox_result(rows=100_000), make_signature())
        assert not result.passed
        assert "RUNTIME_CARDINALITY_BELOW_MINIMUM" in result.fault_codes

    def test_blocks_above_maximum(self):
        validator = RuntimeValidator(RuntimeThresholds(max_rows=50_000))
        result = validator.validate(_make_sandbox_result(rows=100_000), make_signature())
        assert not result.passed
        assert "RUNTIME_CARDINALITY_ABOVE_MAXIMUM" in result.fault_codes


class TestRuntimeValidatorCost:
    def test_passes_under_ceiling(self):
        sig = make_signature(max_cost_dbu=10.0)
        validator = RuntimeValidator()
        result = validator.validate(_make_sandbox_result(cost_dbu=5.0), sig)
        assert "RUNTIME_COST_CEILING_EXCEEDED" not in result.fault_codes

    def test_blocks_over_ceiling_from_signature(self):
        sig = make_signature(max_cost_dbu=3.0)
        validator = RuntimeValidator()
        result = validator.validate(_make_sandbox_result(cost_dbu=5.0), sig)
        assert not result.passed
        assert "RUNTIME_COST_CEILING_EXCEEDED" in result.fault_codes

    def test_blocks_over_ceiling_from_threshold(self):
        validator = RuntimeValidator(RuntimeThresholds(max_cost_dbu=2.0))
        result = validator.validate(_make_sandbox_result(cost_dbu=5.0), make_signature())
        assert not result.passed
        assert "RUNTIME_COST_CEILING_EXCEEDED" in result.fault_codes


class TestRuntimeValidatorNullRatio:
    def test_passes_low_null_ratio(self):
        validator = RuntimeValidator(RuntimeThresholds(max_null_ratio=0.10))
        result = validator.validate(_make_sandbox_result(null_ratio=0.01), make_signature())
        assert result.passed

    def test_warns_high_null_ratio(self):
        validator = RuntimeValidator(RuntimeThresholds(max_null_ratio=0.05))
        result = validator.validate(_make_sandbox_result(null_ratio=0.15), make_signature())
        # Null ratio produces WARNING, not BLOCK — so passed stays True
        null_faults = [f for f in result.fault_codes if "NULL_RATIO" in f]
        assert len(null_faults) > 0


class TestRuntimeValidatorShuffle:
    def test_passes_within_budget(self):
        validator = RuntimeValidator(RuntimeThresholds(max_shuffle_mb=500.0))
        result = validator.validate(_make_sandbox_result(shuffle_mb=50.0), make_signature())
        assert "RUNTIME_SHUFFLE_BUDGET_EXCEEDED" not in result.fault_codes

    def test_blocks_over_budget(self):
        validator = RuntimeValidator(RuntimeThresholds(max_shuffle_mb=10.0))
        result = validator.validate(_make_sandbox_result(shuffle_mb=50.0), make_signature())
        assert not result.passed
        assert "RUNTIME_SHUFFLE_BUDGET_EXCEEDED" in result.fault_codes


class TestRuntimeValidatorSchema:
    def test_schema_missing_required_columns(self):
        validator = RuntimeValidator()
        schema_contract = {"required_columns": ["nfe_id", "total_value"]}
        result = validator.validate(
            _make_sandbox_result(schema=["nfe_id", "cpf_hash"]),
            make_signature(),
            schema_contract=schema_contract,
        )
        assert not result.passed
        assert "RUNTIME_SCHEMA_MISSING_COLUMNS" in result.fault_codes

    def test_schema_forbidden_columns(self):
        validator = RuntimeValidator()
        schema_contract = {"forbidden_columns": ["cpf", "email"]}
        result = validator.validate(
            _make_sandbox_result(schema=["nfe_id", "cpf", "processing_date"]),
            make_signature(),
            schema_contract=schema_contract,
        )
        assert not result.passed
        assert "RUNTIME_SCHEMA_FORBIDDEN_COLUMNS" in result.fault_codes

    def test_skips_validation_on_panic(self):
        validator = RuntimeValidator(RuntimeThresholds(min_rows=1000))
        sr = _make_sandbox_result(rows=0, outcome=SandboxOutcome.PANIC)
        result = validator.validate(sr, make_signature())
        assert result.passed
        assert result.checks_performed == 0
