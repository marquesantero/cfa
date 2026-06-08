# Databricks notebook source
# MAGIC %md
# MAGIC # CFA — Contextual Flux Architecture
# MAGIC ## LLM Demo: Semantic Governance Powered by LLMs
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
# MAGIC This notebook covers the **LLM-powered surfaces**: semantic intent resolution, NL→rules
# MAGIC systematizer, and tamper-evident audit of every LLM call.
# MAGIC For the deterministic core (policy engine, audit, codegen), see `CFA_Demo`.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### What this notebook demonstrates
# MAGIC
# MAGIC | Section | Feature | LLM Role |
# MAGIC |---|---|---|
# MAGIC | S0 | Install + version pin | setup |
# MAGIC | S1 | Setup & secrets | API key from Secret Scope / env vars |
# MAGIC | S2 | Catalog | Operational metadata (grounds the LLM) |
# MAGIC | S3 | LLM Normalizer | Semantic intent resolution (replaces keywords) |
# MAGIC | S4 | Strict Mode | LLM output validated against catalog |
# MAGIC | S5 | LLM Audit Trail | Every call SHA-256 traceable |
# MAGIC | S6 | LLM Systematizer | NL governance → BehaviorSpec → PolicyRules |
# MAGIC | S7 | Full Kernel + LLM | End-to-end governed execution |
# MAGIC | S8 | Runtime Gate + LLM | Guard with LLM-backed rules |
# MAGIC | S9 | Compare Normalizers | Rule-based vs LLM side-by-side |
# MAGIC | S10 | PolicyEngine + LLM Rules | Close the NL→Rules→Engine loop |
# MAGIC
# MAGIC **API key:** stored in Databricks Secret Scope `cfa-secrets`, never in code.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 0 — Install
# MAGIC
# MAGIC Pinned to a known-good version. Use `pip install cfa-kernel[llm]` (without pin) to follow latest.

# COMMAND ----------

# MAGIC %pip install -q cfa-kernel==0.1.9 openai

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 1 — Setup & Secrets
# MAGIC
# MAGIC API key read from Databricks Secret Scope `cfa-secrets/openai-key` or `cfa-secrets/deepseek-key`.
# MAGIC Falls back to `OPENAI_API_KEY` / `DEEPSEEK_API_KEY` env vars for local testing.

# COMMAND ----------

# ── LLM configuration (edit here to switch model or sampling) ──────────────
OPENAI_MODEL    = "gpt-4o-mini"
DEEPSEEK_MODEL  = "deepseek-chat"
DEEPSEEK_URL    = "https://api.deepseek.com"
TEMPERATURE     = 0.0
MAX_TOKENS      = 2048
SECRET_SCOPE    = "cfa-secrets"

# ── Imports ────────────────────────────────────────────────────────────────
import cfa, os, time

HAS_OPENAI = False
try:
    import openai
    HAS_OPENAI = True
except ImportError as e:
    print(f"ERROR: openai not importable: {e}")
    print("Run: %pip install openai")

from cfa.normalizer.llm import OpenAILMProvider, LLMNormalizerBackend
from cfa.normalizer.base import IntentNormalizer, RuleBasedNormalizerBackend
from cfa.runtime import RuntimeGate
from cfa.policy.engine import PolicyEngine
from cfa.types import StateSignature
from cfa.core.kernel import KernelConfig


# ── Helper: section header (keep banners uniform across the notebook) ──────
def section(title: str, width: int = 60) -> None:
    """Print a uniform section banner."""
    print("─" * width)
    print(title)
    print("─" * width)


# ── Read API keys: Secret Scope first, env vars fallback ───────────────────
def _try_secret(key: str):
    """Try to read a secret from Databricks. Returns None if not available."""
    try:
        return dbutils.secrets.get(SECRET_SCOPE, key)  # noqa: F821
    except Exception:
        return None

OPENAI_KEY   = _try_secret("openai-key")   or os.environ.get("OPENAI_API_KEY")
DEEPSEEK_KEY = _try_secret("deepseek-key") or os.environ.get("DEEPSEEK_API_KEY")

# Auto-select: prefer OpenAI, fallback to DeepSeek
if OPENAI_KEY:
    LLM_MODEL    = OPENAI_MODEL
    LLM_BASE_URL = None
    LLM_API_KEY  = OPENAI_KEY
    LLM_PROVIDER = "OpenAI"
