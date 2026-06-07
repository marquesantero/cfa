"""
CFA Runtime Gate — example usage
=================================
Demonstrates the production governance gate for live pipelines.

Compare with examples/full_pipeline.py which uses the KernelOrchestrator
directly (the "manual" approach). The runtime gate wraps the kernel with
production-grade defaults and ergonomic APIs.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cfa.runtime import RuntimeGate, GateConfig


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


def main():
    # Production gate with blocking violations
    gate = RuntimeGate(
        config=GateConfig(
            policy_bundle="prod_v1.0",
            on_violation="block",
            warnings_are_blocking=True,
        ),
        catalog=CATALOG,
    )

    print(f"Gate ID: {gate.gate_id}")

    # Pre-execution validation
    print("\n1. Validating safe intent...")
    result = gate.validate("Join NFe with Clientes and persist to Silver")
    print(f"   Passed: {result.passed}")
    print(f"   State:  {result.state.value}")

    # Intent that will be blocked (PII without protection)
    print("\n2. Validating unsafe intent...")
    try:
        gate.validate("Write raw CPF data to Gold without PII treatment")
    except Exception as e:
        print(f"   Blocked: {e}")

    # Warnings-are-blocking with sensitive data
    print("\n3. Validating with warnings-as-blocking...")
    result = gate.validate("Join NFe with Clientes and persist to Silver")
    print(f"   State:  {result.state.value}")
    print(f"   Hash:   {result.signature_hash}")

    # Scoped execution
    print("\n4. Scoped execution with metrics...")
    with gate.scope("demo_pipeline"):
        # Simulated pipeline execution
        gate.record_metrics(rows=1_000_000, shuffle_mb=120, cost_dbu=5.0)
        print("   Metrics recorded.")

    # Decorator usage
    print("\n5. Decorator usage...")

    @gate.guard("Join NFe with Clientes and persist to Silver")
    def safe_pipeline():
        print("   Pipeline executed successfully.")

    safe_pipeline()


if __name__ == "__main__":
    main()
