"""
cfa.governance -- Uso standalone
=================================
Valida operacoes de dados contra regras de governanca.
Sem LLM. Sem execucao. Sem infraestrutura.

Caso de uso:
  Voce ja tem um pipeline Airflow/Dagster/script.
  Quer adicionar governanca ANTES de executar.

  Antes:
    spark.read("nfe").join(spark.read("clientes")).write("silver")

  Depois:
    sig = montar_signature(...)
    resultado = engine.evaluate(sig)
    if resultado.is_blocked:
        raise "Bloqueado por governanca"
    # so entao executa
"""

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
    Fault,
)

# ── 1. Montar a signature do que voce quer fazer ────────────────────────────
# Isso substitui a "descricao em linguagem natural".
# Voce sabe exatamente o que o pipeline faz — declara aqui.

sig = StateSignature(
    domain="fiscal",
    intent="reconciliation",
    target_layer=TargetLayer.SILVER,
    datasets=(
        DatasetRef("nfe", DatasetClassification.HIGH_VOLUME, size_gb=4000),
        DatasetRef("clientes", DatasetClassification.SENSITIVE, size_gb=0.5, pii_columns=("cpf",)),
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

# ── 2. Validar contra Policy Engine ─────────────────────────────────────────
# Usa as 7 regras default (PII, FinOps, Contract, Cost)

engine = PolicyEngine()
result = engine.evaluate(sig)

print(f"Acao: {result.action.value}")
print(f"Faults: {[f.code for f in result.faults]}")
print(f"Bloqueado: {result.is_blocked}")

if result.is_blocked:
    print(f"Motivo: {result.reasoning}")
    for fault in result.faults:
        print(f"  [{fault.severity.value}] {fault.code}: {fault.message}")
        for r in fault.remediation:
            print(f"    -> {r}")

# ── 3. Adicionar regra customizada ──────────────────────────────────────────

regra_fiscal = PolicyRule(
    name="fiscal_requer_particao_diaria",
    condition=lambda s: (
        s.domain == "fiscal"
        and "processing_date" not in s.constraints.partition_by
    ),
    action=PolicyAction.BLOCK,
    fault_code="FISCAL_SEM_PARTICAO_DIARIA",
    fault_family=FaultFamily.SEMANTIC,
    severity=FaultSeverity.CRITICAL,
    message="Pipeline fiscal DEVE ter particao por processing_date.",
)

engine.add_rule(regra_fiscal)
result2 = engine.evaluate(sig)
print(f"\nCom regra fiscal: {result2.action.value}")

# ── 4. Validar codigo PySpark (opcional) ─────────────────────────────────────

validator = StaticValidator()
from cfa.codegen import GeneratedCode

code = GeneratedCode(
    plan_signature_hash="test",
    intent_id="test",
    language="pyspark",
    code='df.collect()',  # proibido!
)
sv = validator.validate(code, sig)
print(f"\nStatic validation: {'PASSED' if sv.passed else 'FAILED'}")
if not sv.passed:
    print(f"  Faults: {sv.fault_codes}")
