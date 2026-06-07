"""CFA Observability — metrics, otel, notify, indices, promotion."""
from cfa._lazy import LazyLoader

__getattr__ = LazyLoader({
    "get_metrics_text": ("cfa.observability.metrics", "get_metrics_text"),
    "inc_counter": ("cfa.observability.metrics", "inc_counter"),
    "IndexCalculator": ("cfa.observability.indices", "IndexCalculator"),
    "IndexScores": ("cfa.observability.indices", "IndexScores"),
    "ExecutionRecord": ("cfa.observability.indices", "ExecutionRecord"),
    "PromotionEngine": ("cfa.observability.promotion", "PromotionEngine"),
    "PromotionPolicy": ("cfa.observability.promotion", "PromotionPolicy"),
    "SkillState": ("cfa.observability.promotion", "SkillState"),
    "SkillRecord": ("cfa.observability.promotion", "SkillRecord"),
})
