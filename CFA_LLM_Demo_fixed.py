# Databricks notebook source
# MAGIC %md
# MAGIC # CFA — Contextual Flux Architecture
# MAGIC ## LLM-Powered Governance Demo
# MAGIC
# MAGIC | Section | Feature | LLM Role |
# MAGIC |---|---|---|
# MAGIC | S1 | Setup & Secrets | Read API key from Databricks Secret Scope |
# MAGIC | S2 | Catalog | Operational metadata |
# MAGIC | S3 | LLM Normalizer | Semantic intent resolution (replaces keywords) |
# MAGIC | S4 | Strict Mode | LLM output validated against catalog |
# MAGIC | S5 | LLM Audit Trail | Every call SHA-256 traceable |
# MAGIC | S6 | LLM Systematizer | NL governance → BehaviorSpec → PolicyRules |
# MAGIC | S7 | Full Kernel + LLM | End-to-end governed execution |
# MAGIC | S8 | Runtime Gate + LLM | Guard with LLM-backed validation |
# MAGIC | S9 | Compare Normalizers | Rule-based vs LLM side-by-side |
# MAGIC | S10 | PolicyEngine + LLM Rules | Close the NL→Rules→Engine loop |
# MAGIC
# MAGIC **API key:** stored in Databricks Secret Scope `cfa-secrets`, never in code.
# MAGIC
# MAGIC ---
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 0 — Install
# MAGIC
# MAGIC Run this cell first to install dependencies.
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 1 — Setup & Secrets
# MAGIC
# MAGIC API key read from Databricks Secret Scope `cfa-secrets/openai-key` or `cfa-secrets/deepseek-key`.
# MAGIC Falls back to `OPENAI_API_KEY` / `DEEPSEEK_API_KEY` env vars for local testing.
# MAGIC

# COMMAND ----------

# MAGIC %pip install -q cfa-kernel[all] openai

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

# --- Test if openai is importable ---
HAS_OPENAI = False
try:
    import openai
    print(f"openai {openai.__version__} - OK")
    HAS_OPENAI = True
except ImportError as e:
    print(f"ERROR: openai not importable: {e}")
    print("Run: %%pip install openai")

import cfa, os
from cfa.normalizer.llm import OpenAILMProvider, LLMNormalizerBackend
from cfa.normalizer.base import IntentNormalizer, RuleBasedNormalizerBackend
from cfa.runtime import RuntimeGate
from cfa.policy.engine import PolicyEngine
from cfa.types import StateSignature
from cfa.core.kernel import KernelConfig

print(f"CFA version: {cfa.__version__}")

# --- Read API keys from secret scope ---
def _try_secret(key):
    try:
        return dbutils.secrets.get("cfa-secrets", key)
    except Exception:
        return None

# Try Databricks secrets, fall back to env vars
OPENAI_KEY = _try_secret("openai-key") or os.environ.get("OPENAI_API_KEY")
DEEPSEEK_KEY = _try_secret("deepseek-key") or os.environ.get("DEEPSEEK_API_KEY")

# Auto-select: prefer OpenAI (better reachability from Azure), fallback to DeepSeek
if OPENAI_KEY:
    LLM_MODEL = "gpt-4o-mini"
    LLM_BASE_URL = None  # default api.openai.com
    LLM_API_KEY = OPENAI_KEY
    print(f"Using OpenAI ({LLM_MODEL})")
elif DEEPSEEK_KEY:
    LLM_MODEL = "deepseek-chat"
    LLM_BASE_URL = "https://api.deepseek.com"
    LLM_API_KEY = DEEPSEEK_KEY
    print(f"Using DeepSeek ({LLM_MODEL})")
else:
    LLM_MODEL = None
    LLM_BASE_URL = None
    LLM_API_KEY = None
    print("WARNING: No API key found.")
    print("  Databricks: secrets create-scope cfa-secrets")
    print("  Local:      set OPENAI_API_KEY or DEEPSEEK_API_KEY env var")

# Combined gate: need both openai + API key
HAS_LLM = HAS_OPENAI and LLM_API_KEY is not None

# Helper: create an LLM provider with the auto-detected config
def make_provider():
    """Return OpenAILMProvider with auto-detected config."""
    return OpenAILMProvider(
        model=LLM_MODEL,
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
        temperature=0.0,
    )


# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 2 — Data Catalog
# MAGIC
# MAGIC Catalog grounds the LLM. The LLM receives it in the prompt and MUST reference real datasets.
# MAGIC

# COMMAND ----------

CATALOG = {
    'nfe_bronze': {
        'type': 'delta', 'layer': 'bronze', 'size_gb': 50,
        'classification': 'high_volume',
        'partition_by': ['processing_date'], 'pii': False,
        'pii_columns': [],
        'description': 'Notas Fiscais Eletronicas brutas',
    },
    'clientes_bronze': {
        'type': 'delta', 'layer': 'bronze', 'size_gb': 10,
        'classification': 'sensitive',
        'partition_by': ['processing_date'], 'pii': True,
        'pii_columns': ['cpf', 'nome', 'endereco'],
        'description': 'Dados cadastrais com CPF e endereco',
    },
    'vendas_bronze': {
        'type': 'delta', 'layer': 'bronze', 'size_gb': 2000,
        'classification': 'high_volume',
        'partition_by': ['data_venda'], 'pii': False,
        'pii_columns': [],
        'description': 'Registros de transacoes de venda',
    },
    'fornecedores_bronze': {
        'type': 'delta', 'layer': 'bronze', 'size_gb': 10,
        'classification': 'internal',
        'partition_by': ['updated_at'], 'pii': False,
        'pii_columns': [],
        'description': 'Cadastro de fornecedores',
    },
    'vendas_gold_agregado': {
        'type': 'delta', 'layer': 'gold', 'size_gb': 500,
        'classification': 'internal',
        'partition_by': ['data_venda'], 'pii': False,
        'pii_columns': [],
        'description': 'Agregados de vendas para BI',
    },
}

from cfa.policy.catalog import validate_catalog
result = validate_catalog(CATALOG)
print(f"Catalog valid: {result.valid}")
print(f"  {len(CATALOG)} datasets registered")
print("  Classifications: nfe_bronze=high_volume, clientes_bronze=sensitive,")
print("                   vendas_bronze=high_volume, fornecedores_bronze=internal,")
print("                   vendas_gold_agregado=internal")
for msg in result.messages:
    print(f"  {msg}")


# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 3 — LLM Normalizer: Semantic Intent Resolution
# MAGIC
# MAGIC Rule-based = keyword matching (`join`, `aggregate`, `anonymize`).
# MAGIC LLM = sends `intent + catalog` to DeepSeek, parses structured JSON.
# MAGIC
# MAGIC The `SemanticResolution` returned contains the resolved `StateSignature`.
# MAGIC

# COMMAND ----------

if not HAS_LLM:
    print("SKIP: no API key configured.")
else:
    provider = make_provider()
    llm_backend = LLMNormalizerBackend(provider=provider, strict=False)
    normalizer = IntentNormalizer(backend=llm_backend)

    print("=" * 55)
    print("LLM NORMALIZER -- Semantic Resolution")
    print("=" * 55)

    intents = [
        "Join NFe with Clientes anonymize CPF and persist to Silver",
        "Aggregate vendas by region persist to Gold",
        "Export raw clientes PII to Gold",
    ]

    for raw in intents:
        print(f'\nIntent: "{raw}"')
        res = normalizer.normalize(raw, {}, CATALOG)
        sig = res.signature
        print(f"  Domain       : {sig.domain}")
        print(f"  Intent       : {sig.intent}")
        print(f"  Target layer : {sig.target_layer}")
        ds_names = [d.name for d in sig.datasets]
        print(f"  Datasets     : {ds_names}")
        print(f"  Confidence   : {res.confidence_score:.2f}")
        print(f"  Ambiguity    : {res.ambiguity_level}")
        if res.reasoning:
            print(f"  Reasoning    : {res.reasoning[:150]}...")

    print("\nLLM normalizer baseline complete")


# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 4 — Strict Mode: Catalog-Grounded LLM
# MAGIC
# MAGIC `strict=True` validates the LLM output against the catalog.
# MAGIC Hallucinated datasets/references raise `ValueError`.
# MAGIC

# COMMAND ----------

if not HAS_LLM:
    print("SKIP: no API key available")
