"""
PySpark Backend
===============
Code generation backend targeting Apache Spark (PySpark) with Delta Lake.

Generates deterministic PySpark code from an ExecutionPlan.
Template-based — no LLM involved.
"""

from __future__ import annotations

from cfa.core.codegen import GeneratedCode
from cfa.core.planner import ExecutionPlan, ExecutionStep, StepType, WriteMode
from cfa.types import FaultSeverity
from cfa.validation.static import ForbiddenToken

from . import BackendAdapter, BackendCapabilities

_PYSPARK_FORBIDDEN_TOKENS: list[ForbiddenToken] = [
    ForbiddenToken(pattern=".collect()", fault_code="STATIC_FORBIDDEN_COLLECT",
                   severity=FaultSeverity.CRITICAL,
                   message="collect() brings all data to driver."),
    ForbiddenToken(pattern=".toPandas()", fault_code="STATIC_FORBIDDEN_TOPANDAS",
                   severity=FaultSeverity.CRITICAL,
                   message="toPandas() brings all data to driver."),
    ForbiddenToken(pattern="crossJoin(", fault_code="STATIC_FORBIDDEN_CROSSJOIN",
                   severity=FaultSeverity.CRITICAL,
                   message="crossJoin() produces cartesian product."),
    ForbiddenToken(pattern="import os", fault_code="STATIC_FORBIDDEN_IMPORT_OS",
                   severity=FaultSeverity.CRITICAL,
                   message="os module import forbidden in sandboxed execution."),
    ForbiddenToken(pattern="import subprocess", fault_code="STATIC_FORBIDDEN_IMPORT_SUBPROCESS",
                   severity=FaultSeverity.CRITICAL,
                   message="subprocess module import forbidden in sandboxed execution."),
    ForbiddenToken(pattern=r'\.mode\(\"append\"\).*(?:silver|gold)',
                   fault_code="STATIC_APPEND_TO_PROTECTED",
                   severity=FaultSeverity.HIGH,
                   message="Append mode to Silver/Gold detected.", is_regex=True),
]


class PySparkBackend(BackendAdapter):
    """Generates PySpark code from an ExecutionPlan."""

    def get_capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            backend_name="pyspark",
            backend_version="delta-3.x",
            supports_merge=True,
            supports_partition_overwrite=True,
            supports_anonymization=True,
            supports_schema_enforcement=True,
            pii_anonymization_methods=["sha256", "drop", "tokenize", "mask"],
            cost_model_available=True,
            max_recommended_rows=100_000_000,
            supported_languages=["python", "pyspark"],
            forbidden_tokens=_PYSPARK_FORBIDDEN_TOKENS,
        )

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
        merge_keys = step.config.get("merge_keys", ["id"])
        on_clause = ", ".join(f'"{k}"' for k in merge_keys)

        if len(datasets) < 2:
            return "# Join requires at least 2 datasets"

        left_var = _var_name(datasets[0])
        right_var = _var_name(datasets[1])
        result_var = "df_joined"

        lines: list[str] = []
        if join_type == "broadcast":
            lines.append("from pyspark.sql.functions import broadcast")
            lines.append(
                f'{result_var} = {left_var}.join(broadcast({right_var}), on=[{on_clause}], how="inner")'
            )
        else:
            lines.append(
                f'{result_var} = {left_var}.join({right_var}, on=[{on_clause}], how="inner")'
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
        merge_keys = step.config.get("merge_keys", ["id"])
        merge_on = " AND ".join(f't.{k} = s.{k}' for k in merge_keys)

        lines: list[str] = []

        if write_mode == WriteMode.MERGE.value:
            lines.append("from delta.tables import DeltaTable")
            lines.append("")
            lines.append(f'if DeltaTable.isDeltaTable(spark, "{target}"):')
            lines.append(f'    target_table = DeltaTable.forPath(spark, "{target}")')
            lines.append('    target_table.alias("t").merge(')
            lines.append(f'        {source_var}.alias("s"),')
            lines.append(f'        "{merge_on}"')
            lines.append("    ).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()")
            lines.append("else:")

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
    return f"df_{name.replace('-', '_').replace('.', '_')}"
