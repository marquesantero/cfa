"""CFA Core — governance engine."""
from cfa._lazy import LazyLoader

__getattr__ = LazyLoader({
    "KernelOrchestrator": ("cfa.core.kernel", "KernelOrchestrator"),
    "KernelConfig": ("cfa.core.kernel", "KernelConfig"),
    "KernelResult": ("cfa.core.kernel", "KernelResult"),
    "PipelinePhase": ("cfa.core.kernel", "PipelinePhase"),
    "ExecutionPlanner": ("cfa.core.planner", "ExecutionPlanner"),
    "ExecutionPlan": ("cfa.core.planner", "ExecutionPlan"),
    "ExecutionStep": ("cfa.core.planner", "ExecutionStep"),
    "StepType": ("cfa.core.planner", "StepType"),
    "WriteMode": ("cfa.core.planner", "WriteMode"),
    "ConsistencyUnit": ("cfa.core.planner", "ConsistencyUnit"),
    "CodeGenBackend": ("cfa.core.codegen", "CodeGenBackend"),
    "GeneratedCode": ("cfa.core.codegen", "GeneratedCode"),
    "build_condition": ("cfa.core.conditions", "build_condition"),
    "list_conditions": ("cfa.core.conditions", "list_conditions"),
    "register_condition": ("cfa.core.conditions", "register_condition"),
    # Plugin contracts (see docs/adr/0007-layered-architecture.md)
    "Vertical": ("cfa.core.vertical", "Vertical"),
    "VerticalRegistry": ("cfa.core.vertical", "VerticalRegistry"),
    "Integration": ("cfa.core.integration", "Integration"),
    "IntegrationRegistry": ("cfa.core.integration", "IntegrationRegistry"),
    "DecisionSink": ("cfa.core.integration", "DecisionSink"),
    "DecisionSinkRegistry": ("cfa.core.integration", "DecisionSinkRegistry"),
    "IntegrationInputError": ("cfa.core.integration", "IntegrationInputError"),
})
