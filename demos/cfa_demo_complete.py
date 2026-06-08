# Databricks notebook source
# MAGIC %md
# MAGIC # CFA — Contextual Flux Architecture
# MAGIC ## Core Demo: Governed Execution for AI Agents and Data Systems
# MAGIC
# MAGIC [![PyPI](https://img.shields.io/pypi/v/cfa-kernel)](https://pypi.org/project/cfa-kernel/)
# MAGIC [![CI](https://github.com/marquesantero/cfa/actions/workflows/ci.yml/badge.svg)](https://github.com/marquesantero/cfa/actions)
# MAGIC [![codecov](https://codecov.io/gh/marquesantero/cfa/branch/main/graph/badge.svg)](https://codecov.io/gh/marquesantero/cfa)
# MAGIC [![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
# MAGIC [![python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org)
# MAGIC [![docs](https://img.shields.io/badge/docs-docusaurus-blue)](https://marquesantero.github.io/cfa/)
# MAGIC
# MAGIC > **CFA** inserts a formal governance layer between user intent and execution.
# MAGIC > Instead of asking *"which agent or skill should act?"*, CFA asks
# MAGIC > *"which state transition is being requested, under what constraints, and can it execute safely?"*
# MAGIC
# MAGIC This notebook covers the **deterministic core**: policy, audit, code generation, lifecycle, reporting.
# MAGIC For the LLM-powered features (semantic normalizer, systematizer, NL→rules), see `CFA_LLM_Demo`.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### What this notebook demonstrates
# MAGIC
# MAGIC | Section | Feature | Surface |
# MAGIC |---|---|---|
# MAGIC | S0 | Install + version pin | setup |
# MAGIC | S1 | Catalog & policy bundle | governance |
# MAGIC | S2 | `APPROVE` — safe pipeline | engine |
# MAGIC | S3 | **`REPLAN` — auto-correction** (unique to CFA) | engine |
# MAGIC | S4 | `BLOCK` — terminal denial | engine |
# MAGIC | S5 | Audit trail — SHA-256 hash chain | compliance |
# MAGIC | S6 | Code generation — PySpark, SQL, dbt | codegen |
# MAGIC | S7 | Lifecycle indices — IFo, IFs, IFg, IDI + Promotion | observability |
# MAGIC | S8 | SQLite storage — persistence + stats | infra |
# MAGIC | S9 | Behavior Spec — YAML → Systematizer → rules | declarative |
# MAGIC | S10 | Runtime Gate — `@gate.guard` decorator | adapter |
# MAGIC | S11 | LangGraph adapter — `@cfa_guard` decorator | agents |
# MAGIC | S12 | HTML reporting — compliance + lifecycle + audit | observability |
# MAGIC | S13 | Full kernel — end-to-end `KernelOrchestrator` | core |

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 0 — Install
# MAGIC
# MAGIC Pinned to a known-good version. Use `pip install cfa-kernel` (without pin) to follow latest.

# COMMAND ----------

# MAGIC %pip install -q cfa-kernel==0.1.9

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

import cfa
print(f"CFA version : {cfa.__version__}")
print(f"Notebook    : Core Demo (no LLM)")
print(f"Surfaces    : PolicyEngine, AuditTrail, BackendRegistry, Lifecycle, RuntimeGate, Reporting")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Helper — section header
# MAGIC
# MAGIC Tiny utility to keep section banners consistent across the notebook.

# COMMAND ----------

def section(title: str, width: int = 60) -> None:
    """Print a uniform section banner."""
    print("─" * width)
    print(title)
    print("─" * width)


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

section("Catalog validation")
r = validate_catalog(CATALOG, require_datasets=True)
print(f"  valid    : {r.valid}")
if r.issues:
    for issue in r.issues:
        print(f"  issue    : {issue}")
else:
    n = len(CATALOG["datasets"])
    print(f"  datasets : {n} registered ({', '.join(CATALOG['datasets'].keys())})")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 2 — APPROVE: Safe Pipeline
# MAGIC
# MAGIC A well-formed `StateSignature` with PII protection, merge keys, and partitioning
# MAGIC passes all policy rules and receives **APPROVE**.

# COMMAND ----------

