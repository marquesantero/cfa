"""Tests for StateSignature validation."""

from conftest import make_signature

from cfa.validation.signature import validate_signature_data


def test_accepts_valid_signature():
    result = validate_signature_data(make_signature().to_dict(), require_datasets=True)
    assert result.valid
    assert result.issues == []


def test_accepts_wrapped_signature():
    result = validate_signature_data({"signature": make_signature().to_dict()})
    assert result.valid


def test_rejects_unknown_target_layer():
    data = make_signature().to_dict()
    data["target_layer"] = "platinum"
    result = validate_signature_data(data)
    assert not result.valid
    assert any(i.path == "target_layer" for i in result.issues)


def test_rejects_invalid_dataset_classification():
    data = make_signature().to_dict()
    data["datasets"][0]["classification"] = "private"
    result = validate_signature_data(data)
    assert not result.valid
    assert any("classification" in i.path for i in result.issues)


def test_rejects_missing_execution_context():
    data = make_signature().to_dict()
    data.pop("execution_context")
    result = validate_signature_data(data)
    assert not result.valid
    assert any(i.path == "execution_context" for i in result.issues)