else:
    sp = make_provider()
    sb = LLMNormalizerBackend(provider=sp, strict=True)
    sn = IntentNormalizer(backend=sb)

    print("=" * 55)
    print("STRICT MODE — Catalog-grounded LLM")
    print("=" * 55)
    print("  strict=True: LLM output validated against catalog.")
    print("  Hallucinated datasets or invalid classifications raise ValueError.")
    print()

    test_cases = [
        # (intent, expect_pass)
        ("Join NFe with Clientes anonymize CPF persist to Silver", True),
        ("Full scan vendas without partition to Gold", False),
    ]

    for raw, expect_pass in test_cases:
        print(f"Intent: \"{raw}\"")
        try:
            res = sn.normalize(raw, {}, CATALOG)
            status = "PASSED " if expect_pass else "UNEXPECTED PASS"
            print(f"  {status} | confidence={res.confidence_score:.2f}  layer={res.signature.target_layer}")
        except ValueError as e:
            status = "REJECTED (expected)" if not expect_pass else "REJECTED (unexpected)"
            print(f"  {status} | {str(e)[:120]}")
        print()

    print("Strict mode demo complete")


# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 5 — LLM Audit Trail
# MAGIC
# MAGIC Every LLM call is SHA-256 hashed (prompt, response, catalog).
# MAGIC Full traceability for compliance audits.
# MAGIC

# COMMAND ----------

if not HAS_LLM:
    print("SKIP: no API key available")
else:
    # 'sb' is the strict backend created in Section 4.
    # Guard against running this cell out of order.
    try:
        records = sb.audit_records
    except NameError:
        print("NOTE: 'sb' not found — run Section 4 first, or re-run from Section 1.")
        records = []

    print("=" * 55)
    print("LLM AUDIT TRAIL — Tamper-evident LLM calls")
    print("=" * 55)
    print(f"  Total LLM calls recorded: {len(records)}")

    for i, rec in enumerate(records):
        print(f"\n  Call {i+1}:")
        print(f"    Model         : {rec.model}")
        print(f"    Prompt hash   : {rec.prompt_hash[:16]}...")
        print(f"    Response hash : {rec.response_hash[:16]}...")
        print(f"    Catalog hash  : {rec.catalog_hash[:16]}...")
        if rec.catalog_validation_errors:
            for err in rec.catalog_validation_errors:
                print(f"    Val. error    : {err}")
        if rec.parsed_json:
            keys = list(rec.parsed_json.keys())
            print(f"    Parsed keys   : {keys[:8]}")

    print("\nLLM audit trail complete")


# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 6 — LLM Systematizer: NL → PolicyRules
# MAGIC
# MAGIC Describe governance in natural language. LLM produces `BehaviorSpec`.
# MAGIC `Systematizer` converts it to executable `PolicyRule` objects.
# MAGIC

# COMMAND ----------

from cfa.behavior.llm import OpenAISystematizerBackend
from cfa.behavior import Systematizer

taxonomy, rules = None, None

if not HAS_LLM:
    print("SKIP: no LLM available (missing openai or API key)")
else:
    try:
        print("=" * 55)
        print("LLM SYSTEMATIZER -- NL to Policy Rules")
        print("=" * 55)

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
            temperature=0.0,
            max_tokens=2048,
        )

        taxonomy, rules = Systematizer().systematize_from_nl(
            governance_desc,
            backend=sys_backend,
            context="Fiscal ETL: NFe, Clientes, Vendas, Fornecedores on Databricks Delta Lake",
            target_layer="silver",
        )

        print(f"  Categories      : {taxonomy.category_count}")
        print(f"  Rules generated : {len(rules)}")
        print()

        for rule in rules:
            print(f"  Rule : {rule.name}")
            print(f"    code     : {rule.fault_code}")
            print(f"    action   : {rule.action.value}")
            print(f"    severity : {rule.severity.value}")
            print()

        test_intents = taxonomy.generate_test_intents(3)
        print(f"  CI test intents generated: {len(test_intents)}")
        for intent in test_intents:
            print(f"    - {intent}")

        print("\nLLM Systematizer complete")
    except Exception as e:
        print(f"  LLM call failed: {type(e).__name__}: {str(e)[:100]}")


# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 7 — Full Kernel with LLM Normalizer
# MAGIC
# MAGIC Same 5-phase pipeline (Formalize → Govern → Generate → Execute → Validate/Audit).
# MAGIC Only the **Formalize** phase switches from keyword-matching to DeepSeek.
# MAGIC

# COMMAND ----------

from cfa import KernelOrchestrator

if not HAS_LLM:
    print("SKIP: no API key available")
