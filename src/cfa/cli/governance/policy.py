"""cfa policy — evaluate and validate policy bundles."""

from __future__ import annotations

import uuid
from pathlib import Path

from .._helpers import load_catalog, load_policy, load_structured_file


def _cross_validate_signature_against_catalog(signature, catalog: dict) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    catalog_datasets = catalog.get("datasets", {})
    if not isinstance(catalog_datasets, dict):
        errors.append({"path": "catalog.datasets", "message": "must be an object keyed by dataset name"})
        return errors
    for idx, ds in enumerate(signature.datasets):
        base = f"signature.datasets[{idx}]"
        cat_entry = catalog_datasets.get(ds.name)
        if cat_entry is None:
            errors.append({"path": f"{base}.name", "message": f"dataset '{ds.name}' not found in catalog"})
            continue
        if not isinstance(cat_entry, dict):
            errors.append({"path": f"{base}.name", "message": f"catalog entry for '{ds.name}' is not an object"})
            continue
        cat_classification = cat_entry.get("classification", "internal")
        if ds.classification.value != cat_classification:
            errors.append({"path": f"{base}.classification", "message": f"signature says '{ds.classification.value}' but catalog says '{cat_classification}'"})
        cat_pii = set(cat_entry.get("pii_columns", []))
        sig_pii = set(ds.pii_columns)
        if cat_pii - sig_pii:
            errors.append({"path": f"{base}.pii_columns", "message": f"signature missing PII columns from catalog: {sorted(cat_pii - sig_pii)}"})
        if sig_pii - cat_pii:
            errors.append({"path": f"{base}.pii_columns", "message": f"signature declares PII columns not in catalog: {sorted(sig_pii - cat_pii)}"})
        cat_partition = cat_entry.get("partition_column")
        if cat_partition and ds.partition_column and cat_partition != ds.partition_column:
            errors.append({"path": f"{base}.partition_column", "message": f"signature says '{ds.partition_column}' but catalog says '{cat_partition}'"})
    return errors


def cmd_policy_check(args) -> int:
    from cfa.audit.hashing import hash_file_content, hash_governance_artifact
    from cfa.audit.trail import AuditTrail, JsonLinesAuditStorage
    from cfa.cli.formatters import format_json
    from cfa.policy.engine import PolicyEngine
    from cfa.types import PolicyAction, StateSignature
    from cfa.validate.signature import unwrap_signature_data, validate_signature_data

    data = load_structured_file(args.signature, "Error: PyYAML required for YAML signatures.")
    validation = validate_signature_data(data, require_datasets=args.require_datasets)
    if not validation.valid:
        output = {"signature": args.signature, "valid": False, "issue_count": len(validation.issues), "issues": [{"path": i.path, "message": i.message} for i in validation.issues]}
        if args.format == "json": print(format_json(output))
        else:
            print(f"StateSignature INVALID: {args.signature}")
            for msg in validation.messages: print(f"  - {msg}")
        return 1

    signature_data = unwrap_signature_data(data)
    signature = StateSignature.from_dict(signature_data)
    catalog = load_catalog(args.catalog)

    if args.strict and catalog:
        strict_errors = _cross_validate_signature_against_catalog(signature, catalog)
        if strict_errors:
            output = {"signature": args.signature, "valid": False, "issue_count": len(strict_errors), "issues": strict_errors}
            if args.format == "json": print(format_json(output))
            else:
                print(f"StateSignature/catalog mismatch: {args.signature}")
                for issue in strict_errors: print(f"  - {issue['path']}: {issue['message']}")
            return 1

    policy_rules, bundle_version = load_policy(args.policy_bundle)
    engine = PolicyEngine(rules=policy_rules, policy_bundle_version=bundle_version)
    result = engine.evaluate(signature)
    decision_id = str(uuid.uuid4())

    catalog_hash = hash_governance_artifact(catalog) if catalog else ""
    policy_bundle_hash = ""
    if Path(args.policy_bundle).suffix in (".yaml", ".yml", ".json"):
        policy_bundle_hash = hash_file_content(args.policy_bundle)

    faults = [{"code": f.code, "severity": f.severity.value, "family": f.family.value, "message": f.message, "remediation": list(f.remediation)} for f in result.faults]
    audit_event_hash = ""
    if args.audit_log:
        audit = AuditTrail(storage=JsonLinesAuditStorage(args.audit_log))
        event = audit.record(intent_id=signature.intent_id, stage="policy_check", event_type="policy_evaluation", outcome=result.action.value, policy_bundle_version=engine.policy_bundle_version, decision_id=decision_id, signature_hash=signature.signature_hash, catalog_hash=catalog_hash, policy_bundle_hash=policy_bundle_hash, faults=[f["code"] for f in faults], interventions=result.interventions, reasoning=result.reasoning)
        audit_event_hash = event.event_hash

    output = {"schema_version": "cfa.policy_check.v1", "decision_id": decision_id, "signature_hash": signature.signature_hash, "policy_bundle": engine.policy_bundle_version, "catalog_hash": catalog_hash, "policy_bundle_hash": policy_bundle_hash, "action": result.action.value, "passed": result.action == PolicyAction.APPROVE, "faults": faults, "interventions": result.interventions, "reasoning": result.reasoning, "audit_event_hash": audit_event_hash}

    if args.format == "json":
        print(format_json(output))
    else:
        print(f"Policy check {result.action.value.upper()}: {args.signature}")
        print(f"  decision_id:        {decision_id}")
        print(f"  signature_hash:     {signature.signature_hash}")
        print(f"  policy_bundle:      {engine.policy_bundle_version}")
        if catalog_hash: print(f"  catalog_hash:       {catalog_hash}")
        if policy_bundle_hash: print(f"  policy_bundle_hash: {policy_bundle_hash}")
        if audit_event_hash: print(f"  audit_hash:         {audit_event_hash}")
        if result.reasoning: print(f"  reasoning:          {result.reasoning}")
        for fault in faults: print(f"  - [{fault['severity']}] {fault['code']}: {fault['message']}")
    return 1 if (args.exit_code and result.action != PolicyAction.APPROVE) else 0


def cmd_policy_validate(args) -> int:
    from cfa.cli.formatters import format_json
    from cfa.policy.bundle import validate_policy_bundle_data

    data = load_structured_file(args.path, "Error: PyYAML required for YAML policy bundles.")
    result = validate_policy_bundle_data(data)
    output = {"path": args.path, "valid": result.valid, "issue_count": len(result.issues), "issues": [{"path": i.path, "message": i.message} for i in result.issues]}
    if args.format == "json": print(format_json(output))
    else:
        status = "VALID" if result.valid else "INVALID"
        print(f"Policy bundle {status}: {args.path}")
        for msg in result.messages: print(f"  - {msg}")
    return 0 if result.valid else 1
