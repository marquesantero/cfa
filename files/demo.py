"""
CFA Kernel — Exemplo Completo
==============================
Demonstra o Kernel em ação com o caso de uso do whitepaper:
NFe + Clientes → Silver

Executa três cenários:
1. Intent aprovado com replan automático (PII + partição)
2. Intent bloqueado (Gold sem confirmação humana)
3. Kernel describe() — estado atual do sistema
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from cfa.core.kernel import KernelOrchestrator, KernelConfig, InMemoryContextRegistry
from cfa.core.normalizer import AutoRejectHandler

# ─── Catálogo de Dados ────────────────────────────────────────────────────────

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
        "silver_documentos": {
            "classification": "internal",
            "size_gb": 0,
        },
    }
}


def print_separator(title: str = ""):
    width = 60
    if title:
        pad = (width - len(title) - 2) // 2
        print(f"\n{'─' * pad} {title} {'─' * pad}")
    else:
        print(f"\n{'─' * width}")


def print_result(result, show_audit=True):
    print(f"  Estado     : {result.state.value}")
    if result.signature:
        print(f"  Sig Hash   : {result.signature.signature_hash}")
        print(f"  Domínio    : {result.signature.domain}")
        print(f"  Intenção   : {result.signature.intent}")
        print(f"  Camada     : {result.signature.target_layer.value}")
        print(f"  Datasets   : {[d.name for d in result.signature.datasets]}")
        print(f"  Partição   : {result.signature.constraints.partition_by}")
        print(f"  PII safe   : {result.signature.constraints.no_pii_raw}")
        print(f"  Executável : {'✓' if result.is_executable else '✗'}")
    if result.blocked_reason:
        print(f"  Bloqueado  : {result.blocked_reason}")
    if result.replan_history:
        print(f"  Replans    : {len(result.replan_history)}")
        for i, rp in enumerate(result.replan_history, 1):
            codes = [f.code for f in rp.faults]
            print(f"    Replan {i}  : faults={codes}")
    if show_audit:
        print(f"\n  Audit Trail ({len(result.audit_events)} eventos):")
        for evt in result.audit_events:
            stage = evt["stage"].replace("_", " ").title()
            outcome = evt["outcome"]
            extras = {k: v for k, v in evt.items()
                      if k not in ("stage", "event_type", "outcome", "timestamp", "intent_id")}
            extras_str = f"  {json.dumps(extras, ensure_ascii=False)}" if extras else ""
            print(f"    [{outcome:>20}]  {stage}{extras_str}")


# ─── Cenário 1: NFe + Clientes → Silver ──────────────────────────────────────

def cenario_1():
    print_separator("Cenário 1: NFe + Clientes → Silver")
    print("\n  Intent: 'Junte NFe com Clientes e salve na Silver'")
    print("  Esperado: APPROVED_WITH_WARNINGS (após replan automático)")
    print("  Faults esperados: FINOPS + GOVERNANCE → corrigidos automaticamente")

    kernel = KernelOrchestrator(catalog=CATALOG)
    result = kernel.process("Junte NFe com Clientes e salve na Silver")
    print()
    print_result(result)


# ─── Cenário 2: Escrita em Gold com reject ────────────────────────────────────

def cenario_2():
    print_separator("Cenário 2: Gold write + Confirmação Humana Rejeitada")
    print("\n  Intent: 'Publicar dados finais na Gold para consumo'")
    print("  Esperado: BLOCKED (AutoRejectHandler recusa o escalamento)")

    kernel = KernelOrchestrator(
        catalog=CATALOG,
        human_handler=AutoRejectHandler(),
    )
    result = kernel.process("Publicar dados finais na Gold para consumo")
    print()
    print_result(result, show_audit=False)

    # Mostrar apenas os eventos relevantes
    print(f"\n  Eventos relevantes:")
    for evt in result.audit_events:
        if evt["outcome"] in ("rejected", "blocked", "error"):
            print(f"    [{evt['stage']}] {evt['outcome']}: "
                  f"{evt.get('reason', evt.get('error', ''))}")


# ─── Cenário 3: Kernel describe ───────────────────────────────────────────────

def cenario_3():
    print_separator("Cenário 3: Estado do Kernel")

    registry = InMemoryContextRegistry()
    kernel = KernelOrchestrator(catalog=CATALOG, context_registry=registry)

    # Processar duas intenções
    kernel.process("Carregar produtos na Bronze")
    kernel.process("Junte NFe com Clientes e salve na Silver")

    desc = kernel.describe()
    print()
    print("  Configuração do Kernel:")
    for k, v in desc["config"].items():
        print(f"    {k}: {v}")
    print(f"  Context Registry version : {desc['context_registry_version']}")
    print(f"  Datasets no catálogo     : {desc['catalog_datasets']}")
    print(f"  Regras de policy ativas  : {desc['policy_rules']}")
    print()
    print("  Histórico de execuções:")
    for entry in registry._state["execution_history"]:
        print(f"    [{entry['outcome']:>28}]  hash={entry['signature_hash']}  "
              f"ts={entry['timestamp'][:19]}")


# ─── Cenário 4: Context Registry com estado parcial ──────────────────────────

def cenario_4():
    print_separator("Cenário 4: Context Registry com estado 'stale'")
    print("\n  Simula dataset silver_documentos em partially_committed")
    print("  Esperado: Normalizer injeta constraint de ambiente na Signature")

    registry = InMemoryContextRegistry()
    registry.set_dataset_state("silver_documentos", {
        "state": "partially_committed",
        "publish_allowed": False,
        "pending_partitions": ["2026-01-03"],
    })

    kernel = KernelOrchestrator(catalog=CATALOG, context_registry=registry)
    result = kernel.process("Junte NFe com Clientes e salve na Silver")

    print()
    if result.resolution:
        injected = result.resolution.environment_constraints_injected
        if injected:
            print(f"  Constraints injetadas do ambiente:")
            for c in injected:
                print(f"    → {c}")
        else:
            print("  Nenhuma constraint de ambiente injetada")
    print_result(result, show_audit=False)


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  CFA Kernel Orchestrator — Demonstração")
    print(f"  Caso de uso: NFe + Clientes pipeline")
    print("=" * 60)

    cenario_1()
    cenario_2()
    cenario_3()
    cenario_4()

    print_separator()
    print("\n  CFA Kernel v1.0 — Fase 1 completa.")
    print("  Próximos passos: Fase 2 (Execution Planner + Code Generator)")
    print()
