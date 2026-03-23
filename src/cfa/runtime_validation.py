"""
CFA Runtime Validation
======================
Post-execution behavioral validation.

Validates sandbox execution results against:
- Cardinality bounds (rows output within expected range)
- Cost ceiling (actual DBU vs declared maximum)
- Schema contract (output columns match expectation)
- Null ratio thresholds (per-column null limits)
- Shuffle size limits (data movement budget)

Produces Runtime Faults (FaultFamily.RUNTIME) — never throws exceptions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .sandbox import ExecutionMetrics, SandboxResult, SandboxOutcome, StepOutcome
from .types import (
    Fault,
    FaultFamily,
    FaultSeverity,
    PolicyAction,
    StateSignature,
)


# ── Thresholds ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RuntimeThresholds:
    """Configurable thresholds for runtime validation."""

    max_null_ratio: float = 0.10          # 10% null per column
    max_shuffle_mb: float = 500.0         # 500 MB shuffle budget
    min_rows: int = 0                     # minimum expected rows (0 = no check)
    max_rows: int = 0                     # maximum expected rows (0 = no check)
    max_cost_dbu: float | None = None     # cost ceiling (overridden by signature)
    required_output_columns: tuple[str, ...] = ()
    forbidden_output_columns: tuple[str, ...] = ()


# ── Runtime Validation Result ───────────────────────────────────────────────


@dataclass
class RuntimeValidationResult:
    """Result of runtime behavioral validation."""

    passed: bool = True
    faults: list[Fault] = field(default_factory=list)
    checks_performed: int = 0
    metrics_snapshot: dict[str, Any] = field(default_factory=dict)

    @property
    def fault_codes(self) -> list[str]:
        return [f.code for f in self.faults]

    def add_fault(self, fault: Fault) -> None:
        self.faults.append(fault)
        if fault.severity in (FaultSeverity.HIGH, FaultSeverity.CRITICAL):
            self.passed = False


# ── Runtime Validator ───────────────────────────────────────────────────────


class RuntimeValidator:
    """
    Validates SandboxResult metrics against thresholds and signature constraints.

    Called after sandbox execution completes (or partially completes).
    Produces RUNTIME faults that feed back into the decision engine.
    """

    def __init__(self, thresholds: RuntimeThresholds | None = None) -> None:
        self.thresholds = thresholds or RuntimeThresholds()

    def validate(
        self,
        sandbox_result: SandboxResult,
        signature: StateSignature,
        schema_contract: dict[str, Any] | None = None,
    ) -> RuntimeValidationResult:
        result = RuntimeValidationResult()
        metrics = sandbox_result.aggregate_metrics

        # Snapshot metrics for audit
        result.metrics_snapshot = {
            "rows_output": metrics.rows_output,
            "shuffle_mb": metrics.shuffle_mb,
            "cost_dbu": metrics.cost_dbu,
            "duration_seconds": metrics.duration_seconds,
            "null_counts": dict(metrics.null_counts),
            "output_schema": list(metrics.output_schema),
        }

        # Skip validation if sandbox panicked (environmental fault already captured)
        if sandbox_result.outcome == SandboxOutcome.PANIC:
            result.checks_performed = 0
            return result

        # ── Check 1: Cardinality ────────────────────────────────────────
        self._check_cardinality(metrics, result)

        # ── Check 2: Cost ceiling ───────────────────────────────────────
        self._check_cost(metrics, signature, result)

        # ── Check 3: Null ratio ─────────────────────────────────────────
        self._check_null_ratio(metrics, result)

        # ── Check 4: Shuffle budget ─────────────────────────────────────
        self._check_shuffle(metrics, result)

        # ── Check 5: Schema contract ────────────────────────────────────
        self._check_schema(metrics, schema_contract, result)

        # ── Check 6: Output columns from signature ──────────────────────
        self._check_output_columns(metrics, result)

        return result

    def _check_cardinality(self, metrics: ExecutionMetrics, result: RuntimeValidationResult) -> None:
        result.checks_performed += 1

        if self.thresholds.min_rows > 0 and metrics.rows_output < self.thresholds.min_rows:
            result.add_fault(Fault(
                code="RUNTIME_CARDINALITY_BELOW_MINIMUM",
                family=FaultFamily.RUNTIME,
                severity=FaultSeverity.HIGH,
                stage="runtime_validation",
                message=(
                    f"Output rows ({metrics.rows_output}) below minimum "
                    f"threshold ({self.thresholds.min_rows})."
                ),
                mandatory_action=PolicyAction.BLOCK,
                detected_before_execution=False,
            ))

        if self.thresholds.max_rows > 0 and metrics.rows_output > self.thresholds.max_rows:
            result.add_fault(Fault(
                code="RUNTIME_CARDINALITY_ABOVE_MAXIMUM",
                family=FaultFamily.RUNTIME,
                severity=FaultSeverity.HIGH,
                stage="runtime_validation",
                message=(
                    f"Output rows ({metrics.rows_output}) above maximum "
                    f"threshold ({self.thresholds.max_rows})."
                ),
                mandatory_action=PolicyAction.BLOCK,
                detected_before_execution=False,
            ))

    def _check_cost(
        self, metrics: ExecutionMetrics, signature: StateSignature, result: RuntimeValidationResult
    ) -> None:
        result.checks_performed += 1

        # Signature ceiling takes precedence over threshold default
        ceiling = signature.constraints.max_cost_dbu or self.thresholds.max_cost_dbu
        if ceiling is not None and metrics.cost_dbu > ceiling:
            result.add_fault(Fault(
                code="RUNTIME_COST_CEILING_EXCEEDED",
                family=FaultFamily.RUNTIME,
                severity=FaultSeverity.CRITICAL,
                stage="runtime_validation",
                message=(
                    f"Execution cost ({metrics.cost_dbu:.2f} DBU) exceeds "
                    f"ceiling ({ceiling:.2f} DBU)."
                ),
                mandatory_action=PolicyAction.BLOCK,
                detected_before_execution=False,
            ))

    def _check_null_ratio(self, metrics: ExecutionMetrics, result: RuntimeValidationResult) -> None:
        result.checks_performed += 1

        if metrics.rows_output == 0:
            return

        for column, count in metrics.null_counts.items():
            ratio = count / metrics.rows_output
            if ratio > self.thresholds.max_null_ratio:
                result.add_fault(Fault(
                    code=f"RUNTIME_NULL_RATIO_EXCEEDED_{column.upper()}",
                    family=FaultFamily.RUNTIME,
                    severity=FaultSeverity.WARNING,
                    stage="runtime_validation",
                    message=(
                        f"Column '{column}' null ratio ({ratio:.2%}) exceeds "
                        f"threshold ({self.thresholds.max_null_ratio:.2%})."
                    ),
                    mandatory_action=PolicyAction.APPROVE,
                    detected_before_execution=False,
                ))

    def _check_shuffle(self, metrics: ExecutionMetrics, result: RuntimeValidationResult) -> None:
        result.checks_performed += 1

        if metrics.shuffle_mb > self.thresholds.max_shuffle_mb:
            result.add_fault(Fault(
                code="RUNTIME_SHUFFLE_BUDGET_EXCEEDED",
                family=FaultFamily.RUNTIME,
                severity=FaultSeverity.HIGH,
                stage="runtime_validation",
                message=(
                    f"Shuffle size ({metrics.shuffle_mb:.1f} MB) exceeds "
                    f"budget ({self.thresholds.max_shuffle_mb:.1f} MB)."
                ),
                mandatory_action=PolicyAction.BLOCK,
                detected_before_execution=False,
            ))

    def _check_schema(
        self,
        metrics: ExecutionMetrics,
        schema_contract: dict[str, Any] | None,
        result: RuntimeValidationResult,
    ) -> None:
        if not schema_contract:
            return

        result.checks_performed += 1

        required = set(schema_contract.get("required_columns", []))
        forbidden = set(schema_contract.get("forbidden_columns", []))
        actual = set(metrics.output_schema)

        missing = required - actual
        if missing:
            result.add_fault(Fault(
                code="RUNTIME_SCHEMA_MISSING_COLUMNS",
                family=FaultFamily.RUNTIME,
                severity=FaultSeverity.HIGH,
                stage="runtime_validation",
                message=f"Output missing required columns: {sorted(missing)}.",
                mandatory_action=PolicyAction.BLOCK,
                detected_before_execution=False,
            ))

        leaked = forbidden & actual
        if leaked:
            result.add_fault(Fault(
                code="RUNTIME_SCHEMA_FORBIDDEN_COLUMNS",
                family=FaultFamily.RUNTIME,
                severity=FaultSeverity.CRITICAL,
                stage="runtime_validation",
                message=f"Output contains forbidden columns: {sorted(leaked)}.",
                mandatory_action=PolicyAction.BLOCK,
                detected_before_execution=False,
            ))

    def _check_output_columns(self, metrics: ExecutionMetrics, result: RuntimeValidationResult) -> None:
        if not self.thresholds.required_output_columns and not self.thresholds.forbidden_output_columns:
            return

        result.checks_performed += 1
        actual = set(metrics.output_schema)

        missing = set(self.thresholds.required_output_columns) - actual
        if missing:
            result.add_fault(Fault(
                code="RUNTIME_MISSING_REQUIRED_OUTPUT_COLUMNS",
                family=FaultFamily.RUNTIME,
                severity=FaultSeverity.HIGH,
                stage="runtime_validation",
                message=f"Output missing required columns: {sorted(missing)}.",
                mandatory_action=PolicyAction.BLOCK,
                detected_before_execution=False,
            ))

        leaked = set(self.thresholds.forbidden_output_columns) & actual
        if leaked:
            result.add_fault(Fault(
                code="RUNTIME_FORBIDDEN_OUTPUT_COLUMNS",
                family=FaultFamily.RUNTIME,
                severity=FaultSeverity.CRITICAL,
                stage="runtime_validation",
                message=f"Output contains forbidden columns: {sorted(leaked)}.",
                mandatory_action=PolicyAction.BLOCK,
                detected_before_execution=False,
            ))
