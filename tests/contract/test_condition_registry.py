"""Tests for the hardened ConditionRegistry. See ADR-0011."""

from __future__ import annotations

import warnings
from typing import Any

import pytest

from cfa.core.conditions import (
    CONDITION_REGISTRY,
    ConditionRegistry,
    ConditionSpec,
    build_condition,
    list_conditions,
    register_condition,
)
from cfa.types import StateSignature


@pytest.fixture(autouse=True)
def _snapshot_registry():
    """Snapshot the registry's specs and restore them after the test.

    We can't ``reload`` the conditions module to reset state: the reload
    rebinds ``ConditionSpec`` to a new class object, so any test-level
    ``isinstance(spec, ConditionSpec)`` would fail against pre-import
    references. Snapshot/restore preserves identity and the data-vertical
    defaults registered at module import time.
    """
    registry = ConditionRegistry.singleton()
    snapshot = dict(registry._specs)
    try:
        yield
    finally:
        registry._specs.clear()
        registry._specs.update(snapshot)


def _always_true_factory(_meta: dict[str, Any]):
    return lambda _sig: True


class TestRegistryAPI:
    def test_register_and_describe(self) -> None:
        ConditionRegistry.singleton().register(
            "agent.tool_in_allowlist",
            _always_true_factory,
            doc="Fires when the requested tool is not in the configured allow list.",
            expected_params={"allow_list": "List of tool names."},
        )
        spec = ConditionRegistry.singleton().describe("agent.tool_in_allowlist")
        assert isinstance(spec, ConditionSpec)
        assert spec.name == "agent.tool_in_allowlist"
        assert "allow list" in spec.doc
        assert spec.expected_params == {"allow_list": "List of tool names."}

    def test_register_rejects_duplicate_without_overwrite(self) -> None:
        registry = ConditionRegistry.singleton()
        registry.register("my.check", _always_true_factory)
        with pytest.raises(ValueError, match="already registered"):
            registry.register("my.check", _always_true_factory)

    def test_register_with_overwrite_replaces_silently(self) -> None:
        registry = ConditionRegistry.singleton()
        registry.register("my.check", _always_true_factory)

        def factory_v2(_meta):
            return lambda _sig: False

        registry.register("my.check", factory_v2, overwrite=True)
        check = registry.build("my.check")
        assert check(_build_signature()) is False

    def test_build_unknown_raises(self) -> None:
        with pytest.raises(KeyError, match="unknown condition"):
            ConditionRegistry.singleton().build("does.not.exist")

    def test_describe_all_returns_sorted(self) -> None:
        registry = ConditionRegistry.singleton()
        specs = registry.describe_all()
        names = [s.name for s in specs]
        assert names == sorted(names)
        assert "pii_in_protected_layer" in names

    def test_membership_check(self) -> None:
        registry = ConditionRegistry.singleton()
        assert "pii_in_protected_layer" in registry
        assert "this.does.not.exist" not in registry


class TestModuleLevelBackcompat:
    """The legacy register_condition / build_condition / list_conditions
    surface keeps working and delegates to the singleton."""

    def test_register_and_build_via_module_functions(self) -> None:
        register_condition("legacy.simple", _always_true_factory)
        check = build_condition("legacy.simple")
        assert check(_build_signature()) is True

    def test_list_conditions_includes_data_defaults(self) -> None:
        names = list_conditions()
        assert "pii_in_protected_layer" in names
        assert "missing_partition" in names
        assert "cost_budget_exceeded" in names

    def test_module_level_re_register_emits_deprecation_warning(self) -> None:
        register_condition("legacy.dup", _always_true_factory)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            register_condition("legacy.dup", _always_true_factory)
        assert any(
            issubclass(w.category, DeprecationWarning)
            and "silently re-registered" in str(w.message)
            for w in caught
        )


class TestLegacyDictView:
    """CONDITION_REGISTRY remains a mapping for older code paths that
    indexed it directly. Mutation is not supported."""

    def test_indexing_returns_factory(self) -> None:
        factory = CONDITION_REGISTRY["pii_in_protected_layer"]
        check = factory({})
        assert callable(check)

    def test_contains_check(self) -> None:
        assert "pii_in_protected_layer" in CONDITION_REGISTRY
        assert "no.such.thing" not in CONDITION_REGISTRY

    def test_iteration(self) -> None:
        keys = list(CONDITION_REGISTRY)
        assert "pii_in_protected_layer" in keys
        assert keys == sorted(keys)

    def test_get_with_default(self) -> None:
        assert CONDITION_REGISTRY.get("not_there") is None
        assert CONDITION_REGISTRY.get("not_there", _always_true_factory) is _always_true_factory


# ─── helpers ─────────────────────────────────────────────────────────────────


def _build_signature() -> StateSignature:
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
