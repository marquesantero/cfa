"""
CFA Runtime Gate
================
Production-grade governance gate for wrapping pipeline execution.

Two surfaces, one core:
- cfa.testing → pytest-native for CI/CD
- cfa.runtime → production decorator/context-manager for live pipelines

Usage:
    from cfa.runtime import RuntimeGate, GateConfig

    gate = RuntimeGate(
        config=GateConfig(policy_bundle="prod_v4.2"),
        catalog=PROD_CATALOG,
    )

    # Pre-execution validation
    gate.validate("agregar vendas mensais com PII anonimizado")

    # Scoped execution with metrics
    with gate.scope("monthly_aggregation"):
        df = run_pipeline()
        gate.record_metrics(rows=1000000, shuffle_mb=450, cost_dbu=12.0)

    # Decorator for simple functions
    @gate.guard("agregar vendas")
    def my_pipeline():
        ...
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from cfa.audit.context import ContextRegistry
from cfa.audit.trail import AuditTrail
from cfa.core.kernel import KernelConfig, KernelOrchestrator
from cfa.policy.engine import PolicyRule
from cfa.types import DecisionState


class GateViolation(str):
    """Policy for handling governance violations at runtime."""

    BLOCK = "block"          # Raise exception, stop execution
    WARN = "warn"            # Log warning, continue execution
    AUDIT_ONLY = "audit_only"  # Record in audit trail, always continue


@dataclass
class GateConfig:
    """Production configuration for the Runtime Gate."""

    policy_bundle: str = "prod_v1.0"
    on_violation: str = GateViolation.BLOCK
    backend: str = "pyspark"
    sandbox: str = ""             # name in SandboxRegistry, empty = use kernel default
    execute: bool = False         # run sandbox execution phase (Phase 4)
    max_replan_attempts: int = 3
    warnings_are_blocking: bool = True
    enable_planning: bool = True
    enable_codegen: bool = True
    enable_static_validation: bool = True
    enable_sandbox: bool = False  # disabled by default — gate is pre-execution
    enable_promotion: bool = True

    def to_kernel_config(self) -> KernelConfig:
        return KernelConfig(
            policy_bundle_version=self.policy_bundle,
            backend=self.backend,
            max_replan_attempts=self.max_replan_attempts,
            warnings_are_blocking=self.warnings_are_blocking,
            enable_planning=self.enable_planning,
            enable_codegen=self.enable_codegen,
            enable_static_validation=self.enable_static_validation,
            enable_sandbox=self.enable_sandbox,
            enable_promotion=self.enable_promotion,
        )


class GovernanceViolation(Exception):
    """Raised when the runtime gate blocks an intent."""

    def __init__(self, gate_id: str, intent: str, reason: str, faults: list[str]) -> None:
        self.gate_id = gate_id
        self.intent = intent
        self.reason = reason
        self.faults = faults
        super().__init__(
            f"[gate={gate_id}] Governance violation for '{intent[:80]}': {reason}"
        )


@dataclass
class GateResult:
    """Result of a runtime gate validation."""

    gate_id: str
    intent: str
    passed: bool
    state: DecisionState
    blocked_reason: str = ""
    faults: list[str] = field(default_factory=list)
    signature_hash: str = ""
    replay_count: int = 0
    execution_id: str = ""


class RuntimeGate:
    """Production governance gate for live pipelines.

    Wraps KernelOrchestrator with production defaults, metrics recording,
    and configurable violation handling.

    Usage modes:
    - validate(intent) → GateResult for pre-execution checks
    - scope(name) → context manager for scoped execution
    - guard(intent) → decorator for function wrapping
    """

    def __init__(
        self,
        config: GateConfig | None = None,
        catalog: dict[str, Any] | None = None,
        policy_rules: list[PolicyRule] | None = None,
        context_registry: ContextRegistry | None = None,
        audit_trail: AuditTrail | None = None,
    ) -> None:
        self.config = config or GateConfig()
        self._gate_id = str(uuid.uuid4())[:8]

        sandbox_backend = None
        if self.config.sandbox:
            from cfa.sandbox import SandboxRegistry
            registry = SandboxRegistry.singleton()
            sandbox_backend = registry.get(self.config.sandbox)()

        self._kernel = KernelOrchestrator(
            catalog=catalog,
            config=self.config.to_kernel_config(),
            policy_rules=policy_rules,
            context_registry=context_registry,
            audit_trail=audit_trail,
            sandbox_backend=sandbox_backend,
        )
        self._last_result: GateResult | None = None

    @property
    def gate_id(self) -> str:
        return self._gate_id

    # ── Pre-execution validation ──────────────────────────────────────────

    def validate(self, intent: str) -> GateResult:
        """Validate an intent before execution. Does NOT execute code.

        Raises GovernanceViolation if on_violation='block' and intent fails.
        Always returns GateResult.
        """
        kresult = self._kernel.process(intent)
        passed = kresult.is_executable

        faults: list[str] = []
        if kresult.policy_result:
            faults = [f.code for f in kresult.policy_result.faults]

        result = GateResult(
            gate_id=self._gate_id,
            intent=intent,
            passed=passed,
            state=kresult.state,
            blocked_reason=kresult.blocked_reason,
            faults=faults,
            signature_hash=kresult.signature.signature_hash if kresult.signature else "",
            replay_count=len(kresult.replan_history),
            execution_id=kresult.intent_id,
        )
        self._last_result = result

        if not passed and self.config.on_violation == GateViolation.BLOCK:
            raise GovernanceViolation(
                gate_id=self._gate_id,
                intent=intent,
                reason=kresult.blocked_reason,
                faults=faults,
            )

        return result

    # ── Scoped execution ──────────────────────────────────────────────────

    @contextmanager
    def scope(self, name: str) -> Any:
        """Context manager for governed execution scope.

        Usage:
            with gate.scope("monthly_aggregation"):
                df = process(...)
                gate.record_metrics(rows=1000, shuffle_mb=5)
        """
        execution_id = str(uuid.uuid4())
        try:
            yield execution_id
        except Exception:
            self._kernel.audit_trail.record(
                intent_id=execution_id,
                stage="runtime_gate",
                event_type="scope_error",
                outcome="error",
                scope_name=name,
                policy_bundle_version=self.config.policy_bundle,
            )
            raise

    def record_metrics(
        self,
        rows: int = 0,
        shuffle_mb: float = 0.0,
        cost_dbu: float = 0.0,
        duration_seconds: float = 0.0,
        **extra: Any,
    ) -> None:
        """Record execution metrics for the current scope."""
        if self._last_result:
            self._kernel.audit_trail.record(
                intent_id=self._last_result.execution_id,
                stage="runtime_gate",
                event_type="execution_metrics",
                outcome="recorded",
                rows=rows,
                shuffle_mb=shuffle_mb,
                cost_dbu=cost_dbu,
                duration_seconds=duration_seconds,
                policy_bundle_version=self.config.policy_bundle,
                **extra,
            )

    # ── Decorator ─────────────────────────────────────────────────────────

    def guard(self, intent: str) -> Callable[[Callable], Callable]:
        """Decorator that guards a function with governance validation.

        Usage:
            @gate.guard("agregar vendas")
            def my_pipeline():
                ...
        """

        def decorator(fn: Callable) -> Callable:
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                self.validate(intent)
                return fn(*args, **kwargs)

            return wrapper

        return decorator


def runtime_gate(
    intent: str,
    *,
    policy_bundle: str = "prod_v1.0",
    on_violation: str = GateViolation.BLOCK,
    catalog: dict[str, Any] | None = None,
    **gate_kwargs: Any,
) -> Callable[[Callable], Callable]:
    """Standalone decorator for quick runtime governance.

    Usage:
        @runtime_gate("agregar vendas", policy_bundle="prod_v2.0")
        def my_pipeline():
            ...

    This creates a temporary RuntimeGate for the decorated function.
    For multiple functions sharing the same gate, use RuntimeGate directly.
    """
    gate = RuntimeGate(
        config=GateConfig(policy_bundle=policy_bundle, on_violation=on_violation),
        catalog=catalog,
        **gate_kwargs,
    )
    return gate.guard(intent)
