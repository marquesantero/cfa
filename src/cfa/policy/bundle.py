"""
CFA Policy Bundle
=================
Versioned, loadable policy rule sets from YAML/JSON files.

Enables separation of concerns:
- Platform/security teams define policies in YAML
- Data/engineering teams reference them by version
- CI/CD pipelines validate against specific bundle versions

Usage:
    from cfa.policy_bundle import PolicyBundle
    bundle = PolicyBundle.from_yaml("policies/prod-v1.yaml")
    engine = PolicyEngine.from_bundle(bundle)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cfa.core.conditions import build_condition, list_conditions
from cfa.policy.engine import PolicyRule
from cfa.types import FaultFamily, FaultSeverity, PolicyAction

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

_FAMILY_MAP: dict[str, FaultFamily] = {
    "semantic": FaultFamily.SEMANTIC,
    "static": FaultFamily.STATIC,
    "runtime": FaultFamily.RUNTIME,
    "environment": FaultFamily.ENVIRONMENT,
}

_RULE_PARAM_KEYS = {"target_layer", "min_size_gb", "max_dbu"}


@dataclass(frozen=True)
class PolicyBundleValidationIssue:
    path: str
    message: str


@dataclass(frozen=True)
class PolicyBundleValidationResult:
    valid: bool
    issues: list[PolicyBundleValidationIssue] = field(default_factory=list)

    @property
    def messages(self) -> list[str]:
        return [f"{i.path}: {i.message}" for i in self.issues]

    def raise_if_invalid(self, source: str = "") -> None:
        if self.valid:
            return
        location = f" in {source}" if source else ""
        joined = "; ".join(self.messages)
        raise ValueError(f"Invalid policy bundle{location}: {joined}")


def validate_policy_bundle_data(data: dict[str, Any] | None) -> PolicyBundleValidationResult:
    issues: list[PolicyBundleValidationIssue] = []

    if data is None:
        return PolicyBundleValidationResult(
            valid=False,
            issues=[PolicyBundleValidationIssue("policy_bundle", "file is empty")],
        )
    if not isinstance(data, dict):
        return PolicyBundleValidationResult(
            valid=False,
            issues=[PolicyBundleValidationIssue("policy_bundle", "must be an object")],
        )

    bundle_data = data.get("policy_bundle", data)
    if not isinstance(bundle_data, dict):
        return PolicyBundleValidationResult(
            valid=False,
            issues=[PolicyBundleValidationIssue("policy_bundle", "must be an object")],
        )

    version = bundle_data.get("version")
    if not isinstance(version, str) or not version.strip():
        issues.append(PolicyBundleValidationIssue("policy_bundle.version", "is required and must be a non-empty string"))

    rules = bundle_data.get("rules")
    if not isinstance(rules, list) or not rules:
        issues.append(PolicyBundleValidationIssue("policy_bundle.rules", "must be a non-empty list"))
        return PolicyBundleValidationResult(valid=not issues, issues=issues)

    known_conditions = set(list_conditions())
    seen_names: set[str] = set()
    seen_fault_codes: set[str] = set()

    for idx, rule in enumerate(rules):
        base = f"policy_bundle.rules[{idx}]"
        if not isinstance(rule, dict):
            issues.append(PolicyBundleValidationIssue(base, "must be an object"))
            continue

        name = rule.get("name")
        if not isinstance(name, str) or not name.strip():
            issues.append(PolicyBundleValidationIssue(f"{base}.name", "is required and must be a non-empty string"))
        elif name in seen_names:
            issues.append(PolicyBundleValidationIssue(f"{base}.name", f"duplicate rule name '{name}'"))
        else:
            seen_names.add(name)

        condition = rule.get("condition")
        if not isinstance(condition, str) or not condition.strip():
            issues.append(PolicyBundleValidationIssue(f"{base}.condition", "is required and must be a non-empty string"))
        elif condition not in known_conditions:
            issues.append(PolicyBundleValidationIssue(
                f"{base}.condition",
                f"unknown condition '{condition}'. Registered conditions: {', '.join(sorted(known_conditions))}",
            ))

        action = rule.get("action")
        if action not in _ACTION_MAP:
            issues.append(PolicyBundleValidationIssue(f"{base}.action", f"must be one of {sorted(_ACTION_MAP)}"))

        severity = rule.get("severity")
        if severity not in _SEVERITY_MAP:
            issues.append(PolicyBundleValidationIssue(f"{base}.severity", f"must be one of {sorted(_SEVERITY_MAP)}"))

        family = rule.get("family", "semantic")
        if family not in _FAMILY_MAP:
            issues.append(PolicyBundleValidationIssue(f"{base}.family", f"must be one of {sorted(_FAMILY_MAP)}"))

        fault_code = rule.get("fault_code")
        if not isinstance(fault_code, str) or not fault_code.strip():
            issues.append(PolicyBundleValidationIssue(f"{base}.fault_code", "is required and must be a non-empty string"))
        elif fault_code in seen_fault_codes:
            issues.append(PolicyBundleValidationIssue(f"{base}.fault_code", f"duplicate fault code '{fault_code}'"))
        else:
            seen_fault_codes.add(fault_code)

        message = rule.get("message")
        if not isinstance(message, str) or not message.strip():
            issues.append(PolicyBundleValidationIssue(f"{base}.message", "is required and must be a non-empty string"))

        remediation = rule.get("remediation", [])
        if not isinstance(remediation, list):
            issues.append(PolicyBundleValidationIssue(f"{base}.remediation", "must be a list of strings"))
        elif any(not isinstance(item, str) or not item.strip() for item in remediation):
            issues.append(PolicyBundleValidationIssue(f"{base}.remediation", "must contain only non-empty strings"))

        if "target_layer" in rule and rule["target_layer"] not in ("bronze", "silver", "gold"):
            issues.append(PolicyBundleValidationIssue(f"{base}.target_layer", "must be one of ['bronze', 'silver', 'gold']"))
        for numeric_key in ("min_size_gb", "max_dbu"):
            if numeric_key in rule and (
                not isinstance(rule[numeric_key], (int, float))
                or isinstance(rule[numeric_key], bool)
                or rule[numeric_key] < 0
            ):
                issues.append(PolicyBundleValidationIssue(f"{base}.{numeric_key}", "must be a non-negative number"))

    return PolicyBundleValidationResult(valid=not issues, issues=issues)


@dataclass
class PolicyBundle:
    """A versioned collection of policy rules loadable from YAML/JSON.

    Attributes:
        version: Semantic version string (e.g. "prod-v1.0").
        description: Human-readable description of the bundle.
        rules: List of PolicyRules defined in this bundle.
        last_updated: ISO 8601 timestamp.
        source_path: Path the bundle was loaded from (if any).
        metadata: Arbitrary key-value metadata.
    """

    version: str
    description: str = ""
    rules: list[PolicyRule] = field(default_factory=list)
    last_updated: str = ""
    source_path: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str | Path) -> PolicyBundle:
        """Load a policy bundle from a YAML file.

        YAML schema:
            policy_bundle:
              version: "prod-v1.0"
              description: "Production governance rules"
              last_updated: "2026-06-06"
              rules:
                - name: forbid_raw_pii
                  condition: pii_in_protected_layer
                  action: block
                  fault_code: GOVERNANCE_RAW_PII
                  severity: critical
                  message: "PII detected without treatment."
                  remediation:
                    - "Apply sha256 on PII columns"
        """
        raw = Path(path).read_text(encoding="utf-8")
        try:
            import yaml
            data = yaml.safe_load(raw)
        except ImportError:
            raise ImportError(
                "PyYAML is required for YAML policy bundles. "
                "Install: pip install pyyaml"
            )
        return cls._from_raw(data, str(path))

    @classmethod
    def from_json(cls, path: str | Path) -> PolicyBundle:
        """Load a policy bundle from a JSON file."""
        raw = Path(path).read_text(encoding="utf-8")
        data = json.loads(raw)
        return cls._from_raw(data, str(path))

    @classmethod
    def _from_raw(cls, data: dict[str, Any], source: str = "") -> PolicyBundle:
        validate_policy_bundle_data(data).raise_if_invalid(source)
        bundle_data = data.get("policy_bundle", data)
        version = bundle_data.get("version", "unknown")
        description = bundle_data.get("description", "")
        last_updated = bundle_data.get("last_updated", "")
        metadata = bundle_data.get("metadata", {})

        rules: list[PolicyRule] = []
        for rule_data in bundle_data.get("rules", []):
            condition_name = rule_data.get("condition", "")
            condition_meta = {
                k: v for k, v in rule_data.items()
                if k in _RULE_PARAM_KEYS
            }

            condition_fn = build_condition(condition_name, condition_meta)

            severity_str = rule_data.get("severity", "high")
            severity = _SEVERITY_MAP.get(severity_str, FaultSeverity.HIGH)

            action_str = rule_data.get("action", "replan")
            action = _ACTION_MAP.get(action_str, PolicyAction.REPLAN)

            family_str = rule_data.get("family", "semantic")
            family = _FAMILY_MAP.get(family_str, FaultFamily.SEMANTIC)

            rules.append(PolicyRule(
                name=rule_data.get("name", "unnamed"),
                condition=condition_fn,
                action=action,
                fault_code=rule_data.get("fault_code", f"BUNDLE_{condition_name.upper()}"),
                fault_family=family,
                severity=severity,
                message=rule_data.get("message", ""),
                remediation=tuple(rule_data.get("remediation", [])),
            ))

        return cls(
            version=version,
            description=description,
            rules=rules,
            last_updated=last_updated,
            source_path=source,
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_bundle": {
                "version": self.version,
                "description": self.description,
                "last_updated": self.last_updated,
                "metadata": self.metadata,
                "rules": [
                    {
                        "name": r.name,
                        "condition": "see fault_code",
                        "action": r.action.value,
                        "fault_code": r.fault_code,
                        "severity": r.severity.value,
                        "family": r.fault_family.value,
                        "message": r.message,
                        "remediation": list(r.remediation),
                    }
                    for r in self.rules
                ],
            },
            "source": self.source_path,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


def list_available_bundles(directory: str | Path = "policies") -> list[str]:
    """List available policy bundles in a directory (files ending in .yaml or .json)."""
    dir_path = Path(directory)
    if not dir_path.is_dir():
        return []
    bundles: list[str] = []
    for ext in (".yaml", ".yml", ".json"):
        bundles.extend(
            str(p.relative_to(dir_path)) for p in dir_path.glob(f"*{ext}")
        )
    return sorted(bundles)
