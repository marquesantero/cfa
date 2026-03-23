"""
CFA Policy Engine
=================
Applies governance, FinOps and contract rules BEFORE execution.
No plan is executed without passing through here.

Principles:
- Rules are declarative: condition + action + fault_code
- Versioned via policy_bundle_version
- Result: approve / replan / block
- Max 3 replans before terminal block
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .types import (
    DatasetClassification,
    Fault,
    FaultFamily,
    FaultSeverity,
    PolicyAction,
    PolicyResult,
    StateSignature,
    TargetLayer,
)

MAX_REPLAN_ATTEMPTS = 3


# ── Rule contract ────────────────────────────────────────────────────────────


@dataclass
class PolicyRule:
    """
    Minimal unit of a governance rule.
    condition: returns True if the rule fires.
    action: what to do when it fires.
    """

    name: str
    condition: Callable[[StateSignature], bool]
    action: PolicyAction
    fault_code: str
    fault_family: FaultFamily
    severity: FaultSeverity
    message: str
    remediation: tuple[str, ...] = ()

    def evaluate(self, signature: StateSignature) -> Fault | None:
        if self.condition(signature):
            return Fault(
                code=self.fault_code,
                family=self.fault_family,
                severity=self.severity,
                stage="policy_engine",
                message=self.message,
                mandatory_action=self.action,
                remediation=self.remediation,
            )
        return None


# ── Default ruleset ──────────────────────────────────────────────────────────


def build_default_ruleset() -> list[PolicyRule]:
    """
    Default CFA rule set.
    In production, loaded from a versioned policy_bundle.
    """
    return [
        # ── Governance / PII ────────────────────────────────────────────
        PolicyRule(
            name="forbid_raw_pii_in_silver_or_gold",
            condition=lambda sig: (
                sig.writes_to_protected_layer
                and sig.contains_pii
                and not sig.constraints.no_pii_raw
            ),
            action=PolicyAction.REPLAN,
            fault_code="GOVERNANCE_RAW_PII_IN_PROTECTED_LAYER",
            fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.CRITICAL,
            message="PII detected without treatment in write to protected layer.",
            remediation=(
                "Apply sha256() on PII columns before join",
                "Or use drop() to remove sensitive columns",
            ),
        ),
        PolicyRule(
            name="require_pii_anonymization_declaration",
            condition=lambda sig: (
                sig.contains_pii and not sig.constraints.no_pii_raw
            ),
            action=PolicyAction.BLOCK,
            fault_code="GOVERNANCE_PII_WITHOUT_POLICY",
            fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.CRITICAL,
            message="Datasets with PII present but no_pii_raw=False without justification.",
            remediation=(
                "Set constraints.no_pii_raw=True explicitly",
                "Or add PII treatment justification to domain",
            ),
        ),
        # ── FinOps ──────────────────────────────────────────────────────
        PolicyRule(
            name="require_partition_filter_for_high_volume",
            condition=lambda sig: (
                any(d.classification == DatasetClassification.HIGH_VOLUME for d in sig.datasets)
                and len(sig.constraints.partition_by) == 0
            ),
            action=PolicyAction.REPLAN,
            fault_code="FINOPS_MISSING_TEMPORAL_PREDICATE",
            fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.HIGH,
            message="High volume dataset without partition filter — full scan risk.",
            remediation=(
                "Add constraints.partition_by with temporal column",
                "Example: partition_by: [processing_date]",
            ),
        ),
        PolicyRule(
            name="warn_on_sensitive_without_partition",
            condition=lambda sig: (
                any(d.classification == DatasetClassification.SENSITIVE for d in sig.datasets)
                and len(sig.constraints.partition_by) == 0
            ),
            action=PolicyAction.REPLAN,
            fault_code="FINOPS_SENSITIVE_WITHOUT_PARTITION",
            fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.WARNING,
            message="Sensitive dataset without declared partitioning.",
            remediation=("Add partition_by to limit processing scope.",),
        ),
        # ── Data Contract ───────────────────────────────────────────────
        PolicyRule(
            name="require_merge_key_for_silver_gold",
            condition=lambda sig: (
                sig.writes_to_protected_layer and not sig.constraints.merge_key_required
            ),
            action=PolicyAction.BLOCK,
            fault_code="CONTRACT_MISSING_MERGE_KEY",
            fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.CRITICAL,
            message="Write to Silver/Gold without merge_key — direct append forbidden.",
            remediation=(
                "Set constraints.merge_key_required=True",
                "Ensure the Planner uses merge, not append",
            ),
        ),
        PolicyRule(
            name="enforce_type_checking",
            condition=lambda sig: (
                sig.writes_to_protected_layer and not sig.constraints.enforce_types
            ),
            action=PolicyAction.REPLAN,
            fault_code="CONTRACT_TYPE_ENFORCEMENT_DISABLED",
            fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.HIGH,
            message="enforce_types=False in write to protected layer.",
            remediation=(
                "Enable constraints.enforce_types=True",
                "Define expected schema in catalog",
            ),
        ),
        # ── Cost Ceiling ────────────────────────────────────────────────
        PolicyRule(
            name="enforce_cost_ceiling",
            condition=lambda sig: (
                sig.constraints.max_cost_dbu is not None
                and sig.constraints.max_cost_dbu <= 0
            ),
            action=PolicyAction.BLOCK,
            fault_code="FINOPS_INVALID_COST_CEILING",
            fault_family=FaultFamily.SEMANTIC,
            severity=FaultSeverity.HIGH,
            message="max_cost_dbu invalid (must be > 0).",
            remediation=("Set constraints.max_cost_dbu with positive value.",),
        ),
    ]


# ── Policy Engine ────────────────────────────────────────────────────────────


class PolicyEngine:
    """
    Evaluates all governance rules against a State Signature.

    Flow:
    1. Evaluate each rule against the Signature
    2. Collect all Faults
    3. Determine action: approve / replan / block
    4. Control replan limit
    """

    def __init__(
        self,
        rules: list[PolicyRule] | None = None,
        policy_bundle_version: str = "v1.0",
        max_replan_attempts: int = MAX_REPLAN_ATTEMPTS,
    ) -> None:
        self.rules = rules if rules is not None else build_default_ruleset()
        self.policy_bundle_version = policy_bundle_version
        self.max_replan_attempts = max_replan_attempts

    def evaluate(
        self, signature: StateSignature, replan_count: int = 0
    ) -> PolicyResult:
        if replan_count >= self.max_replan_attempts:
            return PolicyResult(
                action=PolicyAction.BLOCK,
                replan_count=replan_count,
                reasoning=f"Replan limit ({self.max_replan_attempts}) reached. Manual intervention required.",
                faults=[
                    Fault(
                        code="POLICY_MAX_REPLAN_EXCEEDED",
                        family=FaultFamily.SEMANTIC,
                        severity=FaultSeverity.CRITICAL,
                        stage="policy_engine",
                        message=f"Max {self.max_replan_attempts} replans exceeded.",
                        mandatory_action=PolicyAction.BLOCK,
                        remediation=("Review the intent manually and fix previous faults.",),
                    )
                ],
            )

        faults: list[Fault] = []
        for rule in self.rules:
            fault = rule.evaluate(signature)
            if fault:
                faults.append(fault)

        action = self._determine_action(faults)

        interventions: list[str] = []
        if action == PolicyAction.REPLAN:
            for fault in faults:
                interventions.extend(fault.remediation)

        return PolicyResult(
            action=action,
            faults=faults,
            interventions=list(dict.fromkeys(interventions)),
            replan_count=replan_count,
            reasoning=self._build_reasoning(action, faults, replan_count),
        )

    def _determine_action(self, faults: list[Fault]) -> PolicyAction:
        """BLOCK > REPLAN > APPROVE."""
        if not faults:
            return PolicyAction.APPROVE
        if any(f.mandatory_action == PolicyAction.BLOCK for f in faults):
            return PolicyAction.BLOCK
        if any(f.mandatory_action == PolicyAction.REPLAN for f in faults):
            return PolicyAction.REPLAN
        return PolicyAction.APPROVE

    def _build_reasoning(
        self, action: PolicyAction, faults: list[Fault], replan_count: int
    ) -> str:
        if not faults:
            return "All rules passed. Execution approved."
        fault_summary = "; ".join(f.code for f in faults)
        base = f"action={action.value} | faults=[{fault_summary}]"
        if action == PolicyAction.REPLAN:
            base += f" | replan {replan_count + 1}/{self.max_replan_attempts}"
        elif action == PolicyAction.BLOCK:
            base += " | TERMINAL"
        return base

    def add_rule(self, rule: PolicyRule) -> None:
        self.rules.append(rule)

    def describe_rules(self) -> list[dict[str, str]]:
        return [
            {
                "name": r.name,
                "action": r.action.value,
                "fault_code": r.fault_code,
                "severity": r.severity.value,
            }
            for r in self.rules
        ]
