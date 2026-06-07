"""Tests for cfa.normalizer_llm — LLM-powered intent normalization."""

from __future__ import annotations

import json

import pytest

from cfa.normalizer.base import (
    IntentNormalizer,
    NormalizerInput,
    NormalizerOutput,
)
from cfa.normalizer.llm import (
    LLMNormalizerBackend,
    LLMProvider,
    OpenAILMProvider,
    _build_user_message,
)

CATALOG = {
    "datasets": {
        "nfe": {"classification": "high_volume", "size_gb": 4000, "pii_columns": [], "partition_column": "processing_date"},
        "clientes": {"classification": "sensitive", "size_gb": 0.5, "pii_columns": ["cpf", "email"], "partition_column": "processing_date"},
        "produtos": {"classification": "internal", "size_gb": 0.1, "pii_columns": []},
    }
}


class MockLLMProvider(LLMProvider):
    """Deterministic mock LLM for testing."""

    def __init__(self, response: str | None = None) -> None:
        self._response = response or self._default_response()
        self.calls: list[tuple[str, str]] = []

    @staticmethod
    def _default_response() -> str:
        return json.dumps({
            "domain": "fiscal_data_processing",
            "intent": "reconciliation_and_persist",
            "target_layer": "silver",
            "datasets": [
                {"name": "nfe", "classification": "high_volume", "size_gb": 4000, "pii_columns": [], "partition_column": "processing_date"},
                {"name": "clientes", "classification": "sensitive", "size_gb": 0.5, "pii_columns": ["cpf", "email"], "partition_column": "processing_date"},
            ],
            "constraints": {
                "no_pii_raw": True,
                "merge_key_required": True,
                "enforce_types": True,
                "partition_by": ["processing_date"],
            },
            "confidence_score": 0.92,
            "ambiguity_level": "low",
            "competing_interpretations": [],
            "environment_constraints_injected": [],
            "reasoning": "Fiscal reconciliation of NFe invoices with customer data, writing to Silver layer with PII protection.",
        })

    def complete(self, system_prompt: str, user_message: str) -> str:
        self.calls.append((system_prompt, user_message))
        return self._response


class TestLLMNormalizerBackend:
    def test_resolve_basic_intent(self):
        provider = MockLLMProvider()
        backend = LLMNormalizerBackend(provider=provider)

        inp = NormalizerInput(
            raw_intent="Join NFe with Clientes and persist to Silver",
            environment_state={"datasets": {}},
            catalog=CATALOG,
            policy_bundle_version="v1.0",
            catalog_snapshot_version="catalog_v1",
            context_registry_version_id="ctx_001",
        )
        output = backend.resolve(inp)

        assert output.domain == "fiscal_data_processing"
        assert output.intent == "reconciliation_and_persist"
        assert output.target_layer == "silver"
        assert len(output.datasets) == 2
        assert output.datasets[0]["name"] == "nfe"
        assert output.confidence_score == 0.92
        assert output.ambiguity_level == "low"
        assert output.constraints["no_pii_raw"] is True
        assert len(provider.calls) == 1

    def test_fallback_to_rule_based_on_error(self):
        provider = MockLLMProvider(response="invalid json {{{")
        backend = LLMNormalizerBackend(provider=provider, strict=False)

        inp = NormalizerInput(
            raw_intent="Join NFe with Clientes persist Silver",
            environment_state={}, catalog=CATALOG,
            policy_bundle_version="v1", catalog_snapshot_version="v1",
            context_registry_version_id="ctx",
        )
        output = backend.resolve(inp)
        assert output.domain in ("fiscal_data_processing", "general")

    def test_strict_mode_raises(self):
        provider = MockLLMProvider(response="invalid json {{{")
        backend = LLMNormalizerBackend(provider=provider, strict=True)

        inp = NormalizerInput(
            raw_intent="test", environment_state={}, catalog=CATALOG,
            policy_bundle_version="v1", catalog_snapshot_version="v1",
            context_registry_version_id="ctx",
        )
        with pytest.raises(ValueError):
            backend.resolve(inp)

    def test_empty_response_fallback(self):
        provider = MockLLMProvider(response="")
        backend = LLMNormalizerBackend(provider=provider, strict=False)

        inp = NormalizerInput(
            raw_intent="test", environment_state={}, catalog=CATALOG,
            policy_bundle_version="v1", catalog_snapshot_version="v1",
            context_registry_version_id="ctx",
        )
        output = backend.resolve(inp)
        assert isinstance(output, NormalizerOutput)

    def test_markdown_wrapped_json(self):
        response = "```json\n" + MockLLMProvider._default_response() + "\n```"
        provider = MockLLMProvider(response=response)
        backend = LLMNormalizerBackend(provider=provider)

        inp = NormalizerInput(
            raw_intent="test", environment_state={}, catalog=CATALOG,
            policy_bundle_version="v1", catalog_snapshot_version="v1",
            context_registry_version_id="ctx",
        )
        output = backend.resolve(inp)
        assert output.domain == "fiscal_data_processing"


