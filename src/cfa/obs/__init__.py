"""CFA Observability — metrics, otel, notify, indices, promotion."""
from cfa._lazy import LazyLoader

__getattr__ = LazyLoader({
    "get_metrics_text": ("cfa.obs.metrics", "get_metrics_text"),
    "inc_counter": ("cfa.obs.metrics", "inc_counter"),
    "IndexCalculator": ("cfa.obs.indices", "IndexCalculator"),
    "IndexScores": ("cfa.obs.indices", "IndexScores"),
    "ExecutionRecord": ("cfa.obs.indices", "ExecutionRecord"),
    "PromotionEngine": ("cfa.obs.promotion", "PromotionEngine"),
    "PromotionPolicy": ("cfa.obs.promotion", "PromotionPolicy"),
    "SkillState": ("cfa.obs.promotion", "SkillState"),
    "SkillRecord": ("cfa.obs.promotion", "SkillRecord"),
})
