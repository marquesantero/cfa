"""
cfa.lifecycle -- Lifecycle de intencoes
========================================
Indices (IFo, IFs, IFg, IDI) e Promotion/Demotion Engine.
Transforma intencoes repetitivas em skills industrializadas.

Uso:
    from cfa.lifecycle import (
        PromotionEngine, PromotionPolicy,
        IndexCalculator, ExecutionRecord,
        SkillState,
    )

    engine = PromotionEngine(policy=PromotionPolicy(min_executions=5))

    # Registrar execucoes
    engine.record_execution(ExecutionRecord(
        signature_hash="abc123",
        timestamp=datetime.now(timezone.utc),
        success=True,
        cost_dbu=5.0,
        duration_seconds=30.0,
    ))

    # Avaliar promocao
    skill, scores = engine.evaluate("abc123")
    print(f"State: {skill.state.value}")
    print(f"IFo={scores.ifo:.2f} IFs={scores.ifs:.2f} IFg={scores.ifg} IDI={scores.idi:.2f}")
"""

from ..indices import ExecutionRecord, IndexCalculator, IndexScores
from ..promotion import (
    PromotionEngine,
    PromotionPolicy,
    SkillGenerationMetadata,
    SkillRecord,
    SkillState,
)

__all__ = [
    # Indices
    "ExecutionRecord",
    "IndexCalculator",
    "IndexScores",
    # Promotion
    "PromotionEngine",
    "PromotionPolicy",
    "SkillGenerationMetadata",
    "SkillRecord",
    "SkillState",
]
