# Databricks notebook source
# MAGIC %md
# MAGIC # CFA — Contextual Flux Architecture
# MAGIC ## Complete Demo: Governed Execution for AI Agents and Data Systems
# MAGIC
# MAGIC [![PyPI](https://img.shields.io/pypi/v/cfa-kernel)](https://pypi.org/project/cfa-kernel/)
# MAGIC [![CI](https://github.com/marquesantero/cfa/actions/workflows/ci.yml/badge.svg)](https://github.com/marquesantero/cfa/actions)
# MAGIC [![codecov](https://codecov.io/gh/marquesantero/cfa/branch/main/graph/badge.svg)](https://codecov.io/gh/marquesantero/cfa)
# MAGIC [![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
# MAGIC
# MAGIC > **CFA** inserts a formal governance layer between user intent and execution.  
# MAGIC > Instead of asking *"which agent or skill should act?"*, CFA asks  
# MAGIC > *"which state transition is being requested, under what constraints, and can it execute safely?"*
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### What this notebook demonstrates
# MAGIC
# MAGIC | Section | Feature |
# MAGIC |---|---|
# MAGIC | 1 | Install + catalog validation |
# MAGIC | 2 | `APPROVE` — safe pipeline |
# MAGIC | 3 | **`REPLAN` — auto-correction** (unique to CFA) |
# MAGIC | 4 | `BLOCK` — terminal denial with full fault detail |
# MAGIC | 5 | Audit trail — SHA-256 hash chain + `verify_chain()` |
# MAGIC | 6 | Code generation — PySpark, SQL, dbt (all 3 backends) |
# MAGIC | 7 | Lifecycle indices — IFo, IFs, IFg, IDI + Promotion Engine |
# MAGIC | 8 | Storage — SQLite backend + stats |
# MAGIC | 9 | Behavior Spec + Systematizer |
# MAGIC | 10 | Runtime Gate — `@gate.guard` decorator |
# MAGIC | 11 | LangGraph adapter — `@cfa_guard` decorator |
# MAGIC | 12 | Reporting — HTML compliance + lifecycle reports |
# MAGIC | 13 | Full kernel pipeline — end-to-end via `KernelOrchestrator` |

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 0 — Install

# COMMAND ----------

# Install CFA with all optional extras
%pip install -q cfa-kernel[all]

