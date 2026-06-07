"""cfa catalog — validate catalog files."""

from __future__ import annotations

from .._helpers import load_catalog


def cmd_catalog_validate(args) -> int:
    from cfa.cli.formatters import format_json
    from cfa.policy.catalog import validate_catalog

    catalog = load_catalog(args.path)
    result = validate_catalog(catalog, require_datasets=args.require_datasets)
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
        print(f"Catalog {status}: {args.path}")
        for msg in result.messages:
            print(f"  - {msg}")
    return 0 if result.valid else 1
