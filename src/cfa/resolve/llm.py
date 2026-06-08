"""
CFA LLM Normalizer Backend
===========================
Replaces keyword matching with real LLM semantic resolution.

The Normalizer is the most critical pipeline component — an error here
contaminates the entire system. This backend uses an LLM to understand
natural language intents and map them to typed StateSignatures using
the data catalog as ground truth.

Architecture:
    NL intent + catalog → LLM prompt → JSON response → NormalizerOutput → StateSignature

Strict mode (default for production):
    - LLM response is validated against catalog
    - Datasets returned by LLM MUST exist in catalog
    - Classifications MUST match catalog metadata
    - No silent fallback — failure raises explicitly
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from cfa.resolve.base import NormalizerBackend, NormalizerInput, NormalizerOutput

_SYSTEM_PROMPT = """\
You are a data governance resolution engine. Your task is to analyze a natural \
language intent and map it to a structured JSON output using the provided data \
catalog as ground truth.

## Rules

1. **domain**: Classify the business domain. Choose from: fiscal_data_processing, \
customer_data, financial_data, inventory, sales, general.
   Use "general" only if no specific domain matches.

2. **intent**: Classify the operation type. Choose from:
   - reconciliation_and_persist (join/merge/reconcile datasets and write)
   - aggregate_and_persist (group by, summarize, aggregate and write)
   - ingest (load/import/ingest raw data)
   - transform_and_persist (apply transformations and write)
   - query (read-only, no write)

3. **target_layer**: Determine the target data layer. Choose from: bronze, silver, gold.
   - bronze: raw ingestion, landing zone
   - silver: refined, joined, cleaned, trusted
   - gold: aggregated, curated, final, master

4. **datasets**: List ONLY datasets that appear in the provided catalog. \
For each, include:
   - name: exact catalog name
   - classification: one of [high_volume, internal, public, sensitive].
     Use the catalog's classification field if present. If absent, derive:
     size_gb > 100 -> high_volume, pii_columns not empty -> sensitive, else -> internal
   - pii_columns: from catalog metadata (empty list if none)
   - size_gb: from catalog metadata
   - partition_column: from catalog metadata (null if none)

5. **constraints**: Derive governance constraints from the intent:
   - no_pii_raw: true if the intent implies PII will be protected/anonymized/masked.
     Set to false ONLY if the user EXPLICITLY mentions leaving PII raw, unprotected,
     or writing without anonymization. Keywords: "raw", "without anonymization",
     "unprotected", "as-is", "direct", "without masking".
   - merge_key_required: true if writing to silver or gold (safe default)
   - enforce_types: true (safe default)
   - partition_by: list partition columns from datasets involved
   - max_cost_dbu: null (no limit unless specified in intent)

6. **confidence_score**: 0.0 to 1.0.
   - 0.90-1.00: all datasets matched in catalog, clear intent
   - 0.70-0.89: most datasets matched, intent is clear
   - 0.50-0.69: partial match or ambiguous intent
   - 0.00-0.49: no catalog match, highly ambiguous

7. **ambiguity_level**: low, medium, or high based on confidence and competing interpretations.

8. **reasoning**: One sentence explaining your classification in plain English.

## Critical: PII Awareness

IMPORTANT: Your job is to faithfully capture the user's expressed intent, NOT to protect
them. The PolicyEngine downstream will BLOCK dangerous operations. Set no_pii_raw: false
only when the user explicitly asks for raw/unprotected PII in their own words.

If any matched dataset has pii_columns in the catalog:
- Set no_pii_raw: true
- Increase merge_key_required if writing to silver/gold
- Note: the PolicyEngine will BLOCK intents that expose raw PII to protected layers

## Output Format

Return ONLY valid JSON. No markdown fences, no explanation outside the JSON.

