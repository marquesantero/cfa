"""
cfa.governance -- Governanca standalone
========================================
Valida operacoes de dados contra regras de governanca SEM precisar de LLM,
SEM executar codigo, SEM infraestrutura.

Funciona em cima de qualquer pipeline existente (Airflow, Dagster, scripts).
Voce monta a StateSignature a mao e valida.

Uso:
    from cfa.governance import PolicyEngine, StaticValidator, StateSignature

    # Monta a signature do que voce quer fazer
    sig = StateSignature(
        domain="fiscal",
        intent="reconciliation",
        target_layer=TargetLayer.SILVER,
        datasets=(DatasetRef("nfe", DatasetClassification.HIGH_VOLUME),),
        constraints=SignatureConstraints(partition_by=("processing_date",)),
        execution_context=ExecutionContext("v1", "c1", "r1"),
    )

    # Valida contra regras de governanca
    engine = PolicyEngine()
    result = engine.evaluate(sig)
    if result.action == PolicyAction.BLOCK:
        raise Exception(f"Blocked: {result.reasoning}")

    # Valida codigo gerado (opcional)
    validator = StaticValidator()
    sv = validator.validate(code, sig)
    if not sv.passed:
        raise Exception(f"Static validation failed: {sv.fault_codes}")
"""

from ..types import (
    DatasetClassification,
    DatasetRef,
    ExecutionContext,
    Fault,
    FaultFamily,
    FaultSeverity,
    PolicyAction,
    PolicyResult,
    SignatureConstraints,
    StateSignature,
    TargetLayer,
)
from ..policy import PolicyEngine, PolicyRule, build_default_ruleset
from ..static_validation import StaticValidator, StaticValidationResult
from ..runtime_validation import RuntimeValidator, RuntimeThresholds, RuntimeValidationResult

__all__ = [
    # Types
    "DatasetClassification",
    "DatasetRef",
    "ExecutionContext",
    "Fault",
    "FaultFamily",
    "FaultSeverity",
    "PolicyAction",
    "PolicyResult",
    "SignatureConstraints",
    "StateSignature",
    "TargetLayer",
    # Policy
    "PolicyEngine",
    "PolicyRule",
    "build_default_ruleset",
    # Validation
    "StaticValidator",
    "StaticValidationResult",
    "RuntimeValidator",
    "RuntimeThresholds",
    "RuntimeValidationResult",
]
