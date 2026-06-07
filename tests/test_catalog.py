"""Tests for catalog validation."""

from conftest import CATALOG

from cfa.core.kernel import KernelConfig, KernelOrchestrator
from cfa.policy.catalog import validate_catalog
from cfa.types import DecisionState


class TestCatalogValidation:
    def test_accepts_valid_catalog(self):
        result = validate_catalog(CATALOG, require_datasets=True)
        assert result.valid
        assert result.issues == []

    def test_requires_datasets_when_strict(self):
        result = validate_catalog({"datasets": {}}, require_datasets=True)
        assert not result.valid
        assert "datasets: must contain at least one dataset" in result.messages

    def test_rejects_invalid_classification(self):
        result = validate_catalog({
            "datasets": {
                "clientes": {"classification": "private"},
            }
        })
        assert not result.valid
        assert any("classification" in msg for msg in result.messages)

    def test_rejects_invalid_pii_columns(self):
        result = validate_catalog({
            "datasets": {
                "clientes": {"pii_columns": "cpf"},
            }
        })
        assert not result.valid
        assert any("pii_columns" in msg for msg in result.messages)


class TestKernelCatalogValidation:
    def test_strict_kernel_blocks_invalid_catalog_before_normalization(self):
        kernel = KernelOrchestrator(
            catalog={"datasets": {"clientes": {"classification": "private"}}},
            config=KernelConfig(strict_normalization=True),
        )
        result = kernel.process("Processar clientes na Silver")
        assert result.state == DecisionState.BLOCKED
        assert result.policy_result is not None
        assert result.policy_result.faults[0].code == "CATALOG_INVALID"
