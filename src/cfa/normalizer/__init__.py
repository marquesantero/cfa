"""CFA Normalizer — intent normalization."""
from cfa._lazy import LazyLoader

__getattr__ = LazyLoader({
    "IntentNormalizer": ("cfa.normalizer.base", "IntentNormalizer"),
    "NormalizerBackend": ("cfa.normalizer.base", "NormalizerBackend"),
    "MockNormalizerBackend": ("cfa.normalizer.base", "MockNormalizerBackend"),
    "RuleBasedNormalizerBackend": ("cfa.normalizer.base", "RuleBasedNormalizerBackend"),
    "ConfirmationOrchestrator": ("cfa.normalizer.base", "ConfirmationOrchestrator"),
    "AutoApproveHandler": ("cfa.normalizer.base", "AutoApproveHandler"),
    "AutoRejectHandler": ("cfa.normalizer.base", "AutoRejectHandler"),
    "LLMNormalizerBackend": ("cfa.normalizer.llm", "LLMNormalizerBackend"),
    "LLMProvider": ("cfa.normalizer.llm", "LLMProvider"),
    "OpenAILMProvider": ("cfa.normalizer.llm", "OpenAILMProvider"),
})