{
  "domain": "<domain>",
  "intent": "<intent>",
  "target_layer": "<bronze|silver|gold>",
  "datasets": [
    {
      "name": "<exact_catalog_name>",
      "classification": "<high_volume|internal|public|sensitive>",
      "pii_columns": ["<col1>", "<col2>"],
      "size_gb": <number>,
      "partition_column": "<col or null>"
    }
  ],
  "constraints": {
    "no_pii_raw": <true|false>,
    "merge_key_required": <true|false>,
    "enforce_types": <true|false>,
    "partition_by": ["<col1>"],
    "max_cost_dbu": <number or null>
  },
  "confidence_score": <0.0-1.0>,
  "ambiguity_level": "<low|medium|high>",
  "competing_interpretations": [],
  "environment_constraints_injected": [],
  "reasoning": "<one sentence>"
}
"""

_RAW_PII_KEYWORDS = [
    "raw pii", "raw data", "unprotected", "without anonymization",
    "without masking", "without protection", "as-is", "without treatment",
    "sem anonimizacao", "sem mascara", "dados brutos", "pii cru",
    "direct to gold", "direct to silver", "write raw", "raw write",
]

_PII_COLUMN_PATTERNS = [
    "nome", "cpf", "email", "documento", "telefone", "endereco",
    "rg", "passport", "ssn", "credit card", "birth", "nascimento",
]

_ALLOWED_CLASSIFICATIONS = {"public", "internal", "sensitive", "high_volume"}
_ALLOWED_LAYERS = {"bronze", "silver", "gold"}


def _user_wants_raw_pii(intent: str) -> bool:
    """Detect if the user explicitly requested raw/unprotected PII."""
    lower = intent.lower()
    if any(kw in lower for kw in _RAW_PII_KEYWORDS):
        return True
    for col in _PII_COLUMN_PATTERNS:
        if f"raw {col}" in lower or f"{col} raw" in lower:
            return True
    if " with raw " in lower:
        return True
    return False


def _build_user_message(inp: NormalizerInput) -> str:
    catalog_json = json.dumps(inp.catalog, indent=2, ensure_ascii=False)
    env_json = json.dumps(inp.environment_state, indent=2, ensure_ascii=False)
    return f"""## User Intent

{inp.raw_intent}

## Data Catalog (ground truth — use ONLY datasets listed here)

```json
{catalog_json}
```

## Environment State

```json
{env_json}
```

## Metadata

- policy_bundle_version: {inp.policy_bundle_version}
- catalog_snapshot_version: {inp.catalog_snapshot_version}
- context_registry_version_id: {inp.context_registry_version_id}

Analyze the intent against the catalog and return the structured JSON output."""


class LLMProvider(ABC):
    """Minimal LLM provider interface — implement for any model."""

    @abstractmethod
    def complete(self, system_prompt: str, user_message: str) -> str: ...


class OpenAILMProvider(LLMProvider):
    """OpenAI-compatible LLM provider.
    Args:
        model: Model name (default: gpt-4o-mini).
        temperature: Sampling temperature (default: 0.0).
        api_key: OpenAI API key. Reads from OPENAI_API_KEY env var if None.
        base_url: Custom API base URL (Azure, local, etc.).
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.0,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.api_key = api_key
        self.base_url = base_url

    def complete(self, system_prompt: str, user_message: str) -> str:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError(
                f"openai package is required for OpenAILMProvider. "
                f"Underlying error: {exc}. "
                f"Install it with: pip install openai"
            ) from exc
        kwargs: dict[str, Any] = {}
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.base_url:
            kwargs["base_url"] = self.base_url
        client = OpenAI(**kwargs)
        response = client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        return response.choices[0].message.content or ""


@dataclass
class LLMAuditRecord:
    model: str
    prompt_hash: str
    response_hash: str
    catalog_hash: str
    raw_response: str
    parsed_json: dict[str, Any] | None
    catalog_validation_errors: list[str]


