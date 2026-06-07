"""CFA Policy — policy engine, bundles, and catalog."""
from cfa._lazy import LazyLoader

__getattr__ = LazyLoader({
    "PolicyEngine": ("cfa.policy.engine", "PolicyEngine"),
    "PolicyRule": ("cfa.policy.engine", "PolicyRule"),
    "build_default_ruleset": ("cfa.policy.engine", "build_default_ruleset"),
    "PolicyBundle": ("cfa.policy.bundle", "PolicyBundle"),
    "validate_policy_bundle_data": ("cfa.policy.bundle", "validate_policy_bundle_data"),
    "list_available_bundles": ("cfa.policy.bundle", "list_available_bundles"),
    "validate_catalog": ("cfa.policy.catalog", "validate_catalog"),
})