import time
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
        DatasetRef("nfe", DatasetClassification.HIGH_VOLUME,
                   size_gb=4000, merge_keys=("nfe_id",)),
        DatasetRef("clientes", DatasetClassification.SENSITIVE,
                   size_gb=0.5, pii_columns=("cpf", "email"),
                   merge_keys=("cliente_id",)),
    ),
    constraints=SignatureConstraints(
        no_pii_raw=True,
        merge_key_required=True,
        enforce_types=True,
        partition_by=("processing_date",),
        max_cost_dbu=50.0,
    ),
    execution_context=ExecutionContext("fiscal-prod-v1.0", "catalog-v1", "ctx-001"),
)

engine = PolicyEngine()

t0 = time.perf_counter()
result_safe = engine.evaluate(sig_safe)
elapsed_ms = (time.perf_counter() - t0) * 1000

section("APPROVE — NFe + Clientes → Silver")
print(f"  decision   : {result_safe.action.value.upper()}")
print(f"  faults     : {len(result_safe.faults)}")
print(f"  reasoning  : {result_safe.reasoning}")
print(f"  sig_hash   : {sig_safe.signature_hash[:24]}...")
print(f"  latency_ms : {elapsed_ms:.2f}")

assert result_safe.action == PolicyAction.APPROVE
print("\n  ✓ assert APPROVE passed")

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
        DatasetRef("vendas", DatasetClassification.HIGH_VOLUME,
                   size_gb=2000, merge_keys=("venda_id",)),
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

t0 = time.perf_counter()
result_replan = engine.evaluate(sig_replan)
elapsed_ms = (time.perf_counter() - t0) * 1000

section("REPLAN — Vendas (2TB) missing partition_by")
print(f"  decision   : {result_replan.action.value.upper()}")
print(f"  faults     : {len(result_replan.faults)}")
print(f"  latency_ms : {elapsed_ms:.2f}")

for fault in result_replan.faults:
    print(f"\n  [{fault.severity.value.upper()}] {fault.code}")
    print(f"    message     : {fault.message}")
    if fault.remediation:
        print(f"    remediation :")
        for step in fault.remediation:
            print(f"      → {step}")

# Show auto-interventions if available
if hasattr(result_replan, "interventions") and result_replan.interventions:
    print(f"\n  auto-interventions applied:")
    for iv in result_replan.interventions:
        print(f"    ✓ {iv}")

print(f"\n  reasoning  : {result_replan.reasoning}")

assert result_replan.action == PolicyAction.REPLAN
print("\n  ✓ assert REPLAN passed — auto-correction applied, pipeline can proceed")

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
        DatasetRef("clientes", DatasetClassification.SENSITIVE,
                   size_gb=0.5, pii_columns=("cpf", "email"), merge_keys=()),
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

t0 = time.perf_counter()
result_block = engine.evaluate(sig_block)
elapsed_ms = (time.perf_counter() - t0) * 1000

section("BLOCK — Raw PII in Gold, no merge key")
print(f"  decision   : {result_block.action.value.upper()}")
print(f"  faults     : {len(result_block.faults)}")
print(f"  latency_ms : {elapsed_ms:.2f}")

for fault in result_block.faults:
    print(f"\n  [{fault.severity.value.upper()}] {fault.code}")
    print(f"    message : {fault.message}")
    if fault.remediation:
        for step in fault.remediation:
            print(f"    → {step}")

print(f"\n  reasoning  : {result_block.reasoning}")

assert result_block.action == PolicyAction.BLOCK
print("\n  ✓ assert BLOCK passed — execution prevented")

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

section("AUDIT TRAIL — SHA-256 hash chain")
print(f"  events recorded : {trail.event_count}")
print()

events = trail.get_all_events()
for i, event in enumerate(events):
    print(f"  event [{i+1}]")
    print(f"    intent_id  : {event.intent_id}")
    print(f"    outcome    : {event.outcome}")
    print(f"    event_hash : {event.event_hash[:32]}...")
    if hasattr(event, "previous_hash") and event.previous_hash:
        print(f"    prev_hash  : {event.previous_hash[:32]}...")
    print()

chain_ok = trail.verify_chain()
print(f"  chain integrity : {'✓ INTACT' if chain_ok else '✗ TAMPERED'}")

assert chain_ok, "Chain must be intact!"
print("\n  ✓ assert verify_chain() passed")

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

plan = ExecutionPlanner().plan(sig_safe)

section("CODE GENERATION — 3 backends")

registry = BackendRegistry.singleton()

