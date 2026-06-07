"""
CFA CLI — main entry point
===========================
argparse-based CLI with zero external dependencies.

Commands are organized by family:
- core/           evaluate, validate
- governance/     rules, audit, catalog, signature, policy
- reporting/      report, serve
- project/        init, taxonomy
- infrastructure/ backend_list
"""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cfa",
        description="CFA — Contextual Flux Architecture. Governed execution for AI and data systems.",
    )
    sub = parser.add_subparsers(dest="command")

    p_eval = sub.add_parser("evaluate", help="Evaluate an intent through the governance pipeline")
    p_eval.add_argument("intent", help="Natural language intent to evaluate")
    p_eval.add_argument("--config", help="Path to cfa.yaml config file")
    p_eval.add_argument("--catalog", "-c", help="Path to catalog JSON/YAML")
    p_eval.add_argument("--policy-bundle", "-p", default="v1.0", help="Policy bundle version")
    p_eval.add_argument("--backend", "-b", default="pyspark", help="Codegen backend name")
    p_eval.add_argument("--format", "-f", choices=["table", "json", "summary"], default="table")
    p_eval.add_argument("--output", "-o", help="Save result to file")
    p_eval.add_argument("--warnings-blocking", action="store_true", help="Treat warnings as blocking")
    p_eval.add_argument("--exit-code", action="store_true", help="Exit 1 if BLOCKED")
    p_eval.add_argument("--normalizer", default="auto", choices=["auto", "rule_based", "mock", "openai", "deepseek", "llm"], help="Normalizer backend")
    p_eval.add_argument("--strict", action="store_true", help="Block ambiguous intents")
    p_eval.add_argument("--llm-model", help="LLM model name")
    p_eval.add_argument("--llm-api-key", help="LLM API key")
    p_eval.add_argument("--llm-base-url", help="LLM API base URL")
    p_eval.add_argument("--llm-strict", action="store_true", help="Require LLM output to match catalog exactly")

    p_val = sub.add_parser("validate", help="Validate an intent against a behavior spec")
    p_val.add_argument("--spec", "-s", required=True, help="Path to behavior spec YAML")
    p_val.add_argument("--intent", "-i", required=True, help="Intent to validate")
    p_val.add_argument("--backend", "-b", default="pyspark")
    p_val.add_argument("--exit-code", action="store_true", help="Exit 1 if BLOCKED")

    p_rules = sub.add_parser("rules", help="Policy rule operations")
    rules_sub = p_rules.add_subparsers(dest="rules_command")
    p_list = rules_sub.add_parser("list", help="List all policy rules")
    p_list.add_argument("--policy-bundle", "-p", default="v1.0")
    p_list.add_argument("--format", "-f", choices=["table", "json"], default="table")
    p_explain = rules_sub.add_parser("explain", help="Explain a fault code")
    p_explain.add_argument("code", help="Fault code to explain")
    p_explain.add_argument("--policy-bundle", "-p", default="v1.0")

    p_audit = sub.add_parser("audit", help="Audit trail operations")
    audit_sub = p_audit.add_subparsers(dest="audit_command")
    p_show = audit_sub.add_parser("show", help="Show audit trail for an intent")
    p_show.add_argument("--id", "-i", required=True, help="Intent ID")
    p_show.add_argument("--file", help="Path to audit JSONL file")
    p_show.add_argument("--data-dir", help="Path to audit data directory")
    p_show.add_argument("--format", "-f", choices=["table", "json"], default="table")
    p_show.add_argument("--output", "-o", help="Save to file")
    p_verify = audit_sub.add_parser("verify", help="Verify audit chain integrity")
    p_verify.add_argument("--id", "-i", help="Intent ID (omit for all)")
    p_verify.add_argument("--file", help="Path to audit JSONL file")
    p_verify.add_argument("--data-dir", help="Path to audit data directory")

    p_tax = sub.add_parser("taxonomy", help="Behavior taxonomy operations")
    tax_sub = p_tax.add_subparsers(dest="taxonomy_command")
    p_gen = tax_sub.add_parser("generate", help="Generate taxonomy from behavior spec")
    p_gen.add_argument("--spec", "-s", required=True, help="Path to behavior spec YAML")
    p_gen.add_argument("--output", "-o", help="Save to file")
    p_ti = tax_sub.add_parser("test-intents", help="Generate test intents from behavior spec")
    p_ti.add_argument("--spec", "-s", required=True, help="Path to behavior spec YAML")
    p_ti.add_argument("--count", "-n", type=int, default=5, help="Number of intents per category")
    p_ti.add_argument("--output", "-o", help="Save to file")

    p_be = sub.add_parser("backend", help="Backend operations")
    be_sub = p_be.add_subparsers(dest="backend_command")
    p_blist = be_sub.add_parser("list", help="List registered backends")
    p_blist.add_argument("--format", "-f", choices=["table", "json"], default="table")

    p_cat = sub.add_parser("catalog", help="Catalog operations")
    cat_sub = p_cat.add_subparsers(dest="catalog_command")
    p_cat_val = cat_sub.add_parser("validate", help="Validate a catalog JSON/YAML file")
    p_cat_val.add_argument("path", help="Path to catalog JSON/YAML")
    p_cat_val.add_argument("--require-datasets", action="store_true", help="Require at least one dataset")
    p_cat_val.add_argument("--format", "-f", choices=["summary", "json"], default="summary")

    p_sig = sub.add_parser("signature", help="StateSignature operations")
    sig_sub = p_sig.add_subparsers(dest="signature_command")
    p_sig_val = sig_sub.add_parser("validate", help="Validate a StateSignature JSON/YAML file")
    p_sig_val.add_argument("path", help="Path to StateSignature JSON/YAML")
    p_sig_val.add_argument("--require-datasets", action="store_true", help="Require at least one dataset")
    p_sig_val.add_argument("--format", "-f", choices=["summary", "json"], default="summary")

    p_pol = sub.add_parser("policy", help="Policy bundle operations")
    pol_sub = p_pol.add_subparsers(dest="policy_command")
    p_pol_val = pol_sub.add_parser("validate", help="Validate a policy bundle JSON/YAML file")
    p_pol_val.add_argument("path", help="Path to policy bundle JSON/YAML")
    p_pol_val.add_argument("--format", "-f", choices=["summary", "json"], default="summary")
    p_pol_check = pol_sub.add_parser("check", help="Evaluate a StateSignature JSON/YAML against policy")
    p_pol_check.add_argument("--config", help="Path to cfa.yaml config file")
    p_pol_check.add_argument("--signature", "-s", required=True, help="Path to StateSignature JSON/YAML")
    p_pol_check.add_argument("--catalog", help="Path to catalog JSON/YAML")
    p_pol_check.add_argument("--policy-bundle", "-p", default="v1.0", help="Policy bundle version or path")
    p_pol_check.add_argument("--format", "-f", choices=["summary", "json"], default="summary")
    p_pol_check.add_argument("--exit-code", action="store_true", help="Exit 1 when action is not approve")
    p_pol_check.add_argument("--require-datasets", action="store_true")
    p_pol_check.add_argument("--strict", action="store_true", help="Validate signature datasets against catalog")
    p_pol_check.add_argument("--audit-log", help="Append decision to audit JSONL file")

    p_rep = sub.add_parser("report", help="Generate rich HTML reports")
    rep_sub = p_rep.add_subparsers(dest="report_command")
    p_rex = rep_sub.add_parser("execution", help="Execution report")
    p_rex.add_argument("--intent", required=True, help="Intent text")
    p_rex.add_argument("--intent-id", default="", help="Intent ID")
    p_rex.add_argument("--state", default="approved", help="Decision state")
    p_rex.add_argument("--signature-hash", default="", help="Signature hash")
    p_rex.add_argument("--policy-bundle", default="v1.0", help="Policy bundle")
    p_rex.add_argument("--replan-count", type=int, default=0)
    p_rex.add_argument("--output", "-o", default="cfa_execution_report.html")
    p_raud = rep_sub.add_parser("audit", help="Audit trail report")
    p_raud.add_argument("--intent-id", required=True, help="Intent ID")
    p_raud.add_argument("--policy-bundle", default="v1.0")
    p_raud.add_argument("--output", "-o", default="cfa_audit_report.html")
    p_rlife = rep_sub.add_parser("lifecycle", help="Lifecycle dashboard")
    p_rlife.add_argument("--period", type=int, default=90, help="Period in days")
    p_rlife.add_argument("--audit-file", help="Path to audit JSONL file for real data")
    p_rlife.add_argument("--output", "-o", default="cfa_lifecycle_dashboard.html")
    p_rcomp = rep_sub.add_parser("compliance", help="Compliance summary for auditors")
    p_rcomp.add_argument("--policy-bundle", default="v1.0")
    p_rcomp.add_argument("--audit-file", help="Path to audit JSONL file for real data")
    p_rcomp.add_argument("--output", "-o", default="cfa_compliance_report.html")
    p_rdash = rep_sub.add_parser("dashboard", help="Multi-pipeline dashboard")
    p_rdash.add_argument("--period", type=int, default=90, help="Period in days")
    p_rdash.add_argument("--audit-file", help="Path to audit JSONL file for real data")
    p_rdash.add_argument("--output", "-o", default="cfa_dashboard.html")

    p_srv = sub.add_parser("serve", help="Start live metrics/health server")
    p_srv.add_argument("--port", "-p", type=int, default=8765)
    p_srv.add_argument("--metrics-port", type=int, default=0, help="Enable /metrics on separate port")

    p_init = sub.add_parser("init", help="Initialize CFA in current directory")
    p_init.add_argument("--dir", "-d", default=".cfa", help="Target directory")

    p_status = sub.add_parser("status", help="Show CFA project health and storage stats")
    p_status.add_argument("--config", help="Path to cfa.yaml config file")
    p_status.add_argument("--format", "-f", choices=["summary", "json"], default="summary")

    # ── lifecycle ──────────────────────────────────────────────────────────
    p_life = sub.add_parser("lifecycle", help="Lifecycle management operations")
    life_sub = p_life.add_subparsers(dest="lifecycle_command")
    p_life_eval = life_sub.add_parser("evaluate", help="Evaluate lifecycle indices for all skills")
    p_life_eval.add_argument("--db", help="Path to SQLite database with execution records")
    p_life_eval.add_argument("--policy-bundle", default="v1.0")
    p_life_eval.add_argument("--window", type=int, default=30, help="Evaluation window in days")
    p_life_eval.add_argument("--format", "-f", choices=["summary", "json"], default="summary")
    p_life_list = life_sub.add_parser("list", help="List all tracked skills")
    p_life_list.add_argument("--db", help="Path to SQLite database")
    p_life_list.add_argument("--format", "-f", choices=["summary", "json"], default="summary")

    # ── storage ────────────────────────────────────────────────────────────
    p_stor = sub.add_parser("storage", help="Storage management operations")
    stor_sub = p_stor.add_subparsers(dest="storage_command")
    p_stor_stats = stor_sub.add_parser("stats", help="Show storage statistics")
    p_stor_stats.add_argument("--db", help="Path to SQLite database")
    p_stor_stats.add_argument("--dir", help="Path to JSONL storage directory")
    p_stor_stats.add_argument("--format", "-f", choices=["summary", "json"], default="summary")
    p_stor_cleanup = stor_sub.add_parser("cleanup", help="Remove records older than threshold")
    p_stor_cleanup.add_argument("--db", help="Path to SQLite database")
    p_stor_cleanup.add_argument("--dir", help="Path to JSONL storage directory")
    p_stor_cleanup.add_argument("--before", help="ISO datetime cutoff (e.g. 2026-01-01T00:00:00)")
    p_stor_cleanup.add_argument("--retention", type=int, dest="retention_days", help="Keep records from last N days")
    p_stor_vacuum = stor_sub.add_parser("vacuum", help="Optimize/compact SQLite database")
    p_stor_vacuum.add_argument("--db", required=True, help="Path to SQLite database")

    return parser


