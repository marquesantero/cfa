"""
CFA LLM Systematizer
====================
Optional LLM-backed plugin for behavior specification.

Transforms natural-language governance descriptions into BehaviorSpecs
that feed the deterministic Systematizer. The LLM is used only for the
"understanding" step — all rules are still generated deterministically.

Usage:
    from cfa.behavior.llm import OpenAISystematizerBackend
    from cfa.behavior import Systematizer

    backend = OpenAISystematizerBackend(model="gpt-4o-mini")
    taxonomy, rules = Systematizer().systematize_from_nl(
        "Pipeline must protect PII, enforce merge keys, and stay within budget.",
        backend=backend,
    )

Architecture:
    NL description → LLM → BehaviorSpec (JSON) → Systematizer → (Taxonomy, Rules)
                   ↑ optional              ↑ deterministic
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from .spec import BehaviorSpec

_SYSTEMATIZER_SYSTEM_PROMPT = """\
You are a data governance specification expert. Given a description of a data \
pipeline's requirements, constraints, and context, produce a structured \
behavior specification in JSON format.

For each potential failure mode, classify it using ONE of these condition types:
{pii_in_protected_layer, missing_merge_key, missing_partition, schema_mismatch,
 cost_budget_exceeded, sensitive_without_partition, enforce_types_disabled,
 pii_without_policy, unauthorized_gold_write, custom}

Condition type meanings:
- pii_in_protected_layer: PII exposed in Silver/Gold without anonymization
- missing_merge_key: Write to Silver/Gold without merge_key enforcement
- missing_partition: High-volume or sensitive dataset processed without partition filter
- schema_mismatch: Output schema differs from contract
- cost_budget_exceeded: Estimated cost exceeds configured ceiling
- sensitive_without_partition: Sensitive dataset without partition declaration
- enforce_types_disabled: Type enforcement disabled on protected layer write
- pii_without_policy: PII present without no_pii_raw constraint
- unauthorized_gold_write: Unauthorized write to Gold layer
- custom: Any other custom governance condition

Output ONLY valid JSON. No markdown fences, no explanation outside the JSON.

JSON schema:
{
  "behavior": {
    "name": "<snake_case_name>",
    "description": "<markdown_description_of_governance_rules>",
    "failure_modes": [
      {
        "code": "<unique_snake_case_code>",
        "label": "<Short human-readable label>",
        "description": "<When this failure occurs and why it matters>",
        "condition": "<condition_type>",
        "severity": "<critical|high|medium|warning|info>",
        "action": "<replan|block>",
        "target_layer": "<bronze|silver|gold>",
        "remediation": ["<actionable step 1>", "<actionable step 2>"]
      }
    ]
  }
}

Rules:
- Generate at least 2 failure modes covering the most important constraints.
- Use "action": "replan" for automatically fixable issues, "action": "block" for
  issues that require human review (e.g., PII in Gold without anonymization).
- Severity: "critical" for PII/security, "high" for data quality, "medium" for
  cost/performance, "warning" for informational.
- Remediation steps must be actionable and specific.
"""

_SYSTEMATIZER_USER_TEMPLATE = """\
Pipeline description:
{description}

Context:
{context}
"""


class LLMSystematizerBackend(ABC):
    """Backend for LLM-assisted behavior specification.

    Implement this to use any LLM provider (OpenAI, Anthropic, Azure, local).
    """

    @abstractmethod
    def complete(self, system_prompt: str, user_message: str) -> str:
        """Send prompts to the LLM and return the completion text."""
        ...


class OpenAISystematizerBackend(LLMSystematizerBackend):
    """OpenAI-compatible backend for NL → BehaviorSpec.

    Requires: pip install openai

    Args:
        model: Model name (default: gpt-4o-mini).
        temperature: Sampling temperature (default: 0.0 for deterministic output).
        api_key: OpenAI API key. If None, reads from OPENAI_API_KEY env var.
        base_url: Custom API base URL (for Azure, local models, etc.).
        max_tokens: Maximum completion tokens.
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.0,
        api_key: str | None = None,
        base_url: str | None = None,
        max_tokens: int = 2048,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.api_key = api_key
        self.base_url = base_url
        self.max_tokens = max_tokens

    def complete(self, system_prompt: str, user_message: str) -> str:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError(
                f"openai package is required for OpenAISystematizerBackend. "
                f"Underlying error: {exc}. "
                f"Install it with: pip install openai"
            ) from exc

        client_kwargs: dict[str, Any] = {}
        if self.api_key:
            client_kwargs["api_key"] = self.api_key
        if self.base_url:
            client_kwargs["base_url"] = self.base_url

        client = OpenAI(**client_kwargs)

        response = client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        return response.choices[0].message.content or ""


class LLMSystematizer:
    """Transforms NL descriptions into BehaviorSpecs via an LLM backend.

    This is the "Phase 6" plugin — adds NL understanding on top of the
    deterministic Systematizer. Without a backend, falls back gracefully.

    Usage:
        backend = OpenAISystematizerBackend()
        spec = LLMSystematizer().systematize_nl(
            "Pipeline must protect PII and enforce merge keys.",
            backend=backend,
        )
        # spec is a BehaviorSpec ready for Systematizer
    """

    def systematize_nl(
        self,
        description: str,
        *,
        backend: LLMSystematizerBackend,
        context: str = "",
    ) -> BehaviorSpec:
        """Transform a natural language description into a BehaviorSpec.

        Args:
            description: Natural language description of governance requirements.
            backend: LLM backend implementation.
            context: Optional context about the target system.

        Returns:
            A BehaviorSpec ready for Systematizer.systematize().

        Raises:
            ValueError: If the LLM response cannot be parsed.
        """
        user_message = _SYSTEMATIZER_USER_TEMPLATE.format(
            description=description, context=context or "No additional context provided."
        )

        raw = backend.complete(_SYSTEMATIZER_SYSTEM_PROMPT, user_message)

        if not raw.strip():
            raise ValueError("LLM returned empty response.")

        data = self._parse_llm_response(raw)
        return BehaviorSpec.from_dict(data)

    def _parse_llm_response(self, raw: str) -> dict[str, Any]:
        raw = raw.strip()
        # Remove markdown code fences if present
        if raw.startswith("```"):
            lines = raw.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw = "\n".join(lines)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Try to find JSON object in the text
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                try:
                    data = json.loads(raw[start : end + 1])
                except json.JSONDecodeError:
                    raise ValueError(
                        f"LLM response is not valid JSON. Raw response:\n{raw[:500]}"
                    )
            else:
                raise ValueError(
                    f"LLM response does not contain JSON. Raw response:\n{raw[:500]}"
                )

        if "behavior" not in data:
            raise ValueError(
                f"LLM response missing 'behavior' key. Got keys: {list(data.keys())}"
            )

        return data
