# NOTE: This module is internal to CFA — not part of the public API. Use at your own risk.
"""
CFA Code Generator
==================
Generates deterministic, governed code from an ExecutionPlan.

The code generator is NOT creative — it fills templates governed by the plan.

Key properties:
- Output is deterministic (same plan = same code)
- All PII handling is explicit (sha256/drop)
- Partition filters are always present when required
- Write operations use merge (never raw append in Silver/Gold)

Backend-specific implementations live in cfa.backends.*.
This module provides the core ABC, the GeneratedCode artifact,
and backward-compatible re-exports.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from cfa.core.planner import ExecutionPlan

# ── Generated Code ───────────────────────────────────────────────────────────


@dataclass
class GeneratedCode:
    """Complete code artifact generated from an execution plan."""

    plan_signature_hash: str
    intent_id: str
    language: str
    code: str
    step_code_map: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def line_count(self) -> int:
        return len(self.code.strip().splitlines())


# ── Code Generator Backend ───────────────────────────────────────────────────


class CodeGenBackend(ABC):
    """Extension point: different code generation targets."""

    @abstractmethod
    def generate(self, plan: ExecutionPlan) -> GeneratedCode: ...


# ── Backward-compatible re-exports ───────────────────────────────────────────
# PySparkGenerator now lives in cfa.backends.pyspark as PySparkBackend.
# Lazy import to avoid circular dependency with backends.__init__.


def __getattr__(name):
    if name == "PySparkGenerator":
        from cfa.backends.pyspark import PySparkBackend
        return PySparkBackend
    raise AttributeError(f"module 'cfa.core.codegen' has no attribute {name!r}")
