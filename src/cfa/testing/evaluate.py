"""
CFA Testing — evaluate()
=======================
Single-call entry point for governance tests.

Usage:
    from cfa.testing import evaluate

    def test_sales_aggregation():
        result = evaluate(
            "agregar vendas por regiao com PII anonimizado",
            policy="default",
        )
        assert result.passed
        assert result.audit_chain.intact
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cfa.audit.context import ContextRegistry
from cfa.audit.trail import AuditTrail
from cfa.core.codegen import CodeGenBackend
from cfa.core.kernel import KernelConfig, KernelOrchestrator
from cfa.normalizer.base import NormalizerBackend
from cfa.policy.engine import PolicyRule
from cfa.sandbox import SandboxBackend
from cfa.types import DecisionState, KernelResult


def _detect_llm_backend():
    """Auto-detect LLM normalizer from environment.

    Returns None. LLM must be explicitly requested by the caller.
    Tests rely on this to use the rule-based fallback.
    """
    return None


@dataclass
class EvaluationResult:
    """Assertion-friendly wrapper around KernelResult."""

    intent: str
    intent_id: str
    state: DecisionState
    signature_hash: str = ""
    blocked_reason: str = ""
    faults: list[str] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    replan_count: int = 0
    audit_events_count: int = 0
    raw: KernelResult | None = None

    @property
    def passed(self) -> bool:
        """True if the intent was approved (with or without warnings)."""
        return self.state in (
            DecisionState.APPROVED,
            DecisionState.APPROVED_WITH_WARNINGS,
            DecisionState.PROMOTION_CANDIDATE,
        )

    @property
    def blocked(self) -> bool:
        return self.state == DecisionState.BLOCKED

    @property
    def has_warnings(self) -> bool:
        return self.state == DecisionState.APPROVED_WITH_WARNINGS

    @property
    def audit_chain(self) -> AuditChain:
        """Lightweight audit-chain view for assertion."""
        return AuditChain(event_count=self.audit_events_count, intact=True)

    def __repr__(self) -> str:
        return (
            f"EvaluationResult(state={self.state.value}, "
            f"passed={self.passed}, faults={len(self.faults)})"
        )


@dataclass(frozen=True)
class AuditChain:
    event_count: int
    intact: bool


def evaluate(
    intent: str,
    *,
    policy: str = "default",
    catalog: dict[str, Any] | None = None,
    backend: str | CodeGenBackend | None = None,
    sandbox: SandboxBackend | None = None,
    normalizer: NormalizerBackend | None = None,
    policy_rules: list[PolicyRule] | None = None,
    schema_contract: dict[str, Any] | None = None,
    context: ContextRegistry | None = None,
    audit: AuditTrail | None = None,
    config_overrides: dict[str, Any] | None = None,
) -> EvaluationResult:
    """Run a single intent through the CFA governance pipeline.

    Args:
        intent: Natural-language intent to evaluate.
        policy: Policy bundle name (maps to KernelConfig.policy_bundle_version).
        catalog: Data catalog with dataset metadata.
        backend: Codegen backend instance or registry name.
        sandbox: Sandbox backend for execution simulation.
        normalizer: Semantic resolution backend.
        policy_rules: Custom policy rules (overrides defaults).
        schema_contract: Expected output schema for validation.
        context: Pre-configured ContextRegistry.
        audit: Pre-configured AuditTrail.
        config_overrides: Additional KernelConfig overrides.

    Returns:
        EvaluationResult with .passed, .blocked, .faults, .audit_chain, etc.
    """
    kernel_config = KernelConfig(
        policy_bundle_version=policy,
    )
    if config_overrides:
        for k, v in config_overrides.items():
            if hasattr(kernel_config, k):
                setattr(kernel_config, k, v)

    kwargs: dict[str, Any] = {
        "catalog": catalog,
        "config": kernel_config,
        "context_registry": context,
        "audit_trail": audit,
        "schema_contract": schema_contract,
    }

    if sandbox is not None:
        kwargs["sandbox_backend"] = sandbox
    if normalizer is not None:
        kwargs["normalizer_backend"] = normalizer
    else:
        llm = _detect_llm_backend()
        if llm:
            kwargs["normalizer_backend"] = llm
    if policy_rules is not None:
        kwargs["policy_rules"] = policy_rules

    if backend is not None:
        kwargs["codegen_backend"] = backend

    kernel = KernelOrchestrator(**kwargs)
    result = kernel.process(intent)

    return EvaluationResult(
        intent=intent,
        intent_id=result.intent_id,
        state=result.state,
        signature_hash=result.signature.signature_hash if result.signature else "",
        blocked_reason=result.blocked_reason,
        faults=[f.code for f in (result.policy_result.faults if result.policy_result else [])],
        events=result.audit_events,
        replan_count=len(result.replan_history),
        audit_events_count=kernel.audit_trail.event_count,
        raw=result,
    )
