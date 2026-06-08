"""cfa.policy — Policy engine, bundles, catalog, and standalone-governance surface.

This package replaces the prior split between ``cfa.policy`` (engine + bundle
+ catalog) and ``cfa.governance`` (a curated re-export for standalone use).
1.0.0 had no external adopters, so the two were collapsed without a shim.

Standalone usage (no kernel, no LLM, no execution — just validate a typed
signature against rules and check generated code statically)::

    from cfa.policy import PolicyEngine, StaticValidator, StateSignature
    from cfa.types import DatasetRef, TargetLayer, DatasetClassification, \
        SignatureConstraints, ExecutionContext

    sig = StateSignature(
        domain="fiscal",
        intent="reconciliation",
        target_layer=TargetLayer.SILVER,
        datasets=(DatasetRef("nfe", DatasetClassification.HIGH_VOLUME),),
        constraints=SignatureConstraints(partition_by=("processing_date",)),
        execution_context=ExecutionContext("v1", "c1", "r1"),
    )

    engine = PolicyEngine()
    result = engine.evaluate(sig)
    if result.is_blocked:
        raise PermissionError(result.reasoning)

    validator = StaticValidator()
    sv = validator.validate(generated_code, sig)
    if not sv.passed:
        raise ValueError(f"Static validation failed: {sv.fault_codes}")
"""

from cfa._lazy import LazyLoader

__getattr__ = LazyLoader({
    # Engine
    "PolicyEngine": ("cfa.policy.engine", "PolicyEngine"),
    "PolicyRule": ("cfa.policy.engine", "PolicyRule"),
    "PolicyResult": ("cfa.policy.engine", "PolicyResult"),
    "build_default_ruleset": ("cfa.policy.engine", "build_default_ruleset"),
    # Bundle
    "PolicyBundle": ("cfa.policy.bundle", "PolicyBundle"),
    "validate_policy_bundle_data": ("cfa.policy.bundle", "validate_policy_bundle_data"),
    "list_available_bundles": ("cfa.policy.bundle", "list_available_bundles"),
    # Catalog
    "validate_catalog": ("cfa.policy.catalog", "validate_catalog"),
    # Curated domain types (former cfa.governance surface)
    "StateSignature": ("cfa.types", "StateSignature"),
    "DatasetRef": ("cfa.types", "DatasetRef"),
    "DatasetClassification": ("cfa.types", "DatasetClassification"),
    "TargetLayer": ("cfa.types", "TargetLayer"),
    "SignatureConstraints": ("cfa.types", "SignatureConstraints"),
    "ExecutionContext": ("cfa.types", "ExecutionContext"),
    "Fault": ("cfa.types", "Fault"),
    "FaultFamily": ("cfa.types", "FaultFamily"),
    "FaultSeverity": ("cfa.types", "FaultSeverity"),
    "PolicyAction": ("cfa.types", "PolicyAction"),
    # Validators (former cfa.governance surface; canonical home is cfa.validate)
    "StaticValidator": ("cfa.validate.static", "StaticValidator"),
    "StaticValidationResult": ("cfa.validate.static", "StaticValidationResult"),
    "RuntimeValidator": ("cfa.validate.runtime", "RuntimeValidator"),
    "RuntimeValidationResult": ("cfa.validate.runtime", "RuntimeValidationResult"),
    "RuntimeThresholds": ("cfa.validate.runtime", "RuntimeThresholds"),
})