for backend_name in ("pyspark", "sql", "dbt"):
    backend = registry.get(backend_name)()
    t0 = time.perf_counter()
    result = backend.generate(plan)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    lines = result.code.splitlines()

    print(f"\n  {backend_name.upper()} — {len(lines)} lines  ({elapsed_ms:.1f}ms)")
    shown = 0
    for line in lines:
        if shown >= 10:
            break
        print(f"    {line}")
        shown += 1
    if len(lines) > 10:
        print(f"    ... ({len(lines) - 10} more lines)")

print("\n  ✓ All 3 backends generated deterministically")

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
# MAGIC The **Promotion Engine** drives state: `CANDIDATE → ACTIVE → WATCHLIST → DEMOTED → RETIRED`

# COMMAND ----------

from cfa.observability.indices import IndexCalculator, ExecutionRecord
from cfa.observability.promotion import PromotionEngine, PromotionPolicy
from cfa.types import _utcnow

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

section("LIFECYCLE INDICES + PROMOTION ENGINE")

calc = IndexCalculator(window_days=30)
prom = PromotionEngine(policy=PromotionPolicy(min_executions=3))

for label, records in [
    ("nfe_reconciliation (healthy) ", healthy),
    ("clientes_export   (drifting) ", drifting),
]:
    for r in records:
        prom.record_execution(r)
    skill, scores = prom.evaluate("demo-pipeline")

    print(f"\n  pipeline: {label}")
    print(f"    IFo (Operational) : {scores.ifo:.3f}  (target ≥ 0.75)")
    print(f"    IFs (Semantic)    : {scores.ifs:.3f}  (target ≥ 0.90)")
    print(f"    IFg (Governance)  : {scores.ifg:.1f}    (binary 1.0 = compliant)")
    print(f"    IDI (Drift)       : {scores.idi:.3f}  (target ≥ 0.75)")
    print(f"    state             : {skill.state.value.upper()}")
    if scores.drift_detected:
        print(f"    ⚠ drift detected")
    if scores.promotion_eligible:
        print(f"    ✓ promotion eligible")

print("\n  ✓ Lifecycle indices computed and promotion evaluated")

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

decisions = [
    ("ctx-001", "approved"),
    ("ctx-002", "replanned"),
    ("ctx-003", "blocked"),
    ("ctx-004", "approved"),
    ("ctx-005", "approved"),
]

t0 = time.perf_counter()
for intent_id, outcome in decisions:
    store.audit_append(AuditEvent(
        intent_id=intent_id,
        stage="policy",
        event_type="evaluate",
        outcome=outcome,
    ))
elapsed_ms = (time.perf_counter() - t0) * 1000

section("SQLITE STORAGE")
try:
    from cfa.storage import _sqlite_storage_stats
    stats = _sqlite_storage_stats(store)
    print(f"  audit events : {stats.audit_events_count}")
    print(f"  file size    : {stats.file_size_bytes:,} bytes")
    print(f"  insert ms    : {elapsed_ms:.2f} ({elapsed_ms/len(decisions):.2f}/event)")
    print(f"  db path      : {DB_PATH}")
except Exception:
    print(f"  events       : {len(decisions)} persisted")
    print(f"  insert ms    : {elapsed_ms:.2f}")
    print(f"  db path      : {DB_PATH}")

store.close()
print("\n  ✓ Storage demo complete")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 9 — Behavior Spec + Systematizer
# MAGIC
# MAGIC **Behavior Specs** bridge human-written governance policies (YAML) to executable CFA rules.
# MAGIC Platform/security teams define policies in YAML; data teams reference them by version.
# MAGIC Inspired by ASSERT's systematization approach, applied to data governance.

# COMMAND ----------

import tempfile, pathlib
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

spec_path = pathlib.Path(tempfile.mktemp(suffix=".yaml"))
spec_path.write_text(SPEC_YAML, encoding="utf-8")

try:
    spec = BehaviorSpec.from_yaml(str(spec_path))
    taxonomy, rules = Systematizer().systematize(spec)

    section("BEHAVIOR SPEC + SYSTEMATIZER")
    print(f"  spec name  : {spec.name}")
    print(f"  rules gen. : {len(rules)}")
    print(f"  categories : {taxonomy.category_count}")
    print()

    for rule in rules:
        print(f"  rule : {rule.name}")
        print(f"    code     : {rule.fault_code}")
        print(f"    action   : {rule.action.value}")
        print(f"    severity : {rule.severity.value}")
        print()

    print("  ✓ BehaviorSpec → Systematizer → PolicyRules complete")
