# CFA Demo — Governed execution for data pipelines
# Run in Colab, Databricks, or any Python 3.11+ environment
# pip install cfa-kernel

print("=" * 64)
print(" CFA Demo — Governed Execution")
print("=" * 64)

# =============================================================================
# 1. Setup — catalog with real fiscal data
# =============================================================================
CATALOG = {
    "datasets": {
        "nfe": {
            "classification": "high_volume", "size_gb": 4000,
            "pii_columns": [], "partition_column": "processing_date",
            "merge_keys": ["nfe_id"],
        },
        "clientes": {
            "classification": "sensitive", "size_gb": 0.5,
            "pii_columns": ["cpf", "email"], "partition_column": "processing_date",
            "merge_keys": ["cliente_id"],
        },
    }
}

from cfa.policy.engine import PolicyEngine
from cfa.types import (
    DatasetClassification, DatasetRef, ExecutionContext,
    PolicyAction, SignatureConstraints, StateSignature, TargetLayer,
)
from cfa.policy.catalog import validate_catalog
from cfa.audit.trail import AuditTrail

# =============================================================================
# 2. APPROVE — Safe signature passes
# =============================================================================
print("\n2. APPROVE — safe signature (PII protected, partition declared)")

sig_safe = StateSignature(
    domain="fiscal", intent="reconciliation", target_layer=TargetLayer.SILVER,
    datasets=(
        DatasetRef("nfe", DatasetClassification.HIGH_VOLUME, merge_keys=("nfe_id",)),
        DatasetRef("clientes", DatasetClassification.SENSITIVE,
                   pii_columns=("cpf", "email"), merge_keys=("cliente_id",)),
    ),
    constraints=SignatureConstraints(
        no_pii_raw=True, merge_key_required=True,
        enforce_types=True, partition_by=("processing_date",),
    ),
    execution_context=ExecutionContext("fiscal-v1", "catalog-v1", "ctx-001"),
)

engine = PolicyEngine()
result = engine.evaluate(sig_safe)
print(f"   decision : {result.action.value.upper()}")
print(f"   reasoning: {result.reasoning}")
assert result.action == PolicyAction.APPROVE

# =============================================================================
# 3. REPLAN — missing partition on high_volume (auto-corrected)
# =============================================================================
print("\n3. REPLAN — missing partition (auto-intervention corrects it)")

sig_replan = StateSignature(
    domain="fiscal", intent="reconciliation", target_layer=TargetLayer.SILVER,
    datasets=(
        DatasetRef("nfe", DatasetClassification.HIGH_VOLUME, merge_keys=("nfe_id",)),
    ),
    constraints=SignatureConstraints(
        no_pii_raw=True, merge_key_required=True,
        enforce_types=True, partition_by=(),  # <-- MISSING
    ),
    execution_context=ExecutionContext("fiscal-v1", "catalog-v1", "ctx-001"),
)

result = engine.evaluate(sig_replan)
print(f"   decision : {result.action.value.upper()}")
print(f"   reasoning: {result.reasoning}")
for f in result.faults:
    print(f"   fault    : {f.code}")
    if f.remediation:
        print(f"   fix      : {f.remediation[0]}")
assert result.action == PolicyAction.REPLAN, "Should trigger REPLAN for missing partition"

# =============================================================================
# 4. BLOCK — raw PII to Gold (multiple violations, terminal)
# =============================================================================
print("\n4. BLOCK — raw PII to Gold (terminal, cannot auto-correct)")

sig_unsafe = StateSignature(
    domain="fiscal", intent="reconciliation", target_layer=TargetLayer.GOLD,
    datasets=(
        DatasetRef("clientes", DatasetClassification.SENSITIVE,
                   pii_columns=("cpf", "email"), merge_keys=("cliente_id",)),
    ),
    constraints=SignatureConstraints(
        no_pii_raw=False,          # <-- RAW PII!
        merge_key_required=False,   # <-- NO MERGE KEY!
        enforce_types=True, partition_by=(),
    ),
    execution_context=ExecutionContext("fiscal-v1", "catalog-v1", "ctx-001"),
)

result = engine.evaluate(sig_unsafe)
print(f"   decision : {result.action.value.upper()}")
for f in result.faults:
    print(f"     [{f.severity.value}] {f.code}")
assert result.action == PolicyAction.BLOCK

# =============================================================================
# 5. Audit trail — SHA-256 hash chain
# =============================================================================
print("\n5. Audit trail (SHA-256 hash chain)")

trail = AuditTrail()
e1 = trail.record("demo-001", "policy", "evaluate", "approved",
                  signature_hash=sig_safe.signature_hash,
                  policy_bundle_version="fiscal-v1.0")
e2 = trail.record("demo-002", "policy", "evaluate", "blocked",
                  signature_hash=sig_unsafe.signature_hash,
                  policy_bundle_version="fiscal-v1.0")

print(f"   events     : {trail.event_count}")
print(f"   chain OK   : {trail.verify_chain()}")
print(f"   event hash : {e1.event_hash[:16]}...")
print(f"   prev  hash : {e2.previous_hash[:16]}...  (links to event above)")
print(f"   sig  hash  : {sig_safe.signature_hash[:16]}...")

# =============================================================================
# 6. Code generation — PySpark, SQL, dbt (real output)
# =============================================================================
print("\n6. Code generation — PySpark, SQL, dbt (real output)")

from cfa.core.planner import ExecutionPlanner
from cfa.backends import BackendRegistry

plan = ExecutionPlanner().plan(sig_safe)

# PySpark
backend = BackendRegistry.singleton().get("pyspark")()
code = backend.generate(plan)
print(f"   --- PySpark ({len(code.code.splitlines())} lines) ---")
for line in code.code.splitlines()[:12]:
    try: print(f"   {line}")
    except UnicodeEncodeError: print(f"   {line.encode('ascii',errors='replace').decode()}")

# SQL
backend = BackendRegistry.singleton().get("sql")()
code = backend.generate(plan)
print(f"\n   --- SQL ({len(code.code.splitlines())} lines) ---")
for line in code.code.splitlines()[:10]:
    print(f"   {line}")

# dbt config block
backend = BackendRegistry.singleton().get("dbt")()
code = backend.generate(plan)
print(f"\n   --- dbt ({len(code.code.splitlines())} lines) ---")
for line in code.code.splitlines()[:10]:
    print(f"   {line}")

# =============================================================================
# 7. Storage — SQLite with stats
# =============================================================================
print("\n7. SQLite storage (persistent, queryable)")

from cfa.storage import SqliteStorage, _sqlite_storage_stats
from cfa.audit.trail import AuditEvent
import os

store = SqliteStorage("cfa_demo.db")
store.ensure_schema()
for i in range(5):
    store.audit_append(AuditEvent(
        intent_id=f"demo-{i}", stage="policy", event_type="eval",
        outcome="approved" if i < 4 else "blocked",
    ))
stats = _sqlite_storage_stats(store)
print(f"   events    : {stats.audit_events_count}")
print(f"   file size : {stats.file_size_bytes} bytes")
print(f"   newest    : {stats.newest_record[:19]}")
store.close()
os.remove("cfa_demo.db")

print("\n" + "=" * 64)
print(" ALL 7 CHECKS PASSED — CFA governance working")
print("=" * 64)
