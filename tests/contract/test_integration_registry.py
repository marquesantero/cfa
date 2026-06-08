"""Tests for the Integration / DecisionSink protocols.

Demonstrates that an integration can be implemented structurally, registered,
and composed with decision sinks — without touching the kernel. See ADR-0010.
"""

from __future__ import annotations

from typing import Any

import pytest

from cfa.core.integration import (
    DecisionSink,
    DecisionSinkRegistry,
    Integration,
    IntegrationInputError,
    IntegrationRegistry,
)
from cfa.types import DecisionState, KernelResult


# ─── Reference integration and sinks ─────────────────────────────────────────


class _MockDbtIntegration:
    name = "mock-dbt-check"
    consumes = ["dbt-manifest"]
    produces = "data"

    def build_signatures(self, raw: Any):
        if not isinstance(raw, dict) or "nodes" not in raw:
            raise IntegrationInputError(
                "$.nodes", "manifest is missing the 'nodes' object"
            )
        from cfa.types import (
            DatasetClassification,
            DatasetRef,
            ExecutionContext,
            SignatureConstraints,
            StateSignature,
            TargetLayer,
        )

        signatures = []
        for node_id in raw["nodes"]:
            sig = StateSignature(
                domain="fiscal",
                intent="reconciliation",
                target_layer=TargetLayer.SILVER,
                datasets=(DatasetRef(name=node_id, classification=DatasetClassification.INTERNAL),),
                constraints=SignatureConstraints(partition_by=("processing_date",)),
                execution_context=ExecutionContext("v1", "c1", "r1"),
            )
            signatures.append(sig)
        return signatures

    def emit_decisions(self, results):
        for r in results:
            _RECORDED.append(("emit", r.intent_id, r.state.value))


class _RecordingSink:
    name = "recorder"

    def __init__(self) -> None:
        self.received: list[KernelResult] = []

    def emit(self, result: KernelResult) -> None:
        self.received.append(result)

    def flush(self) -> None:
        pass


class _ExplodingSink:
    name = "exploder"

    def emit(self, result: KernelResult) -> None:
        raise RuntimeError("boom")

    def flush(self) -> None:
        pass


_RECORDED: list[tuple[str, str, str]] = []


# ─── Setup / teardown ────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolate_registries():
    integration_registry = IntegrationRegistry.singleton()
    sink_registry = DecisionSinkRegistry.singleton()
    integrations_snapshot = dict(integration_registry._items)
    sinks_snapshot = dict(sink_registry._items)
    integration_discovered = integration_registry._discovered
    sink_discovered = sink_registry._discovered
    integration_registry._items.clear()
    integration_registry._discovered = False
    sink_registry._items.clear()
    sink_registry._discovered = False
    _RECORDED.clear()
    try:
        yield
    finally:
        integration_registry._items.clear()
        integration_registry._items.update(integrations_snapshot)
        integration_registry._discovered = integration_discovered
        sink_registry._items.clear()
        sink_registry._items.update(sinks_snapshot)
        sink_registry._discovered = sink_discovered


# ─── The contract ────────────────────────────────────────────────────────────


class TestIntegrationProtocol:
    def test_mock_satisfies_protocol_structurally(self) -> None:
        assert isinstance(_MockDbtIntegration(), Integration)

    def test_register_and_get(self) -> None:
        integration = _MockDbtIntegration()
        IntegrationRegistry.singleton().register(integration)
        assert IntegrationRegistry.singleton().get("mock-dbt-check") is integration

    def test_double_registration_raises(self) -> None:
        IntegrationRegistry.singleton().register(_MockDbtIntegration())
        with pytest.raises(ValueError, match="already registered"):
            IntegrationRegistry.singleton().register(_MockDbtIntegration())

    def test_unknown_integration_raises_with_available_list(self) -> None:
        IntegrationRegistry.singleton().register(_MockDbtIntegration())
        with pytest.raises(KeyError, match="mock-dbt-check"):
            IntegrationRegistry.singleton().get("airflow")


class TestIntegrationInput:
    def test_well_formed_input_yields_signatures(self) -> None:
        integration = _MockDbtIntegration()
        sigs = integration.build_signatures({"nodes": {"a": {}, "b": {}}})
        assert len(sigs) == 2

    def test_malformed_input_raises_with_location(self) -> None:
        integration = _MockDbtIntegration()
        with pytest.raises(IntegrationInputError) as excinfo:
            integration.build_signatures({"not_nodes": []})
        assert excinfo.value.location == "$.nodes"
        assert "missing" in excinfo.value.message


class TestDecisionSink:
    def test_recording_sink_receives_results(self) -> None:
        sink = _RecordingSink()
        DecisionSinkRegistry.singleton().register(sink)

        result = _build_minimal_result()
        DecisionSinkRegistry.singleton().fanout(result)

        assert sink.received == [result]

    def test_exploding_sink_does_not_interrupt_other_sinks(self) -> None:
        recorder = _RecordingSink()
        DecisionSinkRegistry.singleton().register(_ExplodingSink())
        DecisionSinkRegistry.singleton().register(recorder)

        result = _build_minimal_result()
        with pytest.warns(RuntimeWarning, match="exploder"):
            DecisionSinkRegistry.singleton().fanout(result)

        assert recorder.received == [result]

    def test_sink_protocol_rejects_non_conformant_objects(self) -> None:
        class _NotASink:
            pass

        with pytest.raises(TypeError, match="does not implement"):
            DecisionSinkRegistry.singleton().register(_NotASink())  # type: ignore[arg-type]


class TestComposability:
    """End-to-end: integration builds sigs, sinks fan out the result."""

    def test_integration_emit_and_sinks_compose(self) -> None:
        integration = _MockDbtIntegration()
        recorder = _RecordingSink()
        IntegrationRegistry.singleton().register(integration)
        DecisionSinkRegistry.singleton().register(recorder)

        sigs = integration.build_signatures({"nodes": {"a": {}}})
        assert len(sigs) == 1

        result = _build_minimal_result(intent_id=sigs[0].intent_id)
        integration.emit_decisions([result])
        DecisionSinkRegistry.singleton().fanout(result)

        assert _RECORDED == [("emit", result.intent_id, "approved")]
        assert recorder.received == [result]


# ─── helpers ─────────────────────────────────────────────────────────────────


def _build_minimal_result(intent_id: str = "test-intent") -> KernelResult:
    return KernelResult(intent_id=intent_id, state=DecisionState.APPROVED)
