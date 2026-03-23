"""
CFA -- Contextual Flux Architecture v2
=======================================
Biblioteca modular de governanca para sistemas de dados.

3 modulos independentes, cada um usavel sozinho:

    cfa.governance  -- Policy Engine + validacao (sem LLM, sem execucao)
    cfa.resolution  -- Intent Normalizer + Confirmation (requer LLM backend)
    cfa.lifecycle   -- Indices + Promotion/Demotion (requer historico)

Pipeline completo (orquestra tudo):

    from cfa import KernelOrchestrator
    kernel = KernelOrchestrator(catalog=CATALOG)
    result = kernel.process("Join NFe com Clientes e persista na Silver")

Uso modular (so governanca):

    from cfa.governance import PolicyEngine, StaticValidator
    engine = PolicyEngine()
    result = engine.evaluate(signature)
"""

__version__ = "2.0.0"


# Lazy imports -- so carrega quando acessar
def __getattr__(name):
    """Lazy import para evitar carregar tudo na importacao inicial."""
    _lazy = {
        # Pipeline completo
        "KernelOrchestrator": (".kernel", "KernelOrchestrator"),
        "KernelConfig": (".kernel", "KernelConfig"),
        # Types
        "DecisionState": (".types", "DecisionState"),
        "StateSignature": (".types", "StateSignature"),
        "KernelResult": (".types", "KernelResult"),
        "TargetLayer": (".types", "TargetLayer"),
        "Fault": (".types", "Fault"),
        "FaultFamily": (".types", "FaultFamily"),
        "FaultSeverity": (".types", "FaultSeverity"),
        "PolicyAction": (".types", "PolicyAction"),
        # Context + Audit (standalone)
        "ContextRegistry": (".context", "ContextRegistry"),
        "JsonFileContextStorage": (".context", "JsonFileContextStorage"),
        "AuditTrail": (".audit", "AuditTrail"),
        "JsonLinesAuditStorage": (".audit", "JsonLinesAuditStorage"),
    }
    if name in _lazy:
        module_path, attr = _lazy[name]
        import importlib
        module = importlib.import_module(module_path, __package__)
        return getattr(module, attr)
    raise AttributeError(f"module 'cfa' has no attribute {name!r}")
