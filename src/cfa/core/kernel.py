"""
CFA Kernel Orchestrator
=======================
Single entry point for the CFA Kernel. Delegates the 5-phase pipeline
to KernelPhases (core/phases/runner.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from cfa.audit.context import ContextRegistry
from cfa.audit.trail import AuditTrail
from cfa.backends import BackendRegistry
from cfa.core.codegen import CodeGenBackend
from cfa.core.planner import ExecutionPlanner
from cfa.execution.partial import (
    FailurePolicy,
    PartialExecutionManager,
    RetryPolicy,
)
from cfa.execution.state_projection import StateProjectionProtocol
from cfa.normalizer.base import (
    AutoApproveHandler,
    ConfirmationHandler,
    ConfirmationOrchestrator,
    IntentNormalizer,
    MockNormalizerBackend,
    NormalizerBackend,
    RuleBasedNormalizerBackend,
)
from cfa.observability.promotion import PromotionEngine
from cfa.policy.engine import PolicyEngine, PolicyRule
from cfa.sandbox import SandboxBackend
from cfa.sandbox.executor import SandboxExecutor
from cfa.sandbox.mock import MockSandboxBackend
from cfa.types import KernelResult
from cfa.validation.runtime import RuntimeValidator
from cfa.validation.static import StaticValidator

# ── Pipeline Phase ────────────────────────────────────────────────────────────


class PipelinePhase(StrEnum):
    FORMALIZE = "formalize"
    GOVERN = "govern"
    GENERATE = "generate"
    EXECUTE = "execute"
    VALIDATE = "validate"


# ── Kernel Config ────────────────────────────────────────────────────────────


@dataclass
class KernelConfig:
    policy_bundle_version: str = "v1.0"
    catalog_snapshot_version: str = "catalog_default"
    max_replan_attempts: int = 3
    confirmation_timeout_seconds: int = 300
    warnings_are_blocking: bool = False
    backend: str = "pyspark"

    phase_formalize: bool = True
    phase_govern: bool = True
    phase_generate: bool = True
    phase_execute: bool = True
    phase_validate: bool = True

    enable_planning: bool = True
    enable_codegen: bool = True
    enable_static_validation: bool = True
    enable_sandbox: bool = True
    failure_policy: FailurePolicy = FailurePolicy.SELECTIVE_QUARANTINE
    enable_promotion: bool = True
    normalizer: str = "rule_based"
    strict_normalization: bool = False
    min_normalizer_confidence: float = 0.65


# ── Kernel Orchestrator ──────────────────────────────────────────────────────


class KernelOrchestrator:
    """Single entry point for the CFA Kernel.

    Creates a KernelPhases runner with all dependencies and delegates.
    Pipeline phases (5): Formalize → Govern → Generate → Execute → Validate
    """

    def __init__(
        self,
        normalizer_backend: NormalizerBackend | None = None,
        confirmation_handler: ConfirmationHandler | None = None,
        policy_rules: list[PolicyRule] | None = None,
        context_registry: ContextRegistry | None = None,
        audit_trail: AuditTrail | None = None,
        catalog: dict[str, Any] | None = None,
        config: KernelConfig | None = None,
        planner: ExecutionPlanner | None = None,
        codegen_backend: CodeGenBackend | str | None = None,
        static_validator: StaticValidator | None = None,
        sandbox_backend: SandboxBackend | None = None,
        runtime_validator: RuntimeValidator | None = None,
        retry_policy: RetryPolicy | None = None,
        promotion_engine: PromotionEngine | None = None,
        schema_contract: dict[str, Any] | None = None,
    ) -> None:
        self.config = config or KernelConfig()
        self._context_registry = context_registry or ContextRegistry()
        self._audit_trail = audit_trail or AuditTrail()
        self._catalog = catalog or {"datasets": {}}
        self._schema_contract = schema_contract

        self._normalizer = IntentNormalizer(
            backend=normalizer_backend or self._resolve_normalizer_backend(),
            policy_bundle_version=self.config.policy_bundle_version,
            catalog_snapshot_version=self.config.catalog_snapshot_version,
        )
        self._confirmation = ConfirmationOrchestrator(
            handler=confirmation_handler or AutoApproveHandler(),
            timeout_seconds=self.config.confirmation_timeout_seconds,
        )
        self._policy = PolicyEngine(
            rules=policy_rules, policy_bundle_version=self.config.policy_bundle_version,
            max_replan_attempts=self.config.max_replan_attempts,
        )
        self._planner = planner or ExecutionPlanner()
        self._codegen = self._resolve_codegen_backend(codegen_backend)
        self._static_validator = static_validator or StaticValidator()
        self._sandbox_executor = SandboxExecutor(backend=sandbox_backend or MockSandboxBackend())
        self._runtime_validator = runtime_validator or RuntimeValidator()
        self._retry_policy = retry_policy or RetryPolicy()
        self._promotion_engine = promotion_engine or PromotionEngine(system_version="cfa_v0.1.7")

    # Backward-compatible public aliases for internal components
    @property
    def audit_trail(self) -> AuditTrail:
        return self._audit_trail

    @property
    def context_registry(self) -> ContextRegistry:
        return self._context_registry

    @property
    def catalog(self) -> dict[str, Any]:
        return self._catalog

    @property
    def promotion_engine(self) -> PromotionEngine:
        return self._promotion_engine

    def process(self, raw_intent: str) -> KernelResult:
        from cfa.core.phases.runner import KernelPhases

        phases = KernelPhases(
            config=self.config,
            context_registry=self._context_registry,
            audit_trail=self._audit_trail,
            catalog=self._catalog,
            schema_contract=self._schema_contract,
            normalizer=self._normalizer,
            confirmation=self._confirmation,
            policy=self._policy,
            planner=self._planner,
            codegen=self._codegen,
            static_validator=self._static_validator,
            sandbox_executor=self._sandbox_executor,
            runtime_validator=self._runtime_validator,
            partial_execution_manager=PartialExecutionManager(
                sandbox=self._sandbox_executor,
                runtime_validator=self._runtime_validator,
                failure_policy=self.config.failure_policy,
                retry_policy=self._retry_policy,
            ),
            state_projection=StateProjectionProtocol(self._context_registry),
            promotion_engine=self._promotion_engine,
        )
        return phases.process(raw_intent)

    def describe(self) -> dict[str, Any]:
        return {
            "config": {
                "policy_bundle_version": self.config.policy_bundle_version,
                "catalog_snapshot_version": self.config.catalog_snapshot_version,
                "max_replan_attempts": self.config.max_replan_attempts,
                "backend": self.config.backend,
            },
            "pipeline_phases": self.pipeline_config(),
            "context_registry_version": self._context_registry.version_id,
            "catalog_datasets": list(self._catalog.get("datasets", {}).keys()),
            "policy_rules": len(self._policy.rules),
            "audit_events": self._audit_trail.event_count,
        }

    def pipeline_config(self) -> dict[str, bool]:
        return {
            PipelinePhase.FORMALIZE: self.config.phase_formalize,
            PipelinePhase.GOVERN: self.config.phase_govern,
            PipelinePhase.GENERATE: self.config.phase_generate,
            PipelinePhase.EXECUTE: self.config.phase_execute,
            PipelinePhase.VALIDATE: self.config.phase_validate,
        }

    # ── Internal helpers ──────────────────────────────────────────────────

    def _resolve_codegen_backend(
        self, backend: CodeGenBackend | str | None
    ) -> CodeGenBackend:
        if isinstance(backend, CodeGenBackend):
            return backend
        name: str = backend if isinstance(backend, str) else self.config.backend
        factory = BackendRegistry.singleton().get(name)
        return factory()

    def _resolve_normalizer_backend(self) -> NormalizerBackend:
        if self.config.normalizer == "mock":
            return MockNormalizerBackend()
        return RuleBasedNormalizerBackend(
            strict=self.config.strict_normalization,
            min_confidence=self.config.min_normalizer_confidence,
        )
