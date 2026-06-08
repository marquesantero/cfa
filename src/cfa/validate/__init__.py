"""CFA Validation — static, runtime, signature."""
from cfa._lazy import LazyLoader

__getattr__ = LazyLoader({
    "StaticValidator": ("cfa.validate.static", "StaticValidator"),
    "StaticValidationResult": ("cfa.validate.static", "StaticValidationResult"),
    "ForbiddenToken": ("cfa.validate.static", "ForbiddenToken"),
    "RequiredPattern": ("cfa.validate.static", "RequiredPattern"),
    "RuntimeValidator": ("cfa.validate.runtime", "RuntimeValidator"),
    "RuntimeThresholds": ("cfa.validate.runtime", "RuntimeThresholds"),
    "RuntimeValidationResult": ("cfa.validate.runtime", "RuntimeValidationResult"),
    "validate_signature_data": ("cfa.validate.signature", "validate_signature_data"),
    "unwrap_signature_data": ("cfa.validate.signature", "unwrap_signature_data"),
})
