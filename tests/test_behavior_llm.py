"""Tests for cfa.behavior.llm — LLM-assisted behavior systematization."""

from __future__ import annotations

import json

import pytest

from cfa.behavior import Systematizer
from cfa.behavior.llm import (
    LLMSystematizer,
    LLMSystematizerBackend,
    OpenAISystematizerBackend,
)
from cfa.behavior.spec import BehaviorSpec

# ── Mock LLM backend ─────────────────────────────────────────────────────────


class MockLLMBackend(LLMSystematizerBackend):
    """Deterministic mock that returns a predefined BehaviorSpec JSON."""

    def __init__(self, response: str | None = None) -> None:
        self._response = response or self._default_response()
        self.calls: list[tuple[str, str]] = []

    @staticmethod
    def _default_response() -> str:
        return json.dumps({
            "behavior": {
                "name": "mock_pii_governance",
                "description": "Mock governance rules for testing.",
                "failure_modes": [
                    {
                        "code": "raw_pii_in_silver",
                        "label": "Raw PII in Silver",
                        "description": "PII columns exposed in silver write.",
                        "condition": "pii_in_protected_layer",
                        "severity": "critical",
                        "action": "block",
                        "target_layer": "silver",
                        "remediation": [
                            "Apply sha256 on all PII columns",
                            "Enable no_pii_raw constraint",
                        ],
                    },
                    {
                        "code": "missing_merge_key",
                        "label": "Missing Merge Key",
                        "description": "Write to silver without merge key.",
                        "condition": "missing_merge_key",
                        "severity": "critical",
                        "action": "block",
                        "target_layer": "silver",
                        "remediation": [
                            "Set merge_key_required=True",
                            "Define merge key in catalog",
                        ],
                    },
                    {
                        "code": "no_partition_filter",
                        "label": "No Partition Filter",
                        "description": "High volume dataset without partition.",
                        "condition": "missing_partition",
                        "severity": "high",
                        "action": "replan",
                        "target_layer": "silver",
                        "min_size_gb": 1.0,
                        "remediation": [
                            "Add partition_by with processing_date",
                        ],
                    },
                ],
            },
        })

    def complete(self, system_prompt: str, user_message: str) -> str:
        self.calls.append((system_prompt, user_message))
        return self._response


class FailingMockLLMBackend(LLMSystematizerBackend):
    """Mock that returns invalid JSON to test error handling."""

    def complete(self, system_prompt: str, user_message: str) -> str:
        return "This is not valid JSON at all."


class EmptyMockLLMBackend(LLMSystematizerBackend):
    """Mock that returns empty response."""

    def complete(self, system_prompt: str, user_message: str) -> str:
        return ""


class MarkdownMockLLMBackend(LLMSystematizerBackend):
    """Mock that wraps JSON in markdown fences (common LLM behavior)."""

    def __init__(self) -> None:
        inner = json.dumps({
            "behavior": {
                "name": "markdown_test",
                "description": "Wrapped in markdown.",
                "failure_modes": [
                    {
                        "code": "pii_check",
                        "label": "PII Check",
                        "description": "Check for PII exposure.",
                        "condition": "pii_in_protected_layer",
                        "severity": "critical",
                        "action": "block",
                        "target_layer": "silver",
                        "remediation": ["Apply sha256"],
                    },
                ],
            },
        })
        self._response = f"```json\n{inner}\n```"

    def complete(self, system_prompt: str, user_message: str) -> str:
        return self._response


# ── Tests ────────────────────────────────────────────────────────────────────


class TestLLMSystematizer:
    def test_systematize_nl_produces_spec(self):
        backend = MockLLMBackend()
        spec = LLMSystematizer().systematize_nl(
            "Pipeline must protect PII",
            backend=backend,
            context="PySpark ETL on Databricks",
        )
        assert isinstance(spec, BehaviorSpec)
        assert spec.name == "mock_pii_governance"
        assert len(spec.failure_modes) == 3
        assert spec.failure_modes[0]["code"] == "raw_pii_in_silver"
        assert len(backend.calls) == 1

    def test_systematize_nl_empty_response_raises(self):
        backend = EmptyMockLLMBackend()
        with pytest.raises(ValueError, match="empty response"):
            LLMSystematizer().systematize_nl("test", backend=backend)

    def test_systematize_nl_invalid_json_raises(self):
        backend = FailingMockLLMBackend()
        with pytest.raises(ValueError, match="not valid JSON"):
            LLMSystematizer().systematize_nl("test", backend=backend)

    def test_systematize_nl_markdown_wrapped_json(self):
        backend = MarkdownMockLLMBackend()
        spec = LLMSystematizer().systematize_nl("test", backend=backend)
        assert isinstance(spec, BehaviorSpec)
        assert spec.name == "markdown_test"
        assert len(spec.failure_modes) == 1

    def test_systematize_nl_without_context(self):
        backend = MockLLMBackend()
        spec = LLMSystematizer().systematize_nl(
            "Pipeline must protect PII and enforce merge keys.",
            backend=backend,
        )
        assert isinstance(spec, BehaviorSpec)
        assert len(spec.failure_modes) == 3


class TestSystematizerFromNL:
    def test_systematize_from_nl_integration(self):
        backend = MockLLMBackend()
        taxonomy, rules = Systematizer().systematize_from_nl(
            "Pipeline must protect PII and enforce merge keys.",
            backend=backend,
            context="PySpark ETL",
        )
        assert taxonomy.name == "mock_pii_governance"
        assert taxonomy.category_count == 4  # 3 not-allowed + 1 implicit allowed
        assert len(rules) == 3
        assert all(hasattr(r, "name") for r in rules)

    def test_systematize_from_nl_produces_valid_rules(self):
        backend = MockLLMBackend()
        _, rules = Systematizer().systematize_from_nl(
            "Pipeline must protect PII.",
            backend=backend,
        )
        assert len(rules) > 0
        # Verify rules have required attributes
        for rule in rules:
            assert rule.name
            assert rule.fault_code.startswith("BEHAVIOR_")
            assert rule.condition is not None

    def test_systematize_from_nl_respects_target_layer(self):
        backend = MockLLMBackend()
        _, rules = Systematizer().systematize_from_nl(
            "Pipeline must protect PII.",
            backend=backend,
            target_layer="gold",
        )
        assert len(rules) > 0


class TestOpenAISystematizerBackend:
    def test_constructor_defaults(self):
        backend = OpenAISystematizerBackend()
        assert backend.model == "gpt-4o-mini"
        assert backend.temperature == 0.0

    def test_constructor_custom(self):
        backend = OpenAISystematizerBackend(
            model="gpt-4",
            temperature=1.0,
            max_tokens=512,
        )
        assert backend.model == "gpt-4"
        assert backend.max_tokens == 512
