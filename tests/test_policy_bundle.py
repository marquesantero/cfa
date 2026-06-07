"""Tests for policy bundle validation and loading."""

import json
import tempfile
from pathlib import Path

import pytest

from cfa.policy.bundle import PolicyBundle, validate_policy_bundle_data

VALID_BUNDLE = {
    "policy_bundle": {
        "version": "test-v1.0",
        "rules": [
            {
                "name": "require_partition",
                "condition": "missing_partition",
                "action": "replan",
                "fault_code": "TEST_MISSING_PARTITION",
                "severity": "high",
                "family": "semantic",
                "message": "Partition is required.",
                "min_size_gb": 1.0,
                "remediation": ["Add partition_by."],
            }
        ],
    }
}


class TestPolicyBundleValidation:
    def test_accepts_valid_bundle(self):
        result = validate_policy_bundle_data(VALID_BUNDLE)
        assert result.valid
        assert result.issues == []

    def test_rejects_empty_bundle(self):
        result = validate_policy_bundle_data(None)
        assert not result.valid
        assert "policy_bundle: file is empty" in result.messages

    def test_rejects_unknown_condition(self):
        data = json.loads(json.dumps(VALID_BUNDLE))
        data["policy_bundle"]["rules"][0]["condition"] = "not_registered"
        result = validate_policy_bundle_data(data)
        assert not result.valid
        assert any("unknown condition" in msg for msg in result.messages)

    def test_rejects_invalid_enums(self):
        data = json.loads(json.dumps(VALID_BUNDLE))
        rule = data["policy_bundle"]["rules"][0]
        rule["action"] = "deny"
        rule["severity"] = "urgent"
        result = validate_policy_bundle_data(data)
        assert not result.valid
        assert any("action" in msg for msg in result.messages)
        assert any("severity" in msg for msg in result.messages)

    def test_rejects_duplicate_fault_codes(self):
        data = json.loads(json.dumps(VALID_BUNDLE))
        duplicate = json.loads(json.dumps(data["policy_bundle"]["rules"][0]))
        duplicate["name"] = "require_partition_duplicate"
        data["policy_bundle"]["rules"].append(duplicate)
        result = validate_policy_bundle_data(data)
        assert not result.valid
        assert any("duplicate fault code" in msg for msg in result.messages)


class TestPolicyBundleLoading:
    def test_from_json_loads_valid_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            path.write_text(json.dumps(VALID_BUNDLE), encoding="utf-8")
            bundle = PolicyBundle.from_json(path)
            assert bundle.version == "test-v1.0"
            assert len(bundle.rules) == 1

    def test_from_json_rejects_invalid_bundle(self):
        data = json.loads(json.dumps(VALID_BUNDLE))
        data["policy_bundle"]["rules"][0].pop("fault_code")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with pytest.raises(ValueError, match="fault_code"):
                PolicyBundle.from_json(path)