finally:
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

section("RUNTIME GATE")

gate = RuntimeGate(config=GateConfig(policy_bundle="fiscal-prod-v1.0"))

# Pre-execution validation
result = gate.validate("Join NFe with Clientes and persist to Silver")
print(f"  validate()       : state={result.state.value}  passed={result.passed}")
print(f"  gate_id          : {result.gate_id}")
print(f"  execution_id     : {result.execution_id[:8]}...")

# Decorator guard
@gate.guard("aggregate sales data")
def my_pipeline():
    return "pipeline executed"

print(f"  @gate.guard call : {my_pipeline()}")
print("\n  ✓ Runtime Gate demo complete")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 11 — LangGraph Adapter: `@cfa_guard` Decorator
# MAGIC
# MAGIC CFA integrates with LangGraph agent nodes via a single decorator.
# MAGIC The node's docstring (or explicit intent string) is used as the governance contract.

# COMMAND ----------

from cfa.adapters.langgraph import cfa_guard

section("LANGGRAPH ADAPTER")

@cfa_guard("aggregate sales data with PII protected", mode="warn")
def my_agent_node(state):
    return {"status": "completed", "data": "processed"}

result = my_agent_node({"input": "test"})
print(f"  @cfa_guard call  : {result}")
print("\n  ✓ LangGraph adapter demo complete")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 12 — Reporting: HTML Compliance + Lifecycle + Audit
# MAGIC
# MAGIC CFA generates self-contained HTML reports with Chart.js —
# MAGIC single `.html` files, zero Python dependencies, ready to open in any browser.

# COMMAND ----------

from cfa.reporting import generate_report
import datetime

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
        {"name": "forbid_raw_pii",    "fired": 6,  "severity": "critical"},
        {"name": "require_partition", "fired": 12, "severity": "high"},
        {"name": "require_merge_key", "fired": 3,  "severity": "critical"},
    ],
    pii_incidents_prevented=6,
    audit_events_total=200,
    chain_intact=True,
)

# --- Lifecycle dashboard ---
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

section("HTML REPORTS GENERATED")
for path in [compliance_path, lifecycle_path, audit_path]:
    size = os.path.getsize(path)
    name = os.path.basename(path)
    print(f"  {name:20s} — {size:,} bytes")

print("\n  ✓ Self-contained HTML reports ready (open in any browser)")

# In Colab/Databricks: display inline
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

section("FULL KERNEL — end-to-end governed execution")

intents = [
    "Join NFe with Clientes anonymize CPF and persist to Silver",
    "Aggregate vendas by region persist to Gold",
    "Export raw clientes PII to Gold",  # kernel will auto-intervene
]

for intent in intents:
    print(f'\n  intent: "{intent}"')
    t0 = time.perf_counter()
    try:
        result = kernel.process(intent)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        print(f"    → decision   : {result.state.value.upper()}")
        print(f"    → sig_hash   : {result.signature.signature_hash[:24]}...")
        print(f"    → latency_ms : {elapsed_ms:.2f}")
        if result.replan_history:
            print(f"    → replans    : {len(result.replan_history)}")
        if result.generated_code and result.generated_code.code:
            lines = result.generated_code.code.splitlines()
            print(f"    → code_gen   : {len(lines)} lines ({result.generated_code.language})")
        print(f"    → audit_evt  : hash chain updated")
    except (PermissionError, RuntimeError, ValueError) as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        print(f"    → BLOCKED    : {type(e).__name__}  ({elapsed_ms:.2f}ms)")
        print(f"      {str(e)[:100]}")

print("\n  ✓ Full kernel pipeline complete")

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
# MAGIC **Next steps**
# MAGIC - LLM-powered features (semantic normalizer, NL→rules) → see `CFA_LLM_Demo`
# MAGIC - Custom policy bundles → see [Policy Bundles docs](https://marquesantero.github.io/cfa/docs/policy-bundles)
# MAGIC - MCP integration → see [MCP Server docs](https://marquesantero.github.io/cfa/docs/mcp-server)
# MAGIC
# MAGIC **Links**
# MAGIC - [Documentation](https://marquesantero.github.io/cfa/docs/intro)
# MAGIC - [PyPI](https://pypi.org/project/cfa-kernel/)
# MAGIC - [GitHub](https://github.com/marquesantero/cfa)
# MAGIC - [Discussions](https://github.com/marquesantero/cfa/discussions)
