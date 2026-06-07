"""CFA Validation — static, runtime, signature."""
from cfa._lazy import LazyLoader

__getattr__ = LazyLoader({
    "StaticValidator": ("cfa.validation.static", "StaticValidator"),
    "StaticValidationResult": ("cfa.validation.static", "StaticValidationResult"),
    "ForbiddenToken": ("cfa.validation.static", "ForbiddenToken"),
    "RequiredPattern": ("cfa.validation.static", "RequiredPattern"),
    "RuntimeValidator": ("cfa.validation.runtime", "RuntimeValidator"),
    "RuntimeThresholds": ("cfa.validation.runtime", "RuntimeThresholds"),
    "RuntimeValidationResult": ("cfa.validation.runtime", "RuntimeValidationResult"),
    "validate_signature_data": ("cfa.validation.signature", "validate_signature_data"),
    "unwrap_signature_data": ("cfa.validation.signature", "unwrap_signature_data"),
})
