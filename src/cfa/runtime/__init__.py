"""CFA Runtime — all imports are lazy to avoid circular dependencies."""
from cfa._lazy import LazyLoader

__all__ = ["RuntimeGate", "GateConfig", "GateResult", "GateViolation", "GovernanceViolation", "runtime_gate"]

__getattr__ = LazyLoader({
    "RuntimeGate": ("cfa.runtime.gate", "RuntimeGate"),
    "GateConfig": ("cfa.runtime.gate", "GateConfig"),
    "GateResult": ("cfa.runtime.gate", "GateResult"),
    "GateViolation": ("cfa.runtime.gate", "GateViolation"),
    "GovernanceViolation": ("cfa.runtime.gate", "GovernanceViolation"),
    "runtime_gate": ("cfa.runtime.gate", "runtime_gate"),
})
