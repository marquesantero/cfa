"""cfa init — bootstrap CFA project."""

from __future__ import annotations

import json
from pathlib import Path


def cmd_init(args) -> int:
    cfa_dir = Path(args.dir or ".cfa")
    cfa_dir.mkdir(exist_ok=True)
    (cfa_dir / "policies").mkdir(exist_ok=True)

    example_catalog = {
        "datasets": {
            "nfe": {"classification": "high_volume", "size_gb": 4000, "pii_columns": [],
                     "partition_column": "processing_date", "merge_keys": ["nfe_id"]},
            "clientes": {"classification": "sensitive", "size_gb": 0.5,
                          "pii_columns": ["cpf", "email"], "partition_column": "processing_date",
                          "merge_keys": ["cliente_id"]},
        }
    }

    (cfa_dir / "catalog.json").write_text(json.dumps(example_catalog, indent=2), encoding="utf-8")

    prod_policy = {
        "policy_bundle": {
            "version": "prod-v1.0",
            "description": "Production governance rules",
            "rules": [
                {"name": "forbid_raw_pii", "condition": "pii_in_protected_layer",
                 "action": "block", "fault_code": "GOVERNANCE_RAW_PII", "severity": "critical",
                 "family": "semantic", "message": "PII in protected layer without anonymization.",
                 "remediation": ["Apply sha256 on PII columns"]},
                {"name": "require_partition", "condition": "missing_partition",
                 "action": "replan", "fault_code": "FINOPS_MISSING_PARTITION", "severity": "high",
                 "family": "semantic", "message": "High-volume dataset without partition.",
                 "remediation": ["Add partition_by column"]},
                {"name": "require_merge_key", "condition": "missing_merge_key",
                 "action": "block", "fault_code": "CONTRACT_MISSING_MERGE_KEY", "severity": "critical",
                 "family": "semantic", "message": "Silver/Gold write without merge key.",
                 "remediation": ["Set merge_key_required=True"]},
            ],
        }
    }
    (cfa_dir / "policies" / "prod-v1.yaml").write_text(
        json.dumps(prod_policy, indent=2), encoding="utf-8"
    )

    config = (
        "# CFA Configuration\n"
        "version: \"1.0\"\n"
        "\n"
        "storage:\n"
        "  backend: sqlite\n"
        "  path: cfa.db\n"
        "  retention_days: 90\n"
        "\n"
        "defaults:\n"
        f"  catalog: {cfa_dir / 'catalog.json'}\n"
        f"  policy_bundle: {cfa_dir / 'policies' / 'prod-v1.yaml'}\n"
        "  backend: pyspark\n"
    )
    (cfa_dir / "config.yaml").write_text(config, encoding="utf-8")

    (cfa_dir / ".gitignore").write_text("*\n!.gitignore\n", encoding="utf-8")

    print(f"CFA initialized in {cfa_dir}/")
    print("  config.yaml          — CFA configuration")
    print("  catalog.json         — example data catalog")
    print("  policies/prod-v1.yaml — production policy bundle")
    print(f"\nNext: cfa evaluate \"your intent\" --config {cfa_dir / 'config.yaml'}")
    return 0
