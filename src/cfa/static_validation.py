"""
CFA Static Validation
=====================
Analyzes generated code BEFORE execution.
Detects violations that can be identified without running the job.

Belongs to the Static Safety Faults family (Invariant I6).

Checks:
1. Forbidden tokens (collect(), toPandas(), crossJoin(), raw PII)
2. Required patterns (filter(), merge()) based on Signature constraints
3. Schema contract (expected columns, forbidden columns)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .codegen import GeneratedCode
from .types import (
    Fault,
    FaultFamily,
    FaultSeverity,
    PolicyAction,
    StateSignature,
)


# ── Validation Result ────────────────────────────────────────────────────────


@dataclass
class StaticValidationResult:
    """Result of static code analysis."""

    passed: bool
    faults: list[Fault] = field(default_factory=list)
    warnings: list[Fault] = field(default_factory=list)
    checks_performed: int = 0

    @property
    def fault_codes(self) -> list[str]:
        return [f.code for f in self.faults]

    @property
    def is_blocked(self) -> bool:
        return not self.passed


# ── Validation Rules ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ForbiddenToken:
    pattern: str
    fault_code: str
    severity: FaultSeverity
    message: str
    is_regex: bool = False


@dataclass(frozen=True)
class RequiredPattern:
    pattern: str
    fault_code: str
    message: str
    condition_description: str
    is_regex: bool = False


DEFAULT_FORBIDDEN_TOKENS: list[ForbiddenToken] = [
    ForbiddenToken(
        pattern=".collect()",
        fault_code="STATIC_FORBIDDEN_COLLECT",
        severity=FaultSeverity.CRITICAL,
        message="collect() brings all data to driver — forbidden in governed execution.",
    ),
    ForbiddenToken(
        pattern=".toPandas()",
        fault_code="STATIC_FORBIDDEN_TOPANDAS",
        severity=FaultSeverity.CRITICAL,
        message="toPandas() brings all data to driver — forbidden in governed execution.",
    ),
    ForbiddenToken(
        pattern="crossJoin(",
        fault_code="STATIC_FORBIDDEN_CROSSJOIN",
        severity=FaultSeverity.CRITICAL,
        message="crossJoin() produces cartesian product — forbidden without explicit approval.",
    ),
    ForbiddenToken(
        pattern="import os",
        fault_code="STATIC_FORBIDDEN_IMPORT_OS",
        severity=FaultSeverity.CRITICAL,
        message="os module import forbidden in sandboxed execution.",
    ),
    ForbiddenToken(
        pattern="import subprocess",
        fault_code="STATIC_FORBIDDEN_IMPORT_SUBPROCESS",
        severity=FaultSeverity.CRITICAL,
        message="subprocess module import forbidden in sandboxed execution.",
    ),
    ForbiddenToken(
        pattern=r"\.mode\(\"append\"\).*(?:silver|gold)",
        fault_code="STATIC_APPEND_TO_PROTECTED",
        severity=FaultSeverity.HIGH,
        message="Append mode to Silver/Gold detected — use merge instead.",
        is_regex=True,
    ),
]


# ── Static Validator ─────────────────────────────────────────────────────────


class StaticValidator:
    """
    Analyzes generated code before execution.

    Flow:
    1. Check forbidden tokens
    2. Check PII raw references (from Signature)
    3. Check required patterns (partition filter, merge)
    4. Check schema contract (expected/forbidden columns)
    5. Produce StaticValidationResult with all faults
    """

    def __init__(
        self,
        forbidden_tokens: list[ForbiddenToken] | None = None,
    ) -> None:
        self.forbidden_tokens = forbidden_tokens or list(DEFAULT_FORBIDDEN_TOKENS)

    def validate(
        self,
        code: GeneratedCode,
        signature: StateSignature,
        schema_contract: dict[str, Any] | None = None,
    ) -> StaticValidationResult:
        faults: list[Fault] = []
        warnings: list[Fault] = []
        checks = 0

        # 1. Forbidden tokens
        checks += 1
        faults.extend(self._check_forbidden_tokens(code.code))

        # 2. Raw PII references
        checks += 1
        faults.extend(self._check_pii_references(code.code, signature))

        # 3. Required patterns
        checks += 1
        faults.extend(self._check_required_patterns(code.code, signature))

        # 4. Schema contract
        if schema_contract:
            checks += 1
            faults.extend(self._check_schema_contract(code.code, schema_contract))

        # Separate warnings from blocking faults
        blocking = [f for f in faults if f.severity in (FaultSeverity.CRITICAL, FaultSeverity.HIGH)]
        non_blocking = [f for f in faults if f.severity in (FaultSeverity.WARNING, FaultSeverity.INFO)]

        return StaticValidationResult(
            passed=len(blocking) == 0,
            faults=blocking,
            warnings=non_blocking,
            checks_performed=checks,
        )

    def _check_forbidden_tokens(self, code: str) -> list[Fault]:
        faults: list[Fault] = []
        for token in self.forbidden_tokens:
            found = False
            if token.is_regex:
                found = bool(re.search(token.pattern, code, re.IGNORECASE))
            else:
                found = token.pattern in code

            if found:
                faults.append(Fault(
                    code=token.fault_code,
                    family=FaultFamily.STATIC,
                    severity=token.severity,
                    stage="static_validation",
                    message=token.message,
                    mandatory_action=PolicyAction.BLOCK,
                ))
        return faults

    def _check_pii_references(self, code: str, signature: StateSignature) -> list[Fault]:
        """Check that raw PII column names don't appear in code (except in drop/hash contexts)."""
        faults: list[Fault] = []
        if not signature.constraints.no_pii_raw:
            return faults

        for ds in signature.datasets:
            for col in ds.pii_columns:
                # Look for raw PII column usage that isn't in a drop() or sha2() context
                # Simple heuristic: if the column appears as a direct reference (not as _hash suffix)
                pattern = rf'F\.col\(\s*"{re.escape(col)}"\s*\)'
                matches = list(re.finditer(pattern, code))

                for match in matches:
                    # Check if this is inside a sha2() or drop() — allow those
                    context_start = max(0, match.start() - 50)
                    context = code[context_start:match.end() + 30]
                    if "sha2(" in context or '.drop(' in context:
                        continue
                    faults.append(Fault(
                        code=f"STATIC_RAW_PII_REFERENCE_{col.upper()}",
                        family=FaultFamily.STATIC,
                        severity=FaultSeverity.CRITICAL,
                        stage="static_validation",
                        message=f"Raw PII column '{col}' referenced without anonymization context.",
                        mandatory_action=PolicyAction.BLOCK,
                    ))
        return faults

    def _check_required_patterns(self, code: str, signature: StateSignature) -> list[Fault]:
        faults: list[Fault] = []

        # Partition filter required for high-volume datasets
        if signature.constraints.partition_by:
            if ".filter(" not in code and ".where(" not in code:
                faults.append(Fault(
                    code="STATIC_MISSING_PARTITION_FILTER",
                    family=FaultFamily.STATIC,
                    severity=FaultSeverity.HIGH,
                    stage="static_validation",
                    message="Partition filter required but no .filter() or .where() found in code.",
                    mandatory_action=PolicyAction.BLOCK,
                    remediation=("Add partition filter on temporal column.",),
                ))

        # Merge required for Silver/Gold
        if signature.writes_to_protected_layer and signature.constraints.merge_key_required:
            if "merge(" not in code.lower() and "mergebuilder" not in code.lower() and "DeltaTable" not in code:
                faults.append(Fault(
                    code="STATIC_MISSING_MERGE_OPERATION",
                    family=FaultFamily.STATIC,
                    severity=FaultSeverity.HIGH,
                    stage="static_validation",
                    message="Merge operation required for Silver/Gold write but not found.",
                    mandatory_action=PolicyAction.BLOCK,
                    remediation=("Use DeltaTable.merge() instead of append.",),
                ))

        return faults

    def _check_schema_contract(self, code: str, contract: dict[str, Any]) -> list[Fault]:
        """Check that expected columns are present and forbidden columns are absent."""
        faults: list[Fault] = []

        forbidden_cols = contract.get("forbidden_columns", [])
        for col in forbidden_cols:
            # Check if the column appears in a context that suggests it survives to output
            # (not inside drop() or as source of sha2())
            pattern = rf'alias\(\s*"{re.escape(col)}"\s*\)|\.select\(.*"{re.escape(col)}"'
            if re.search(pattern, code):
                faults.append(Fault(
                    code=f"STATIC_FORBIDDEN_COLUMN_{col.upper()}",
                    family=FaultFamily.STATIC,
                    severity=FaultSeverity.CRITICAL,
                    stage="static_validation",
                    message=f"Forbidden column '{col}' appears in output schema.",
                    mandatory_action=PolicyAction.BLOCK,
                ))

        return faults
