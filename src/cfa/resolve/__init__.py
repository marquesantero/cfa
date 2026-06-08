"""cfa.resolve — Intent resolution (natural language → typed StateSignature).

Single resolver surface. Replaces the prior split between ``cfa.normalizer``
(the engine) and ``cfa.resolution`` (a curated re-export). 1.0.0 had no
external adopters, so we collapsed both into one package without a shim.

Usage (mock backend, for tests)::

    from cfa.resolve import IntentNormalizer, MockNormalizerBackend

    resolver = IntentNormalizer(backend=MockNormalizerBackend())
    resolution = resolver.normalize(
        raw_intent="Join NFe com Clientes na Silver",
        catalog=CATALOG,
    )
    print(resolution.signature, resolution.confidence_score)

Usage (rule-based, the production default)::

    from cfa.resolve import IntentNormalizer, RuleBasedNormalizerBackend

    resolver = IntentNormalizer(backend=RuleBasedNormalizerBackend(strict=True))

Usage (LLM)::

    from cfa.resolve import IntentNormalizer
    from cfa.resolve.llm import LLMNormalizerBackend, OpenAILMProvider

    resolver = IntentNormalizer(
        backend=LLMNormalizerBackend(provider=OpenAILMProvider(api_key=...)),
    )
"""

from cfa._lazy import LazyLoader

__getattr__ = LazyLoader({
    # Engine
    "IntentNormalizer": ("cfa.resolve.base", "IntentNormalizer"),
    "NormalizerBackend": ("cfa.resolve.base", "NormalizerBackend"),
    "NormalizerInput": ("cfa.resolve.base", "NormalizerInput"),
    "NormalizerOutput": ("cfa.resolve.base", "NormalizerOutput"),
    "MockNormalizerBackend": ("cfa.resolve.base", "MockNormalizerBackend"),
    "RuleBasedNormalizerBackend": ("cfa.resolve.base", "RuleBasedNormalizerBackend"),
    # Confirmation orchestration
    "ConfirmationOrchestrator": ("cfa.resolve.base", "ConfirmationOrchestrator"),
    "ConfirmationHandler": ("cfa.resolve.base", "ConfirmationHandler"),
    "AutoApproveHandler": ("cfa.resolve.base", "AutoApproveHandler"),
    "AutoRejectHandler": ("cfa.resolve.base", "AutoRejectHandler"),
    # LLM backend (requires the [llm] extra to actually run)
    "LLMNormalizerBackend": ("cfa.resolve.llm", "LLMNormalizerBackend"),
    "LLMProvider": ("cfa.resolve.llm", "LLMProvider"),
    "OpenAILMProvider": ("cfa.resolve.llm", "OpenAILMProvider"),
    # Re-exported domain types for convenience
    "AmbiguityLevel": ("cfa.types", "AmbiguityLevel"),
    "ConfirmationMode": ("cfa.types", "ConfirmationMode"),
    "SemanticResolution": ("cfa.types", "SemanticResolution"),
    "StateSignature": ("cfa.types", "StateSignature"),
})
