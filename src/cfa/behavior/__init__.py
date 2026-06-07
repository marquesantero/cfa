"""
CFA Behavior — specification-driven governance
===============================================
Bridge between human-written governance intent and executable policy rules.

Usage:
    from cfa.behavior import BehaviorSpec, Systematizer

    spec = BehaviorSpec.from_yaml("fiscal_governance.yaml")
    taxonomy, rules = Systematizer().systematize(spec)

    from cfa import KernelOrchestrator
    kernel = KernelOrchestrator(policy_rules=rules)
    result = kernel.process("agregar vendas com PII")

    # Generate test intents
    intents = taxonomy.generate_test_intents(5)
"""

from __future__ import annotations

from .spec import (
    BehaviorCategory,
    BehaviorSpec,
    BehaviorTaxonomy,
    ConditionType,
)
from .systematizer import Systematizer

# Optional LLM backend
try:
    from .llm import LLMSystematizer, LLMSystematizerBackend, OpenAISystematizerBackend
    _HAS_LLM = True
except ImportError:
    _HAS_LLM = False
    LLMSystematizerBackend = None  # type: ignore
    OpenAISystematizerBackend = None  # type: ignore
    LLMSystematizer = None  # type: ignore

__all__ = [
    "BehaviorSpec",
    "BehaviorCategory",
    "BehaviorTaxonomy",
    "ConditionType",
    "Systematizer",
    "LLMSystematizerBackend",
    "OpenAISystematizerBackend",
    "LLMSystematizer",
]
