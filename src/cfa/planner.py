"""
CFA Execution Planner
=====================
Generates a governed execution DAG from an approved State Signature.

The Planner is NOT free — it fills templates, follows the plan approved
by the Policy Engine, and respects all constraints declared in the Signature.

Key properties:
- Every plan is idempotent (merge with deterministic key, partition overwrite)
- Supports Composite Intent decomposition
- Consistency unit selection follows whitepaper enum (partition | dataset | dag_branch | time_window)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .types import DatasetClassification, DatasetRef, StateSignature, TargetLayer


# ── Consistency Unit ─────────────────────────────────────────────────────────


class ConsistencyUnit(str, Enum):
    PARTITION = "partition"
    DATASET = "dataset"
    DAG_BRANCH = "dag_branch"
    TIME_WINDOW = "time_window"


# ── Execution Steps ──────────────────────────────────────────────────────────


class StepType(str, Enum):
    EXTRACT = "extract"
    ANONYMIZE = "anonymize"
    JOIN = "join"
    TRANSFORM = "transform"
    LOAD = "load"
    FILTER = "filter"
    AGGREGATE = "aggregate"


@dataclass(frozen=True)
class ExecutionStep:
    """Single node in the execution DAG."""

    id: str
    step_type: StepType
    source: str | None = None
    target: str | None = None
    config: dict[str, Any] = field(default_factory=dict)
    depends_on: tuple[str, ...] = ()

    @property
    def description(self) -> str:
        parts = [f"{self.step_type.value}"]
        if self.source:
            parts.append(f"source={self.source}")
        if self.target:
            parts.append(f"target={self.target}")
        return " | ".join(parts)


# ── Execution Plan ───────────────────────────────────────────────────────────


class WriteMode(str, Enum):
    MERGE = "merge"
    OVERWRITE_PARTITION = "overwrite_partition"
    APPEND = "append"  # only allowed in Bronze


@dataclass
class ExecutionPlan:
    """
    Governed execution DAG generated from an approved Signature.
    Immutable once finalized — any change requires a new plan.
    """

    signature_hash: str
    intent_id: str
    steps: list[ExecutionStep]
    consistency_unit: ConsistencyUnit
    write_mode: WriteMode
    idempotent: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def step_ids(self) -> list[str]:
        return [s.id for s in self.steps]

    @property
    def step_count(self) -> int:
        return len(self.steps)

    def get_step(self, step_id: str) -> ExecutionStep | None:
        return next((s for s in self.steps if s.id == step_id), None)

    def execution_order(self) -> list[ExecutionStep]:
        """Topological sort of steps respecting depends_on."""
        resolved: list[ExecutionStep] = []
        resolved_ids: set[str] = set()
        pending = list(self.steps)

        max_iterations = len(pending) * len(pending)
        iteration = 0
        while pending:
            iteration += 1
            if iteration > max_iterations:
                raise ValueError("Cyclic dependency detected in execution plan")

            for step in list(pending):
                if all(dep in resolved_ids for dep in step.depends_on):
                    resolved.append(step)
                    resolved_ids.add(step.id)
                    pending.remove(step)

        return resolved

    def to_dict(self) -> dict[str, Any]:
        return {
            "signature_hash": self.signature_hash,
            "intent_id": self.intent_id,
            "consistency_unit": self.consistency_unit.value,
            "write_mode": self.write_mode.value,
            "idempotent": self.idempotent,
            "steps": [
                {
                    "id": s.id,
                    "type": s.step_type.value,
                    "source": s.source,
                    "target": s.target,
                    "config": s.config,
                    "depends_on": list(s.depends_on),
                }
                for s in self.steps
            ],
        }


# ── Execution Planner ────────────────────────────────────────────────────────


class ExecutionPlanner:
    """
    Generates an ExecutionPlan from an approved StateSignature.

    The planner does NOT generate arbitrary code — it assembles governed steps
    based on the Signature's intent, datasets, constraints and target layer.
    """

    def plan(self, signature: StateSignature) -> ExecutionPlan:
        steps = self._build_steps(signature)
        consistency_unit = self._select_consistency_unit(signature)
        write_mode = self._select_write_mode(signature)

        return ExecutionPlan(
            signature_hash=signature.signature_hash,
            intent_id=signature.intent_id,
            steps=steps,
            consistency_unit=consistency_unit,
            write_mode=write_mode,
            metadata={
                "domain": signature.domain,
                "target_layer": signature.target_layer.value,
            },
        )

    def _build_steps(self, sig: StateSignature) -> list[ExecutionStep]:
        steps: list[ExecutionStep] = []
        extract_ids: list[str] = []
        post_extract_ids: list[str] = []

        # Step 1: Extract each dataset (with partition filter if required)
        for i, ds in enumerate(sig.datasets):
            step_id = f"extract_{ds.name}"
            config: dict[str, Any] = {}

            if sig.constraints.partition_by:
                config["filter"] = {
                    "column": sig.constraints.partition_by[0],
                    "predicate": ">=",
                    "required_by": "FINOPS",
                }

            steps.append(ExecutionStep(
                id=step_id,
                step_type=StepType.EXTRACT,
                source=ds.name,
                config=config,
            ))
            extract_ids.append(step_id)

        # Step 2: Anonymize datasets with PII
        for ds in sig.datasets:
            if ds.contains_pii and sig.constraints.no_pii_raw:
                anon_id = f"anonymize_{ds.name}"
                depends = (f"extract_{ds.name}",)
                steps.append(ExecutionStep(
                    id=anon_id,
                    step_type=StepType.ANONYMIZE,
                    source=ds.name,
                    config={
                        "pii_columns": list(ds.pii_columns),
                        "strategy": "sha256",
                    },
                    depends_on=depends,
                ))
                post_extract_ids.append(anon_id)
            else:
                post_extract_ids.append(f"extract_{ds.name}")

        # Step 3: Join if multiple datasets and intent is reconciliation
        if len(sig.datasets) > 1 and "reconcil" in sig.intent:
            join_id = "join_datasets"
            steps.append(ExecutionStep(
                id=join_id,
                step_type=StepType.JOIN,
                config={
                    "type": "broadcast" if self._needs_broadcast(sig) else "sort_merge",
                    "datasets": [d.name for d in sig.datasets],
                },
                depends_on=tuple(post_extract_ids),
            ))
            load_depends = (join_id,)
        elif len(post_extract_ids) == 1:
            load_depends = (post_extract_ids[0],)
        else:
            load_depends = tuple(post_extract_ids)

        # Step 4: Aggregate if intent calls for it
        if "aggregate" in sig.intent:
            agg_id = "aggregate"
            steps.append(ExecutionStep(
                id=agg_id,
                step_type=StepType.AGGREGATE,
                config={"group_by": list(sig.constraints.partition_by)},
                depends_on=load_depends,
            ))
            load_depends = (agg_id,)

        # Step 5: Load to target
        target_name = self._derive_target_name(sig)
        load_config: dict[str, Any] = {
            "write_mode": self._select_write_mode(sig).value,
        }
        if sig.constraints.merge_key_required:
            load_config["merge_key"] = True
        if sig.constraints.partition_by:
            load_config["partition_by"] = list(sig.constraints.partition_by)

        steps.append(ExecutionStep(
            id="load_target",
            step_type=StepType.LOAD,
            target=target_name,
            config=load_config,
            depends_on=load_depends,
        ))

        return steps

    def _needs_broadcast(self, sig: StateSignature) -> bool:
        """Use broadcast join when one dataset is much smaller than the other."""
        if len(sig.datasets) != 2:
            return False
        sizes = sorted(d.size_gb for d in sig.datasets)
        return sizes[0] < 1.0 and sizes[1] > 100.0

    def _select_consistency_unit(self, sig: StateSignature) -> ConsistencyUnit:
        """Per whitepaper: selection based on execution context."""
        if sig.constraints.partition_by:
            return ConsistencyUnit.PARTITION
        if len(sig.datasets) > 2:
            return ConsistencyUnit.DAG_BRANCH
        return ConsistencyUnit.DATASET

    def _select_write_mode(self, sig: StateSignature) -> WriteMode:
        """Per whitepaper: append only in Bronze, merge in Silver/Gold."""
        if sig.target_layer == TargetLayer.BRONZE:
            return WriteMode.OVERWRITE_PARTITION if sig.constraints.partition_by else WriteMode.APPEND
        return WriteMode.MERGE

    def _derive_target_name(self, sig: StateSignature) -> str:
        layer = sig.target_layer.value
        if len(sig.datasets) == 1:
            return f"{layer}_{sig.datasets[0].name}"
        return f"{layer}_{sig.domain}"
