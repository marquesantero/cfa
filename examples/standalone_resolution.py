"""
Standalone resolution example.

Use this when natural-language requests must be converted into a typed
`StateSignature` before any policy or execution decision.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cfa.resolution import (
    IntentNormalizer,
    MockNormalizerBackend,
    NormalizerBackend,
    NormalizerInput,
    NormalizerOutput,
    ConfirmationOrchestrator,
    AutoApproveHandler,
)

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
        },
    }
}

normalizer = IntentNormalizer(backend=MockNormalizerBackend())

resolution = normalizer.normalize(
    raw_intent="Join NFe with Clientes and persist to Silver",
    environment_state={},
    catalog=CATALOG,
)

signature = resolution.signature
print(f"Domain:        {signature.domain}")
print(f"Intent:        {signature.intent}")
print(f"Layer:         {signature.target_layer.value}")
print(f"Datasets:      {[d.name for d in signature.datasets]}")
print(f"Contains PII:  {signature.contains_pii}")
print(f"Confidence:    {resolution.confidence_score:.0%}")
print(f"Confirmation:  {resolution.confirmation_mode.value}")
print(f"Hash:          {signature.signature_hash}")

confirmator = ConfirmationOrchestrator(handler=AutoApproveHandler())
approved, reason, fault = confirmator.process(resolution)
print(f"\nApproved:      {approved}")
print(f"Reason:        {reason}")
print(f"Fault:         {fault.code if fault else 'None'}")


class ExampleLLMBackend(NormalizerBackend):
    """Replace this with your actual LLM integration."""

    def resolve(self, inp: NormalizerInput) -> NormalizerOutput:
        raise NotImplementedError("Implement resolve() with your production LLM")


print("\nExampleLLMBackend is a placeholder for a real semantic backend.")
