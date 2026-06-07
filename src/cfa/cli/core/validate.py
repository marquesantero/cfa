"""cfa validate — validate an intent against a behavior spec."""

from __future__ import annotations

import sys


def cmd_validate(args) -> int:
    from cfa.behavior import BehaviorSpec, Systematizer
    from cfa.cli.formatters import _icon
    from cfa.core.kernel import KernelConfig, KernelOrchestrator

    try:
        spec = BehaviorSpec.from_yaml(args.spec)
    except Exception as e:
        print(f"Error loading spec: {e}", file=sys.stderr)
        return 1

    _, rules = Systematizer().systematize(spec)
    config = KernelConfig(policy_bundle_version=spec.name, backend=args.backend)
    kernel = KernelOrchestrator(config=config, policy_rules=rules)
    result = kernel.process(args.intent)

    if result.is_executable:
        print(f"{_icon('approved')} PASSED  | {result.state.value} | {args.intent[:60]}")
        return 0
    else:
        print(f"{_icon('blocked')} BLOCKED | {result.blocked_reason}")
        return 1 if args.exit_code else 0