else:
    provider = make_provider()
    # strict=False: LLM resolves intent semantically; catalog used for grounding
    # but validation errors do not block execution (strict mode is for S4 demo only)
    backend = LLMNormalizerBackend(provider=provider, strict=False)

    kernel = KernelOrchestrator(
        catalog=CATALOG,
        config=KernelConfig(
            policy_bundle_version="fiscal-prod-v1.0",
            backend="pyspark",
        ),
        normalizer_backend=backend,
    )

    print("=" * 55)
    print("FULL KERNEL + LLM NORMALIZER")
    print("=" * 55)

    for intent in [
        "Join NFe with Clientes anonymize CPF and persist to Silver",
        "Aggregate vendas by region persist to Gold",
        "Export raw clientes PII to Gold",
    ]:
        print(f"\nIntent: \"{intent}\"")
        try:
            result = kernel.process(intent)
            print(f"  -> Decision  : {result.state.value.upper()}")
            if result.signature is not None:
                print(f"  -> Sig hash  : {result.signature.signature_hash[:24]}...")
            if result.replan_history:
                print(f"  -> Replans   : {len(result.replan_history)}")
            if result.generated_code and result.generated_code.code:
                lines = result.generated_code.code.splitlines()
                print(f"  -> Code gen  : {len(lines)} lines ({result.generated_code.language})")
                preview = [l for l in lines if l.strip()][:6]
                for line in preview:
                    print(f"     {line}")
                if len(lines) > 6:
                    print(f"     ... ({len(lines) - 6} more lines)")
        except Exception as e:
            print(f"  -> BLOCKED   : {type(e).__name__} | {str(e)[:100]}")

    calls = backend.audit_records
    print(f"\n  LLM calls by kernel: {len(calls)}")
    for rec in calls:
        print(f"    prompt={rec.prompt_hash[:16]}...  response={rec.response_hash[:16]}...")

    print("\nFull kernel + LLM complete")


# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 8 — Runtime Gate
# MAGIC
# MAGIC `RuntimeGate` validates intents before execution.
# MAGIC With `policy_rules` from LLM Systematizer, the gate inherits NL-defined governance.
# MAGIC

# COMMAND ----------

import traceback
print("=" * 55)
print("RUNTIME GATE")
print("=" * 55)

# Guard: 'rules' is set by Section 6 (LLM Systematizer).
# If that section was skipped or failed, fall back to default rules gracefully.
try:
    _rules = rules
except NameError:
    _rules = None

if _rules is None:
    print("NOTE: LLM-generated rules not available (Section 6 skipped or no API key).")
    print("      Using default CFA policy rules instead.")
else:
    print(f"  Using {len(_rules)} LLM-generated rules from Section 6")

try:
    gate = RuntimeGate(
        catalog=CATALOG,
        policy_rules=_rules,
    )

    result = gate.validate("Join NFe with Clientes and persist to Silver")
    print(f"  validate() -> state={result.state.value}  passed={result.passed}")
    print(f"  gate_id={result.gate_id}  execution_id={result.execution_id[:8]}...")

    @gate.guard("aggregate sales data with PII protected")
    def my_pipeline():
        return "pipeline executed"

    print(f"  @gate.guard -> {my_pipeline()}")
    print("\nRuntime Gate demo complete")
except Exception as e:
    print(f"  RUNTIME GATE FAILED: {type(e).__name__}")
    traceback.print_exc()


# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 9 — Comparing Normalizers: Rule-Based vs LLM
# MAGIC
# MAGIC Same intent, two backends — side-by-side comparison.
# MAGIC

# COMMAND ----------

print("=" * 55)
print("NORMALIZER COMPARISON: Rule-Based vs LLM")
print("=" * 55)

rule_norm = IntentNormalizer(backend=RuleBasedNormalizerBackend())
llm_norm = None
if HAS_LLM:
    provider = make_provider()
    # strict=False for comparison — we want to see the LLM output, not block it
    llm_norm = IntentNormalizer(backend=LLMNormalizerBackend(provider=provider, strict=False))

header = f"{'Intent':<50s} | {'Method':<12s} | {'Domain':<14s} | {'Layer':<8s} | {'Confidence':>10s}"
print(header)
print("-" * len(header))