class TestLLMNormalizerEndToEnd:
    def test_full_pipeline_with_llm_normalizer(self):
        """End-to-end: LLM normalizer → IntentNormalizer → SemanticResolution."""
        provider = MockLLMProvider()
        backend = LLMNormalizerBackend(provider=provider)

        normalizer = IntentNormalizer(
            backend=backend,
            policy_bundle_version="v1.0",
            catalog_snapshot_version="catalog_v1",
        )
        resolution = normalizer.normalize(
            raw_intent="Join NFe with Clientes and persist to Silver",
            environment_state={"datasets": {}},
            catalog=CATALOG,
            context_registry_version_id="ctx_001",
        )

        assert resolution.signature is not None
        assert resolution.signature.domain == "fiscal_data_processing"
        assert resolution.confidence_score == 0.92
        assert resolution.ambiguity_level.value == "low"

    def test_kernel_with_llm_normalizer(self):
        """Full kernel pipeline with LLM normalizer."""
        from cfa.core.kernel import KernelConfig, KernelOrchestrator

        provider = MockLLMProvider()
        backend = LLMNormalizerBackend(provider=provider)

        kernel = KernelOrchestrator(
            catalog=CATALOG,
            config=KernelConfig(normalizer="llm"),
            normalizer_backend=backend,
        )
        result = kernel.process("Join NFe with Clientes and persist to Silver")

        assert result.is_executable
        assert result.resolution is not None
        assert result.resolution.signature.domain == "fiscal_data_processing"
        assert len(result.audit_events) > 0

    def test_mock_vs_llm_consistency(self):
        """LLM normalizer should produce similar results to mock for known intents."""
        from cfa.core.kernel import KernelConfig, KernelOrchestrator

        # Mock normalizer
        kernel_mock = KernelOrchestrator(catalog=CATALOG)
        result_mock = kernel_mock.process("Join NFe with Clientes and persist to Silver")
        assert result_mock.is_executable

        # LLM normalizer
        provider = MockLLMProvider()
        backend = LLMNormalizerBackend(provider=provider)
        kernel_llm = KernelOrchestrator(
            catalog=CATALOG,
            config=KernelConfig(normalizer="llm"),
            normalizer_backend=backend,
        )
        result_llm = kernel_llm.process("Join NFe with Clientes and persist to Silver")
        assert result_llm.is_executable

        # Both should produce valid, executable results
        assert result_mock.state.value in ("approved", "approved_with_warnings")
        assert result_llm.state.value in ("approved", "approved_with_warnings")


