"""cfa rules — policy rule operations."""

from __future__ import annotations

import sys


def cmd_rules_list(args) -> int:
    from cfa.cli.formatters import format_json, format_rules_table
    from cfa.policy.engine import PolicyEngine

    engine = PolicyEngine(policy_bundle_version=args.policy_bundle)
    rule_dicts = engine.describe_rules()
    fmt = args.format or "table"

    if fmt == "json":
        print(format_json(rule_dicts))
    else:
        print(format_rules_table(rule_dicts))
    print(f"\nPolicy bundle: {args.policy_bundle}  |  Rules: {len(rule_dicts)}")
    return 0


def cmd_rules_explain(args) -> int:
    from cfa.policy.engine import PolicyEngine

    engine = PolicyEngine(policy_bundle_version=args.policy_bundle)
    for r in engine.rules:
        if r.fault_code == args.code:
            print(f"Fault Code:    {r.fault_code}")
            print(f"Rule:          {r.name}")
            print(f"Action:        {r.action.value.upper()}")
            print(f"Severity:      {r.severity.value.upper()}")
            print(f"Family:        {r.fault_family.value}")
            print(f"Message:       {r.message}")
            if r.remediation:
                print("Remediation:")
                for i, rem in enumerate(r.remediation):
                    print(f"  {i+1}. {rem}")
            return 0
    print(f"Unknown fault code: {args.code}", file=sys.stderr)
    return 1
