"""
Standalone governance example.

Use this when you already have a pipeline and want a governance gate before
any execution happens.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cfa.governance import (
    PolicyEngine,
    PolicyRule,
    StaticValidator,
    DatasetClassification,
    DatasetRef,
    ExecutionContext,
    SignatureConstraints,
    StateSignature,
    TargetLayer,
    PolicyAction,
    FaultFamily,
    FaultSeverity,
)

from cfa.codegen import GeneratedCode


signature = StateSignature(
    domain="fiscal",
    intent="reconciliation",
    target_layer=TargetLayer.SILVER,
    datasets=(
        DatasetRef("nfe", DatasetClassification.HIGH_VOLUME, size_gb=4000),
        DatasetRef(
            "clientes",
            DatasetClassification.SENSITIVE,
            size_gb=0.5,
            pii_columns=("cpf",),
        ),
    ),
    constraints=SignatureConstraints(
        no_pii_raw=True,
        merge_key_required=True,
        enforce_types=True,
        partition_by=("processing_date",),
        max_cost_dbu=50.0,
    ),
    execution_context=ExecutionContext("v1.0", "catalog_2026", "ctx_1"),
)

engine = PolicyEngine()
result = engine.evaluate(signature)

print(f"Action:    {result.action.value}")
print(f"Faults:    {[f.code for f in result.faults]}")
print(f"Blocked:   {result.is_blocked}")

if result.is_blocked:
    print(f"Reason:    {result.reasoning}")
    for fault in result.faults:
        print(f"  [{fault.severity.value}] {fault.code}: {fault.message}")
        for remediation in fault.remediation:
            print(f"    -> {remediation}")

daily_partition_rule = PolicyRule(
    name="fiscal_requires_daily_partition",
    condition=lambda s: (
        s.domain == "fiscal"
        and "processing_date" not in s.constraints.partition_by
    ),
    action=PolicyAction.BLOCK,
    fault_code="FISCAL_MISSING_DAILY_PARTITION",
    fault_family=FaultFamily.SEMANTIC,
    severity=FaultSeverity.CRITICAL,
    message="Fiscal pipelines must partition by processing_date.",
)

engine.add_rule(daily_partition_rule)
result_with_custom_rule = engine.evaluate(signature)
print(f"\nWith custom rule: {result_with_custom_rule.action.value}")

validator = StaticValidator()
generated = GeneratedCode(
    plan_signature_hash="test",
    intent_id="test",
    language="pyspark",
    code="df.collect()",
)
validation = validator.validate(generated, signature)
print(f"\nStatic validation: {'PASSED' if validation.passed else 'FAILED'}")
if not validation.passed:
    print(f"Faults: {validation.fault_codes}")
