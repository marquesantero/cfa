"""End-to-end integration tests — complete CFA governance flow.

Exercises: catalog → signature → policy check → audit → verify → storage → lifecycle
"""

import json
import tempfile
from pathlib import Path

from cfa.cli import main


def _write_catalog(directory: Path) -> Path:
    path = directory / "catalog.json"
    path.write_text(json.dumps({
        "datasets": {
            "nfe": {
                "classification": "high_volume", "size_gb": 4000,
                "pii_columns": [], "partition_column": "processing_date",
                "merge_keys": ["nfe_id"],
            },
            "clientes": {
                "classification": "sensitive", "size_gb": 0.5,
                "pii_columns": ["cpf", "email"], "partition_column": "processing_date",
                "merge_keys": ["cliente_id"],
            },
        }
    }), encoding="utf-8")
    return path


def _write_policy(directory: Path) -> Path:
    path = directory / "policy.json"
    path.write_text(json.dumps({
        "policy_bundle": {
            "version": "test-v1.0",
            "rules": [
                {"name": "forbid_raw_pii", "condition": "pii_in_protected_layer",
                 "action": "block", "fault_code": "GOVERNANCE_RAW_PII", "severity": "critical",
                 "family": "semantic", "message": "PII in protected layer.", "remediation": ["hash PII"]},
                {"name": "require_partition", "condition": "missing_partition",
                 "action": "replan", "fault_code": "FINOPS_MISSING_PARTITION", "severity": "high",
                 "family": "semantic", "message": "Missing partition.", "remediation": ["add partition"]},
                {"name": "require_merge", "condition": "missing_merge_key",
                 "action": "block", "fault_code": "CONTRACT_MISSING_MERGE_KEY", "severity": "critical",
                 "family": "semantic", "message": "Missing merge key.", "remediation": ["add merge key"]},
            ],
        }
    }), encoding="utf-8")
    return path


def _write_safe_signature(directory: Path) -> Path:
    path = directory / "signature_safe.json"
    path.write_text(json.dumps({
        "domain": "fiscal",
        "intent": "reconciliation",
        "target_layer": "silver",
        "datasets": [
            {"name": "nfe", "classification": "high_volume", "size_gb": 4000,
             "pii_columns": [], "partition_column": "processing_date", "merge_keys": ["nfe_id"]},
            {"name": "clientes", "classification": "sensitive", "size_gb": 0.5,
             "pii_columns": ["cpf", "email"], "partition_column": "processing_date", "merge_keys": ["cliente_id"]},
        ],
        "constraints": {"no_pii_raw": True, "merge_key_required": True,
                         "enforce_types": True, "partition_by": ["processing_date"]},
        "execution_context": {"policy_bundle_version": "test", "catalog_snapshot_version": "v1",
                               "context_registry_version_id": "ctx1"},
    }), encoding="utf-8")
    return path


def _write_unsafe_signature(directory: Path) -> Path:
    path = directory / "signature_unsafe.json"
    path.write_text(json.dumps({
        "domain": "fiscal", "intent": "reconciliation", "target_layer": "gold",
        "datasets": [
            {"name": "clientes", "classification": "sensitive", "size_gb": 0.5,
             "pii_columns": ["cpf", "email"], "partition_column": "processing_date", "merge_keys": ["cliente_id"]},
        ],
        "constraints": {"no_pii_raw": False, "merge_key_required": False,
                         "enforce_types": True, "partition_by": []},
        "execution_context": {"policy_bundle_version": "test", "catalog_snapshot_version": "v1",
                               "context_registry_version_id": "ctx1"},
    }), encoding="utf-8")
    return path


