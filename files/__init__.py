"""
CFA — Contextual Flux Architecture
====================================
Kernel Orchestrator v1.0

Componentes do Kernel (Fase 1):
- KernelOrchestrator    — ponto de entrada único
- IntentNormalizer      — resolução semântica
- ConfirmationOrchestrator — escalonamento por risco
- PolicyEngine          — enforcement antes da execução
- Types                 — contratos tipados

Uso básico:
    from cfa import KernelOrchestrator

    kernel = KernelOrchestrator(catalog=meu_catalogo)
    result = kernel.process("Junte NFe com Clientes e salve na Silver")
    print(result.summary())
"""

from .core.kernel import KernelOrchestrator, KernelConfig, InMemoryContextRegistry
from .core.normalizer import (
    IntentNormalizer,
    ConfirmationOrchestrator,
    NormalizerBackend,
    MockNormalizerBackend,
    AutoApproveHandler,
    AutoRejectHandler,
    HumanConfirmationHandler,
)
from .core.policy_engine import PolicyEngine, PolicyRule, build_default_ruleset
from .core.types import (
    StateSignature,
    SemanticResolution,
    KernelResult,
    PolicyResult,
    Fault,
    DecisionState,
    ConfirmationMode,
    AmbiguityLevel,
    FaultFamily,
    FaultSeverity,
    PolicyAction,
    DatasetRef,
    DatasetClassification,
    TargetLayer,
    ExecutionContext,
    SignatureConstraints,
)

__version__ = "1.0.0-kernel"
__all__ = [
    "KernelOrchestrator",
    "KernelConfig",
    "InMemoryContextRegistry",
    "IntentNormalizer",
    "ConfirmationOrchestrator",
    "NormalizerBackend",
    "MockNormalizerBackend",
    "AutoApproveHandler",
    "AutoRejectHandler",
    "HumanConfirmationHandler",
    "PolicyEngine",
    "PolicyRule",
    "build_default_ruleset",
    "StateSignature",
    "SemanticResolution",
    "KernelResult",
    "PolicyResult",
    "Fault",
    "DecisionState",
    "ConfirmationMode",
    "AmbiguityLevel",
    "FaultFamily",
    "FaultSeverity",
    "PolicyAction",
    "DatasetRef",
    "DatasetClassification",
    "TargetLayer",
    "ExecutionContext",
    "SignatureConstraints",
]
