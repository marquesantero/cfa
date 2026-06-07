"""
CFA Testing — pytest fixtures
==============================
Pre-built pytest fixtures for governance testing.

Usage:
    from cfa.testing import cfa_kernel, cfa_catalog

    def test_my_pipeline(cfa_kernel):
        result = cfa_kernel.process("intent text")
        assert result.state.value == "approved"
"""

from __future__ import annotations

from typing import Any

try:
    import pytest
except ImportError:
    pytest = None  # type: ignore[assignment]

from cfa.core.kernel import KernelConfig, KernelOrchestrator

from ..sandbox.mock import MockSandboxBackend

_fixture = pytest.fixture if pytest else (lambda f: f)

DEFAULT_CATALOG = {
    "datasets": {
        "nfe": {
            "classification": "high_volume",
            "size_gb": 4000,
            "pii_columns": [],
            "partition_column": "processing_date",
        },
        "clientes": {
            "classification": "sensitive",
            "size_gb": 0.5,
            "pii_columns": ["cpf", "email"],
            "partition_column": "processing_date",
        },
        "produtos": {
            "classification": "internal",
            "size_gb": 0.1,
            "pii_columns": [],
        },
    }
}


@_fixture
def cfa_catalog() -> dict[str, Any]:
    """Default data catalog for governance tests."""
    return DEFAULT_CATALOG


@_fixture
def cfa_kernel(cfa_catalog: dict[str, Any]) -> KernelOrchestrator:
    """Pre-configured KernelOrchestrator for testing.

    Uses MockSandboxBackend (deterministic), defaults for all other components.
    Override by passing parameters to KernelOrchestrator() in your test.
    """
    return KernelOrchestrator(
        catalog=cfa_catalog,
        config=KernelConfig(policy_bundle_version="test"),
        sandbox_backend=MockSandboxBackend(),
    )


@_fixture
def cfa_strict_kernel(cfa_catalog: dict[str, Any]) -> KernelOrchestrator:
    """KernelOrchestrator with warnings treated as blocking."""
    return KernelOrchestrator(
        catalog=cfa_catalog,
        config=KernelConfig(policy_bundle_version="test", warnings_are_blocking=True),
        sandbox_backend=MockSandboxBackend(),
    )


@_fixture
def cfa_noexec_kernel(cfa_catalog: dict[str, Any]) -> KernelOrchestrator:
    """KernelOrchestrator with execution disabled (policy-only gate)."""
    return KernelOrchestrator(
        catalog=cfa_catalog,
        config=KernelConfig(
            policy_bundle_version="test",
            enable_planning=False,
            enable_codegen=False,
            enable_static_validation=False,
            enable_sandbox=False,
        ),
    )
