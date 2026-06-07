"""
CFA Static Validation
=====================
Analyzes generated code BEFORE execution.
Detects violations that can be identified without running the job.

Belongs to the Static Safety Faults family (Invariant I6).

Checks:
1. Forbidden tokens (backend-declared)
2. Required patterns (filter(), merge()) based on Signature constraints
3. Schema contract (expected columns, forbidden columns)

Forbidden tokens are declared by each backend via ``BackendCapabilities``.
New backends automatically bring their own validation rules — no central registry.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from cfa.core.codegen import GeneratedCode
from cfa.types import (
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
    """A pattern that must not appear in generated code.

    Declared by each backend in its ``BackendCapabilities.forbidden_tokens``.
    """

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


# ── Static Validator ─────────────────────────────────────────────────────────


class StaticValidator:
    """Analyzes generated code before execution.

    Forbidden tokens come from the backend that generated the code,
    queried via ``backend.get_capabilities().forbidden_tokens``.

    If no backend is provided, a minimal set of common-sense defaults
    is used (``import os``, ``import subprocess``).
    """

    _MINIMAL_FORBIDDEN: list[ForbiddenToken] = (
        ForbiddenToken("import os", "STATIC_FORBIDDEN_IMPORT_OS",
                       FaultSeverity.CRITICAL, "os module import forbidden."),
        ForbiddenToken("import subprocess", "STATIC_FORBIDDEN_IMPORT_SUBPROCESS",
                       FaultSeverity.CRITICAL, "subprocess module import forbidden."),
    )

    def __init__(
        self,
        forbidden_tokens: list[ForbiddenToken] | None = None,
    ) -> None:
        self._explicit_tokens = forbidden_tokens

    def validate(
        self,
        code: GeneratedCode,
        signature: StateSignature,
        schema_contract: dict[str, Any] | None = None,
        *,
        backend: Any | None = None,
    ) -> StaticValidationResult:
        faults: list[Fault] = []
        checks = 0

        # 1. Forbidden tokens (from backend or explicit override or minimal defaults)
        checks += 1
        tokens = self._resolve_tokens(code, backend)
        faults.extend(self._check_forbidden_tokens(code.code, tokens))

        # 2. Raw PII references
        checks += 1
        faults.extend(self._check_pii_references(code.code, signature))

        # 3. Required patterns
        checks += 1
        faults.extend(self._check_required_patterns(code.code, signature, language=code.language))

        # 4. Schema contract
        if schema_contract:
            checks += 1
            faults.extend(self._check_schema_contract(code.code, schema_contract))

        blocking = [f for f in faults if f.severity in (FaultSeverity.CRITICAL, FaultSeverity.HIGH)]
        non_blocking = [f for f in faults if f.severity in (FaultSeverity.WARNING, FaultSeverity.INFO)]

        return StaticValidationResult(
            passed=len(blocking) == 0,
            faults=blocking,
            warnings=non_blocking,
            checks_performed=checks,
        )

    def _resolve_tokens(
        self, code: GeneratedCode, backend: Any | None
    ) -> list[ForbiddenToken]:
        if self._explicit_tokens is not None:
            return self._explicit_tokens
        if backend is not None and hasattr(backend, "get_capabilities"):
            return list(backend.get_capabilities().forbidden_tokens)
        return list(self._MINIMAL_FORBIDDEN)

    # ── Private checks ────────────────────────────────────────────────────

    def _check_forbidden_tokens(
        self, src: str, tokens: list[ForbiddenToken]
    ) -> list[Fault]:
        faults: list[Fault] = []
        for token in tokens:
            found = bool(re.search(token.pattern, src, re.IGNORECASE)) if token.is_regex else token.pattern in src
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

    def _check_pii_references(self, src: str, signature: StateSignature) -> list[Fault]:
        faults: list[Fault] = []
        if not signature.constraints.no_pii_raw:
            return faults

        for ds in signature.datasets:
            for col in ds.pii_columns:
                pattern = rf'F\.col\(\s*"{re.escape(col)}"\s*\)'
                matches = list(re.finditer(pattern, src))
                for match in matches:
                    context_start = max(0, match.start() - 50)
                    context = src[context_start:match.end() + 30]
                    if "sha2(" in context or ".drop(" in context:
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

    def _check_required_patterns(self, src: str, signature: StateSignature, *, language: str = "") -> list[Fault]:
        faults: list[Fault] = []
        is_sql = language == "sql"

        # Partition filter
        if signature.constraints.partition_by:
            has_filter = (
                ".filter(" in src or ".where(" in src
                or (is_sql and bool(re.search(r"\bWHERE\b", src, re.IGNORECASE)))
            )
            if not has_filter:
                faults.append(Fault(
                    code="STATIC_MISSING_PARTITION_FILTER",
                    family=FaultFamily.STATIC,
                    severity=FaultSeverity.HIGH,
                    stage="static_validation",
                    message="Partition filter required but not found in code.",
                    mandatory_action=PolicyAction.BLOCK,
                    remediation=("Add a filter/WHERE clause on the temporal column.",),
                ))

        # Merge operation for Silver/Gold
        if signature.writes_to_protected_layer and signature.constraints.merge_key_required:
            has_merge = (
                "merge(" in src.lower()
                or "mergebuilder" in src.lower()
                or "DeltaTable" in src
                or (is_sql and bool(re.search(r"\bMERGE\s+INTO\b", src, re.IGNORECASE)))
            )
            if not has_merge:
                faults.append(Fault(
                    code="STATIC_MISSING_MERGE_OPERATION",
                    family=FaultFamily.STATIC,
                    severity=FaultSeverity.HIGH,
                    stage="static_validation",
                    message="Merge operation required for Silver/Gold write but not found.",
                    mandatory_action=PolicyAction.BLOCK,
                    remediation=("Use MERGE INTO or DeltaTable.merge() instead of append.",),
                ))

        return faults

    def _check_schema_contract(self, src: str, contract: dict[str, Any]) -> list[Fault]:
        faults: list[Fault] = []
        forbidden_cols = contract.get("forbidden_columns", [])
        for col in forbidden_cols:
            if re.search(rf'\b{re.escape(col)}\b', src):
                faults.append(Fault(
                    code=f"STATIC_FORBIDDEN_COLUMN_{col.upper()}",
                    family=FaultFamily.STATIC,
                    severity=FaultSeverity.CRITICAL,
                    stage="static_validation",
                    message=f"Forbidden column '{col}' detected in output.",
                    mandatory_action=PolicyAction.BLOCK,
                ))
        return faults
