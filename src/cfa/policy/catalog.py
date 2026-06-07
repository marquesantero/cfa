"""CFA catalog validation.

The catalog is the grounding source for governed transitions. Validation here is
intentionally structural and backend-agnostic: it checks that CFA can safely use
the metadata before any normalizer or policy rule depends on it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cfa.types import Fault, FaultFamily, FaultSeverity, PolicyAction

ALLOWED_CLASSIFICATIONS = {"public", "internal", "sensitive", "high_volume"}


@dataclass(frozen=True)
class CatalogValidationIssue:
    path: str
    message: str


@dataclass(frozen=True)
class CatalogValidationResult:
    valid: bool
    issues: list[CatalogValidationIssue] = field(default_factory=list)

    @property
    def messages(self) -> list[str]:
        return [f"{i.path}: {i.message}" for i in self.issues]

    def to_fault(self) -> Fault:
        return Fault(
            code="CATALOG_INVALID",
            family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.CRITICAL,
            stage="catalog_validation",
            message="Catalog validation failed.",
            mandatory_action=PolicyAction.BLOCK,
            remediation=(
                "Fix the catalog structure before evaluating governed transitions.",
                *self.messages[:5],
            ),
        )


def validate_catalog(
    catalog: dict[str, Any] | None,
    *,
    require_datasets: bool = False,
) -> CatalogValidationResult:
    issues: list[CatalogValidationIssue] = []

    if catalog is None:
        if require_datasets:
            issues.append(CatalogValidationIssue("catalog", "catalog is required"))
        return CatalogValidationResult(valid=not issues, issues=issues)

    if not isinstance(catalog, dict):
        return CatalogValidationResult(
            valid=False,
            issues=[CatalogValidationIssue("catalog", "must be an object")],
        )

    datasets = catalog.get("datasets")
    if datasets is None:
        if require_datasets:
            issues.append(CatalogValidationIssue("datasets", "is required"))
        return CatalogValidationResult(valid=not issues, issues=issues)

    if not isinstance(datasets, dict):
        return CatalogValidationResult(
            valid=False,
            issues=[CatalogValidationIssue("datasets", "must be an object keyed by dataset name")],
        )

    if require_datasets and not datasets:
        issues.append(CatalogValidationIssue("datasets", "must contain at least one dataset"))

    for name, meta in datasets.items():
        dataset_path = f"datasets.{name}"
        if not isinstance(name, str) or not name.strip():
            issues.append(CatalogValidationIssue("datasets", "dataset names must be non-empty strings"))
            continue
        if not isinstance(meta, dict):
            issues.append(CatalogValidationIssue(dataset_path, "metadata must be an object"))
            continue

        classification = meta.get("classification", "internal")
        if classification not in ALLOWED_CLASSIFICATIONS:
            issues.append(CatalogValidationIssue(
                f"{dataset_path}.classification",
                f"must be one of {sorted(ALLOWED_CLASSIFICATIONS)}",
            ))

        size_gb = meta.get("size_gb", 0.0)
        if not isinstance(size_gb, (int, float)) or isinstance(size_gb, bool) or size_gb < 0:
            issues.append(CatalogValidationIssue(f"{dataset_path}.size_gb", "must be a non-negative number"))

        pii_columns = meta.get("pii_columns", [])
        if not isinstance(pii_columns, (list, tuple)):
            issues.append(CatalogValidationIssue(f"{dataset_path}.pii_columns", "must be a list of strings"))
        elif any(not isinstance(col, str) or not col.strip() for col in pii_columns):
            issues.append(CatalogValidationIssue(f"{dataset_path}.pii_columns", "must contain only non-empty strings"))

        partition_column = meta.get("partition_column")
        if partition_column is not None and not isinstance(partition_column, str):
            issues.append(CatalogValidationIssue(f"{dataset_path}.partition_column", "must be a string or null"))

        merge_keys = meta.get("merge_keys", [])
        if not isinstance(merge_keys, (list, tuple)):
            issues.append(CatalogValidationIssue(f"{dataset_path}.merge_keys", "must be a list of strings"))
        elif any(not isinstance(key, str) or not key.strip() for key in merge_keys):
            issues.append(CatalogValidationIssue(f"{dataset_path}.merge_keys", "must contain only non-empty strings"))

    return CatalogValidationResult(valid=not issues, issues=issues)