for raw in [
    "Join NFe with Clientes anonymize CPF and persist to Silver",
    "Aggregate vendas by region persist to Gold",
    "Export raw clientes PII to Gold",
]:
    # Rule-based
    rb = rule_norm.normalize(raw, {}, CATALOG)
    sig_rb = rb.signature
    print(f"{raw[:47]:<50s} | {'rule-based':<12s} | {sig_rb.domain:<14s} | {str(sig_rb.target_layer):<8s} | {rb.confidence_score:>9.2f}")
    # LLM
    if llm_norm is not None:
        try:
            llm = llm_norm.normalize(raw, {}, CATALOG)
            sig_llm = llm.signature
            print(f"{'':50s} | {'LLM':<12s} | {sig_llm.domain:<14s} | {str(sig_llm.target_layer):<8s} | {llm.confidence_score:>9.2f}")
        except Exception as e:
            print(f"{'':50s} | {'LLM':<12s} | ERROR: {type(e).__name__}: {str(e)[:60]}")
    else:
        print(f"{'':50s} | {'LLM':<12s} | (no API key)")
    print()

print("Normalizer comparison complete")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 10 — PolicyEngine with LLM-Generated Rules
# MAGIC
# MAGIC Rules from `LLMSystematizer` (Section 6) feed `PolicyEngine`.
# MAGIC Closes the loop: NL governance → LLM → BehaviorSpec → PolicyRules → Engine.
# MAGIC

# COMMAND ----------

from cfa.types import DatasetRef, SignatureConstraints, TargetLayer, ExecutionContext

print("=" * 55)
print("POLICY ENGINE WITH LLM-GENERATED RULES")
print("=" * 55)

# Guard: 'rules' is set by Section 6 (LLM Systematizer).
try:
    _rules_s10 = rules
except NameError:
    _rules_s10 = None

if _rules_s10 is None:
    print("NOTE: LLM-generated rules not available (Section 6 skipped or no API key).")
    print("      Using default CFA policy rules instead.")
    engine = PolicyEngine()  # default rules
else:
    print(f"  Using {len(_rules_s10)} LLM-generated rules from Section 6")
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

r = engine.evaluate(sig_safe)
print(f"\n  Safe signature   -> {r.action.value.upper()}  faults={len(r.faults)}")

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

r2 = engine.evaluate(sig_unsafe)
print(f"  Unsafe signature -> {r2.action.value.upper()}  faults={len(r2.faults)}")
for fault in r2.faults[:4]:
    print(f"    [{fault.severity.value.upper():<10s}] {fault.code}")

print("\nLLM-rules PolicyEngine complete")


# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Summary
# MAGIC
# MAGIC | LLM Feature | Status | Notes |
# MAGIC |---|---|---|
# MAGIC | LLM Normalizer | ✓ | Semantic intent resolution via DeepSeek/OpenAI |
# MAGIC | Strict Mode | ✓ | LLM output validated against catalog |
# MAGIC | LLM Audit Trail | ✓ | Every call SHA-256 traceable |
# MAGIC | LLM Systematizer | ✓ | NL → BehaviorSpec → PolicyRules |
# MAGIC | Full Kernel + LLM | ✓ | End-to-end with LLM normalizer |
# MAGIC | Runtime Gate | ✓ | Guard with LLM-generated policy rules |
# MAGIC | Normalizer Comparison | ✓ | Rule-based vs LLM side-by-side |
# MAGIC | Secret Management | ✓ | Databricks Secret Scope `cfa-secrets` |
# MAGIC
# MAGIC **Key differences from rule-based:**
# MAGIC
# MAGIC - LLM understands intent **semantics**, not just keywords
# MAGIC - Natural language governance descriptions → executable rules
# MAGIC - Every LLM call is audited (prompt/response/catalog SHA-256)
# MAGIC - Strict mode prevents hallucinations by validating against catalog
# MAGIC - API key stored in **Databricks Secret Scope** — never in code
# MAGIC
# MAGIC **Secret scope setup (one-time):**
# MAGIC ```bash
# MAGIC databricks secrets create-scope cfa-secrets
# MAGIC databricks secrets put-secret cfa-secrets deepseek-key
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Links**
# MAGIC - [Documentation](https://marquesantero.github.io/cfa/docs/intro)
# MAGIC - [PyPI](https://pypi.org/project/cfa-kernel/)
# MAGIC - [GitHub](https://github.com/marquesantero/cfa)
# MAGIC