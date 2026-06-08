"""Tests for the first-party data vertical.

The data vertical proves the kernel's plugin architecture works for the
original CFA use case (lakehouse-shaped governance) without changing any
existing behavior. Once 1.2 lands the type migration described in
ADR-0008, the data-shaped primitives currently in ``cfa.types`` will
live inside this vertical.
"""

from __future__ import annotations

import importlib

import pytest

from cfa.core.conditions import ConditionRegistry, list_conditions
from cfa.core.vertical import Vertical, VerticalRegistry


@pytest.fixture(autouse=True)
def _isolate_registries():
    """Snapshot the registry state and restore it after every test.

    The data vertical auto-registers when ``cfa.verticals.data`` is
    imported; tests must not leak that registration to one another.
    """
    vertical_registry = VerticalRegistry.singleton()
    condition_registry = ConditionRegistry.singleton()
    verticals_snapshot = dict(vertical_registry._verticals)
    discovered = vertical_registry._discovered
    conditions_snapshot = dict(condition_registry._specs)
    try:
        yield
    finally:
        vertical_registry._verticals.clear()
        vertical_registry._verticals.update(verticals_snapshot)
        vertical_registry._discovered = discovered
        condition_registry._specs.clear()
        condition_registry._specs.update(conditions_snapshot)


class TestDataVerticalProtocol:
    def test_implements_vertical_protocol(self) -> None:
        from cfa.verticals.data import DataVertical

        assert isinstance(DataVertical(), Vertical)

    def test_has_name_data(self) -> None:
        from cfa.verticals.data import DataVertical

        assert DataVertical().name == "data"


class TestSchemas:
    def test_payload_schema_documents_target_layer_and_datasets(self) -> None:
        from cfa.verticals.data import PAYLOAD_SCHEMA

        assert PAYLOAD_SCHEMA["type"] == "object"
        assert "target_layer" in PAYLOAD_SCHEMA["required"]
        assert "datasets" in PAYLOAD_SCHEMA["required"]
        assert PAYLOAD_SCHEMA["properties"]["target_layer"]["enum"] == [
            "bronze",
            "silver",
            "gold",
        ]

    def test_constraints_schema_documents_lakehouse_invariants(self) -> None:
        from cfa.verticals.data import CONSTRAINTS_SCHEMA

        props = CONSTRAINTS_SCHEMA["properties"]
        assert "no_pii_raw" in props
        assert "merge_key_required" in props
        assert "enforce_types" in props
        assert "partition_by" in props
        assert "max_cost_dbu" in props

    def test_catalog_schema_describes_datasets_map(self) -> None:
        from cfa.verticals.data import CATALOG_SCHEMA

        assert CATALOG_SCHEMA["type"] == "object"
        assert "datasets" in CATALOG_SCHEMA["required"]


class TestRegistrationAndDiscovery:
    def test_explicit_import_registers_the_vertical(self) -> None:
        # Clean slate: drop both the registry entry and the cached module
        # so the autoregister code runs again on import.
        import sys

        VerticalRegistry.singleton()._verticals.pop("data", None)
        sys.modules.pop("cfa.verticals.data", None)
        sys.modules.pop("cfa.verticals.data.vertical", None)

        import cfa.verticals.data  # noqa: F401

        registry = VerticalRegistry.singleton()
        assert "data" in registry._verticals

    def test_registry_discovery_imports_builtin_verticals(self) -> None:
        # Wipe and force a fresh discovery pass.
        registry = VerticalRegistry.singleton()
        registry._verticals.pop("data", None)
        registry._discovered = False
        # Wipe the cfa.verticals.data module so the re-import re-runs.
        import sys

        sys.modules.pop("cfa.verticals.data", None)
        sys.modules.pop("cfa.verticals.data.vertical", None)

        assert "data" in registry.list()  # triggers discovery

    def test_idempotent_autoregistration(self) -> None:
        # Re-importing the module must not raise even if data is already
        # registered.
        import cfa.verticals.data as data_module

        # Force a reload — _autoregister() should see "data" already
        # present and short-circuit.
        importlib.reload(data_module)
        assert "data" in VerticalRegistry.singleton()._verticals


class TestConditionsAreNamespaced:
    def test_data_prefixed_conditions_are_registered(self) -> None:
        # Register via the registry so auto-prefixing kicks in.
        from cfa.verticals.data import DataVertical

        VerticalRegistry.singleton()._verticals.pop("data", None)
        VerticalRegistry.singleton().register(DataVertical())

        names = list_conditions()
        assert "data.pii_in_protected_layer" in names
        assert "data.missing_partition" in names
        assert "data.cost_budget_exceeded" in names

    def test_unprefixed_aliases_still_work_for_back_compat(self) -> None:
        names = list_conditions()
        # The unprefixed forms are registered at module import time by
        # cfa.core.conditions for back-compat through 1.x.
        assert "pii_in_protected_layer" in names


class TestDefaultRules:
    def test_default_rules_returned_from_vertical(self) -> None:
        from cfa.verticals.data import DataVertical

        rules = DataVertical().default_rules()
        names = {rule.name for rule in rules}
        # The data vertical ships the lakehouse defaults — pick a few
        # representative ones.
        assert "forbid_raw_pii_in_silver_or_gold" in names
        assert "require_partition_filter_for_high_volume" in names


class TestBackends:
    def test_data_backends_include_pyspark_sql_dbt(self) -> None:
        from cfa.verticals.data import DataVertical

        backends = DataVertical().backends()
        assert {"pyspark", "sql", "dbt"}.issubset(set(backends))

    def test_backend_factories_produce_real_instances(self) -> None:
        from cfa.backends import BackendAdapter
        from cfa.verticals.data import DataVertical

        backends = DataVertical().backends()
        pyspark_backend = backends["pyspark"]()
        assert isinstance(pyspark_backend, BackendAdapter)
        # Smoke check: the backend exposes the abstract surface expected
        # by the static validator.
        capabilities = pyspark_backend.get_capabilities()
        assert capabilities is not None
        assert hasattr(capabilities, "forbidden_tokens")
