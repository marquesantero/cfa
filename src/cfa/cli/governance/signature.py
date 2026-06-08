"""cfa signature — validate StateSignature files."""

from __future__ import annotations

from .._helpers import load_structured_file


def cmd_signature_validate(args) -> int:
    from cfa.cli.formatters import format_json
    from cfa.validate.signature import validate_signature_data

    data = load_structured_file(
        args.path,
        "Error: PyYAML required for YAML signatures. Install: pip install pyyaml",
    )
    result = validate_signature_data(data, require_datasets=args.require_datasets)
    output = {
        "path": args.path,
        "valid": result.valid,
        "issue_count": len(result.issues),
        "issues": [{"path": i.path, "message": i.message} for i in result.issues],
    }

    if args.format == "json":
        print(format_json(output))
    else:
        status = "VALID" if result.valid else "INVALID"
        print(f"StateSignature {status}: {args.path}")
        for msg in result.messages:
            print(f"  - {msg}")
    return 0 if result.valid else 1
