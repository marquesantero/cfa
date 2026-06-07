"""
CFA Behavior Spec
=================
Structured specification of allowed and prohibited behaviors.

A BehaviorSpec bridges the gap between human-written governance policies
(in natural language or YAML) and executable CFA policy rules.

Inspired by ASSERT's systematization: BehaviorSpec → BehaviorTaxonomy → PolicyRules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class ConditionType(StrEnum):
    """Condition types that map to CFA constraint checks."""

    PII_IN_PROTECTED_LAYER = "pii_in_protected_layer"
    MISSING_MERGE_KEY = "missing_merge_key"
    SCHEMA_MISMATCH = "schema_mismatch"
    SHUFFLE_BUDGET_EXCEEDED = "shuffle_budget_exceeded"
    MISSING_PARTITION = "missing_partition"
    COST_BUDGET_EXCEEDED = "cost_budget_exceeded"
    UNAUTHORIZED_GOLD_WRITE = "unauthorized_gold_write"
    ENFORCE_TYPES_DISABLED = "enforce_types_disabled"
    PII_WITHOUT_POLICY = "pii_without_policy"
    SENSITIVE_WITHOUT_PARTITION = "sensitive_without_partition"
    CUSTOM = "custom"


@dataclass
class BehaviorCategory:
    """A single behavior category in the taxonomy.

    Attributes:
        code: Unique identifier, e.g. "raw_pii_exposure".
        label: Human-readable label, e.g. "Raw PII in Silver/Gold".
        description: Detailed description of the behavior.
        allowed: True if this behavior is permitted, False if prohibited.
        condition_type: The CFA ConditionType that detects this behavior.
        severity: Fault severity when this behavior is detected.
        remediation: Ordered list of remediation actions.
        metadata: Custom key-value pairs for condition refinements.
    """

    code: str
    label: str
    description: str
    allowed: bool = True
    condition_type: ConditionType = ConditionType.CUSTOM
    severity: str = "high"
    remediation: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BehaviorTaxonomy:
    """Complete taxonomy of behaviors for a governance domain.

    Separates behaviors into allowed (permissible) and not_allowed (prohibited)
    categories, with metadata for traceability.
    """

    name: str
    description: str = ""
    context: str = ""

    allowed: list[BehaviorCategory] = field(default_factory=list)
    not_allowed: list[BehaviorCategory] = field(default_factory=list)

    spec_version: str = "v1.0"
    source_yaml: str = ""

    @property
    def categories(self) -> list[BehaviorCategory]:
        return self.allowed + self.not_allowed

    @property
    def category_count(self) -> int:
        return len(self.categories)

    def generate_test_intents(self, count: int = 3) -> list[str]:
        """Generate test intent strings for each behavior category.

        Used for automated test case generation in CI.
        """
        intents: list[str] = []
        template_map = {
            ConditionType.PII_IN_PROTECTED_LAYER: (
                "Join {datasets} with PII columns and persist to {layer}"
            ),
            ConditionType.MISSING_MERGE_KEY: (
                "Write {datasets} directly to {layer} without merge key"
            ),
            ConditionType.MISSING_PARTITION: (
                "Scan full {datasets} without partition filter"
            ),
            ConditionType.SCHEMA_MISMATCH: (
                "Write {datasets} to {layer} with modified schema"
            ),
            ConditionType.SHUFFLE_BUDGET_EXCEEDED: (
                "Join massive {datasets} with cross join"
            ),
            ConditionType.COST_BUDGET_EXCEEDED: (
                "Process full {datasets} without budget limit"
            ),
        }
        for cat in self.not_allowed:
            template = template_map.get(
                cat.condition_type,
                "Process {datasets} in {layer} layer",
            )
            for i in range(min(count, 3)):
                intents.append(
                    template.format(
                        datasets=cat.code.replace("_", " "),
                        layer=cat.metadata.get("target_layer", "Silver"),
                    )
                    + f" #{cat.code}#{i}"
                )
        return intents

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "context": self.context,
            "allowed": [
                {
                    "code": c.code,
                    "label": c.label,
                    "description": c.description,
                    "condition_type": c.condition_type.value,
                }
                for c in self.allowed
            ],
            "not_allowed": [
                {
                    "code": c.code,
                    "label": c.label,
                    "description": c.description,
                    "condition_type": c.condition_type.value,
                    "severity": c.severity,
                    "remediation": c.remediation,
                }
                for c in self.not_allowed
            ],
            "spec_version": self.spec_version,
        }


@dataclass
class BehaviorSpec:
    """Top-level behavior specification, typically loaded from YAML.

    Schema:
        behavior:
          name: fiscal_reconciliation
          description: |
            # Fiscal Data Reconciliation Governance
            ...
          failure_modes:
            - code: raw_pii_exposure
              ...
        context: |
          Target is a PySpark ETL pipeline...
        generate:
          taxonomy: true
          test_cases: true
    """

    name: str
    description: str = ""
    context: str = ""
    failure_modes: list[dict[str, Any]] = field(default_factory=list)
    target_layer: str = "silver"
    backend: str = "pyspark"
    auto_generate_rules: bool = True
    generate_test_cases: bool = True

    @classmethod
    def from_yaml(cls, path: str | Path) -> BehaviorSpec:
        """Parse a BehaviorSpec from a YAML file.

        Requires PyYAML. Falls back gracefully with a clear message if not installed.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Behavior spec file not found: {path}")

        try:
            import yaml
        except ImportError:
            raise ImportError(
                "PyYAML is required to load BehaviorSpec from YAML. "
                "Install it with: pip install pyyaml"
            )

        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        behavior = raw.get("behavior", raw)
        pipeline = raw.get("pipeline", raw.get("generate", {}))

        return cls(
            name=behavior.get("name", "unnamed"),
            description=behavior.get("description", ""),
            context=raw.get("context", ""),
            failure_modes=behavior.get("failure_modes", []),
            target_layer=behavior.get("target_layer", raw.get("default_model", {}).get("target_layer", "silver")),
            backend=behavior.get("backend", raw.get("default_model", {}).get("backend", "pyspark")),
            auto_generate_rules=pipeline.get("policy", {}).get("auto_generate_rules", True),
            generate_test_cases=pipeline.get("generate", {}).get("test_cases", True),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BehaviorSpec:
        """Build from a dictionary (e.g. loaded from JSON or programmatic)."""
        behavior = data.get("behavior", data)
        pipeline = data.get("pipeline", {})
        generate = pipeline.get("generate", data.get("generate", {}))

        return cls(
            name=behavior.get("name", "unnamed"),
            description=behavior.get("description", ""),
            context=data.get("context", ""),
            failure_modes=behavior.get("failure_modes", []),
            target_layer=behavior.get("target_layer", data.get("default_model", {}).get("target_layer", "silver")),
            backend=behavior.get("backend", data.get("default_model", {}).get("backend", "pyspark")),
            auto_generate_rules=pipeline.get("policy", {}).get("auto_generate_rules", True),
            generate_test_cases=generate.get("test_cases", True),
        )
