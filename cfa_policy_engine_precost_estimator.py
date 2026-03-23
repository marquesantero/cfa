
"""
CFA v2.2 - Policy Engine + Pre-cost Estimator
MVP prático para validar uma intenção/plano antes da execução.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Literal
import hashlib
import json

Decision = Literal["approve", "replan", "block"]
Layer = Literal["bronze", "silver", "gold"]


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class DatasetMetadata:
    name: str
    size_gb: float
    layer: Layer
    classification: str = "standard"
    pii_columns: List[str] = field(default_factory=list)
    partition_columns: List[str] = field(default_factory=list)
    primary_key: Optional[str] = None
    avg_daily_increment_gb: Optional[float] = None


@dataclass(frozen=True)
class JoinSpec:
    left: str
    right: str
    join_type: str
    condition: str
    broadcast_hint: bool = False


@dataclass(frozen=True)
class OutputSpec:
    target_table: str
    target_layer: Layer
    write_mode: str
    merge_key: Optional[str] = None
    publish_requested: bool = False


@dataclass(frozen=True)
class PlanInput:
    intent_text: str
    datasets: List[str]
    selected_columns: Dict[str, List[str]]
    filters: Dict[str, List[str]]
    joins: List[JoinSpec]
    output: OutputSpec
    domain: str = "general"
    execution_mode: str = "batch"
    signature_hash: Optional[str] = None

    def resolved_signature_hash(self) -> str:
        if self.signature_hash:
            return self.signature_hash
        payload = {
            "intent_text": self.intent_text,
            "datasets": self.datasets,
            "selected_columns": self.selected_columns,
            "filters": self.filters,
            "joins": [asdict(j) for j in self.joins],
            "output": asdict(self.output),
            "domain": self.domain,
            "execution_mode": self.execution_mode,
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:16]


@dataclass
class CostEstimate:
    estimated_scan_gb: float
    estimated_shuffle_gb: float
    estimated_dbu: float
    risk_score: float


@dataclass
class RuleViolation:
    code: str
    category: str
    severity: Severity
    message: str
    suggestion: Optional[str] = None


@dataclass
class EvaluationResult:
    decision: Decision
    signature_hash: str
    cost_estimate: CostEstimate
    violations: List[RuleViolation]
    suggestions: List[str]
    rationale: str


class MetadataCatalog:
    def __init__(self, items: Dict[str, DatasetMetadata]):
        self._items = items

    def get(self, name: str) -> DatasetMetadata:
        if name not in self._items:
            raise KeyError(f"Dataset '{name}' não encontrado no catálogo.")
        return self._items[name]


class HistoricalMetricsStore:
    def __init__(self, metrics: Optional[Dict[str, Dict[str, float]]] = None):
        self._metrics = metrics or {}

    def get(self, signature_hash: str) -> Optional[Dict[str, float]]:
        return self._metrics.get(signature_hash)


class PreCostEstimator:
    def __init__(self, catalog: MetadataCatalog, history: HistoricalMetricsStore):
        self.catalog = catalog
        self.history = history

    def estimate(self, plan: PlanInput) -> CostEstimate:
        signature_hash = plan.resolved_signature_hash()
        historical = self.history.get(signature_hash)
        if historical:
            return CostEstimate(
                estimated_scan_gb=historical.get("scan_gb", 0.0),
                estimated_shuffle_gb=historical.get("shuffle_gb", 0.0),
                estimated_dbu=historical.get("dbu", 0.0),
                risk_score=historical.get("risk_score", 0.0),
            )

        scan_gb = 0.0
        for ds_name in plan.datasets:
            md = self.catalog.get(ds_name)
            reduction_factor = self._infer_filter_reduction(md, plan.filters.get(ds_name, []))
            scan_gb += md.size_gb * reduction_factor

        shuffle_gb = 0.0
        for join in plan.joins:
            left = self.catalog.get(join.left)
            right = self.catalog.get(join.right)
            left_size = left.size_gb * self._infer_filter_reduction(left, plan.filters.get(join.left, []))
            right_size = right.size_gb * self._infer_filter_reduction(right, plan.filters.get(join.right, []))
            smaller = min(left_size, right_size)
            larger = max(left_size, right_size)
            if join.broadcast_hint or smaller <= 2.0:
                shuffle_gb += larger * 0.15
            else:
                shuffle_gb += (left_size + right_size) * 0.75

        write_penalty = 1.0
        if plan.output.write_mode == "merge":
            write_penalty = 1.35
        elif plan.output.write_mode == "overwrite":
            write_penalty = 1.15

        estimated_dbu = round((scan_gb * 0.18 + shuffle_gb * 0.22) * write_penalty, 2)

        risk = 0.0
        risk += min(scan_gb / 10.0, 30.0)
        risk += min(shuffle_gb / 5.0, 40.0)
        if any(self.catalog.get(ds).classification == "sensitive" for ds in plan.datasets):
            risk += 10.0
        if any(self.catalog.get(ds).classification == "high_volume" for ds in plan.datasets):
            risk += 10.0
        if plan.output.write_mode == "overwrite" and plan.output.target_layer in {"silver", "gold"}:
            risk += 15.0
        risk_score = min(round(risk, 1), 100.0)

        return CostEstimate(
            estimated_scan_gb=round(scan_gb, 2),
            estimated_shuffle_gb=round(shuffle_gb, 2),
            estimated_dbu=estimated_dbu,
            risk_score=risk_score,
        )

    @staticmethod
    def _infer_filter_reduction(md: DatasetMetadata, filters: List[str]) -> float:
        if not filters:
            return 1.0
        filters_lower = " ".join(filters).lower()
        has_partition_filter = any(col.lower() in filters_lower for col in md.partition_columns)
        if has_partition_filter:
            return 0.08 if md.classification == "high_volume" else 0.18
        return 0.45


class PolicyEngine:
    def __init__(self, catalog: MetadataCatalog):
        self.catalog = catalog

    def evaluate(self, plan: PlanInput, cost: CostEstimate) -> List[RuleViolation]:
        violations: List[RuleViolation] = []

        if plan.output.target_layer in {"silver", "gold"} and plan.output.write_mode == "append":
            violations.append(
                RuleViolation(
                    code="CONTRACT_APPEND_ON_CURATED_LAYER",
                    category="contract",
                    severity=Severity.CRITICAL,
                    message="Append direto em camada curada pode gerar duplicidade e quebra de contrato.",
                    suggestion="Trocar para merge com merge_key definida.",
                )
            )

        if plan.output.write_mode == "merge" and not plan.output.merge_key:
            violations.append(
                RuleViolation(
                    code="CONTRACT_MISSING_MERGE_KEY",
                    category="contract",
                    severity=Severity.CRITICAL,
                    message="Merge solicitado sem merge_key.",
                    suggestion="Declarar merge_key compatível com a chave de negócio.",
                )
            )

        if plan.output.target_layer == "gold" and plan.output.write_mode == "overwrite":
            violations.append(
                RuleViolation(
                    code="CONTRACT_OVERWRITE_GOLD",
                    category="contract",
                    severity=Severity.HIGH,
                    message="Overwrite em Gold é operação de alto risco.",
                    suggestion="Preferir merge incremental ou overwrite por partição controlada.",
                )
            )

        for ds_name, cols in plan.selected_columns.items():
            md = self.catalog.get(ds_name)
            selected_lower = {c.lower() for c in cols}
            pii_selected = [c for c in md.pii_columns if c.lower() in selected_lower]
            if pii_selected and plan.output.target_layer in {"silver", "gold"}:
                violations.append(
                    RuleViolation(
                        code="GOVERNANCE_RAW_PII_EXPOSED",
                        category="governance",
                        severity=Severity.CRITICAL,
                        message=f"Colunas sensíveis selecionadas sem tratamento explícito: {', '.join(pii_selected)}.",
                        suggestion="Aplicar hash/drop antes da escrita em Silver/Gold.",
                    )
                )

        for ds_name in plan.datasets:
            md = self.catalog.get(ds_name)
            has_filters = bool(plan.filters.get(ds_name, []))
            has_partition_filter = any(
                pcol.lower() in " ".join(plan.filters.get(ds_name, [])).lower()
                for pcol in md.partition_columns
            )
            if md.classification == "high_volume" and not has_partition_filter:
                violations.append(
                    RuleViolation(
                        code="FINOPS_MISSING_PARTITION_FILTER",
                        category="finops",
                        severity=Severity.HIGH,
                        message=f"Dataset de alto volume '{ds_name}' sem filtro por partição.",
                        suggestion=f"Adicionar filtro por {md.partition_columns or ['partição adequada']}.",
                    )
                )
            if md.size_gb >= 100 and not has_filters:
                violations.append(
                    RuleViolation(
                        code="FINOPS_UNBOUNDED_SCAN",
                        category="finops",
                        severity=Severity.HIGH,
                        message=f"Scan amplo detectado em dataset grande '{ds_name}'.",
                        suggestion="Restringir o escopo com filtro temporal ou incremental.",
                    )
                )

        for join in plan.joins:
            left = self.catalog.get(join.left)
            right = self.catalog.get(join.right)
            left_size = left.size_gb * PreCostEstimator._infer_filter_reduction(left, plan.filters.get(join.left, []))
            right_size = right.size_gb * PreCostEstimator._infer_filter_reduction(right, plan.filters.get(join.right, []))
            smaller = min(left_size, right_size)
            larger = max(left_size, right_size)
            if larger > 50 and smaller > 5 and not join.broadcast_hint:
                violations.append(
                    RuleViolation(
                        code="FINOPS_HEAVY_JOIN",
                        category="finops",
                        severity=Severity.HIGH,
                        message=f"Join pesado detectado entre '{join.left}' e '{join.right}' com alta chance de shuffle excessivo.",
                        suggestion="Reduzir escopo do join ou aplicar broadcast ao lado menor quando possível.",
                    )
                )

        if cost.estimated_dbu > 40:
            violations.append(
                RuleViolation(
                    code="FINOPS_COST_ABOVE_THRESHOLD",
                    category="finops",
                    severity=Severity.HIGH,
                    message=f"Custo estimado alto: {cost.estimated_dbu} DBUs.",
                    suggestion="Replanejar com predicados mais seletivos ou redução de join scope.",
                )
            )

        return violations


class CFAEvaluator:
    def __init__(self, catalog: MetadataCatalog, history: HistoricalMetricsStore):
        self.catalog = catalog
        self.estimator = PreCostEstimator(catalog=catalog, history=history)
        self.policy_engine = PolicyEngine(catalog=catalog)

    def evaluate(self, plan: PlanInput) -> EvaluationResult:
        signature_hash = plan.resolved_signature_hash()
        cost = self.estimator.estimate(plan)
        violations = self.policy_engine.evaluate(plan, cost)
        decision = self._decide(violations)
        suggestions = self._collect_suggestions(violations)

        if decision == "approve":
            rationale = "Plano aprovado. Nenhuma violação crítica ou de alto risco foi detectada."
        elif decision == "replan":
            rationale = "Plano requer replanejamento por risco de custo, contrato ou governança."
        else:
            rationale = "Plano bloqueado. Há violações críticas incompatíveis com execução segura."

        return EvaluationResult(
            decision=decision,
            signature_hash=signature_hash,
            cost_estimate=cost,
            violations=violations,
            suggestions=suggestions,
            rationale=rationale,
        )

    @staticmethod
    def _decide(violations: List[RuleViolation]) -> Decision:
        if any(v.severity == Severity.CRITICAL for v in violations):
            return "block"
        if any(v.severity == Severity.HIGH for v in violations):
            return "replan"
        return "approve"

    @staticmethod
    def _collect_suggestions(violations: List[RuleViolation]) -> List[str]:
        seen = set()
        ordered: List[str] = []
        for v in violations:
            if v.suggestion and v.suggestion not in seen:
                ordered.append(v.suggestion)
                seen.add(v.suggestion)
        return ordered


def result_to_dict(result: EvaluationResult) -> Dict:
    return {
        "decision": result.decision,
        "signature_hash": result.signature_hash,
        "cost_estimate": asdict(result.cost_estimate),
        "violations": [
            {
                "code": v.code,
                "category": v.category,
                "severity": v.severity.value,
                "message": v.message,
                "suggestion": v.suggestion,
            }
            for v in result.violations
        ],
        "suggestions": result.suggestions,
        "rationale": result.rationale,
    }


def pretty_print_result(result: EvaluationResult) -> None:
    print(json.dumps(result_to_dict(result), indent=2, ensure_ascii=False))


def build_demo_catalog() -> MetadataCatalog:
    return MetadataCatalog(
        items={
            "bronze.nfe": DatasetMetadata(
                name="bronze.nfe",
                size_gb=4200.0,
                layer="bronze",
                classification="high_volume",
                pii_columns=["cpf_emitente", "cpf_destinatario"],
                partition_columns=["processing_date"],
                avg_daily_increment_gb=38.0,
            ),
            "silver.clientes": DatasetMetadata(
                name="silver.clientes",
                size_gb=0.5,
                layer="silver",
                classification="sensitive",
                pii_columns=["cpf", "nome", "email"],
                partition_columns=["snapshot_date"],
                primary_key="cliente_id",
            ),
            "silver.documentos_fiscais": DatasetMetadata(
                name="silver.documentos_fiscais",
                size_gb=180.0,
                layer="silver",
                classification="standard",
                partition_columns=["processing_date"],
                primary_key="nfe_id",
            ),
        }
    )


def build_demo_history() -> HistoricalMetricsStore:
    return HistoricalMetricsStore(metrics={})


def demo_bad_plan() -> PlanInput:
    return PlanInput(
        intent_text="Junte NFe com clientes e salve na Silver",
        datasets=["bronze.nfe", "silver.clientes"],
        selected_columns={
            "bronze.nfe": ["nfe_id", "valor_total", "cpf_destinatario", "processing_date"],
            "silver.clientes": ["cpf", "nome", "email"],
        },
        filters={
            "silver.clientes": ["snapshot_date >= '2026-01-01'"],
        },
        joins=[
            JoinSpec(
                left="bronze.nfe",
                right="silver.clientes",
                join_type="left",
                condition="bronze.nfe.cpf_destinatario = silver.clientes.cpf",
                broadcast_hint=False,
            )
        ],
        output=OutputSpec(
            target_table="silver.documentos_fiscais",
            target_layer="silver",
            write_mode="append",
            merge_key=None,
            publish_requested=True,
        ),
        domain="fiscal",
    )


def demo_better_plan() -> PlanInput:
    return PlanInput(
        intent_text="Enriquecer NFe recentes com cliente anonimizado e persistir na Silver",
        datasets=["bronze.nfe", "silver.clientes"],
        selected_columns={
            "bronze.nfe": ["nfe_id", "valor_total", "cpf_destinatario", "processing_date"],
            "silver.clientes": ["cpf"],
        },
        filters={
            "bronze.nfe": ["processing_date >= '2026-01-01'"],
            "silver.clientes": ["snapshot_date >= '2026-01-01'"],
        },
        joins=[
            JoinSpec(
                left="bronze.nfe",
                right="silver.clientes",
                join_type="left",
                condition="hash(bronze.nfe.cpf_destinatario) = hash(silver.clientes.cpf)",
                broadcast_hint=True,
            )
        ],
        output=OutputSpec(
            target_table="silver.documentos_fiscais",
            target_layer="silver",
            write_mode="merge",
            merge_key="nfe_id",
            publish_requested=True,
        ),
        domain="fiscal",
    )


if __name__ == "__main__":
    catalog = build_demo_catalog()
    history = build_demo_history()
    evaluator = CFAEvaluator(catalog=catalog, history=history)

    print("=" * 80)
    print("PLANO RUIM")
    print("=" * 80)
    pretty_print_result(evaluator.evaluate(demo_bad_plan()))

    print("\n" + "=" * 80)
    print("PLANO MELHORADO")
    print("=" * 80)
    pretty_print_result(evaluator.evaluate(demo_better_plan()))
