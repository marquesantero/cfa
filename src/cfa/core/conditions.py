"""
CFA Condition Registry
======================
Central registry mapping condition strings to callable checks.

Used by:
- PolicyBundle YAML/JSON loader (maps "pii_in_protected_layer" → lambda)
- BehaviorSpec Systematizer (maps ConditionType → lambda)
- Programmatic PolicyRule creation

Single source of truth for all built-in governance conditions.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cfa.types import DatasetClassification, StateSignature

ConditionFn = Callable[[StateSignature], bool]


def _pii_in_protected_layer(meta: dict[str, Any]) -> ConditionFn:
    target_layer = meta.get("target_layer", "")
    def check(sig: StateSignature) -> bool:
        protected = (target_layer in ("silver", "gold")) or sig.writes_to_protected_layer
        return protected and sig.contains_pii and not sig.constraints.no_pii_raw
    return check


def _missing_merge_key(meta: dict[str, Any]) -> ConditionFn:
    def check(sig: StateSignature) -> bool:
        return sig.writes_to_protected_layer and not sig.constraints.merge_key_required
    return check


def _missing_partition(meta: dict[str, Any]) -> ConditionFn:
    min_size_gb = meta.get("min_size_gb", 1.0)
    def check(sig: StateSignature) -> bool:
        has_large = any(
            d.classification in (DatasetClassification.HIGH_VOLUME, DatasetClassification.SENSITIVE)
            or d.size_gb >= min_size_gb
            for d in sig.datasets
        )
        return has_large and len(sig.constraints.partition_by) == 0
    return check


def _enforce_types_disabled(meta: dict[str, Any]) -> ConditionFn:
    def check(sig: StateSignature) -> bool:
        return sig.writes_to_protected_layer and not sig.constraints.enforce_types
    return check


def _pii_without_policy(meta: dict[str, Any]) -> ConditionFn:
    def check(sig: StateSignature) -> bool:
        return sig.contains_pii and not sig.constraints.no_pii_raw
    return check


def _sensitive_without_partition(meta: dict[str, Any]) -> ConditionFn:
    def check(sig: StateSignature) -> bool:
        return (
            any(d.classification == DatasetClassification.SENSITIVE for d in sig.datasets)
            and len(sig.constraints.partition_by) == 0
        )
    return check


def _cost_budget_exceeded(meta: dict[str, Any]) -> ConditionFn:
    max_dbu = meta.get("max_dbu", 0.0)
    def check(sig: StateSignature) -> bool:
        if max_dbu > 0 and sig.constraints.max_cost_dbu is not None:
            return sig.constraints.max_cost_dbu > max_dbu
        return sig.constraints.max_cost_dbu is not None and sig.constraints.max_cost_dbu <= 0
    return check


CONDITION_REGISTRY: dict[str, Callable[[dict[str, Any]], ConditionFn]] = {
    "pii_in_protected_layer": _pii_in_protected_layer,
    "missing_merge_key": _missing_merge_key,
    "missing_partition": _missing_partition,
    "enforce_types_disabled": _enforce_types_disabled,
    "pii_without_policy": _pii_without_policy,
    "sensitive_without_partition": _sensitive_without_partition,
    "cost_budget_exceeded": _cost_budget_exceeded,
    "schema_mismatch": _missing_partition,   # alias: schema mismatch = check partition/schema
    "shuffle_budget_exceeded": _missing_partition,  # alias
    "unauthorized_gold_write": _pii_in_protected_layer,  # alias: gold = protected
}


def register_condition(name: str, builder: Callable[[dict[str, Any]], ConditionFn]) -> None:
    """Register a custom condition builder for use in policy bundles.

    Args:
        name: Condition name used in YAML/JSON (e.g. "my_custom_check").
        builder: Function that takes metadata dict and returns ConditionFn.
    """
    CONDITION_REGISTRY[name] = builder


def build_condition(name: str, metadata: dict[str, Any] | None = None) -> ConditionFn:
    """Build a condition function from a registered name and metadata.

    Args:
        name: Registered condition name (e.g. "pii_in_protected_layer").
        metadata: Optional parameters for the condition builder.

    Returns:
        A callable that takes StateSignature and returns bool.

    Raises:
        KeyError: If the condition name is not registered.
    """
    meta = metadata or {}
    builder = CONDITION_REGISTRY.get(name)
    if builder is None:
        raise KeyError(
            f"Unknown condition '{name}'. "
            f"Registered conditions: {', '.join(sorted(CONDITION_REGISTRY))}"
        )
    return builder(meta)


def list_conditions() -> list[str]:
    """Return all registered condition names."""
    return sorted(CONDITION_REGISTRY)
