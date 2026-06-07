"""
Full kernel example.

Use this when you want the entire governed path from natural-language intent
to execution result.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cfa import KernelOrchestrator

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
result = kernel.process("Join NFe with Clientes and persist to Silver")

print(f"State:  {result.state.value}")
if result.signature:
    print(f"Hash:   {result.signature.signature_hash}")
if result.blocked_reason:
    print(f"Reason: {result.blocked_reason}")
