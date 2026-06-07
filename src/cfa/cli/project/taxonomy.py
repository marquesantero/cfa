"""cfa taxonomy — behavior taxonomy operations."""

from __future__ import annotations

from pathlib import Path


def cmd_taxonomy_generate(args) -> int:
    import sys

    from cfa.behavior import BehaviorSpec, Systematizer
    from cfa.cli.formatters import format_json

    try: spec = BehaviorSpec.from_yaml(args.spec)
    except Exception as e: print(f"Error loading spec: {e}", file=sys.stderr); return 1

    taxonomy, rules = Systematizer().systematize(spec)
    output = {"taxonomy": taxonomy.to_dict(), "rules": [{"name": r.name, "action": r.action.value, "fault_code": r.fault_code, "severity": r.severity.value, "message": r.message, "remediation": list(r.remediation)} for r in rules]}
    out_text = format_json(output)
    if args.output: Path(args.output).write_text(out_text, encoding="utf-8"); print(f"Taxonomy saved to {args.output}"); print(f"  Categories: {taxonomy.category_count}"); print(f"  Rules:      {len(rules)}")
    else: print(out_text)
    return 0


def cmd_taxonomy_test_intents(args) -> int:
    import sys

    from cfa.behavior import BehaviorSpec, Systematizer

    try: spec = BehaviorSpec.from_yaml(args.spec)
    except Exception as e: print(f"Error loading spec: {e}", file=sys.stderr); return 1

    intents = Systematizer().generate_test_intents(spec, count=args.count)
    out_text = "\n".join(intents)
    if args.output: Path(args.output).write_text(out_text, encoding="utf-8"); print(f"{len(intents)} test intents saved to {args.output}")
    else:
        for intent in intents: print(intent)
    return 0