elif DEEPSEEK_KEY:
    LLM_MODEL    = DEEPSEEK_MODEL
    LLM_BASE_URL = DEEPSEEK_URL
    LLM_API_KEY  = DEEPSEEK_KEY
    LLM_PROVIDER = "DeepSeek"
else:
    LLM_MODEL    = None
    LLM_BASE_URL = None
    LLM_API_KEY  = None
    LLM_PROVIDER = None

HAS_LLM = HAS_OPENAI and (LLM_API_KEY is not None)


def make_provider() -> OpenAILMProvider:
    """Return an LLM provider with the auto-detected config."""
    return OpenAILMProvider(
        model=LLM_MODEL,
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
        temperature=TEMPERATURE,
    )


# ── Status ─────────────────────────────────────────────────────────────────
section("Setup")
print(f"  CFA version  : {cfa.__version__}")
print(f"  openai SDK   : {openai.__version__ if HAS_OPENAI else 'not installed'}")
if HAS_LLM:
    print(f"  LLM provider : {LLM_PROVIDER}")
    print(f"  model        : {LLM_MODEL}")
    print(f"  temperature  : {TEMPERATURE}")
    print(f"  max_tokens   : {MAX_TOKENS}")
else:
    print(f"  LLM provider : NONE — set secret '{SECRET_SCOPE}/openai-key'")
    print(f"                 or env var OPENAI_API_KEY / DEEPSEEK_API_KEY")
    print(f"                 LLM cells will be skipped gracefully.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 2 — Data Catalog
# MAGIC
# MAGIC Catalog grounds the LLM. The LLM receives it in the prompt and **must** reference real datasets.
# MAGIC Hallucinated datasets are rejected by `strict=True` (see Section 4).

# COMMAND ----------

CATALOG = {
    "nfe_bronze": {
        "type": "delta", "layer": "bronze", "size_gb": 50,
        "classification": "high_volume",
        "partition_by": ["processing_date"], "pii": False,
        "pii_columns": [],
        "description": "Notas Fiscais Eletronicas brutas",
    },
    "clientes_bronze": {
        "type": "delta", "layer": "bronze", "size_gb": 10,
        "classification": "sensitive",
        "partition_by": ["processing_date"], "pii": True,
        "pii_columns": ["cpf", "nome", "endereco"],
        "description": "Dados cadastrais com CPF e endereco",
    },
    "vendas_bronze": {
        "type": "delta", "layer": "bronze", "size_gb": 2000,
        "classification": "high_volume",
        "partition_by": ["data_venda"], "pii": False,
        "pii_columns": [],
        "description": "Registros de transacoes de venda",
    },
    "fornecedores_bronze": {
        "type": "delta", "layer": "bronze", "size_gb": 10,
        "classification": "internal",
        "partition_by": ["updated_at"], "pii": False,
        "pii_columns": [],
        "description": "Cadastro de fornecedores",
    },
    "vendas_gold_agregado": {
        "type": "delta", "layer": "gold", "size_gb": 500,
        "classification": "internal",
        "partition_by": ["data_venda"], "pii": False,
        "pii_columns": [],
        "description": "Agregados de vendas para BI",
    },
}

from cfa.policy.catalog import validate_catalog

section("Catalog validation")
result = validate_catalog(CATALOG)
print(f"  valid    : {result.valid}")
print(f"  datasets : {len(CATALOG)} registered")
classifications = ", ".join(
    f"{name}={meta['classification']}" for name, meta in CATALOG.items()
)
print(f"  classes  : {classifications}")
for msg in result.messages:
    print(f"  message  : {msg}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 3 — LLM Normalizer: Semantic Intent Resolution
# MAGIC
# MAGIC Rule-based = keyword matching (`join`, `aggregate`, `anonymize`).
# MAGIC LLM = sends `intent + catalog` to the model, parses structured JSON output.
# MAGIC
# MAGIC The returned `SemanticResolution` contains the resolved `StateSignature`,
# MAGIC plus `confidence_score`, `ambiguity_level`, and `reasoning`.

# COMMAND ----------

if not HAS_LLM:
    print("SKIP: no API key configured.")
else:
    provider = make_provider()
    llm_backend = LLMNormalizerBackend(provider=provider, strict=False)
    normalizer = IntentNormalizer(backend=llm_backend)

    section("LLM NORMALIZER — semantic resolution")

    intents = [
        "Join NFe with Clientes anonymize CPF and persist to Silver",
        "Aggregate vendas by region persist to Gold",
        "Export raw clientes PII to Gold",
    ]

    for raw in intents:
        print(f'\n  intent: "{raw}"')
        t0 = time.perf_counter()
        res = normalizer.normalize(raw, {}, CATALOG)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        sig = res.signature
        ds_names = [d.name for d in sig.datasets]
        print(f"    domain       : {sig.domain}")
        print(f"    intent       : {sig.intent}")
        print(f"    target_layer : {sig.target_layer}")
        print(f"    datasets     : {ds_names}")
        print(f"    confidence   : {res.confidence_score:.2f}")
        print(f"    ambiguity    : {res.ambiguity_level}")
        print(f"    latency_ms   : {elapsed_ms:.0f}")
        if res.reasoning:
            reasoning = res.reasoning.replace("\n", " ")
            print(f"    reasoning    : {reasoning[:140]}...")

    print("\n  ✓ LLM normalizer baseline complete")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 4 — Strict Mode: Catalog-Grounded LLM
# MAGIC
# MAGIC `strict=True` validates the LLM output against the catalog.
# MAGIC Hallucinated datasets or invalid classifications raise `ValueError`.

# COMMAND ----------

if not HAS_LLM:
    print("SKIP: no API key available")
else:
    sp = make_provider()
    sb = LLMNormalizerBackend(provider=sp, strict=True)
    sn = IntentNormalizer(backend=sb)

    section("STRICT MODE — catalog-grounded LLM")
    print("  strict=True : LLM output validated against catalog")
    print("  hallucinated datasets or invalid classifications raise ValueError")

    test_cases = [
        # (intent, expect_pass)
        ("Join NFe with Clientes anonymize CPF persist to Silver", True),
        ("Full scan vendas without partition to Gold", False),
    ]

    for raw, expect_pass in test_cases:
        print(f'\n  intent: "{raw}"')
        try:
            res = sn.normalize(raw, {}, CATALOG)
            status = "PASSED" if expect_pass else "UNEXPECTED PASS"
            print(f"    {status}  | confidence={res.confidence_score:.2f}  layer={res.signature.target_layer}")
        except ValueError as e:
            status = "REJECTED (expected)" if not expect_pass else "REJECTED (unexpected)"
            print(f"    {status} | {str(e)[:120]}")

    print("\n  ✓ Strict mode demo complete")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 5 — LLM Audit Trail
# MAGIC
# MAGIC Every LLM call is SHA-256 hashed (prompt, response, catalog).
# MAGIC Full traceability for compliance audits — the unique CFA differentiator vs. LangSmith/ASSERT.

# COMMAND ----------

if not HAS_LLM:
    print("SKIP: no API key available")
else:
    # 'sb' is the strict backend created in Section 4.
    try:
        records = sb.audit_records
    except NameError:
        print("NOTE: 'sb' not found — run Section 4 first, or re-run from Section 1.")
        records = []

    section("LLM AUDIT TRAIL — tamper-evident LLM calls")
    print(f"  total calls recorded : {len(records)}")

    for i, rec in enumerate(records):
        print(f"\n  call [{i+1}]")
        print(f"    model          : {rec.model}")
        print(f"    prompt_hash    : {rec.prompt_hash[:16]}...")
        print(f"    response_hash  : {rec.response_hash[:16]}...")
        print(f"    catalog_hash   : {rec.catalog_hash[:16]}...")
        if rec.catalog_validation_errors:
            for err in rec.catalog_validation_errors:
                print(f"    val.error      : {err}")
        if rec.parsed_json:
            keys = list(rec.parsed_json.keys())
            print(f"    parsed_keys    : {keys[:8]}")

    print("\n  ✓ LLM audit trail complete")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 6 — LLM Systematizer: NL → PolicyRules
# MAGIC
# MAGIC Describe governance in natural language. LLM produces `BehaviorSpec`.
# MAGIC `Systematizer` converts it to executable `PolicyRule` objects — closing the loop
# MAGIC from English (or Portuguese) to deterministic governance rules.

# COMMAND ----------

from cfa.behavior.llm import OpenAISystematizerBackend
from cfa.behavior import Systematizer

taxonomy, rules = None, None

if not HAS_LLM:
    print("SKIP: no LLM available (missing openai or API key)")
else:
    try:
        section("LLM SYSTEMATIZER — NL to PolicyRules")

        governance_desc = """\
Fiscal ETL pipeline governance:
1. All datasets moving from Bronze to Silver/Gold MUST anonymize PII (CPF, nome, endereco)
2. Every Silver and Gold write requires a merge_key (upsert, not append)
3. Datasets larger than 100GB MUST have partition_by defined
4. No raw PII columns may appear in Gold layer
5. Maximum cost per pipeline run: 50 DBU
"""

        sys_backend = OpenAISystematizerBackend(
            model=LLM_MODEL,
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )

        t0 = time.perf_counter()
        taxonomy, rules = Systematizer().systematize_from_nl(
            governance_desc,
            backend=sys_backend,
            context="Fiscal ETL: NFe, Clientes, Vendas, Fornecedores on Databricks Delta Lake",
            target_layer="silver",
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000

        print(f"  categories       : {taxonomy.category_count}")
        print(f"  rules generated  : {len(rules)}")
        print(f"  latency_ms       : {elapsed_ms:.0f}")
        print()

        for rule in rules:
            print(f"  rule : {rule.name}")
            print(f"    code     : {rule.fault_code}")
            print(f"    action   : {rule.action.value}")
            print(f"    severity : {rule.severity.value}")
            print()

        test_intents = taxonomy.generate_test_intents(3)
        print(f"  CI test intents generated: {len(test_intents)}")
        for intent in test_intents[:6]:
            print(f"    - {intent}")
        if len(test_intents) > 6:
            print(f"    ... ({len(test_intents) - 6} more)")

        print("\n  ✓ LLM Systematizer complete")
    except Exception as e:
        print(f"  LLM call failed: {type(e).__name__}: {str(e)[:120]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 7 — Full Kernel with LLM Normalizer
# MAGIC
# MAGIC Same 5-phase pipeline (Formalize → Govern → Generate → Execute → Validate/Audit).
# MAGIC Only the **Formalize** phase switches from keyword-matching to the LLM.
# MAGIC
# MAGIC **Note:** when the kernel sees an unsafe intent (e.g., raw PII to Gold), it may APPROVE
# MAGIC after auto-intervening — adding `no_pii_raw=True` and an `anonymize` step to the generated
# MAGIC code. The kernel does not approve unsafe operations; it approves *the corrected version*.

# COMMAND ----------

from cfa import KernelOrchestrator

if not HAS_LLM:
    print("SKIP: no API key available")
else:
    provider = make_provider()
    # strict=False: LLM resolves intent semantically; catalog used for grounding
    # but validation errors do not block (strict mode is for S4 demo only)
    backend = LLMNormalizerBackend(provider=provider, strict=False)

    kernel = KernelOrchestrator(
        catalog=CATALOG,
        config=KernelConfig(
            policy_bundle_version="fiscal-prod-v1.0",
            backend="pyspark",
        ),
        normalizer_backend=backend,
    )

    section("FULL KERNEL + LLM NORMALIZER")

    for intent in [
        "Join NFe with Clientes anonymize CPF and persist to Silver",
        "Aggregate vendas by region persist to Gold",
        "Export raw clientes PII to Gold",
    ]:
        print(f'\n  intent: "{intent}"')
        t0 = time.perf_counter()
        try:
            result = kernel.process(intent)
            elapsed_ms = (time.perf_counter() - t0) * 1000

            print(f"    → decision    : {result.state.value.upper()}")
            if result.signature is not None:
                print(f"    → sig_hash    : {result.signature.signature_hash[:24]}...")
            print(f"    → latency_ms  : {elapsed_ms:.0f}")
            if result.replan_history:
                print(f"    → replans     : {len(result.replan_history)}")
            if result.generated_code and result.generated_code.code:
                lines = result.generated_code.code.splitlines()
                print(f"    → code_gen    : {len(lines)} lines ({result.generated_code.language})")
                preview = [l for l in lines if l.strip()][:6]
                for line in preview:
                    print(f"      {line}")
                if len(lines) > 6:
                    print(f"      ... ({len(lines) - 6} more lines)")
        except Exception as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            print(f"    → BLOCKED     : {type(e).__name__}  ({elapsed_ms:.0f}ms)")
            print(f"      {str(e)[:100]}")

    calls = backend.audit_records
    print(f"\n  LLM calls by kernel: {len(calls)}")
    for rec in calls:
        print(f"    prompt={rec.prompt_hash[:16]}...  response={rec.response_hash[:16]}...")

    print("\n  ✓ Full kernel + LLM complete")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 8 — Runtime Gate with LLM-Generated Rules
# MAGIC
# MAGIC `RuntimeGate` validates intents before execution.
# MAGIC With `policy_rules` from the Systematizer, the gate inherits NL-defined governance.

# COMMAND ----------

import traceback

section("RUNTIME GATE")

# Guard: 'rules' is set by Section 6. Fall back gracefully if missing.
try:
    _rules = rules
except NameError:
    _rules = None

if _rules is None:
    print("  NOTE: LLM-generated rules not available (Section 6 skipped).")
    print("        Using default CFA policy rules instead.")
else:
    print(f"  using {len(_rules)} LLM-generated rules from Section 6")

try:
    gate = RuntimeGate(catalog=CATALOG, policy_rules=_rules)

    result = gate.validate("Join NFe with Clientes and persist to Silver")
    print(f"  validate()       : state={result.state.value}  passed={result.passed}")
    print(f"  gate_id          : {result.gate_id}")
    print(f"  execution_id     : {result.execution_id[:8]}...")

    @gate.guard("aggregate sales data with PII protected")
    def my_pipeline():
        return "pipeline executed"

    print(f"  @gate.guard call : {my_pipeline()}")
    print("\n  ✓ Runtime Gate demo complete")
except Exception as e:
    print(f"  RUNTIME GATE FAILED: {type(e).__name__}")
    traceback.print_exc()

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 9 — Comparing Normalizers: Rule-Based vs LLM
# MAGIC
# MAGIC Same intent, two backends — side-by-side. The most persuasive cell of the notebook:
# MAGIC rule-based confidence stays near 0.15 because it can't resolve semantics;
# MAGIC the LLM hits 0.90+ because it understands the intent.

# COMMAND ----------

section("NORMALIZER COMPARISON — rule-based vs LLM")

rule_norm = IntentNormalizer(backend=RuleBasedNormalizerBackend())
llm_norm = None
if HAS_LLM:
    provider = make_provider()
    # strict=False for comparison — we want to see the LLM output, not block it
    llm_norm = IntentNormalizer(backend=LLMNormalizerBackend(provider=provider, strict=False))

header = f"  {'intent':<48s} | {'method':<11s} | {'domain':<13s} | {'layer':<7s} | {'conf':>5s}"
print(header)
print("  " + "-" * (len(header) - 2))

for raw in [
    "Join NFe with Clientes anonymize CPF and persist to Silver",
    "Aggregate vendas by region persist to Gold",
    "Export raw clientes PII to Gold",
]:
    # Rule-based
    rb = rule_norm.normalize(raw, {}, CATALOG)
    sig_rb = rb.signature
    layer_rb = str(sig_rb.target_layer).split(".")[-1].lower() if sig_rb.target_layer else "—"
    print(
        f"  {raw[:48]:<48s} | {'rule-based':<11s} | {sig_rb.domain:<13s} | "
        f"{layer_rb:<7s} | {rb.confidence_score:>5.2f}"
    )

    # LLM
    if llm_norm is not None:
        try:
            llm = llm_norm.normalize(raw, {}, CATALOG)
            sig_llm = llm.signature
            layer_llm = str(sig_llm.target_layer).split(".")[-1].lower() if sig_llm.target_layer else "—"
            print(
                f"  {'':48s} | {'LLM':<11s} | {sig_llm.domain:<13s} | "
                f"{layer_llm:<7s} | {llm.confidence_score:>5.2f}"
            )
        except Exception as e:
            print(f"  {'':48s} | {'LLM':<11s} | ERROR: {type(e).__name__}: {str(e)[:50]}")
    else:
        print(f"  {'':48s} | {'LLM':<11s} | (no API key)")
    print()

print("  ✓ Normalizer comparison complete")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 10 — PolicyEngine with LLM-Generated Rules
# MAGIC
# MAGIC Rules from `Systematizer` (Section 6) feed `PolicyEngine`.
# MAGIC Closes the loop: **NL governance → LLM → BehaviorSpec → PolicyRules → Engine**.

# COMMAND ----------

from cfa.types import (
    DatasetRef, SignatureConstraints, TargetLayer, ExecutionContext,
)

section("POLICY ENGINE WITH LLM-GENERATED RULES")

# Guard: 'rules' is set by Section 6.
try:
    _rules_s10 = rules
except NameError:
    _rules_s10 = None

if _rules_s10 is None:
    print("  NOTE: LLM-generated rules not available (Section 6 skipped).")
    print("        Using default CFA policy rules instead.")
    engine = PolicyEngine()
else:
    print(f"  using {len(_rules_s10)} LLM-generated rules from Section 6")
    engine = PolicyEngine(rules=_rules_s10)

# --- Safe signature ---
sig_safe = StateSignature(
    domain="fiscal",
    intent="Join NFe with Clientes anonymize CPF persist to Silver",
    source_intent_raw="Join NFe with Clientes anonymize CPF persist to Silver",
    target_layer=TargetLayer.SILVER,
    datasets=(
        DatasetRef(name="nfe_bronze"),
        DatasetRef(name="clientes_bronze", pii_columns=("cpf", "nome")),
    ),
    constraints=SignatureConstraints(
        no_pii_raw=True,
        merge_key_required=True,
        partition_by=("processing_date",),
    ),
    execution_context=ExecutionContext(
        policy_bundle_version="v1.0",
        catalog_snapshot_version="catalog_default",
        context_registry_version_id="ctx-default",
    ),
)

t0 = time.perf_counter()
r = engine.evaluate(sig_safe)
elapsed_ms = (time.perf_counter() - t0) * 1000
print(f"\n  safe signature   → {r.action.value.upper()}  faults={len(r.faults)}  ({elapsed_ms:.2f}ms)")

# --- Unsafe signature ---
sig_unsafe = StateSignature(
    domain="fiscal",
    intent="Export raw clientes PII to Gold",
    source_intent_raw="Export raw clientes PII to Gold",
    target_layer=TargetLayer.GOLD,
    datasets=(
        DatasetRef(name="clientes_bronze", pii_columns=("cpf", "nome", "endereco")),
    ),
    constraints=SignatureConstraints(
        no_pii_raw=False,
        merge_key_required=False,
        partition_by=(),
    ),
    execution_context=ExecutionContext(
        policy_bundle_version="v1.0",
        catalog_snapshot_version="catalog_default",
        context_registry_version_id="ctx-default",
    ),
)

t0 = time.perf_counter()
r2 = engine.evaluate(sig_unsafe)
elapsed_ms = (time.perf_counter() - t0) * 1000
print(f"  unsafe signature → {r2.action.value.upper()}  faults={len(r2.faults)}  ({elapsed_ms:.2f}ms)")
for fault in r2.faults[:4]:
    print(f"    [{fault.severity.value.upper():<10s}] {fault.code}")

print("\n  ✓ LLM-rules PolicyEngine complete")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Summary
# MAGIC
# MAGIC | LLM Feature | Status | Notes |
# MAGIC |---|---|---|
# MAGIC | LLM Normalizer | ✓ | Semantic intent resolution via OpenAI/DeepSeek |
# MAGIC | Strict Mode | ✓ | LLM output validated against catalog |
# MAGIC | LLM Audit Trail | ✓ | Every call SHA-256 traceable |
# MAGIC | LLM Systematizer | ✓ | NL → BehaviorSpec → PolicyRules |
# MAGIC | Full Kernel + LLM | ✓ | End-to-end with LLM normalizer |
# MAGIC | Runtime Gate | ✓ | Guard with LLM-generated policy rules |
# MAGIC | Normalizer Comparison | ✓ | Rule-based vs LLM side-by-side |
# MAGIC | Secret Management | ✓ | Databricks Secret Scope `cfa-secrets` |
# MAGIC
# MAGIC **Key differences from rule-based:**
# MAGIC - LLM understands intent **semantics**, not just keywords
# MAGIC - Natural language governance descriptions → executable rules
# MAGIC - Every LLM call is audited (prompt + response + catalog SHA-256)
# MAGIC - Strict mode prevents hallucinations by validating against catalog
# MAGIC - API key stored in **Databricks Secret Scope** — never in code
# MAGIC
# MAGIC **Secret scope setup (one-time):**
# MAGIC ```bash
# MAGIC databricks secrets create-scope cfa-secrets
# MAGIC databricks secrets put-secret cfa-secrets openai-key
# MAGIC # or
# MAGIC databricks secrets put-secret cfa-secrets deepseek-key
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Next steps**
# MAGIC - Deterministic core (policy, audit, codegen) → see `CFA_Demo`
# MAGIC - Custom behavior specs → see [Behavior Spec docs](https://marquesantero.github.io/cfa/docs/behavior-spec)
# MAGIC - MCP integration → see [MCP Server docs](https://marquesantero.github.io/cfa/docs/mcp-server)
# MAGIC
# MAGIC **Links**
# MAGIC - [Documentation](https://marquesantero.github.io/cfa/docs/intro)
# MAGIC - [PyPI](https://pypi.org/project/cfa-kernel/)
# MAGIC - [GitHub](https://github.com/marquesantero/cfa)
# MAGIC - [Discussions](https://github.com/marquesantero/cfa/discussions)