class TestEndToEndFlow:
    """Complete governance flow: catalog → signature → policy → audit → lifecycle."""

    def test_01_catalog_validate(self, capsys):
        with tempfile.TemporaryDirectory() as tmp:
            cat = _write_catalog(Path(tmp))
            code = main(["catalog", "validate", str(cat), "--require-datasets", "--format", "json"])
            out = json.loads(capsys.readouterr().out)
            assert code == 0
            assert out["valid"] is True

    def test_02_signature_validate(self, capsys):
        with tempfile.TemporaryDirectory() as tmp:
            sig = _write_safe_signature(Path(tmp))
            code = main(["signature", "validate", str(sig), "--require-datasets", "--format", "json"])
            out = json.loads(capsys.readouterr().out)
            assert code == 0
            assert out["valid"] is True

    def test_03_policy_validate(self, capsys):
        with tempfile.TemporaryDirectory() as tmp:
            pol = _write_policy(Path(tmp))
            code = main(["policy", "validate", str(pol), "--format", "json"])
            out = json.loads(capsys.readouterr().out)
            assert code == 0
            assert out["valid"] is True

    def test_04_policy_check_safe_approves(self, capsys):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            sig = _write_safe_signature(d)
            pol = _write_policy(d)
            cat = _write_catalog(d)
            code = main([
                "policy", "check",
                "--signature", str(sig),
                "--policy-bundle", str(pol),
                "--catalog", str(cat),
                "--strict",
                "--format", "json",
            ])
            out = json.loads(capsys.readouterr().out)
            assert code == 0
            assert out["action"] == "approve"
            assert out["passed"] is True

    def test_05_policy_check_unsafe_blocks(self, capsys):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            sig = _write_unsafe_signature(d)
            pol = _write_policy(d)
            code = main([
                "policy", "check",
                "--signature", str(sig),
                "--policy-bundle", str(pol),
                "--format", "json",
                "--exit-code",
            ])
            out = json.loads(capsys.readouterr().out)
            assert code == 1
            assert out["action"] == "block"
            assert out["passed"] is False

    def test_06_policy_check_with_audit(self, capsys):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            sig = _write_safe_signature(d)
            pol = _write_policy(d)
            audit_path = d / "audit.jsonl"

            # Run checks
            code1 = main([
                "policy", "check", "--signature", str(sig),
                "--policy-bundle", str(pol), "--audit-log", str(audit_path), "--format", "json",
            ])
            out1 = json.loads(capsys.readouterr().out)
            assert code1 == 0
            assert len(out1["audit_event_hash"]) == 64

            # Run again against unsafe signature
            capsys.readouterr()  # clear
            sig_unsafe = _write_unsafe_signature(d)
            code2 = main([
                "policy", "check", "--signature", str(sig_unsafe),
                "--policy-bundle", str(pol), "--audit-log", str(audit_path),
                "--format", "json", "--exit-code",
            ])
            out2 = json.loads(capsys.readouterr().out)
            assert code2 != 0
            assert out2["action"] == "block"

            # Verify audit chain
            code3 = main(["audit", "verify", "--file", str(audit_path)])
            output3 = capsys.readouterr().out
            assert code3 == 0
            assert "INTACT" in output3

    def test_07_storage_management(self, capsys):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            db_path = d / "cfa.db"
            audit_path = d / "audit.jsonl"
            sig = _write_safe_signature(d)
            pol = _write_policy(d)

            from cfa.storage import SqliteStorage
            store = SqliteStorage(db_path)
            store.ensure_schema()

            # Generate audit data via policy check
            for _ in range(2):
                main([
                    "policy", "check", "--signature", str(sig),
                    "--policy-bundle", str(pol),
                    "--audit-log", str(audit_path),
                ])
                capsys.readouterr()

            # Verify audit log exists and has data
            assert audit_path.exists()
            content = audit_path.read_text(encoding="utf-8")
            assert len(content) > 0

            # Verify storage stats via SQLite works separately
            store.execution_append({
                "signature_hash": "abc", "timestamp": "2026-01-01T00:00:00",
                "success": True, "replanned": False, "cost_dbu": 5.0,
                "duration_seconds": 10.0, "faults": [],
                "schema_match": True, "pii_exposure": False,
                "policy_compliant": True, "layer_adherent": True,
            })
            store.close()

            code = main(["storage", "stats", "--db", str(db_path), "--format", "json"])
            stats = json.loads(capsys.readouterr().out)
            assert code == 0
            assert stats["execution_records_count"] >= 1

    def test_08_full_workflow_via_python_api(self):
        """End-to-end via Python API: catalog → signature → policy check → audit."""
        from cfa.policy.bundle import validate_policy_bundle_data
        from cfa.policy.catalog import validate_catalog
        from cfa.policy.engine import PolicyEngine
        from cfa.types import (
            PolicyAction,
            StateSignature,
        )
        from cfa.validate.signature import validate_signature_data

        catalog = {
            "datasets": {
                "nfe": {"classification": "high_volume", "size_gb": 4000, "pii_columns": [],
                         "partition_column": "processing_date", "merge_keys": ["nfe_id"]},
                "clientes": {"classification": "sensitive", "size_gb": 0.5,
                              "pii_columns": ["cpf", "email"], "partition_column": "processing_date",
                              "merge_keys": ["cliente_id"]},
            }
        }

        policy_data = {
            "policy_bundle": {
                "version": "test",
                "rules": [
                    {"name": "forbid_pii", "condition": "pii_in_protected_layer",
                     "action": "block", "fault_code": "PII_BLOCK", "severity": "critical",
                     "family": "semantic", "message": "PII blocked.", "remediation": ["hash"]},
                ],
            }
        }

        sig_dict = {
            "domain": "fiscal", "intent": "reconciliation", "target_layer": "silver",
            "datasets": [
                {"name": "nfe", "classification": "high_volume", "size_gb": 4000,
                 "pii_columns": [], "partition_column": "processing_date", "merge_keys": ["nfe_id"]},
                {"name": "clientes", "classification": "sensitive", "size_gb": 0.5,
                 "pii_columns": ["cpf", "email"], "partition_column": "processing_date", "merge_keys": ["cliente_id"]},
            ],
            "constraints": {"no_pii_raw": True, "merge_key_required": True,
                             "enforce_types": True, "partition_by": ["processing_date"]},
            "execution_context": {"policy_bundle_version": "t", "catalog_snapshot_version": "t",
                                   "context_registry_version_id": "t"},
        }

        # Validate catalog
        assert validate_catalog(catalog, require_datasets=True).valid

        # Validate policy
        assert validate_policy_bundle_data(policy_data).valid

        # Validate signature
        assert validate_signature_data(sig_dict, require_datasets=True).valid

        # Build and evaluate
        signature = StateSignature.from_dict(sig_dict)
        engine = PolicyEngine()
        result = engine.evaluate(signature)

        # With PII protected and merge key set, should approve
        assert result.action == PolicyAction.APPROVE
