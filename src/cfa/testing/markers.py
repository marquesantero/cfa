"""
CFA Testing — pytest markers
=============================
Custom pytest markers for governance testing.

Usage:
    import pytest
    from cfa.testing import cfa_kernel

    @pytest.mark.cfa_governance
    def test_pii_protection(cfa_kernel):
        ...

    @pytest.mark.cfa_policy("finops_strict")
    def test_cost_limits(cfa_kernel):
        ...

    @pytest.mark.cfa_audit
    def test_audit_chain(cfa_kernel):
        ...
"""

from __future__ import annotations


def _register_markers(config) -> None:
    """Register CFA markers with pytest config."""
    markers = [
        "cfa_governance: mark a test as a CFA governance test",
        "cfa_policy(policy_bundle): specify the policy bundle version for this test",
        "cfa_audit: mark a test for audit chain verification",
        "cfa_backend(backend_name): specify the codegen backend for this test",
        "cfa_layer(bronze|silver|gold): specify the target layer under test",
    ]
    for marker in markers:
        config.addinivalue_line("markers", marker)
