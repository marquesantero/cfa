"""
SQL Backend
============
Code generation backend targeting standard SQL.

Generates governed SQL from an ExecutionPlan. The output is dialect-agnostic
SQL that runs on Snowflake, BigQuery, Postgres, DuckDB, and similar engines.

Template-based — no LLM involved. Every SQL statement is traceable back to
the execution step that produced it.
"""

from __future__ import annotations

from cfa.core.codegen import GeneratedCode
from cfa.core.planner import ExecutionPlan, ExecutionStep, StepType, WriteMode
from cfa.types import FaultSeverity
from cfa.validate.static import ForbiddenToken

from . import BackendAdapter, BackendCapabilities

_SQL_FORBIDDEN_TOKENS: list[ForbiddenToken] = [
    ForbiddenToken(pattern=r"\bDROP\s+TABLE\b", fault_code="STATIC_SQL_DROP_TABLE",
                   severity=FaultSeverity.CRITICAL,
                   message="DROP TABLE in governed SQL forbidden.", is_regex=True),
    ForbiddenToken(pattern=r"\bDROP\s+DATABASE\b", fault_code="STATIC_SQL_DROP_DATABASE",
                   severity=FaultSeverity.CRITICAL,
                   message="DROP DATABASE in governed SQL forbidden.", is_regex=True),
    ForbiddenToken(pattern=r"\bTRUNCATE\b", fault_code="STATIC_SQL_TRUNCATE",
                   severity=FaultSeverity.CRITICAL,
                   message="TRUNCATE forbidden — use MERGE or INSERT OVERWRITE.", is_regex=True),
    ForbiddenToken(pattern=r"\bDELETE\s+FROM\b(?!.*WHERE)", fault_code="STATIC_SQL_DELETE_WITHOUT_WHERE",
                   severity=FaultSeverity.CRITICAL,
                   message="DELETE FROM without WHERE forbidden.", is_regex=True),
    ForbiddenToken(pattern=r"\bALTER\s+TABLE\b", fault_code="STATIC_SQL_ALTER_TABLE",
                   severity=FaultSeverity.HIGH,
                   message="ALTER TABLE requires explicit approval.", is_regex=True),
]


