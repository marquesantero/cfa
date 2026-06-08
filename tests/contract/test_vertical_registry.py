"""Tests for the Vertical protocol and VerticalRegistry.

These tests demonstrate (and pin down) the plug-in contract: a third
party can implement a Vertical structurally, register it, and have CFA
work with it — without touching kernel internals. See ADR-0009.
"""

from __future__ import annotations

from typing import Any

import pytest

from cfa.core.conditions import ConditionRegistry, list_conditions
from cfa.core.vertical import Vertical, VerticalRegistry
from cfa.types import StateSignature


# ─── A minimal reference vertical used across the contract tests ──────────────


class _MockAgentVertical:
    """Reference vertical for the "agent tool call" domain.

    Demonstrates the minimum surface required by the protocol. Not the
    real cfa.verticals.agent (that lands in 1.3); this exists only so we
    can prove the contract works.
    """

    name = "mock-agent"

    def payload_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["tool", "args"],
            "properties": {
                "tool": {"type": "string"},
                "args": {"type": "object"},
            },
        }

    def constraints_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "allowed_tools": {"type": "array", "items": {"type": "string"}},
                "rate_limit_per_minute": {"type": "integer"},
            },
        }

    def conditions(self) -> dict[str, Any]:
        def factory(_meta: dict[str, Any]):
            return lambda _sig: True
        return {"tool_in_allowlist": factory}

    def default_rules(self) -> list[Any]:
        return []

    def catalog_schema(self) -> dict[str, Any] | None:
        return None

    def backends(self) -> dict[str, Any]:
        return {}


# ─── Setup / teardown ────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolate_registries():
    """Snapshot vertical + condition registries; restore after each test.

    Vertical tests need a clean vertical registry (so duplicate-detection
    assertions are meaningful), but they must not lose the data-vertical
    conditions registered at module import time. Snapshot/restore
    preserves both — and keeps ConditionSpec / Vertical identity stable
    across tests.
    """
    vertical_registry = VerticalRegistry.singleton()
    condition_registry = ConditionRegistry.singleton()
    verticals_snapshot = dict(vertical_registry._verticals)
    discovered = vertical_registry._discovered
    conditions_snapshot = dict(condition_registry._specs)
    # Start each test from an empty vertical registry so tests can assert
    # on registration behavior. Conditions stay populated.
    vertical_registry._verticals.clear()
    vertical_registry._discovered = False
    try:
        yield
    finally:
        vertical_registry._verticals.clear()
        vertical_registry._verticals.update(verticals_snapshot)
        vertical_registry._discovered = discovered
        condition_registry._specs.clear()
        condition_registry._specs.update(conditions_snapshot)


# ─── The contract ────────────────────────────────────────────────────────────


class TestVerticalProtocol:
    def test_mock_satisfies_protocol_structurally(self) -> None:
        assert isinstance(_MockAgentVertical(), Vertical)

    def test_a_non_vertical_object_is_rejected(self) -> None:
        class _Broken:
            name = "broken"

        with pytest.raises(TypeError, match="does not implement"):
            VerticalRegistry.singleton().register(_Broken())  # type: ignore[arg-type]


class TestVerticalRegistry:
    def test_register_and_get(self) -> None:
        vertical = _MockAgentVertical()
        VerticalRegistry.singleton().register(vertical)

        retrieved = VerticalRegistry.singleton().get("mock-agent")
        assert retrieved is vertical

    def test_list_returns_sorted_names(self) -> None:
        VerticalRegistry.singleton().register(_MockAgentVertical())
        assert "mock-agent" in VerticalRegistry.singleton().list()

    def test_unknown_name_raises_with_available_list(self) -> None:
        VerticalRegistry.singleton().register(_MockAgentVertical())
        with pytest.raises(KeyError, match="mock-agent"):
            VerticalRegistry.singleton().get("infra")

    def test_double_registration_is_rejected(self) -> None:
        VerticalRegistry.singleton().register(_MockAgentVertical())
        with pytest.raises(ValueError, match="already registered"):
            VerticalRegistry.singleton().register(_MockAgentVertical())

    def test_contains_check_works(self) -> None:
        VerticalRegistry.singleton().register(_MockAgentVertical())
        assert "mock-agent" in VerticalRegistry.singleton()


class TestConditionNamespacing:
    """Verify that a vertical's conditions get auto-prefixed by name."""

    def test_conditions_are_prefixed_with_vertical_name(self) -> None:
        VerticalRegistry.singleton().register(_MockAgentVertical())
        names = list_conditions()
        assert "mock-agent.tool_in_allowlist" in names

    def test_prefixed_condition_is_callable_via_build(self) -> None:
        from cfa.core.conditions import build_condition

        VerticalRegistry.singleton().register(_MockAgentVertical())
        check = build_condition("mock-agent.tool_in_allowlist", {})
        # The mock condition returns True regardless of the signature.
        signature = _build_minimal_data_signature()
        assert check(signature) is True


class TestEntryPointDiscovery:
    """Discovery must be lazy and degrade gracefully on broken entry points."""

    def test_discovery_runs_on_first_query(self, monkeypatch) -> None:
        calls = {"count": 0}

        class FakeEP:
            name = "fake-vertical"

            def load(self):
                calls["count"] += 1
                return _MockAgentVertical

        def fake_entry_points(*_a, **_k):
            return [FakeEP()]

        monkeypatch.setattr(
            "cfa.core.vertical.entry_points", fake_entry_points, raising=False
        )
        # Patch importlib.metadata.entry_points used inside the registry.
        import importlib.metadata

        monkeypatch.setattr(importlib.metadata, "entry_points", fake_entry_points)

        # First query triggers discovery.
        names = VerticalRegistry.singleton().list()
        assert "mock-agent" in names
        assert calls["count"] == 1

        # Second query reuses cached state — no extra load.
        VerticalRegistry.singleton().list()
        assert calls["count"] == 1

    def test_broken_entry_point_emits_warning_and_is_skipped(self, monkeypatch) -> None:
        class BoomEP:
            name = "boom"

            def load(self):
                raise RuntimeError("boom")

        def fake_entry_points(*_a, **_k):
            return [BoomEP()]

        import importlib.metadata

        monkeypatch.setattr(importlib.metadata, "entry_points", fake_entry_points)

        with pytest.warns(RuntimeWarning, match="failed to load"):
            # Discovery happens here.
            assert VerticalRegistry.singleton().list() == []


# ─── helpers ─────────────────────────────────────────────────────────────────


def _build_minimal_data_signature() -> StateSignature:
    """Build a data-shaped signature so the mock condition has something
    to evaluate. The mock condition itself doesn't care about the shape."""
    from cfa.types import (
        DatasetClassification,
        DatasetRef,
        ExecutionContext,
        SignatureConstraints,
        TargetLayer,
    )

    return StateSignature(
        domain="fiscal",
        intent="reconciliation",
        target_layer=TargetLayer.SILVER,
        datasets=(DatasetRef(name="nfe", classification=DatasetClassification.HIGH_VOLUME),),
        constraints=SignatureConstraints(partition_by=("processing_date",)),
        execution_context=ExecutionContext("v1", "c1", "r1"),
    )
