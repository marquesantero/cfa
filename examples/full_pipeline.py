"""
Pipeline completo -- KernelOrchestrator
========================================
Orquestra todos os modulos juntos.
So use isso quando precisar do fluxo inteiro:
  linguagem natural -> governanca -> execucao -> projecao -> lifecycle
"""

from cfa import KernelOrchestrator, KernelConfig

CATALOG = {
    "datasets": {
        "nfe": {
            "classification": "high_volume",
            "size_gb": 4000,
            "pii_columns": [],
            "partition_column": "processing_date",
        },
        "clientes": {
            "classification": "sensitive",
            "size_gb": 0.5,
            "pii_columns": ["cpf", "email"],
            "partition_column": "processing_date",
        },
    }
}

kernel = KernelOrchestrator(catalog=CATALOG)
result = kernel.process("Join NFe com Clientes e persista na Silver")

print(f"Estado: {result.state.value}")
if result.signature:
    print(f"Hash:   {result.signature.signature_hash}")
if result.blocked_reason:
    print(f"Motivo: {result.blocked_reason}")