class SqlBackend(BackendAdapter):
    """Generates governed SQL from an ExecutionPlan."""

    def get_capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            backend_name="sql",
            backend_version="ansi-sql-2023",
            supports_merge=True,
            supports_partition_overwrite=True,
            supports_anonymization=True,
            supports_schema_enforcement=True,
            pii_anonymization_methods=["sha256", "drop", "md5", "tokenize"],
            cost_model_available=False,
            max_recommended_rows=1_000_000_000,
            supported_languages=["sql"],
            forbidden_tokens=_SQL_FORBIDDEN_TOKENS,
        )

    def generate(self, plan: ExecutionPlan) -> GeneratedCode:
        lines: list[str] = []
        step_code: dict[str, str] = {}
        ordered = plan.execution_order()

        for step in ordered:
            code = self._generate_step(step, plan)
            step_code[step.id] = code
            lines.append(f"-- Step: {step.id} ({step.step_type.value})")
            lines.append(code)
            lines.append("")

        full_code = "\n".join(lines)

        return GeneratedCode(
            plan_signature_hash=plan.signature_hash,
            intent_id=plan.intent_id,
            language="sql",
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
                return f"-- TODO: unsupported step type {step.step_type.value}"

    # ── Step generators ───────────────────────────────────────────────────

    def _gen_extract(self, step: ExecutionStep) -> str:
        source = step.source or "unknown_source"
        columns = self._resolve_extract_columns(step)
        lines = [f"-- EXTRACT: {source}"]
        lines.append(f"SELECT {columns} FROM {_quote_ident(source)}")

        filt = step.config.get("filter")
        if filt:
            col = _quote_ident(filt["column"])
            pred = filt["predicate"]
            lines.append(f"WHERE {col} {pred} '{{date_param}}'")

        return "\n".join(lines)

    def _gen_anonymize(self, step: ExecutionStep) -> str:
        source = f"cte_{step.source}" if step.source else "source_cte"
        pii_cols = step.config.get("pii_columns", [])
        strategy = step.config.get("strategy", "sha256")

        if not pii_cols:
            return f"-- No PII columns to anonymize for {source}"

        lines: list[str] = [f"-- ANONYMIZE: {source} (strategy={strategy})"]
        for col in pii_cols:
            safe = _quote_ident(col)
            if strategy == "sha256":
                lines.append(f"--   {safe} → SHA256({safe})")
            elif strategy == "drop":
                lines.append(f"--   {safe} → DROPPED")
            elif strategy == "md5":
                lines.append(f"--   {safe} → MD5({safe})")
            else:
                lines.append(f"--   {safe} → anonymized ({strategy})")
        return "\n".join(lines)

    def _gen_join(self, step: ExecutionStep, plan: ExecutionPlan) -> str:
        datasets = step.config.get("datasets", [])
        merge_keys = step.config.get("merge_keys", ["id"])
        join_type = step.config.get("type", "sort_merge")

        if len(datasets) < 2:
            return "-- Join requires at least 2 datasets"

        left_alias = _cte_name(datasets[0])
        right_alias = _cte_name(datasets[1])
        on_clause = " AND ".join(
            f"{left_alias}.{_quote_ident(k)} = {right_alias}.{_quote_ident(k)}"
            for k in merge_keys
        )

        lines: list[str] = [f"-- JOIN: {datasets[0]} + {datasets[1]}"]
        hint = "/*+ BROADCAST */ " if join_type == "broadcast" else ""
        lines.append(
            f"SELECT {left_alias}.*, {right_alias}.*"
        )
        lines.append(f"FROM {_quote_ident(datasets[0])} {left_alias}")
        lines.append(f"{hint}INNER JOIN {_quote_ident(datasets[1])} {right_alias}")
        lines.append(f"  ON {on_clause}")

        return "\n".join(lines)

    def _gen_aggregate(self, step: ExecutionStep) -> str:
        group_by = step.config.get("group_by", [])

        lines: list[str] = ["-- AGGREGATE"]
        if not group_by:
            lines.append("SELECT COUNT(*) AS cnt FROM joined_cte")
        else:
            cols = ", ".join(_quote_ident(c) for c in group_by)
            lines.append(f"SELECT {cols}, COUNT(*) AS cnt")
            lines.append("FROM joined_cte")
            lines.append(f"GROUP BY {cols}")

        return "\n".join(lines)

    def _gen_load(self, step: ExecutionStep, plan: ExecutionPlan) -> str:
        target = step.target or "target_table"
        write_mode = step.config.get("write_mode", plan.write_mode.value)
        partition_by = step.config.get("partition_by", [])
        merge_keys = step.config.get("merge_keys", ["id"])
        source_cte = self._resolve_source_cte(step, plan)

        lines: list[str] = [f"-- LOAD: {target} (mode={write_mode})"]

        if write_mode == WriteMode.MERGE.value:
            merge_on = " AND ".join(
                f"target.{_quote_ident(k)} = source.{_quote_ident(k)}"
                for k in merge_keys
            )
            set_clause = ", ".join(
                f"{_quote_ident(k)} = source.{_quote_ident(k)}"
                for k in merge_keys
            )
            lines.append(f"MERGE INTO {_quote_ident(target)} AS target")
            lines.append(f"USING ({source_cte}) AS source")
            lines.append(f"  ON {merge_on}")
            lines.append("WHEN MATCHED THEN")
            lines.append(f"  UPDATE SET {set_clause}")
            lines.append("WHEN NOT MATCHED THEN")
            lines.append("  INSERT (*)")

        elif write_mode == WriteMode.OVERWRITE_PARTITION.value:
            partition_clause = ""
            if partition_by:
                parts = ", ".join(_quote_ident(p) for p in partition_by)
                partition_clause = f" PARTITION ({parts})"
            lines.append(f"INSERT OVERWRITE {_quote_ident(target)}{partition_clause}")
            lines.append(source_cte)

        elif write_mode == WriteMode.APPEND.value:
            lines.append(f"INSERT INTO {_quote_ident(target)}")
            lines.append(source_cte)

        else:
            lines.append(f"-- Unsupported write mode: {write_mode}")

        return "\n".join(lines)

    def _gen_filter(self, step: ExecutionStep) -> str:
        condition = step.config.get("condition", "1=1")
        return f"-- FILTER: WHERE {condition}"

    def _gen_transform(self, step: ExecutionStep) -> str:
        return f"-- TRANSFORM: {step.config}"

    # ── Helpers ────────────────────────────────────────────────────────────

    def _resolve_extract_columns(self, step: ExecutionStep) -> str:
        target_columns = step.config.get("target_columns")
        if target_columns and isinstance(target_columns, list):
            return ", ".join(_quote_ident(c) for c in target_columns)
        return "*"

    def _resolve_source_cte(self, step: ExecutionStep, plan: ExecutionPlan) -> str:
        if step.depends_on:
            dep = step.depends_on[0]
            if "join" in dep:
                return "joined_cte"
            if "aggregate" in dep or "agg" in dep:
                return "aggregated_cte"
            dep_step = plan.get_step(dep)
            if dep_step and dep_step.source:
                return f"SELECT * FROM {_quote_ident(dep_step.source)}"
        return "source_cte"


# ── SQL helpers ──────────────────────────────────────────────────────────────


def _quote_ident(name: str) -> str:
    """Quote a SQL identifier if it contains special characters or is a reserved word."""
    sanitized = str(name).replace('"', '""')
    return f'"{sanitized}"'


def _cte_name(source: str) -> str:
    """Generate a short CTE alias from a dataset name."""
    clean = source.replace("-", "_").replace(".", "_").lower()
    if len(clean) <= 8:
        return clean
    parts = clean.split("_")
    if len(parts) >= 2:
        return parts[0][:4] + "_" + parts[-1][:4]
    return clean[:8]
