"""cfa evaluate — run an intent through the governance pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def cmd_evaluate(args) -> int:
    from cfa.cli._helpers import apply_config_defaults, load_catalog, load_policy, resolve_config, resolve_normalizer
    from cfa.cli.formatters import format_evaluate_table, format_json, format_summary
    from cfa.core.kernel import KernelConfig, KernelOrchestrator

    config = resolve_config(args)
    apply_config_defaults(args, config)
    catalog = load_catalog(args.catalog)
    policy_rules, bundle_version = load_policy(args.policy_bundle)
    normalizer_backend = resolve_normalizer(args)

    config = KernelConfig(
        policy_bundle_version=bundle_version,
        backend=args.backend,
        warnings_are_blocking=args.warnings_blocking,
        normalizer=args.normalizer,
        strict_normalization=args.strict,
    )

    kernel = KernelOrchestrator(
        catalog=catalog, config=config, policy_rules=policy_rules,
        normalizer_backend=normalizer_backend,
    )
    result = kernel.process(args.intent)

    faults: list[dict[str, Any]] = []
    if result.policy_result:
        for f in result.policy_result.faults:
            faults.append({
                "code": f.code,
                "severity": f.severity.value,
                "family": f.family.value,
                "message": f.message,
                "remediation": list(f.remediation),
            })

    output: dict[str, Any] = {
        "intent": args.intent,
        "intent_id": result.intent_id,
        "state": result.state.value,
        "signature_hash": result.signature.signature_hash if result.signature else "",
        "replan_count": len(result.replan_history),
        "policy_bundle": config.policy_bundle_version,
        "faults": faults,
    }

    fmt = args.format or "table"
    if fmt == "json":
        print(format_json(output))
    elif fmt == "summary":
        print(format_summary(output, faults))
    else:
        print(format_evaluate_table(output, faults))

    if args.output:
        out_path = Path(args.output)
        if out_path.suffix == ".json":
            out_path.write_text(format_json(output), encoding="utf-8")
        else:
            out_path.write_text(format_summary(output, faults), encoding="utf-8")

    if args.exit_code and result.state.value == "blocked":
        return 1
    return 0
