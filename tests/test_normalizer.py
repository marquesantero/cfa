"""Tests for CFA Intent Normalizer and Confirmation Orchestrator."""

from cfa.normalizer import (
    AutoApproveHandler,
    AutoRejectHandler,
    ConfirmationOrchestrator,
    IntentNormalizer,
    MockNormalizerBackend,
)
from cfa.types import (
    AmbiguityLevel,
    ConfirmationMode,
    SemanticResolution,
    TargetLayer,
)
from conftest import CATALOG, make_signature


class TestMockBackend:
    def test_detects_silver_layer(self):
        normalizer = IntentNormalizer(backend=MockNormalizerBackend())
        res = normalizer.normalize(
            "Junte nfe com clientes e salve na Silver",
            environment_state={"datasets": {}},
            catalog=CATALOG,
        )
        assert res.signature.target_layer == TargetLayer.SILVER

    def test_detects_bronze_layer(self):
        normalizer = IntentNormalizer(backend=MockNormalizerBackend())
        res = normalizer.normalize(
            "Carregar produtos na Bronze",
            environment_state={"datasets": {}},
            catalog=CATALOG,
        )
        assert res.signature.target_layer == TargetLayer.BRONZE

    def test_detects_gold_layer(self):
        normalizer = IntentNormalizer(backend=MockNormalizerBackend())
        res = normalizer.normalize(
            "Publicar dados finais na Gold",
            environment_state={"datasets": {}},
            catalog=CATALOG,
        )
        assert res.signature.target_layer == TargetLayer.GOLD

    def test_detects_datasets_from_catalog(self):
        normalizer = IntentNormalizer(backend=MockNormalizerBackend())
        res = normalizer.normalize(
            "Junte nfe com clientes na Silver",
            environment_state={"datasets": {}},
            catalog=CATALOG,
        )
        dataset_names = {d.name for d in res.signature.datasets}
        assert "nfe" in dataset_names
        assert "clientes" in dataset_names

    def test_detects_pii(self):
        normalizer = IntentNormalizer(backend=MockNormalizerBackend())
        res = normalizer.normalize(
            "Processar clientes na Silver",
            environment_state={"datasets": {}},
            catalog=CATALOG,
        )
        assert res.signature.contains_pii

    def test_low_confidence_without_catalog_match(self):
        normalizer = IntentNormalizer(backend=MockNormalizerBackend())
        res = normalizer.normalize(
            "Fazer algo generico",
            environment_state={"datasets": {}},
            catalog=CATALOG,
        )
        assert res.confidence_score < 0.50

    def test_injects_environment_constraints(self):
        normalizer = IntentNormalizer(backend=MockNormalizerBackend())
        env = {
            "datasets": {
                "silver_docs": {"state": "partially_committed", "publish_allowed": False}
            }
        }
        res = normalizer.normalize(
            "Processar nfe na Silver",
            environment_state=env,
            catalog=CATALOG,
        )
        assert len(res.environment_constraints_injected) > 0

    def test_detects_fiscal_domain(self):
        normalizer = IntentNormalizer(backend=MockNormalizerBackend())
        res = normalizer.normalize(
            "Processar nfe fiscal na Silver",
            environment_state={"datasets": {}},
            catalog=CATALOG,
        )
        assert res.signature.domain == "fiscal_data_processing"


class TestConfirmationOrchestrator:
    def test_auto_passes_through(self):
        orch = ConfirmationOrchestrator()
        sig = make_signature(target_layer=TargetLayer.BRONZE)
        res = SemanticResolution(
            signature=sig, confidence_score=0.92, ambiguity_level=AmbiguityLevel.LOW,
        )
        approved, reason, fault = orch.process(res)
        assert approved
        assert fault is None

    def test_soft_passes_through(self):
        orch = ConfirmationOrchestrator()
        sig = make_signature(target_layer=TargetLayer.BRONZE)
        res = SemanticResolution(
            signature=sig, confidence_score=0.75, ambiguity_level=AmbiguityLevel.LOW,
        )
        approved, _, fault = orch.process(res)
        assert approved
        assert fault is None

    def test_hard_approved(self):
        orch = ConfirmationOrchestrator(handler=AutoApproveHandler())
        sig = make_signature(target_layer=TargetLayer.SILVER, include_pii=True)
        res = SemanticResolution(
            signature=sig, confidence_score=0.90, ambiguity_level=AmbiguityLevel.LOW,
            confirmation_mode=ConfirmationMode.HARD,
        )
        approved, _, fault = orch.process(res)
        assert approved
        assert fault is None

    def test_hard_rejected(self):
        orch = ConfirmationOrchestrator(handler=AutoRejectHandler())
        sig = make_signature(target_layer=TargetLayer.SILVER, include_pii=True)
        res = SemanticResolution(
            signature=sig, confidence_score=0.90, ambiguity_level=AmbiguityLevel.LOW,
            confirmation_mode=ConfirmationMode.HARD,
        )
        approved, _, fault = orch.process(res)
        assert not approved
        assert fault is not None
        assert "REJECTED" in fault.code

    def test_human_escalation_approved(self):
        orch = ConfirmationOrchestrator(handler=AutoApproveHandler())
        sig = make_signature(target_layer=TargetLayer.GOLD)
        res = SemanticResolution(
            signature=sig, confidence_score=0.55, ambiguity_level=AmbiguityLevel.HIGH,
            confirmation_mode=ConfirmationMode.HUMAN_ESCALATION,
        )
        approved, _, fault = orch.process(res)
        assert approved

    def test_human_escalation_rejected(self):
        orch = ConfirmationOrchestrator(handler=AutoRejectHandler())
        sig = make_signature(target_layer=TargetLayer.GOLD)
        res = SemanticResolution(
            signature=sig, confidence_score=0.55, ambiguity_level=AmbiguityLevel.HIGH,
            confirmation_mode=ConfirmationMode.HUMAN_ESCALATION,
        )
        approved, _, fault = orch.process(res)
        assert not approved
        assert fault is not None
        assert fault.code == "CONFIRMATION_HUMAN_ESCALATION_REJECTED"
