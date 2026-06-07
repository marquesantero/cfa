"""StateSignature validation utilities.

Validation is intentionally separate from ``StateSignature.from_dict`` so legacy
internal callers can keep deserializing permissively while CLI/API boundaries can
enforce a strict contract for external systems.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cfa.types import DatasetClassification, TargetLayer

_LAYERS = {layer.value for layer in TargetLayer}
_CLASSIFICATIONS = {classification.value for classification in DatasetClassification}


@dataclass(frozen=True)
class SignatureValidationIssue:
    path: str
    message: str


@dataclass(frozen=True)
class SignatureValidationResult:
    valid: bool
    issues: list[SignatureValidationIssue] = field(default_factory=list)

    @property
    def messages(self) -> list[str]:
        return [f"{i.path}: {i.message}" for i in self.issues]


def unwrap_signature_data(data: dict[str, Any]) -> dict[str, Any]:
    """Accept common wrappers used by APIs and CLI payloads."""
    if isinstance(data, dict):
        wrapped = data.get("signature", data.get("state_signature"))
        if isinstance(wrapped, dict):
            return wrapped
    return data


def validate_signature_data(
    data: dict[str, Any] | None,
    *,
    require_datasets: bool = False,
) -> SignatureValidationResult:
    issues: list[SignatureValidationIssue] = []

    if data is None:
        return SignatureValidationResult(
            valid=False,
            issues=[SignatureValidationIssue("signature", "file is empty")],
        )
    if not isinstance(data, dict):
        return SignatureValidationResult(
            valid=False,
            issues=[SignatureValidationIssue("signature", "must be an object")],
        )

    sig = unwrap_signature_data(data)
    if not isinstance(sig, dict):
        return SignatureValidationResult(
            valid=False,
            issues=[SignatureValidationIssue("signature", "must be an object")],
        )

    _require_non_empty_string(sig, "domain", issues)
    _require_non_empty_string(sig, "intent", issues)

    target_layer = sig.get("target_layer")
    if target_layer not in _LAYERS:
        issues.append(SignatureValidationIssue("target_layer", f"must be one of {sorted(_LAYERS)}"))

    datasets = sig.get("datasets")
    if datasets is None:
        if require_datasets:
            issues.append(SignatureValidationIssue("datasets", "is required"))
    elif not isinstance(datasets, list):
        issues.append(SignatureValidationIssue("datasets", "must be a list"))
    elif require_datasets and not datasets:
        issues.append(SignatureValidationIssue("datasets", "must contain at least one dataset"))
    elif isinstance(datasets, list):
        for idx, dataset in enumerate(datasets):
            base = f"datasets[{idx}]"
            if not isinstance(dataset, dict):
                issues.append(SignatureValidationIssue(base, "must be an object"))
                continue
            _require_non_empty_string(dataset, f"{base}.name", issues, key="name")
            classification = dataset.get("classification", "internal")
            if classification not in _CLASSIFICATIONS:
                issues.append(SignatureValidationIssue(f"{base}.classification", f"must be one of {sorted(_CLASSIFICATIONS)}"))
            size_gb = dataset.get("size_gb", 0.0)
            if not isinstance(size_gb, (int, float)) or isinstance(size_gb, bool) or size_gb < 0:
                issues.append(SignatureValidationIssue(f"{base}.size_gb", "must be a non-negative number"))
            pii_columns = dataset.get("pii_columns", [])
            if not isinstance(pii_columns, list):
                issues.append(SignatureValidationIssue(f"{base}.pii_columns", "must be a list of strings"))
            elif any(not isinstance(col, str) or not col.strip() for col in pii_columns):
                issues.append(SignatureValidationIssue(f"{base}.pii_columns", "must contain only non-empty strings"))
            partition_column = dataset.get("partition_column")
            if partition_column is not None and not isinstance(partition_column, str):
                issues.append(SignatureValidationIssue(f"{base}.partition_column", "must be a string or null"))

    constraints = sig.get("constraints", {})
    if not isinstance(constraints, dict):
        issues.append(SignatureValidationIssue("constraints", "must be an object"))
    else:
        for key in ("no_pii_raw", "merge_key_required", "enforce_types"):
            if key in constraints and not isinstance(constraints[key], bool):
                issues.append(SignatureValidationIssue(f"constraints.{key}", "must be a boolean"))
        partition_by = constraints.get("partition_by", [])
        if not isinstance(partition_by, list):
            issues.append(SignatureValidationIssue("constraints.partition_by", "must be a list of strings"))
        elif any(not isinstance(col, str) or not col.strip() for col in partition_by):
            issues.append(SignatureValidationIssue("constraints.partition_by", "must contain only non-empty strings"))
        max_cost = constraints.get("max_cost_dbu")
        if max_cost is not None and (not isinstance(max_cost, (int, float)) or isinstance(max_cost, bool) or max_cost < 0):
            issues.append(SignatureValidationIssue("constraints.max_cost_dbu", "must be a non-negative number or null"))
        custom = constraints.get("custom", {})
        if custom is not None and not isinstance(custom, dict):
            issues.append(SignatureValidationIssue("constraints.custom", "must be an object"))

    ctx = sig.get("execution_context")
    if not isinstance(ctx, dict):
        issues.append(SignatureValidationIssue("execution_context", "is required and must be an object"))
    else:
        _require_non_empty_string(ctx, "execution_context.policy_bundle_version", issues, key="policy_bundle_version")
        _require_non_empty_string(ctx, "execution_context.catalog_snapshot_version", issues, key="catalog_snapshot_version")
        _require_non_empty_string(ctx, "execution_context.context_registry_version_id", issues, key="context_registry_version_id")

    return SignatureValidationResult(valid=not issues, issues=issues)


def _require_non_empty_string(
    data: dict[str, Any],
    path: str,
    issues: list[SignatureValidationIssue],
    *,
    key: str | None = None,
) -> None:
    lookup = key or path
    value = data.get(lookup)
    if not isinstance(value, str) or not value.strip():
        issues.append(SignatureValidationIssue(path, "is required and must be a non-empty string"))
