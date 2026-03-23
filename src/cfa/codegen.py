"""
CFA Code Generator
==================
Generates deterministic, governed code from an ExecutionPlan.

Phase 2: template-based PySpark code generation.
The generator is NOT creative — it fills templates governed by the plan.

Key properties:
- Output is deterministic (same plan = same code)
- All PII handling is explicit (sha256/drop)
- Partition filters are always present when required
- Write operations use merge (never raw append in Silver/Gold)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .planner import ExecutionPlan, ExecutionStep, StepType, WriteMode


# ── Generated Code ───────────────────────────────────────────────────────────


@dataclass
class GeneratedCode:
    """Complete code artifact generated from an execution plan."""

    plan_signature_hash: str
    intent_id: str
    language: str
    code: str
    step_code_map: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def line_count(self) -> int:
        return len(self.code.strip().splitlines())


# ── Code Generator Backend ───────────────────────────────────────────────────


class CodeGenBackend(ABC):
    """Extension point: different code generation targets."""

    @abstractmethod
    def generate(self, plan: ExecutionPlan) -> GeneratedCode: ...


# ── PySpark Generator ────────────────────────────────────────────────────────


class PySparkGenerator(CodeGenBackend):
    """
    Generates PySpark code from an ExecutionPlan.
    Template-based — no LLM involved.
    """

    def generate(self, plan: ExecutionPlan) -> GeneratedCode:
        lines: list[str] = []
        step_code: dict[str, str] = {}

        lines.append("from pyspark.sql import SparkSession, functions as F")
        lines.append("")
        lines.append("spark = SparkSession.builder.getOrCreate()")
        lines.append("")

        ordered = plan.execution_order()
        for step in ordered:
            code = self._generate_step(step, plan)
            step_code[step.id] = code
            lines.append(f"# ── Step: {step.id} ({step.step_type.value}) ──")
            lines.append(code)
            lines.append("")

        full_code = "\n".join(lines)

        return GeneratedCode(
            plan_signature_hash=plan.signature_hash,
            intent_id=plan.intent_id,
            language="pyspark",
            code=full_code,
            step_code_map=step_code,
            metadata={
                "write_mode": plan.write_mode.value,
                "consistency_unit": plan.consistency_unit.value,
                "step_count": plan.step_count,
            },
        )

    def _generate_step(self, step: ExecutionStep, plan: ExecutionPlan) -> str:
        match step.step_type:
            case StepType.EXTRACT:
                return self._gen_extract(step)
            case StepType.ANONYMIZE:
                return self._gen_anonymize(step)
            case StepType.JOIN:
                return self._gen_join(step, plan)
            case StepType.AGGREGATE:
                return self._gen_aggregate(step)
            case StepType.LOAD:
                return self._gen_load(step, plan)
            case StepType.FILTER:
                return self._gen_filter(step)
            case StepType.TRANSFORM:
                return self._gen_transform(step)
            case _:
                return f"# TODO: unsupported step type {step.step_type.value}"

    def _gen_extract(self, step: ExecutionStep) -> str:
        var = _var_name(step.source or "data")
        lines = [f'{var} = spark.read.format("delta").load("{step.source}")']

        filt = step.config.get("filter")
        if filt:
            col = filt["column"]
            pred = filt["predicate"]
            lines.append(
                f'{var} = {var}.filter(F.col("{col}") {pred} F.lit("{{date_param}}"))'
            )

        return "\n".join(lines)

    def _gen_anonymize(self, step: ExecutionStep) -> str:
        var = _var_name(step.source or "data")
        pii_cols = step.config.get("pii_columns", [])
        strategy = step.config.get("strategy", "sha256")

        lines: list[str] = []
        for col in pii_cols:
            if strategy == "sha256":
                lines.append(
                    f'{var} = {var}.withColumn("{col}_hash", F.sha2(F.col("{col}").cast("string"), 256))'
                )
                lines.append(f'{var} = {var}.drop("{col}")')
            else:
                lines.append(f'{var} = {var}.drop("{col}")')

        return "\n".join(lines) if lines else f"# No PII columns to anonymize in {step.source}"

    def _gen_join(self, step: ExecutionStep, plan: ExecutionPlan) -> str:
        datasets = step.config.get("datasets", [])
        join_type = step.config.get("type", "sort_merge")

        if len(datasets) < 2:
            return "# Join requires at least 2 datasets"

        left_var = _var_name(datasets[0])
        right_var = _var_name(datasets[1])
        result_var = "df_joined"

        lines: list[str] = []
        if join_type == "broadcast":
            lines.append(f"from pyspark.sql.functions import broadcast")
            lines.append(
                f'{result_var} = {left_var}.join(broadcast({right_var}), on="merge_key", how="inner")'
            )
        else:
            lines.append(
                f'{result_var} = {left_var}.join({right_var}, on="merge_key", how="inner")'
            )

        return "\n".join(lines)

    def _gen_aggregate(self, step: ExecutionStep) -> str:
        group_by = step.config.get("group_by", [])
        if not group_by:
            return "df_agg = df_joined.groupBy().count()  # WARNING: no group_by specified"

        cols = ", ".join(f'"{c}"' for c in group_by)
        return f"df_agg = df_joined.groupBy({cols}).agg(F.count(F.lit(1)).alias(\"count\"))"

    def _gen_load(self, step: ExecutionStep, plan: ExecutionPlan) -> str:
        target = step.target or "target"
        source_var = self._resolve_source_var(step, plan)
        write_mode = step.config.get("write_mode", plan.write_mode.value)
        partition_by = step.config.get("partition_by", [])

        lines: list[str] = []

        if write_mode == WriteMode.MERGE.value:
            lines.append(f'from delta.tables import DeltaTable')
            lines.append(f"")
            lines.append(f'if DeltaTable.isDeltaTable(spark, "{target}"):')
            lines.append(f'    target_table = DeltaTable.forPath(spark, "{target}")')
            lines.append(f'    target_table.alias("t").merge(')
            lines.append(f'        {source_var}.alias("s"),')
            lines.append(f'        "t.merge_key = s.merge_key"')
            lines.append(f'    ).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()')
            lines.append(f"else:")

            writer = f'    {source_var}.write.format("delta")'
            if partition_by:
                cols = ", ".join(f'"{c}"' for c in partition_by)
                writer += f".partitionBy({cols})"
            writer += f'.mode("overwrite").save("{target}")'
            lines.append(writer)

        elif write_mode == WriteMode.OVERWRITE_PARTITION.value:
            writer = f'{source_var}.write.format("delta")'
            if partition_by:
                cols = ", ".join(f'"{c}"' for c in partition_by)
                writer += f".partitionBy({cols})"
            writer += f'.mode("overwrite").option("replaceWhere", "{{partition_predicate}}").save("{target}")'
            lines.append(writer)

        else:
            writer = f'{source_var}.write.format("delta").mode("append").save("{target}")'
            lines.append(writer)

        return "\n".join(lines)

    def _gen_filter(self, step: ExecutionStep) -> str:
        var = _var_name(step.source or "data")
        condition = step.config.get("condition", "1=1")
        return f'{var} = {var}.filter("{condition}")'

    def _gen_transform(self, step: ExecutionStep) -> str:
        return f"# Transform step: {step.config}"

    def _resolve_source_var(self, step: ExecutionStep, plan: ExecutionPlan) -> str:
        """Determine which variable name feeds into a step."""
        if step.depends_on:
            dep = step.depends_on[0]
            if "join" in dep:
                return "df_joined"
            if "aggregate" in dep or "agg" in dep:
                return "df_agg"
            dep_step = plan.get_step(dep)
            if dep_step and dep_step.source:
                return _var_name(dep_step.source)
        return "df"


def _var_name(name: str) -> str:
    """Convert dataset name to valid Python variable name."""
    return f"df_{name.replace('-', '_').replace('.', '_')}"