class TestBuildUserMessage:
    def test_includes_catalog(self):
        inp = NormalizerInput(
            raw_intent="test", environment_state={}, catalog=CATALOG,
            policy_bundle_version="v1", catalog_snapshot_version="v1",
            context_registry_version_id="ctx",
        )
        msg = _build_user_message(inp)
        assert "nfe" in msg
        assert "clientes" in msg
        assert "cpf" in msg
        assert "User Intent" in msg
        assert "Data Catalog" in msg

    def test_includes_environment(self):
        inp = NormalizerInput(
            raw_intent="test",
            environment_state={"datasets": {"nfe": {"state": "published"}}},
            catalog=CATALOG,
            policy_bundle_version="v1", catalog_snapshot_version="v1",
            context_registry_version_id="ctx",
        )
        msg = _build_user_message(inp)
        assert "published" in msg


class TestOpenAILMProvider:
    def test_constructor_defaults(self):
        provider = OpenAILMProvider()
        assert provider.model == "gpt-4o-mini"
        assert provider.temperature == 0.0

    def test_deepseek_config(self):
        provider = OpenAILMProvider(
            model="deepseek-chat",
            base_url="https://api.deepseek.com",
            api_key="sk-test",
        )
        assert provider.model == "deepseek-chat"
        assert provider.base_url == "https://api.deepseek.com"


class TestLLMStrictMode:
    def test_strict_rejects_missing_catalog_dataset(self):
        """LLM returns a dataset not in the catalog → should raise."""
        fake_response = json.dumps({
            "domain": "fiscal",
            "intent": "ingest",
            "target_layer": "bronze",
            "datasets": [
                {"name": "dataset_inexistente", "classification": "internal", "pii_columns": [], "size_gb": 0},
            ],
            "constraints": {"no_pii_raw": True, "merge_key_required": False, "enforce_types": True, "partition_by": []},
            "confidence_score": 0.80,
            "ambiguity_level": "low",
            "competing_interpretations": [],
            "environment_constraints_injected": [],
            "reasoning": "test",
        })
        provider = MockLLMProvider(response=fake_response)
        backend = LLMNormalizerBackend(provider=provider, strict=True)

        inp = NormalizerInput(
            raw_intent="test", environment_state={}, catalog=CATALOG,
            policy_bundle_version="v1", catalog_snapshot_version="v1",
            context_registry_version_id="ctx",
        )
        with pytest.raises(ValueError, match="catalog validation"):
            backend.resolve(inp)

    def test_strict_accepts_valid_catalog_match(self):
        provider = MockLLMProvider()
        backend = LLMNormalizerBackend(provider=provider, strict=True)

        inp = NormalizerInput(
            raw_intent="Join NFe with Clientes persist Silver",
            environment_state={}, catalog=CATALOG,
            policy_bundle_version="v1", catalog_snapshot_version="v1",
            context_registry_version_id="ctx",
        )
        output = backend.resolve(inp)
        assert output.domain == "fiscal_data_processing"
        assert len(backend.audit_records) >= 1
        assert backend.audit_records[-1].prompt_hash
        assert backend.audit_records[-1].response_hash
        assert backend.audit_records[-1].catalog_hash

    def test_strict_rejects_misclassified_dataset(self):
        """LLM returns wrong classification for a known dataset."""
        fake_response = json.dumps({
            "domain": "fiscal",
            "intent": "ingest",
            "target_layer": "bronze",
            "datasets": [
                {"name": "nfe", "classification": "internal", "pii_columns": [], "size_gb": 4000},
            ],
            "constraints": {"no_pii_raw": True, "merge_key_required": False, "enforce_types": True, "partition_by": []},
            "confidence_score": 0.80,
            "ambiguity_level": "low",
            "competing_interpretations": [],
            "environment_constraints_injected": [],
            "reasoning": "test",
        })
        provider = MockLLMProvider(response=fake_response)
        backend = LLMNormalizerBackend(provider=provider, strict=True)

        inp = NormalizerInput(
            raw_intent="test", environment_state={}, catalog=CATALOG,
            policy_bundle_version="v1", catalog_snapshot_version="v1",
            context_registry_version_id="ctx",
        )
        with pytest.raises(ValueError, match="catalog validation"):
            backend.resolve(inp)
