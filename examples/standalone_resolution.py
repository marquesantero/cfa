"""
cfa.resolution -- Uso standalone
==================================
Transforma linguagem natural em intencao tipada.
Requer um backend (LLM ou mock).

Caso de uso:
  Usuarios nao-tecnicos pedem operacoes de dados.
  Voce quer entender O QUE eles querem antes de executar.

  Antes:
    usuario_pede("junta as notas com clientes")
    # ...e agora? qual dataset? qual layer? tem PII?

  Depois:
    resolution = normalizer.normalize("junta as notas com clientes", catalog=CATALOG)
    # resolution.signature tem tudo tipado: domain, layer, datasets, constraints
    # resolution.confidence_score diz se o LLM tem certeza
    # resolution.confirmation_mode diz se precisa aprovacao humana
"""

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

# ── 1. Normalizar com mock (teste) ──────────────────────────────────────────

normalizer = IntentNormalizer(backend=MockNormalizerBackend())

resolution = normalizer.normalize(
    raw_intent="Join NFe com Clientes e persista na Silver",
    environment_state={},
    catalog=CATALOG,
)

sig = resolution.signature
print(f"Domain:      {sig.domain}")
print(f"Intent:      {sig.intent}")
print(f"Layer:       {sig.target_layer.value}")
print(f"Datasets:    {[d.name for d in sig.datasets]}")
print(f"PII:         {sig.contains_pii}")
print(f"Confidence:  {resolution.confidence_score:.0%}")
print(f"Confirmacao: {resolution.confirmation_mode.value}")
print(f"Hash:        {sig.signature_hash}")

# ── 2. Confirmation Orchestrator ─────────────────────────────────────────────

confirmator = ConfirmationOrchestrator(handler=AutoApproveHandler())
approved, reason, fault = confirmator.process(resolution)
print(f"\nAprovado: {approved}")
print(f"Motivo:   {reason}")

# ── 3. Como implementar com LLM real ────────────────────────────────────────

class MeuLLMBackend(NormalizerBackend):
    """
    Substitua pelo seu LLM preferido.
    O metodo resolve() recebe contexto completo e retorna NormalizerOutput.
    """
    def resolve(self, inp: NormalizerInput) -> NormalizerOutput:
        # inp.raw_intent  -> texto do usuario
        # inp.catalog     -> datasets disponiveis
        # inp.environment_state -> estado atual dos dados
        #
        # Chame seu LLM aqui:
        # response = llm.chat(system=PROMPT, user=inp.raw_intent, context=inp.catalog)
        # return NormalizerOutput(**response.parsed)
        raise NotImplementedError("Implemente com seu LLM")

print("\n(MeuLLMBackend precisa de implementacao real)")