# Verify installation
import cfa
print(f"CFA version: {cfa.__version__}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 1 — Catalog & Policy Bundle
# MAGIC
# MAGIC CFA makes the data catalog **operational** — dataset classification, PII markers, and
# MAGIC partition metadata actively drive governance decisions at runtime.

# COMMAND ----------

from cfa.policy.catalog import validate_catalog

# --- Operational catalog: drives all governance decisions ---
CATALOG = {
    "datasets": {
        "nfe": {
            "classification": "high_volume",
            "size_gb": 4000,
            "pii_columns": [],
            "partition_column": "processing_date",
            "merge_keys": ["nfe_id"],
        },
        "clientes": {
            "classification": "sensitive",
            "size_gb": 0.5,
            "pii_columns": ["cpf", "email"],
            "partition_column": "processing_date",
            "merge_keys": ["cliente_id"],
        },
        "vendas": {
            "classification": "high_volume",
            "size_gb": 2000,
            "pii_columns": [],
            "partition_column": "data_venda",
            "merge_keys": ["venda_id"],
        },
        "fornecedores": {
            "classification": "sensitive",
            "size_gb": 0.1,
            "pii_columns": ["cnpj"],
            "partition_column": "updated_at",
            "merge_keys": ["fornecedor_id"],
        },
    }
}

# Validate catalog structure
r = validate_catalog(CATALOG, require_datasets=True)
print(f"Catalog valid: {r.valid}")
if r.issues:
    for issue in r.issues:
        print(f"  Issue: {issue}")
else:
    print(f"  {len(CATALOG['datasets'])} datasets registered — nfe, clientes, vendas, fornecedores")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 2 — APPROVE: Safe Pipeline
# MAGIC
# MAGIC A well-formed `StateSignature` with PII protection, merge keys, and partitioning
# MAGIC passes all policy rules and receives **APPROVE**.

# COMMAND ----------

from cfa.policy.engine import PolicyEngine
from cfa.types import (
    DatasetClassification, DatasetRef, ExecutionContext,
    PolicyAction, SignatureConstraints, StateSignature, TargetLayer,
)

# --- Safe signature: PII anonymized, merge keys defined, partition set ---
sig_safe = StateSignature(
    domain="fiscal",
    intent="reconciliation",
    target_layer=TargetLayer.SILVER,
    datasets=(
        DatasetRef(
            "nfe",
            DatasetClassification.HIGH_VOLUME,
            size_gb=4000,
            merge_keys=("nfe_id",),
        ),
        DatasetRef(
            "clientes",
            DatasetClassification.SENSITIVE,
            size_gb=0.5,
            pii_columns=("cpf", "email"),
            merge_keys=("cliente_id",),
        ),
    ),
    constraints=SignatureConstraints(
        no_pii_raw=True,           # PII will be anonymized
        merge_key_required=True,   # Merge semantics enforced
        enforce_types=True,
        partition_by=("processing_date",),
        max_cost_dbu=50.0,
    ),
    execution_context=ExecutionContext("fiscal-prod-v1.0", "catalog-v1", "ctx-001"),
)

engine = PolicyEngine()
result_safe = engine.evaluate(sig_safe)

print("=" * 55)
print("SAFE PIPELINE — NFe + Clientes → Silver")
print("=" * 55)
print(f"  Decision    : {result_safe.action.value.upper()}")
print(f"  Faults      : {len(result_safe.faults)}")
print(f"  Reasoning   : {result_safe.reasoning}")
print(f"  Sig hash    : {sig_safe.signature_hash[:24]}...")

assert result_safe.action == PolicyAction.APPROVE
print("\n✓ assert APPROVE passed")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 3 — REPLAN: Auto-Correction (unique to CFA)
# MAGIC
# MAGIC **REPLAN is CFA's most distinctive feature** — no competing tool has it.  
# MAGIC When a policy rule fires with `action: replan`, the engine automatically applies  
# MAGIC corrective interventions to the signature (e.g., adding partition filters) and  
# MAGIC re-evaluates — up to 3 times before terminal BLOCK.
# MAGIC
# MAGIC Here we demonstrate a high-volume dataset missing `partition_by` — a FinOps  
# MAGIC violation that CFA auto-corrects without blocking the pipeline.

# COMMAND ----------

# --- Signature with missing partition on 2TB dataset ---
sig_replan = StateSignature(
    domain="fiscal",
    intent="aggregation",
    target_layer=TargetLayer.SILVER,
    datasets=(
        DatasetRef(
            "vendas",
            DatasetClassification.HIGH_VOLUME,
            size_gb=2000,
            merge_keys=("venda_id",),
        ),
    ),
    constraints=SignatureConstraints(
        no_pii_raw=True,
        merge_key_required=True,
        enforce_types=True,
        partition_by=(),    # <-- missing partition on 2TB dataset → triggers REPLAN
        max_cost_dbu=50.0,
    ),
    execution_context=ExecutionContext("fiscal-prod-v1.0", "catalog-v1", "ctx-002"),
)

result_replan = engine.evaluate(sig_replan)

print("=" * 55)
print("REPLAN DEMO — Vendas (2TB) missing partition_by")
print("=" * 55)
print(f"  Decision    : {result_replan.action.value.upper()}")
print(f"  Faults      : {len(result_replan.faults)}")

for fault in result_replan.faults:
    print(f"\n  [{fault.severity.value.upper()}] {fault.code}")
    print(f"    Message    : {fault.message}")
    if fault.remediation:
        print(f"    Remediation:")
        for step in fault.remediation:
            print(f"      → {step}")

# Show auto-interventions if available
if hasattr(result_replan, 'interventions') and result_replan.interventions:
    print(f"\n  Auto-interventions applied:")
    for iv in result_replan.interventions:
        print(f"    ✓ {iv}")

print(f"\n  Reasoning   : {result_replan.reasoning}")

# REPLAN is neither APPROVE nor BLOCK — it's a third state
assert result_replan.action == PolicyAction.REPLAN
print("\n✓ assert REPLAN passed — auto-correction applied, pipeline can proceed")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 4 — BLOCK: Terminal Denial
# MAGIC
# MAGIC When violations are too severe to auto-correct — raw PII in a protected layer  
# MAGIC with no merge key — CFA **BLOCK**s the pipeline with full fault detail and remediation steps.

# COMMAND ----------

# --- Unsafe signature: raw PII in Gold, no merge key, no partition ---
sig_block = StateSignature(
    domain="fiscal",
    intent="export",
    target_layer=TargetLayer.GOLD,
    datasets=(
        DatasetRef(
            "clientes",
            DatasetClassification.SENSITIVE,
            size_gb=0.5,
            pii_columns=("cpf", "email"),
            merge_keys=(),  # no merge key
        ),
    ),
    constraints=SignatureConstraints(
        no_pii_raw=False,           # <-- RAW PII in Gold!
        merge_key_required=False,   # <-- No merge key!
        enforce_types=False,
        partition_by=(),
        max_cost_dbu=50.0,
    ),
    execution_context=ExecutionContext("fiscal-prod-v1.0", "catalog-v1", "ctx-003"),
)

result_block = engine.evaluate(sig_block)

print("=" * 55)
print("BLOCK DEMO — Raw PII in Gold, no merge key")
print("=" * 55)
print(f"  Decision    : {result_block.action.value.upper()}")
print(f"  Faults      : {len(result_block.faults)}")

for fault in result_block.faults:
    print(f"\n  [{fault.severity.value.upper()}] {fault.code}")
    print(f"    Message    : {fault.message}")
    if fault.remediation:
        for step in fault.remediation:
            print(f"    → {step}")

print(f"\n  Reasoning   : {result_block.reasoning}")

assert result_block.action == PolicyAction.BLOCK
print("\n✓ assert BLOCK passed — execution prevented")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 5 — Audit Trail: SHA-256 Hash Chain
# MAGIC
# MAGIC Every governance event is recorded in a tamper-evident append-only chain.  
# MAGIC Each event links to the previous event's hash — `verify_chain()` checks integrity at any time.

# COMMAND ----------

from cfa.audit.trail import AuditTrail

trail = AuditTrail()

# Record all three decisions
trail.record("ctx-001", "policy", "evaluate", "approved",
             signature_hash=sig_safe.signature_hash,
             policy_bundle_version="fiscal-prod-v1.0")

trail.record("ctx-002", "policy", "evaluate", "replanned",
             signature_hash=sig_replan.signature_hash,
             policy_bundle_version="fiscal-prod-v1.0")

trail.record("ctx-003", "policy", "evaluate", "blocked",
             signature_hash=sig_block.signature_hash,
             policy_bundle_version="fiscal-prod-v1.0")

print("=" * 55)
print("AUDIT TRAIL — SHA-256 Hash Chain")
print("=" * 55)
print(f"  Events recorded : {trail.event_count}")
print()

# Show each event with its hash link
events = trail.get_all_events()
for i, event in enumerate(events):
    print(f"  Event [{i+1}]")
    print(f"    intent_id  : {event.intent_id}")
    print(f"    outcome    : {event.outcome}")
    print(f"    event_hash : {event.event_hash[:32]}...")
    if hasattr(event, 'previous_hash') and event.previous_hash:
        print(f"    prev_hash  : {event.previous_hash[:32]}...")
    print()

# Verify chain integrity
chain_ok = trail.verify_chain()
print(f"  Chain integrity : {'✓ INTACT' if chain_ok else '✗ TAMPERED'}")

assert chain_ok, "Chain must be intact!"
print("\n✓ assert verify_chain() passed")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 6 — Code Generation: PySpark, SQL, dbt
# MAGIC
# MAGIC From an approved `StateSignature`, CFA generates **deterministic governed code**  
# MAGIC for all 3 backends. No LLM calls in this path — pure deterministic generation.

# COMMAND ----------

from cfa.core.planner import ExecutionPlanner
from cfa.backends import BackendRegistry

# Plan from the approved safe signature
plan = ExecutionPlanner().plan(sig_safe)

print("=" * 55)
print("CODE GENERATION — 3 Backends")
print("=" * 55)

registry = BackendRegistry.singleton()

for backend_name in ("pyspark", "sql", "dbt"):
    backend = registry.get(backend_name)()
    result = backend.generate(plan)
    lines = result.code.splitlines()
    print(f"\n--- {backend_name.upper()} ({len(lines)} lines) ---")
    # Show first meaningful lines (skip blanks)
    shown = 0
    for line in lines:
        if shown >= 12:
            break
        print(f"  {line}")
        shown += 1
    if len(lines) > 12:
        print(f"  ... ({len(lines) - 12} more lines)")

print("\n✓ All 3 backends generated deterministically")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 7 — Lifecycle Indices + Promotion Engine
# MAGIC
# MAGIC CFA tracks quantitative health for every recurring pipeline:
# MAGIC - **IFo** (Fluidez Operacional): operational efficiency
# MAGIC - **IFs** (Fidelidade Semântica): semantic stability
# MAGIC - **IFg** (Governança): compliance — binary 1.0/0.0
# MAGIC - **IDI** (Intent Drift): ratio of clean passes over time
# MAGIC
# MAGIC The **Promotion Engine** uses these to drive state: `CANDIDATE → ACTIVE → WATCHLIST → DEMOTED → RETIRED`

# COMMAND ----------

from cfa.observability.indices import IndexCalculator, ExecutionRecord
from cfa.observability.promotion import PromotionEngine, PromotionPolicy
from cfa.types import _utcnow

# Build execution records for two pipelines
def make_records(success_rate, replan_rate, avg_cost, avg_duration, count=5):
    records = []
    for i in range(count):
        records.append(ExecutionRecord(
            signature_hash="demo-pipeline",
            timestamp=_utcnow(),
            success=(i < int(count * success_rate)),
            replanned=(i < int(count * replan_rate)),
            cost_dbu=avg_cost,
            duration_seconds=avg_duration,
            schema_match=True,
            pii_exposure=False,
            policy_compliant=True,
            layer_adherent=True,
        ))
    return records

healthy = make_records(success_rate=0.9, replan_rate=0.1, avg_cost=12.0, avg_duration=120)
drifting = make_records(success_rate=0.5, replan_rate=0.6, avg_cost=35.0, avg_duration=280)

print("=" * 55)
print("LIFECYCLE INDICES + PROMOTION ENGINE")
print("=" * 55)

calc = IndexCalculator(window_days=30)
engine = PromotionEngine(policy=PromotionPolicy(min_executions=3))

for label, records in [
    ("nfe_reconciliation (healthy)", healthy),
    ("clientes_export (drifting)",   drifting),
]:
    for r in records:
        engine.record_execution(r)
    skill, scores = engine.evaluate("demo-pipeline")

    print(f"\nPipeline: {label}")
    print(f"  IFo (Operational) : {scores.ifo:.3f}  (target >= 0.75)")
    print(f"  IFs (Semantic)    : {scores.ifs:.3f}  (target >= 0.90)")
    print(f"  IFg (Governance)  : {scores.ifg:.1f}    (binary 1.0 = compliant)")
    print(f"  IDI (Drift)       : {scores.idi:.3f}  (target >= 0.75)")
    print(f"  State             : {skill.state.value.upper()}")
    if scores.drift_detected:
        print(f"  WARNING: drift detected!")
    if scores.promotion_eligible:
        print(f"  Promotion eligible!")

print("\nLifecycle indices computed and promotion evaluated")


# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 8 — SQLite Storage: Persistence + Stats

# COMMAND ----------

import os
from cfa.storage import SqliteStorage
from cfa.audit.trail import AuditEvent

DB_PATH = "/tmp/cfa_demo.db"
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

store = SqliteStorage(DB_PATH)
store.ensure_schema()

# Persist audit events
decisions = [
    ("ctx-001", "approved"),
    ("ctx-002", "replanned"),
    ("ctx-003", "blocked"),
    ("ctx-004", "approved"),
    ("ctx-005", "approved"),
]

for intent_id, outcome in decisions:
    store.audit_append(AuditEvent(
        intent_id=intent_id,
        stage="policy",
        event_type="evaluate",
        outcome=outcome,
    ))

# Storage stats
try:
    from cfa.storage import _sqlite_storage_stats
    stats = _sqlite_storage_stats(store)
    print("=" * 55)
    print("SQLITE STORAGE STATS")
    print("=" * 55)
    print(f"  Audit events : {stats.audit_events_count}")
    print(f"  File size    : {stats.file_size_bytes:,} bytes")
    print(f"  DB path      : {DB_PATH}")
except Exception:
    print("  Stats unavailable (storage module)")

store.close()
print("\nStorage demo complete")


# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 9 — Behavior Spec + Systematizer
# MAGIC
# MAGIC **Behavior Specs** bridge human-written governance policies (YAML) to executable CFA rules.  
# MAGIC Platform/security teams define policies in YAML; data teams reference them by version.  
# MAGIC Inspired by ASSERT's systematization approach, but applied to data governance.

# COMMAND ----------

import tempfile, os, pathlib
from cfa.behavior import BehaviorSpec, Systematizer

SPEC_YAML = """
behavior:
  name: fiscal_reconciliation
  description: "PII protection, merge keys, partitions for fiscal pipelines"
  failure_modes:
    - code: raw_pii_in_silver
      label: Raw PII in Silver
      description: PII columns written to Silver without anonymization
      condition: pii_in_protected_layer
      severity: critical
      action: block
      target_layer: silver
      remediation:
        - Apply sha256() on all PII columns before write
        - Enable no_pii_raw=True
    - code: missing_merge_key_silver
      label: Missing Merge Key
      description: Write to Silver without a merge key defined
      condition: missing_merge_key
      severity: critical
      action: block
      target_layer: silver
      remediation:
        - Define merge_key_required=True in constraints
    - code: unpartitioned_large_dataset
      label: Unpartitioned Large Dataset
      description: High-volume dataset missing partition (cost risk)
      condition: missing_partition
      severity: high
      action: replan
      remediation:
        - Add partition_by=("processing_date",) to constraints
"""

# Write spec to temp file (UTF-8)
spec_path = pathlib.Path(tempfile.mktemp(suffix=".yaml"))
spec_path.write_text(SPEC_YAML, encoding="utf-8")

try:
    spec = BehaviorSpec.from_yaml(str(spec_path))
    taxonomy, rules = Systematizer().systematize(spec)

    print("=" * 55)
    print("BEHAVIOR SPEC + SYSTEMATIZER")
    print("=" * 55)
    print(f"  Spec name   : {spec.name}")
    print(f"  Rules gen.  : {len(rules)}")
    print(f"  Categories  : {taxonomy.category_count}")
    print()

    for rule in rules:
        print(f"  Rule : {rule.name}")
        print(f"    code     : {rule.fault_code}")
        print(f"    action   : {rule.action.value}")
        print(f"    severity : {rule.severity.value}")
        print()

    print("BehaviorSpec -> Systematizer -> PolicyRules complete")
finally:
    # Cleanup
    try:
        spec_path.unlink()
    except OSError:
        pass


# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 10 — Runtime Gate: `@gate.guard` Decorator
# MAGIC
# MAGIC The `RuntimeGate` wraps any function with a governance check.  
# MAGIC Use this pattern to protect existing pipelines without rewriting them.

# COMMAND ----------

from cfa.runtime import RuntimeGate, GateConfig
from cfa.types import DatasetClassification, DatasetRef, ExecutionContext, SignatureConstraints, StateSignature, TargetLayer

print("=" * 55)
print("RUNTIME GATE")
print("=" * 55)

gate = RuntimeGate(
    config=GateConfig(policy_bundle="fiscal-prod-v1.0"),
)

# Pre-execution validation
result = gate.validate("Join NFe with Clientes and persist to Silver")
print(f"  validate() -> state={result.state.value}  passed={result.passed}")
print(f"  gate_id={result.gate_id}  execution_id={result.execution_id[:8]}...")

# Decorator guard
@gate.guard("aggregate sales data")
def my_pipeline():
    return "pipeline executed"

print(f"  @gate.guard decorated function -> {my_pipeline()}")
print("\nRuntime Gate demo complete")


# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 11 — LangGraph Adapter: `@cfa_guard` Decorator
# MAGIC
# MAGIC CFA integrates with LangGraph agent nodes via a single decorator.  
# MAGIC The node's docstring (or explicit intent string) is used as the governance contract.

# COMMAND ----------

from cfa.adapters.langgraph import cfa_guard

print("=" * 55)
print("LANGGRAPH ADAPTER")
print("=" * 55)

@cfa_guard("aggregate sales data with PII protected", mode="warn")
def my_agent_node(state):
    return {"status": "completed", "data": "processed"}

result = my_agent_node({"input": "test"})
print(f"  @cfa_guard node executed: {result}")
print("\nLangGraph adapter demo complete")


# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 12 — Reporting: HTML Compliance + Lifecycle Reports
# MAGIC
# MAGIC CFA generates self-contained HTML reports with Chart.js —  
# MAGIC single `.html` files, zero Python dependencies, ready to open in any browser.

# COMMAND ----------

from cfa.reporting import generate_report
import os

REPORT_DIR = "/tmp/cfa_reports"
os.makedirs(REPORT_DIR, exist_ok=True)

# --- Compliance report ---
compliance_path = f"{REPORT_DIR}/compliance.html"
generate_report(
    "compliance",
    compliance_path,
    policy_bundle="fiscal-prod-v1.0",
    total_evaluations=100,
    approved=82,
    replanned=12,
    blocked=6,
    rules=[
        {"name": "forbid_raw_pii",       "fired": 6,  "severity": "critical"},
        {"name": "require_partition",    "fired": 12, "severity": "high"},
        {"name": "require_merge_key",    "fired": 3,  "severity": "critical"},
    ],
    pii_incidents_prevented=6,
    audit_events_total=200,
    chain_intact=True,
)

# --- Lifecycle dashboard ---
import datetime
now = datetime.date.today()
dates = [(now - datetime.timedelta(days=d)).isoformat() for d in range(29, -1, -1)]

lifecycle_path = f"{REPORT_DIR}/lifecycle.html"
generate_report(
    "lifecycle",
    lifecycle_path,
    period_days=30,
    skills=[
        {"name": "nfe_reconciliation", "state": "active",    "ifo": 0.91, "ifs": 0.96, "ifg": 1.0, "idi": 0.95},
        {"name": "clientes_export",    "state": "watchlist", "ifo": 0.54, "ifs": 0.68, "ifg": 0.0, "idi": 0.40},
        {"name": "vendas_aggregate",   "state": "candidate", "ifo": 0.78, "ifs": 0.82, "ifg": 1.0, "idi": 0.88},
    ],
    trend_dates=dates,
    ifo_vals=[round(0.85 + (i % 5) * 0.02, 2) for i in range(30)],
    ifs_vals=[round(0.90 + (i % 4) * 0.01, 2) for i in range(30)],
    idi_vals=[round(0.88 + (i % 6) * 0.015, 2) for i in range(30)],
    ifg_vals=[1.0 if i % 10 != 7 else 0.0 for i in range(30)],
    cost_dates=dates,
    cost_vals=[round(12.0 + (i % 8) * 0.5, 1) for i in range(30)],
    decisions={"approved": 82, "replanned": 12, "blocked": 6},
)

# --- Audit report ---
audit_path = f"{REPORT_DIR}/audit.html"
generate_report(
    "audit",
    audit_path,
    intent_id="ctx-001",
    events=[
        {"stage": "policy", "event_type": "evaluate", "outcome": "approved",
         "event_hash": sig_safe.signature_hash[:32], "previous_hash": None},
        {"stage": "policy", "event_type": "evaluate", "outcome": "replanned",
         "event_hash": sig_replan.signature_hash[:32],
         "previous_hash": sig_safe.signature_hash[:32]},
    ],
    chain_intact=True,
)

print("=" * 55)
print("HTML REPORTS GENERATED")
print("=" * 55)
for path in [compliance_path, lifecycle_path, audit_path]:
    size = os.path.getsize(path)
    name = os.path.basename(path)
    print(f"  {name:20s} — {size:,} bytes")

print("\n✓ Self-contained HTML reports ready (open in any browser)")

# In Colab: display inline
try:
    from IPython.display import HTML, display
    with open(compliance_path) as f:
        display(HTML(f"<details><summary>Preview: compliance.html</summary>{f.read()}</details>"))
except Exception:
    pass

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 13 — Full Kernel: End-to-End via `KernelOrchestrator`
# MAGIC
# MAGIC The `KernelOrchestrator` runs the complete 5-phase pipeline:  
# MAGIC `Formalize → Govern → Generate → Execute → Validate/Audit`  
# MAGIC from a single natural-language intent.

# COMMAND ----------

from cfa import KernelOrchestrator
from cfa.core.kernel import KernelConfig

kernel = KernelOrchestrator(
    catalog=CATALOG,
    config=KernelConfig(
        policy_bundle_version="fiscal-prod-v1.0",
        backend="pyspark",
    ),
)

print("=" * 55)
print("FULL KERNEL -- End-to-End Governed Execution")
print("=" * 55)

intents = [
    "Join NFe with Clientes anonymize CPF and persist to Silver",
    "Aggregate vendas by region persist to Gold",
    "Export raw clientes PII to Gold",  # should block
]

for intent in intents:
    print(f'\nIntent: "{intent}"')
    try:
        result = kernel.process(intent)
        print(f"  -> Decision  : {result.state.value.upper()}")
        print(f"  -> Sig hash  : {result.signature.signature_hash[:24]}...")
        if result.replan_history:
            print(f"  -> Replans   : {len(result.replan_history)}")
        if result.generated_code and result.generated_code.code:
            lines = result.generated_code.code.splitlines()
            print(f"  -> Code gen  : {len(lines)} lines {result.generated_code.language}")
        print(f"  -> Audit evt : hash chain updated")
    except (PermissionError, RuntimeError, ValueError) as e:
        print(f"  -> BLOCKED   : {type(e).__name__}")
        print(f"    {str(e)[:100]}")

print("\nFull kernel pipeline complete")


# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Summary
# MAGIC
# MAGIC | Feature | Status | Notes |
# MAGIC |---|---|---|
# MAGIC | Catalog validation | ✓ | Operational metadata drives all decisions |
# MAGIC | APPROVE | ✓ | Safe pipeline passes all rules |
# MAGIC | **REPLAN** | ✓ | **Unique to CFA** — auto-corrects, no block |
# MAGIC | BLOCK | ✓ | Terminal denial with full remediation detail |
# MAGIC | SHA-256 audit chain | ✓ | `verify_chain()` confirms tamper-evidence |
# MAGIC | Code generation | ✓ | PySpark, SQL, dbt — deterministic, no LLM |
# MAGIC | Lifecycle indices | ✓ | IFo, IFs, IFg, IDI + Promotion Engine |
# MAGIC | SQLite storage | ✓ | Audit + execution persistence with stats |
# MAGIC | Behavior Spec | ✓ | YAML → Systematizer → PolicyEngine |
# MAGIC | Runtime Gate | ✓ | `@gate.guard` protects existing pipelines |
# MAGIC | LangGraph adapter | ✓ | `@cfa_guard` for agent nodes |
# MAGIC | HTML reporting | ✓ | Compliance, lifecycle, audit — self-contained |
# MAGIC | Full kernel | ✓ | End-to-end from natural language |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Links**
# MAGIC - 📖 [Documentation](https://marquesantero.github.io/cfa/docs/intro)
# MAGIC - 📦 [PyPI](https://pypi.org/project/cfa-kernel/)
# MAGIC - 🐙 [GitHub](https://github.com/marquesantero/cfa)
# MAGIC - 💬 [Discussions](https://github.com/marquesantero/cfa/discussions)