"""Extending CFA's rule-based normalizer with a Portuguese/NFe vocabulary.

The production default ``RuleBasedNormalizerBackend`` ships with minimal
English-only keyword maps:

- ``DEFAULT_LAYER_KEYWORDS`` covers ``bronze`` / ``silver`` / ``gold`` and a
  small set of generic English synonyms.
- ``DEFAULT_INTENT_KEYWORDS`` covers a small set of generic English verbs
  (``join`` / ``reconcil`` / ``ingest`` / ``load`` / ``aggregat`` / …).
- ``DEFAULT_DOMAIN_KEYWORDS`` is empty — domain detection is
  application-specific.

If your project speaks Portuguese and processes Brazilian fiscal data (NF-e,
NFC-e, SPED, cadastros de clientes/CPF/CNPJ, etc.), pass tailored keyword
maps to the backend constructor. The vocabulary below was the hard-coded
default in CFA 1.0.0; it now lives here as an opt-in extension.

Run::

    python examples/fiscal_pt_br_normalizer.py
"""

from __future__ import annotations

import json

from cfa.resolve import IntentNormalizer, RuleBasedNormalizerBackend
from cfa.types import TargetLayer


# ─── Portuguese (Brazilian) fiscal vocabulary ─────────────────────────────────

# Medallion layer synonyms common in Brazilian data engineering teams.
PT_BR_LAYER_KEYWORDS: dict[TargetLayer, list[str]] = {
    TargetLayer.GOLD: ["gold", "ouro", "master", "curated", "final"],
    TargetLayer.SILVER: ["silver", "prata", "refined", "trusted", "join", "reconcil"],
    TargetLayer.BRONZE: ["bronze", "raw", "ingest", "landing"],
}

# Generic verbs in EN + PT (carregar = load/ingest).
PT_BR_INTENT_KEYWORDS: dict[str, list[str]] = {
    "reconciliation_and_persist": ["join", "reconcil", "merg"],
    "ingest": ["ingest", "load", "import", "carregar"],
    "aggregate_and_persist": ["aggregat", "summ", "group"],
    "transform_and_persist": [],
}

# Domain-specific to a Brazilian fiscal/CRM/finance setup.
FISCAL_PT_BR_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "fiscal_data_processing": ["nfe", "nfc-e", "nota fiscal", "fiscal", "tribut", "sped"],
    "customer_data": ["client", "customer", "cpf", "cnpj", "cadastro"],
    "financial_data": ["payment", "transac", "financ", "pagamento", "contas a pagar"],
}


# ─── Example: configure a backend with the vocabulary above ────────────────────

CATALOG = {
    "datasets": {
        "nfe": {
            "classification": "high_volume",
            "size_gb": 4000,
            "pii_columns": [],
            "partition_column": "processing_date",
            "merge_keys": ["nfe_id"],
        },
        "clientes": {
            "classification": "sensitive",
            "size_gb": 0.5,
            "pii_columns": ["cpf", "email"],
            "partition_column": "processing_date",
            "merge_keys": ["cliente_id"],
        },
    }
}


def build_fiscal_pt_br_backend(*, strict: bool = False) -> RuleBasedNormalizerBackend:
    """Return a normalizer pre-loaded with PT-BR fiscal vocabulary."""
    return RuleBasedNormalizerBackend(
        strict=strict,
        layer_keywords=PT_BR_LAYER_KEYWORDS,
        domain_keywords=FISCAL_PT_BR_DOMAIN_KEYWORDS,
        intent_keywords=PT_BR_INTENT_KEYWORDS,
    )


def main() -> None:
    normalizer = IntentNormalizer(backend=build_fiscal_pt_br_backend())

    intents = [
        "Junte nfe com clientes e salve na Silver",
        "Carregar nfe na Bronze",
        "Agregar pagamentos por cliente na Gold",
        "Processar nota fiscal eletrônica e persistir na Prata",
    ]

    for raw in intents:
        resolution = normalizer.normalize(
            raw_intent=raw,
            environment_state={"datasets": {}},
            catalog=CATALOG,
        )
        print(f"\n>>> {raw}")
        print(
            json.dumps(
                {
                    "domain": resolution.signature.domain,
                    "intent": resolution.signature.intent,
                    "target_layer": resolution.signature.target_layer.value,
                    "datasets": [d.name for d in resolution.signature.datasets],
                    "confidence": resolution.confidence_score,
                },
                indent=2,
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
