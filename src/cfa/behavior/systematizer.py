"""
CFA Systematizer
================
Transforms a BehaviorSpec into a BehaviorTaxonomy and optionally
auto-generates PolicyRules for the CFA Policy Engine.

This is the systematization step: bridge between human-written
governance intent and executable rules.

Supports two modes:
- Template-based (MVP, no LLM): maps failure_modes → PolicyRules via conditions
- LLM-assisted (Phase 6): NL description → behavior spec (future)
"""

from __future__ import annotations

from typing import Any

from cfa.core.conditions import build_condition
from cfa.policy.engine import PolicyRule
from cfa.types import (
    FaultFamily,
    FaultSeverity,
    PolicyAction,
)

from .spec import (
    BehaviorCategory,
    BehaviorSpec,
    BehaviorTaxonomy,
    ConditionType,
)

# Re-export for convenience
try:
    from .llm import LLMSystematizer, LLMSystematizerBackend  # noqa: F401
    _HAS_LLM = True
except ImportError:
    _HAS_LLM = False

# Map ConditionType enum values to ConditionRegistry names
_CONDITION_TYPE_MAP: dict[ConditionType, str] = {
    ConditionType.PII_IN_PROTECTED_LAYER: "pii_in_protected_layer",
    ConditionType.MISSING_MERGE_KEY: "missing_merge_key",
    ConditionType.MISSING_PARTITION: "missing_partition",
    ConditionType.ENFORCE_TYPES_DISABLED: "enforce_types_disabled",
    ConditionType.PII_WITHOUT_POLICY: "pii_without_policy",
    ConditionType.SENSITIVE_WITHOUT_PARTITION: "sensitive_without_partition",
    ConditionType.COST_BUDGET_EXCEEDED: "cost_budget_exceeded",
    ConditionType.SCHEMA_MISMATCH: "schema_mismatch",
    ConditionType.SHUFFLE_BUDGET_EXCEEDED: "shuffle_budget_exceeded",
    ConditionType.UNAUTHORIZED_GOLD_WRITE: "unauthorized_gold_write",
}

_SEVERITY_MAP: dict[str, FaultSeverity] = {
    "info": FaultSeverity.INFO,
    "warning": FaultSeverity.WARNING,
    "high": FaultSeverity.HIGH,
    "critical": FaultSeverity.CRITICAL,
}

_ACTION_MAP: dict[str, PolicyAction] = {
    "block": PolicyAction.BLOCK,
    "replan": PolicyAction.REPLAN,
    "approve": PolicyAction.APPROVE,
}


class Systematizer:
    """Transforms a BehaviorSpec into a BehaviorTaxonomy and PolicyRules."""

    def systematize(
        self, spec: BehaviorSpec
    ) -> tuple[BehaviorTaxonomy, list[PolicyRule]]:
        """Main entry point: spec → (taxonomy, rules).

        Args:
            spec: Parsed BehaviorSpec from YAML or programmatic construction.

        Returns:
            Tuple of (BehaviorTaxonomy, list of PolicyRules).
        """
        taxonomy = self._build_taxonomy(spec)
        rules: list[PolicyRule] = []

        if spec.auto_generate_rules:
            rules = self._generate_rules(spec, taxonomy)

        return taxonomy, rules

    def systematize_from_nl(
        self,
        description: str,
        *,
        backend: Any = None,
        context: str = "",
        target_layer: str = "silver",
    ) -> tuple[BehaviorTaxonomy, list[PolicyRule]]:
        """Natural language → BehaviorTaxonomy + PolicyRules via LLM.

        Requires an LLM backend implementing LLMSystematizerBackend.

        Args:
            description: NL description of governance requirements.
            backend: LLM backend instance (e.g. OpenAISystematizerBackend).
            context: Optional context about the target system.
            target_layer: Default target layer for generated rules.

        Returns:
            Tuple of (BehaviorTaxonomy, list of PolicyRules).
        """
        from .llm import LLMSystematizer

        llm = LLMSystematizer()
        spec = llm.systematize_nl(description, backend=backend, context=context)
        spec.target_layer = target_layer
        return self.systematize(spec)

    def _build_taxonomy(self, spec: BehaviorSpec) -> BehaviorTaxonomy:
        allowed: list[BehaviorCategory] = []
        not_allowed: list[BehaviorCategory] = []

        for mode in spec.failure_modes:
            code = mode.get("code", "unnamed")
            label = mode.get("label", code.replace("_", " ").title())
            description = mode.get("description", "")
            severity = mode.get("severity", "high")

            condition_str = mode.get("condition", "custom")
            try:
                condition_type = ConditionType(condition_str)
            except ValueError:
                condition_type = ConditionType.CUSTOM

            category = BehaviorCategory(
                code=code,
                label=label,
                description=description,
                allowed=False,
                condition_type=condition_type,
                severity=severity,
                remediation=mode.get("remediation", []),
                metadata={
                    "target_layer": mode.get("target_layer", spec.target_layer),
                    "max_dbu": mode.get("max_dbu"),
                    "min_size_gb": mode.get("min_size_gb", 1.0),
                    **mode.get("metadata", {}),
                },
            )
            not_allowed.append(category)

        # Implicit allowed behaviors (the inverse of what we test for)
        # This would be enriched by an LLM in Phase 6
        allowed.append(
            BehaviorCategory(
                code="valid_governed_processing",
                label="Valid Governed Processing",
                description=(
                    "All pipeline operations that respect PII, schema, budget, "
                    "and partition constraints."
                ),
                allowed=True,
                condition_type=ConditionType.CUSTOM,
            )
        )

        return BehaviorTaxonomy(
            name=spec.name,
            description=spec.description,
            context=spec.context,
            allowed=allowed,
            not_allowed=not_allowed,
        )

    def _generate_rules(
        self, spec: BehaviorSpec, taxonomy: BehaviorTaxonomy
    ) -> list[PolicyRule]:
        """Auto-generate PolicyRules from the taxonomy's not_allowed categories."""

        rules: list[PolicyRule] = []

        for category in taxonomy.not_allowed:
            condition_name = _CONDITION_TYPE_MAP.get(category.condition_type)
            if condition_name is None:
                continue

            try:
                condition_fn = build_condition(condition_name, category.metadata)
            except KeyError:
                continue

            severity_enum = _SEVERITY_MAP.get(category.severity, FaultSeverity.HIGH)
            action_enum = _ACTION_MAP.get(
                category.metadata.get("action", "replan"), PolicyAction.REPLAN
            )

            rules.append(
                PolicyRule(
                    name=f"behavior_spec_{category.code}",
                    condition=condition_fn,
                    action=action_enum,
                    fault_code=f"BEHAVIOR_{category.code.upper()}",
                    fault_family=FaultFamily.SEMANTIC,
                    severity=severity_enum,
                    message=f"{category.label}: {category.description}",
                    remediation=tuple(category.remediation),
                )
            )

        return rules

    def generate_test_intents(
        self, spec: BehaviorSpec, count: int = 3
    ) -> list[str]:
        """Generate test intent strings that exercise each failure mode.

        Useful for automated governance testing in CI.
        """
        taxonomy, _ = self.systematize(spec)
        if spec.generate_test_cases:
            return taxonomy.generate_test_intents(count)
        return []