def main(args: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(args)

    if ns.command is None:
        parser.print_help()
        return 0

    from .core.evaluate import cmd_evaluate
    from .core.validate import cmd_validate
    from .governance.audit import cmd_audit_show, cmd_audit_verify
    from .governance.catalog import cmd_catalog_validate
    from .governance.policy import cmd_policy_check, cmd_policy_validate
    from .governance.rules import cmd_rules_explain, cmd_rules_list
    from .governance.signature import cmd_signature_validate
    from .infrastructure.backend_list import cmd_backend_list
    from .infrastructure.storage import cmd_storage_cleanup, cmd_storage_stats, cmd_storage_vacuum
    from .project.init import cmd_init
    from .project.lifecycle import cmd_lifecycle_evaluate, cmd_lifecycle_list
    from .project.status import cmd_status
    from .project.taxonomy import cmd_taxonomy_generate, cmd_taxonomy_test_intents
    from .reporting.report import (
        cmd_report_audit,
        cmd_report_compliance,
        cmd_report_dashboard,
        cmd_report_execution,
        cmd_report_lifecycle,
    )
    from .reporting.serve import cmd_serve

    dispatch = {
        "evaluate": cmd_evaluate,
        "validate": cmd_validate,
        "rules": lambda ns: (
            cmd_rules_list(ns) if ns.rules_command == "list"
            else cmd_rules_explain(ns) if ns.rules_command == "explain"
            else _unknown(parser, "rules", ns.rules_command)
        ),
        "audit": lambda ns: (
            cmd_audit_show(ns) if ns.audit_command == "show"
            else cmd_audit_verify(ns) if ns.audit_command == "verify"
            else _unknown(parser, "audit", ns.audit_command)
        ),
        "taxonomy": lambda ns: (
            cmd_taxonomy_generate(ns) if ns.taxonomy_command == "generate"
            else cmd_taxonomy_test_intents(ns) if ns.taxonomy_command == "test-intents"
            else _unknown(parser, "taxonomy", ns.taxonomy_command)
        ),
        "backend": lambda ns: (
            cmd_backend_list(ns) if ns.backend_command == "list"
            else _unknown(parser, "backend", ns.backend_command)
        ),
        "catalog": lambda ns: (
            cmd_catalog_validate(ns) if ns.catalog_command == "validate"
            else _unknown(parser, "catalog", ns.catalog_command)
        ),
        "signature": lambda ns: (
            cmd_signature_validate(ns) if ns.signature_command == "validate"
            else _unknown(parser, "signature", ns.signature_command)
        ),
        "policy": lambda ns: (
            cmd_policy_validate(ns) if ns.policy_command == "validate"
            else cmd_policy_check(ns) if ns.policy_command == "check"
            else _unknown(parser, "policy", ns.policy_command)
        ),
        "report": lambda ns: (
            cmd_report_execution(ns) if ns.report_command == "execution"
            else cmd_report_audit(ns) if ns.report_command == "audit"
            else cmd_report_lifecycle(ns) if ns.report_command == "lifecycle"
            else cmd_report_compliance(ns) if ns.report_command == "compliance"
            else cmd_report_dashboard(ns) if ns.report_command == "dashboard"
            else _unknown(parser, "report", ns.report_command)
        ),
        "serve": cmd_serve,
        "init": cmd_init,
        "status": cmd_status,
        "lifecycle": lambda ns: (
            cmd_lifecycle_evaluate(ns) if ns.lifecycle_command == "evaluate"
            else cmd_lifecycle_list(ns) if ns.lifecycle_command == "list"
            else _unknown(parser, "lifecycle", ns.lifecycle_command)
        ),
        "storage": lambda ns: (
            cmd_storage_stats(ns) if ns.storage_command == "stats"
            else cmd_storage_cleanup(ns) if ns.storage_command == "cleanup"
            else cmd_storage_vacuum(ns) if ns.storage_command == "vacuum"
            else _unknown(parser, "storage", ns.storage_command)
        ),
    }

    handler = dispatch.get(ns.command)
    if handler is None:
        parser.print_help()
        return 1

    try:
        return handler(ns)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _unknown(parser: argparse.ArgumentParser, group: str, command: str | None) -> int:
    print(f"Unknown {group} command: {command}", file=sys.stderr)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
