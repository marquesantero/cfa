"""CFA Execution — partial execution and state projection."""
from cfa._lazy import LazyLoader

__getattr__ = LazyLoader({
    "PartialExecutionManager": ("cfa.execution.partial", "PartialExecutionManager"),
    "PartialExecutionState": ("cfa.execution.partial", "PartialExecutionState"),
    "PublishState": ("cfa.execution.partial", "PublishState"),
    "FailurePolicy": ("cfa.execution.partial", "FailurePolicy"),
    "RetryPolicy": ("cfa.execution.partial", "RetryPolicy"),
    "StateProjectionProtocol": ("cfa.execution.state_projection", "StateProjectionProtocol"),
    "ProjectionResult": ("cfa.execution.state_projection", "ProjectionResult"),
})
