"""Tests for agnostic CLI validation commands."""

import json
import tempfile
from pathlib import Path

from conftest import CATALOG, make_signature

from cfa.audit.hashing import hash_file_content, hash_governance_artifact
from cfa.cli import main


def test_catalog_validate_valid_json(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "catalog.json"
        path.write_text(json.dumps({
            "datasets": {
                "clientes": {
                    "classification": "sensitive",
                    "pii_columns": ["cpf"],
                    "size_gb": 1.0,
                }
            }
        }), encoding="utf-8")

        code = main(["catalog", "validate", str(path), "--require-datasets", "--format", "json"])
        out = json.loads(capsys.readouterr().out)
        assert code == 0
        assert out["valid"] is True
        assert out["issue_count"] == 0


def test_catalog_validate_invalid_json(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "catalog.json"
        path.write_text(json.dumps({"datasets": {"clientes": {"classification": "private"}}}), encoding="utf-8")

        code = main(["catalog", "validate", str(path), "--format", "json"])
        out = json.loads(capsys.readouterr().out)
        assert code == 1
        assert out["valid"] is False
        assert "classification" in out["issues"][0]["path"]


def test_policy_validate_valid_json(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "policy.json"
        path.write_text(json.dumps({
            "policy_bundle": {
                "version": "test-v1",
                "rules": [{
                    "name": "require_partition",
                    "condition": "missing_partition",
                    "action": "replan",
                    "fault_code": "TEST_MISSING_PARTITION",
                    "severity": "high",
                    "family": "semantic",
                    "message": "Partition required.",
                    "remediation": ["Add partition_by"],
                }],
            }
        }), encoding="utf-8")

        code = main(["policy", "validate", str(path), "--format", "json"])
        out = json.loads(capsys.readouterr().out)
        assert code == 0
        assert out["valid"] is True


def test_policy_validate_invalid_json(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "policy.json"
        path.write_text(json.dumps({
            "policy_bundle": {
                "version": "test-v1",
                "rules": [{
                    "name": "bad",
                    "condition": "missing_partition",
                    "action": "deny",
                    "fault_code": "BAD",
                    "severity": "high",
                    "message": "Bad action.",
                }],
            }
        }), encoding="utf-8")

        code = main(["policy", "validate", str(path), "--format", "json"])
        out = json.loads(capsys.readouterr().out)
        assert code == 1
        assert out["valid"] is False
        assert any("action" in issue["path"] for issue in out["issues"])


def test_policy_check_approves_signature_json(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "signature.json"
        path.write_text(json.dumps(make_signature().to_dict()), encoding="utf-8")

        code = main(["policy", "check", "--signature", str(path), "--format", "json", "--exit-code"])
        out = json.loads(capsys.readouterr().out)
        assert code == 0
        assert out["action"] == "approve"
        assert out["passed"] is True
        assert out["signature_hash"]


def test_policy_check_blocks_signature_json_with_exit_code(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        sig = make_signature(include_pii=True, no_pii_raw=False).to_dict()
        path = Path(tmp) / "signature.json"
        path.write_text(json.dumps({"signature": sig}), encoding="utf-8")

        code = main(["policy", "check", "--signature", str(path), "--format", "json", "--exit-code"])
        out = json.loads(capsys.readouterr().out)
        assert code == 1
        assert out["action"] == "block"
        assert out["passed"] is False
        assert any(f["code"] == "GOVERNANCE_PII_WITHOUT_POLICY" for f in out["faults"])


def test_policy_check_writes_audit_log(capsys):
    from cfa.audit.trail import AuditTrail, JsonLinesAuditStorage

    with tempfile.TemporaryDirectory() as tmp:
        sig_path = Path(tmp) / "signature.json"
        audit_path = Path(tmp) / "audit.jsonl"
        sig_path.write_text(json.dumps(make_signature().to_dict()), encoding="utf-8")

        code = main([
            "policy", "check",
            "--signature", str(sig_path),
            "--audit-log", str(audit_path),
            "--format", "json",
        ])
        out = json.loads(capsys.readouterr().out)
        assert code == 0
        assert out["schema_version"] == "cfa.policy_check.v1"
        assert out["decision_id"]
        assert len(out["audit_event_hash"]) == 64

        trail = AuditTrail(storage=JsonLinesAuditStorage(audit_path))
        events = trail.get_all_events()
        assert len(events) == 1
        assert events[0].stage == "policy_check"
        assert trail.verify_chain()


def test_audit_verify_file_from_policy_check(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        sig_path = Path(tmp) / "signature.json"
        audit_path = Path(tmp) / "audit.jsonl"
        sig = make_signature().to_dict()
        sig_path.write_text(json.dumps(sig), encoding="utf-8")

        assert main([
            "policy", "check",
            "--signature", str(sig_path),
            "--audit-log", str(audit_path),
        ]) == 0
        capsys.readouterr()

        code = main(["audit", "verify", "--file", str(audit_path)])
        output = capsys.readouterr().out
        assert code == 0
        assert "INTACT" in output


def test_audit_show_file_from_policy_check(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        sig_path = Path(tmp) / "signature.json"
        audit_path = Path(tmp) / "audit.jsonl"
        sig = make_signature().to_dict()
        sig_path.write_text(json.dumps(sig), encoding="utf-8")

        assert main([
            "policy", "check",
            "--signature", str(sig_path),
            "--audit-log", str(audit_path),
        ]) == 0
        capsys.readouterr()

        code = main([
            "audit", "show",
            "--id", sig["intent_id"],
            "--file", str(audit_path),
            "--format", "json",
        ])
        out = json.loads(capsys.readouterr().out)
        assert code == 0
        assert out["chain_intact"] is True
        assert len(out["events"]) == 1


def test_signature_validate_valid_json(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "signature.json"
        path.write_text(json.dumps(make_signature().to_dict()), encoding="utf-8")

        code = main(["signature", "validate", str(path), "--require-datasets", "--format", "json"])
        out = json.loads(capsys.readouterr().out)
        assert code == 0
        assert out["valid"] is True


def test_signature_validate_invalid_json(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        sig = make_signature().to_dict()
        sig["target_layer"] = "platinum"
        path = Path(tmp) / "signature.json"
        path.write_text(json.dumps(sig), encoding="utf-8")

        code = main(["signature", "validate", str(path), "--format", "json"])
        out = json.loads(capsys.readouterr().out)
        assert code == 1
        assert out["valid"] is False
        assert any(issue["path"] == "target_layer" for issue in out["issues"])


def test_policy_check_rejects_invalid_signature_before_policy(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        sig = make_signature().to_dict()
        sig["target_layer"] = "platinum"
        path = Path(tmp) / "signature.json"
        path.write_text(json.dumps(sig), encoding="utf-8")

        code = main(["policy", "check", "--signature", str(path), "--format", "json"])
        out = json.loads(capsys.readouterr().out)
        assert code == 1
        assert out["valid"] is False
        assert any(issue["path"] == "target_layer" for issue in out["issues"])


def test_policy_check_includes_catalog_hash(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        sig_path = Path(tmp) / "signature.json"
        cat_path = Path(tmp) / "catalog.json"
        sig_path.write_text(json.dumps(make_signature().to_dict()), encoding="utf-8")
        cat_path.write_text(json.dumps(CATALOG), encoding="utf-8")

        code = main([
            "policy", "check",
            "--signature", str(sig_path),
            "--catalog", str(cat_path),
            "--format", "json",
        ])
        out = json.loads(capsys.readouterr().out)
        assert code == 0
        assert len(out["catalog_hash"]) == 64
        assert out["catalog_hash"] == hash_governance_artifact(CATALOG)


def test_policy_check_includes_policy_bundle_hash(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        sig_path = Path(tmp) / "signature.json"
        pol_path = Path(tmp) / "policy.json"
        sig_path.write_text(json.dumps(make_signature().to_dict()), encoding="utf-8")
        pol_path.write_text(json.dumps({
            "policy_bundle": {
                "version": "test-v1",
                "rules": [{
                    "name": "require_partition",
                    "condition": "missing_partition",
                    "action": "replan",
                    "fault_code": "TEST_PARTITION",
                    "severity": "high",
                    "family": "semantic",
                    "message": "Partition required.",
                    "remediation": ["Add partition_by"],
                }],
            }
        }), encoding="utf-8")

        code = main([
            "policy", "check",
            "--signature", str(sig_path),
            "--policy-bundle", str(pol_path),
            "--format", "json",
        ])
        out = json.loads(capsys.readouterr().out)
        assert code == 0
        assert len(out["policy_bundle_hash"]) == 64
        assert out["policy_bundle_hash"] == hash_file_content(str(pol_path))


def test_policy_check_audit_includes_artifact_hashes(capsys):
    from cfa.audit.trail import AuditTrail, JsonLinesAuditStorage

    with tempfile.TemporaryDirectory() as tmp:
        sig_path = Path(tmp) / "signature.json"
        cat_path = Path(tmp) / "catalog.json"
        pol_path = Path(tmp) / "policy.json"
        audit_path = Path(tmp) / "audit.jsonl"

        sig_path.write_text(json.dumps(make_signature().to_dict()), encoding="utf-8")
        cat_path.write_text(json.dumps(CATALOG), encoding="utf-8")
        pol_path.write_text(json.dumps({
            "policy_bundle": {
                "version": "test-v1",
                "rules": [{
                    "name": "require_partition",
                    "condition": "missing_partition",
                    "action": "replan",
                    "fault_code": "TEST_PARTITION",
                    "severity": "high",
                    "family": "semantic",
                    "message": "Partition required.",
                    "remediation": ["Add partition_by"],
                }],
            }
        }), encoding="utf-8")

        code = main([
            "policy", "check",
            "--signature", str(sig_path),
            "--catalog", str(cat_path),
            "--policy-bundle", str(pol_path),
            "--audit-log", str(audit_path),
            "--format", "json",
        ])
        out = json.loads(capsys.readouterr().out)
        assert code == 0

        trail = AuditTrail(storage=JsonLinesAuditStorage(audit_path))
        events = trail.get_all_events()
        assert len(events) == 1
        assert events[0].details.get("catalog_hash") == out["catalog_hash"]
        assert events[0].details.get("policy_bundle_hash") == out["policy_bundle_hash"]
        assert trail.verify_chain()


def test_policy_check_strict_blocks_dataset_not_in_catalog(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        sig = make_signature().to_dict()
        sig["datasets"][0]["name"] = "dataset_inexistente"
        sig_path = Path(tmp) / "signature.json"
        cat_path = Path(tmp) / "catalog.json"
        sig_path.write_text(json.dumps(sig), encoding="utf-8")
        cat_path.write_text(json.dumps(CATALOG), encoding="utf-8")

        code = main([
            "policy", "check",
            "--signature", str(sig_path),
            "--catalog", str(cat_path),
            "--strict",
            "--format", "json",
        ])
        out = json.loads(capsys.readouterr().out)
        assert code == 1
        assert out["valid"] is False
        assert any("not found in catalog" in issue["message"] for issue in out["issues"])


def test_policy_check_strict_blocks_misclassified_dataset(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        sig = make_signature().to_dict()
        sig["datasets"][0]["classification"] = "public"
        sig_path = Path(tmp) / "signature.json"
        cat_path = Path(tmp) / "catalog.json"
        sig_path.write_text(json.dumps(sig), encoding="utf-8")
        cat_path.write_text(json.dumps(CATALOG), encoding="utf-8")

        code = main([
            "policy", "check",
            "--signature", str(sig_path),
            "--catalog", str(cat_path),
            "--strict",
            "--format", "json",
        ])
        out = json.loads(capsys.readouterr().out)
        assert code == 1
        assert any("classification" in issue["path"] for issue in out["issues"])


def test_policy_check_strict_passes_consistent_signature(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        sig = make_signature().to_dict()
        sig_path = Path(tmp) / "signature.json"
        cat_path = Path(tmp) / "catalog.json"
        sig_path.write_text(json.dumps(sig), encoding="utf-8")
        cat_path.write_text(json.dumps(CATALOG), encoding="utf-8")

        code = main([
            "policy", "check",
            "--signature", str(sig_path),
            "--catalog", str(cat_path),
            "--strict",
            "--format", "json",
        ])
        out = json.loads(capsys.readouterr().out)
        assert code == 0
        assert out["passed"] is True
