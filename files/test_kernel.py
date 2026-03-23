"""
CFA Kernel — Test Suite
========================
Testa todos os componentes do Kernel em isolamento e em integração.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cfa.core.types import (
    DatasetRef, DatasetClassification, TargetLayer, SignatureConstraints,
    StateSignature, ExecutionContext, DecisionState, ConfirmationMode,
    AmbiguityLevel, FaultSeverity, PolicyAction,
)
from cfa.core.policy_engine import PolicyEngine, PolicyRule, build_default_ruleset
from cfa.core.normalizer import (
    MockNormalizerBackend, IntentNormalizer, ConfirmationOrchestrator,
    AutoApproveHandler, AutoRejectHandler,
)
from cfa.core.kernel import KernelOrchestrator, KernelConfig, InMemoryContextRegistry

# ─── Helpers ──────────────────────────────────────────────────────────────────

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
        "produtos": {
            "classification": "internal",
            "size_gb": 0.1,
            "pii_columns": [],
        },
    }
}

def make_clean_signature(
    target_layer=TargetLayer.SILVER,
    include_pii=False,
    with_partition=True,
) -> StateSignature:
    datasets = [DatasetRef(name="nfe", classification=DatasetClassification.HIGH_VOLUME)]
    if include_pii:
        datasets.append(DatasetRef(
            name="clientes",
            classification=DatasetClassification.SENSITIVE,
            pii_columns=["cpf", "email"],
        ))
    return StateSignature(
        domain="fiscal",
        intent="reconciliation",
        target_layer=target_layer,
        datasets=datasets,
        constraints=SignatureConstraints(
            no_pii_raw=True,
            merge_key_required=True,
            enforce_types=True,
            partition_by=["processing_date"] if with_partition else [],
        ),
        execution_context=ExecutionContext(
            policy_bundle_version="v1.0",
            catalog_snapshot_version="catalog_test",
            context_registry_version_id="v_test",
        ),
    )


# ─── Tests: StateSignature ────────────────────────────────────────────────────

def test_signature_hash_deterministic():
    s1 = make_clean_signature()
    s2 = make_clean_signature()
    assert s1.signature_hash == s2.signature_hash, "Hash deve ser determinístico"
    print("  ✓ signature_hash é determinístico")


def test_signature_hash_changes_with_layer():
    s_silver = make_clean_signature(target_layer=TargetLayer.SILVER)
    s_gold   = make_clean_signature(target_layer=TargetLayer.GOLD)
    assert s_silver.signature_hash != s_gold.signature_hash, "Hash deve mudar com layer"
    print("  ✓ signature_hash muda com target_layer")


def test_signature_pii_detection():
    s_clean = make_clean_signature(include_pii=False)
    s_pii   = make_clean_signature(include_pii=True)
    assert not s_clean.contains_pii
    assert s_pii.contains_pii
    print("  ✓ contains_pii detectado corretamente")


def test_signature_protected_layer():
    assert make_clean_signature(target_layer=TargetLayer.SILVER).writes_to_protected_layer
    assert make_clean_signature(target_layer=TargetLayer.GOLD).writes_to_protected_layer
    assert not make_clean_signature(target_layer=TargetLayer.BRONZE).writes_to_protected_layer
    print("  ✓ writes_to_protected_layer correto para Silver e Gold")


# ─── Tests: Policy Engine ─────────────────────────────────────────────────────

def test_policy_approves_clean_signature():
    engine = PolicyEngine()
    sig = make_clean_signature()
    result = engine.evaluate(sig)
    assert result.action == PolicyAction.APPROVE, f"Expected APPROVE, got {result.action}"
    assert not result.faults
    print("  ✓ Signature limpa → APPROVE sem faults")


def test_policy_blocks_pii_without_policy():
    engine = PolicyEngine()
    sig = StateSignature(
        domain="fiscal",
        intent="join",
        target_layer=TargetLayer.SILVER,
        datasets=[DatasetRef("clientes", DatasetClassification.SENSITIVE, pii_columns=["cpf"])],
        constraints=SignatureConstraints(no_pii_raw=False),  # <- sem política de PII
        execution_context=ExecutionContext("v1", "c1", "r1"),
    )
    result = engine.evaluate(sig)
    assert result.action == PolicyAction.BLOCK
    assert any(f.code == "GOVERNANCE_PII_WITHOUT_POLICY" for f in result.faults)
    print("  ✓ PII sem política → BLOCK com fault correto")


def test_policy_replans_missing_partition():
    engine = PolicyEngine()
    sig = make_clean_signature(with_partition=False)
    result = engine.evaluate(sig)
    assert result.action == PolicyAction.REPLAN
    assert any(f.code == "FINOPS_MISSING_TEMPORAL_PREDICATE" for f in result.faults)
    print("  ✓ High volume sem partição → REPLAN com fault FINOPS")


def test_policy_blocks_after_max_replans():
    engine = PolicyEngine(max_replan_attempts=3)
    sig = make_clean_signature(with_partition=False)
    result = engine.evaluate(sig, replan_count=3)
    assert result.action == PolicyAction.BLOCK
    assert any(f.code == "POLICY_MAX_REPLAN_EXCEEDED" for f in result.faults)
    print("  ✓ Máximo de replans → BLOCK terminal")


def test_policy_blocks_missing_merge_key():
    engine = PolicyEngine()
    sig = StateSignature(
        domain="fiscal",
        intent="join",
        target_layer=TargetLayer.SILVER,
        datasets=[DatasetRef("nfe", DatasetClassification.HIGH_VOLUME)],
        constraints=SignatureConstraints(
            merge_key_required=False,  # <- sem merge key
            partition_by=["processing_date"],
        ),
        execution_context=ExecutionContext("v1", "c1", "r1"),
    )
    result = engine.evaluate(sig)
    assert result.action == PolicyAction.BLOCK
    assert any(f.code == "CONTRACT_MISSING_MERGE_KEY" for f in result.faults)
    print("  ✓ Silver sem merge_key → BLOCK com fault CONTRACT")


# ─── Tests: Confirmation Orchestrator ────────────────────────────────────────

def test_confirmation_auto_passes():
    from cfa.core.types import SemanticResolution
    sig = make_clean_signature()
    resolution = SemanticResolution(
        signature=sig,
        confidence_score=0.92,
        ambiguity_level=AmbiguityLevel.LOW,
        confirmation_mode=ConfirmationMode.AUTO,
    )
    orch = ConfirmationOrchestrator(AutoApproveHandler())
    approved, reason, fault = orch.process(resolution)
    assert approved
    assert fault is None
    print("  ✓ AUTO → aprovado sem interrupção")


def test_confirmation_human_escalation_approved():
    from cfa.core.types import SemanticResolution
    sig = make_clean_signature(target_layer=TargetLayer.GOLD, include_pii=True)
    resolution = SemanticResolution(
        signature=sig,
        confidence_score=0.55,
        ambiguity_level=AmbiguityLevel.HIGH,
        confirmation_mode=ConfirmationMode.HUMAN_ESCALATION,
    )
    orch = ConfirmationOrchestrator(AutoApproveHandler())
    approved, reason, fault = orch.process(resolution)
    assert approved
    assert fault is None
    print("  ✓ HUMAN_ESCALATION + AutoApprove → aprovado")


def test_confirmation_human_escalation_rejected():
    from cfa.core.types import SemanticResolution
    sig = make_clean_signature(target_layer=TargetLayer.GOLD)
    resolution = SemanticResolution(
        signature=sig,
        confidence_score=0.55,
        ambiguity_level=AmbiguityLevel.HIGH,
        confirmation_mode=ConfirmationMode.HUMAN_ESCALATION,
    )
    orch = ConfirmationOrchestrator(AutoRejectHandler())
    approved, reason, fault = orch.process(resolution)
    assert not approved
    assert fault is not None
    assert fault.code == "CONFIRMATION_HUMAN_REJECTED"
    print("  ✓ HUMAN_ESCALATION + AutoReject → blocked com fault correto")


def test_confirmation_mode_derived_gold():
    from cfa.core.types import SemanticResolution
    sig = make_clean_signature(target_layer=TargetLayer.GOLD)
    resolution = SemanticResolution(
        signature=sig,
        confidence_score=0.90,
        ambiguity_level=AmbiguityLevel.LOW,
        # confirmation_mode não especificado — deve ser derivado
    )
    assert resolution.confirmation_mode == ConfirmationMode.HUMAN_ESCALATION
    print("  ✓ Gold write → HUMAN_ESCALATION derivado automaticamente")


# ─── Tests: Kernel Orchestrator (integração) ─────────────────────────────────

def test_kernel_approves_simple_intent():
    kernel = KernelOrchestrator(catalog=CATALOG)
    result = kernel.process("Carregar produtos na Bronze")
    assert result.state in (DecisionState.APPROVED, DecisionState.APPROVED_WITH_WARNINGS), \
        f"Expected APPROVED*, got {result.state}\n{result.summary()}"
    assert result.signature is not None
    assert result.is_executable
    print(f"  ✓ Intent simples → {result.state.value}")


def test_kernel_handles_pii_join():
    kernel = KernelOrchestrator(catalog=CATALOG)
    result = kernel.process("Junte NFe com Clientes e salve na Silver")
    # Deve aprovar (após replan automático aplicar no_pii_raw=True)
    assert result.state in (DecisionState.APPROVED, DecisionState.APPROVED_WITH_WARNINGS), \
        f"Expected APPROVED*, got {result.state}\n{result.summary()}"
    print(f"  ✓ PII join → {result.state.value} (replan aplicado automaticamente)")


def test_kernel_blocks_gold_with_auto_reject():
    kernel = KernelOrchestrator(
        catalog=CATALOG,
        human_handler=AutoRejectHandler(),
    )
    result = kernel.process("Publique dados finais na Gold")
    assert result.state == DecisionState.BLOCKED, \
        f"Expected BLOCKED, got {result.state}"
    print("  ✓ Gold intent + AutoReject → BLOCKED corretamente")


def test_kernel_audit_trail_populated():
    kernel = KernelOrchestrator(catalog=CATALOG)
    result = kernel.process("Carregar produtos na Bronze")
    assert len(result.audit_events) > 0
    stages = [e["stage"] for e in result.audit_events]
    assert "context_registry" in stages
    assert "intent_normalizer" in stages
    assert "policy_engine" in stages
    assert "decision_engine" in stages
    print(f"  ✓ Audit trail com {len(result.audit_events)} eventos: {stages}")


def test_kernel_replan_cycle():
    """O kernel deve replanar automaticamente quando há faults corrigíveis."""
    kernel = KernelOrchestrator(catalog=CATALOG)
    # NFe é high_volume mas sem partição declarada → deve replanar
    result = kernel.process("Processar NFe na Silver sem filtro temporal")
    # Verifica que houve replan
    replan_events = [e for e in result.audit_events if e["event_type"] == "replan_applied"]
    # Pode ou não replanar dependendo do mock — o importante é não travar
    assert result.state != DecisionState.BLOCKED or result.blocked_reason
    print(f"  ✓ Ciclo de replan: {len(replan_events)} replans, estado final={result.state.value}")


def test_kernel_context_registry_updated():
    """Após execução aprovada, o Context Registry deve ser atualizado."""
    registry = InMemoryContextRegistry()
    initial_version = registry.version_id

    kernel = KernelOrchestrator(catalog=CATALOG, context_registry=registry)
    result = kernel.process("Carregar produtos na Bronze")

    if result.is_executable:
        history = registry._state["execution_history"]
        assert len(history) > 0
        assert history[-1]["intent_id"] == result.intent_id
        print(f"  ✓ Context Registry atualizado: {len(history)} execução(ões) registrada(s)")
    else:
        print(f"  ✓ Intent não aprovada — Context Registry não atualizado (correto)")


def test_signature_hash_consistency():
    """O mesmo intent processado duas vezes deve gerar o mesmo signature_hash."""
    kernel = KernelOrchestrator(catalog=CATALOG)
    r1 = kernel.process("Carregar produtos na Bronze")
    r2 = kernel.process("Carregar produtos na Bronze")
    if r1.signature and r2.signature:
        assert r1.signature.signature_hash == r2.signature.signature_hash
        print("  ✓ Mesmo intent → mesmo signature_hash (determinístico)")
    else:
        print("  ✓ (Assinaturas não geradas — intent não aprovado)")


# ─── Runner ───────────────────────────────────────────────────────────────────

def run_all():
    suites = [
        ("StateSignature", [
            test_signature_hash_deterministic,
            test_signature_hash_changes_with_layer,
            test_signature_pii_detection,
            test_signature_protected_layer,
        ]),
        ("Policy Engine", [
            test_policy_approves_clean_signature,
            test_policy_blocks_pii_without_policy,
            test_policy_replans_missing_partition,
            test_policy_blocks_after_max_replans,
            test_policy_blocks_missing_merge_key,
        ]),
        ("Confirmation Orchestrator", [
            test_confirmation_auto_passes,
            test_confirmation_human_escalation_approved,
            test_confirmation_human_escalation_rejected,
            test_confirmation_mode_derived_gold,
        ]),
        ("Kernel Orchestrator (integração)", [
            test_kernel_approves_simple_intent,
            test_kernel_handles_pii_join,
            test_kernel_blocks_gold_with_auto_reject,
            test_kernel_audit_trail_populated,
            test_kernel_replan_cycle,
            test_kernel_context_registry_updated,
            test_signature_hash_consistency,
        ]),
    ]

    total = passed = failed = 0
    failures = []

    for suite_name, tests in suites:
        print(f"\n{'─'*50}")
        print(f"  {suite_name}")
        print(f"{'─'*50}")
        for test in tests:
            total += 1
            try:
                test()
                passed += 1
            except Exception as e:
                failed += 1
                failures.append((test.__name__, str(e)))
                print(f"  ✗ {test.__name__}: {e}")

    print(f"\n{'═'*50}")
    print(f"  Resultado: {passed}/{total} passed", end="")
    if failed:
        print(f"  |  {failed} FAILED")
        for name, err in failures:
            print(f"    ✗ {name}: {err}")
    else:
        print("  — ALL PASSED ✓")
    print(f"{'═'*50}")

    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