class LLMNormalizerBackend(NormalizerBackend):
    """Normalizer backend powered by an LLM — replaces keyword matching.

    In strict mode (``strict=True``, the default), the LLM response is validated
    against the catalog and any mismatch is raised as an error. In non-strict
    mode (``strict=False``), fallback to rule-based is used on failure.

    Every LLM call is audited: prompt hash, response hash, and catalog validation
    are recorded in ``_audit_records`` for traceability.

    Usage:
        from cfa.resolve import IntentNormalizer
        from cfa.resolve.llm import OpenAILMProvider, LLMNormalizerBackend

        provider = OpenAILMProvider(model="gpt-4o-mini")
        backend = LLMNormalizerBackend(provider=provider)
        normalizer = IntentNormalizer(backend=backend)
        resolution = normalizer.normalize(intent, env_state, catalog)
    """

    def __init__(
        self,
        provider: LLMProvider,
        *,
        strict: bool = True,
    ) -> None:
        self.provider = provider
        self.strict = strict
        self._audit_records: list[LLMAuditRecord] = []

    @property
    def audit_records(self) -> list[LLMAuditRecord]:
        return list(self._audit_records)

    def resolve(self, inp: NormalizerInput) -> NormalizerOutput:
        user_msg = _build_user_message(inp)
        prompt_hash = hashlib.sha256(
            (_SYSTEM_PROMPT + user_msg).encode("utf-8")
        ).hexdigest()

        catalog_json = json.dumps(inp.catalog, sort_keys=True, default=str)
        catalog_hash = hashlib.sha256(catalog_json.encode("utf-8")).hexdigest()

        try:
            raw = self.provider.complete(_SYSTEM_PROMPT, user_msg)
            response_hash = hashlib.sha256(
                (raw or "").encode("utf-8")
            ).hexdigest()

            if not raw or not raw.strip():
                raise ValueError("LLM returned empty response")

            data = self._parse_json(raw)
            record = LLMAuditRecord(
                model=getattr(self.provider, "model", "unknown"),
                prompt_hash=prompt_hash,
                response_hash=response_hash,
                catalog_hash=catalog_hash,
                raw_response=raw,
                parsed_json=data,
                catalog_validation_errors=[],
            )

            if self.strict:
                errors = self._validate_against_catalog(data, inp.catalog)
                record.catalog_validation_errors = errors
                self._audit_records.append(record)
                if errors:
                    err_msg = "; ".join(errors)
                    raise ValueError(f"LLM response failed catalog validation: {err_msg}")

            self._audit_records.append(record)
            return self._build_output(data, inp)

        except (ValueError, ImportError, ConnectionError, TimeoutError, json.JSONDecodeError, OSError):
            if self.strict:
                raise
            from cfa.resolve.base import RuleBasedNormalizerBackend
            return RuleBasedNormalizerBackend().resolve(inp)

    # ── Output builder ────────────────────────────────────────────────────

    def _build_output(
        self, data: dict[str, Any], inp: NormalizerInput
    ) -> NormalizerOutput:
        output = NormalizerOutput(
            domain=data.get("domain", "general"),
            intent=data.get("intent", "transform_and_persist"),
            target_layer=data.get("target_layer", "silver"),
            datasets=data.get("datasets", []),
            constraints=data.get("constraints", {
                "no_pii_raw": True,
                "merge_key_required": True,
                "enforce_types": True,
                "partition_by": [],
            }),
            confidence_score=float(data.get("confidence_score", 0.5)),
            ambiguity_level=data.get("ambiguity_level", "medium"),
            competing_interpretations=data.get("competing_interpretations", []),
            environment_constraints_injected=data.get("environment_constraints_injected", []),
            reasoning=data.get("reasoning", ""),
        )

        if _user_wants_raw_pii(inp.raw_intent):
            output.constraints["no_pii_raw"] = False
            if not output.reasoning:
                output.reasoning = ""
            output.reasoning += " [RAW PII REQUESTED — set no_pii_raw=False]"

        return output

    # ── Catalog validation (strict mode) ──────────────────────────────────

    def _validate_against_catalog(
        self, data: dict[str, Any], catalog: dict[str, Any]
    ) -> list[str]:
        errors: list[str] = []
        # Support both flat dict {name: meta} and nested {"datasets": {name: meta}}
        catalog_datasets = catalog.get("datasets") if isinstance(catalog.get("datasets"), dict) else catalog

        for ds in data.get("datasets", []):
            name = ds.get("name", "")
            if not name:
                errors.append("dataset name is missing in LLM response")
                continue
            if name not in catalog_datasets:
                errors.append(
                    f"dataset '{name}' returned by LLM does not exist in catalog. "
                    f"Available: {sorted(catalog_datasets.keys())}"
                )
                continue

            cat_entry = catalog_datasets[name]
            llm_classification = ds.get("classification", "")
            cat_classification = cat_entry.get("classification", "internal")
            if llm_classification and llm_classification != cat_classification:
                errors.append(
                    f"dataset '{name}': LLM said classification='{llm_classification}' "
                    f"but catalog says '{cat_classification}'"
                )

            llm_pii = set(ds.get("pii_columns", []))
            cat_pii = set(cat_entry.get("pii_columns", []))
            if cat_pii - llm_pii:
                errors.append(
                    f"dataset '{name}': LLM missed PII columns declared in catalog: "
                    f"{sorted(cat_pii - llm_pii)}"
                )

        target_layer = data.get("target_layer", "")
        if target_layer and target_layer not in _ALLOWED_LAYERS:
            errors.append(f"target_layer '{target_layer}' is not valid. Use: {sorted(_ALLOWED_LAYERS)}")

        for ds in data.get("datasets", []):
            classification = ds.get("classification", "")
            if classification and classification not in _ALLOWED_CLASSIFICATIONS:
                errors.append(
                    f"classification '{classification}' for dataset '{ds.get('name', '?')}' "
                    f"is not valid. Use: {sorted(_ALLOWED_CLASSIFICATIONS)}"
                )

        return errors

    # ── JSON parser ───────────────────────────────────────────────────────

    def _parse_json(self, raw: str) -> dict[str, Any]:
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw = "\n".join(lines)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                return json.loads(raw[start : end + 1])
            raise ValueError("LLM response does not contain valid JSON")
