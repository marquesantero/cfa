"""
cfa.resolution -- Resolucao de intencoes
=========================================
Transforma linguagem natural em StateSignature tipada.
Requer um NormalizerBackend (LLM ou rule-based).

Uso com mock (para teste):
    from cfa.resolution import IntentNormalizer, MockNormalizerBackend

    normalizer = IntentNormalizer(backend=MockNormalizerBackend())
    resolution = normalizer.normalize(
        raw_intent="Join NFe com Clientes na Silver",
        catalog=CATALOG,
    )
    print(resolution.signature)
    print(resolution.confidence_score)

Uso com LLM real:
    class MeuLLMBackend(NormalizerBackend):
        def resolve(self, inp: NormalizerInput) -> NormalizerOutput:
            # Chamar seu LLM aqui
            ...

    normalizer = IntentNormalizer(backend=MeuLLMBackend())
"""

from ..normalizer import (
    ConfirmationOrchestrator,
    ConfirmationHandler,
    AutoApproveHandler,
    AutoRejectHandler,
    IntentNormalizer,
    MockNormalizerBackend,
    NormalizerBackend,
    NormalizerInput,
    NormalizerOutput,
)
from ..types import (
    AmbiguityLevel,
    ConfirmationMode,
    SemanticResolution,
    StateSignature,
)

__all__ = [
    # Normalizer
    "IntentNormalizer",
    "NormalizerBackend",
    "NormalizerInput",
    "NormalizerOutput",
    "MockNormalizerBackend",
    # Confirmation
    "ConfirmationOrchestrator",
    "ConfirmationHandler",
    "AutoApproveHandler",
    "AutoRejectHandler",
    # Types
    "AmbiguityLevel",
    "ConfirmationMode",
    "SemanticResolution",
    "StateSignature",
]
