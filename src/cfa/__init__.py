"""
CFA — Contextual Flux Architecture
===================================
Governed execution for AI agents and data systems.
"""

from cfa._lazy import LazyLoader

__version__ = "0.1.7"

__getattr__ = LazyLoader({
    "KernelOrchestrator": ("cfa.core.kernel", "KernelOrchestrator"),
    "KernelConfig": ("cfa.core.kernel", "KernelConfig"),
    "PipelinePhase": ("cfa.core.kernel", "PipelinePhase"),
    "DecisionState": ("cfa.types", "DecisionState"),
    "StateSignature": ("cfa.types", "StateSignature"),
    "KernelResult": ("cfa.types", "KernelResult"),
    "TargetLayer": ("cfa.types", "TargetLayer"),
    "Fault": ("cfa.types", "Fault"),
    "FaultFamily": ("cfa.types", "FaultFamily"),
    "FaultSeverity": ("cfa.types", "FaultSeverity"),
    "PolicyAction": ("cfa.types", "PolicyAction"),
    "ContextRegistry": ("cfa.audit.context", "ContextRegistry"),
    "JsonFileContextStorage": ("cfa.audit.context", "JsonFileContextStorage"),
    "AuditTrail": ("cfa.audit.trail", "AuditTrail"),
    "JsonLinesAuditStorage": ("cfa.audit.trail", "JsonLinesAuditStorage"),
    "BackendAdapter": ("cfa.backends", "BackendAdapter"),
    "BackendCapabilities": ("cfa.backends", "BackendCapabilities"),
    "BackendRegistry": ("cfa.backends", "BackendRegistry"),
    "PySparkBackend": ("cfa.backends.pyspark", "PySparkBackend"),
    "evaluate": ("cfa.testing.evaluate", "evaluate"),
    "EvaluationResult": ("cfa.testing.evaluate", "EvaluationResult"),
    "BehaviorSpec": ("cfa.behavior.spec", "BehaviorSpec"),
    "BehaviorTaxonomy": ("cfa.behavior.spec", "BehaviorTaxonomy"),
    "Systematizer": ("cfa.behavior.systematizer", "Systematizer"),
    "RuntimeGate": ("cfa.runtime.gate", "RuntimeGate"),
    "GateConfig": ("cfa.runtime.gate", "GateConfig"),
    "GovernanceViolation": ("cfa.runtime.gate", "GovernanceViolation"),
})
