"""Tests for governance artifact hashing."""

import tempfile
from pathlib import Path

from cfa.audit.hashing import hash_file_content, hash_governance_artifact


def test_hash_deterministic():
    a = hash_governance_artifact({"datasets": {"nfe": {"classification": "internal"}}})
    b = hash_governance_artifact({"datasets": {"nfe": {"classification": "internal"}}})
    assert a == b
    assert len(a) == 64


def test_hash_changes_with_content():
    a = hash_governance_artifact({"datasets": {"nfe": {"classification": "internal"}}})
    b = hash_governance_artifact({"datasets": {"nfe": {"classification": "sensitive"}}})
    assert a != b


def test_hash_none():
    assert hash_governance_artifact(None) == ""


def test_hash_file_content():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.json"
        path.write_text('{"key":"value"}', encoding="utf-8")
        h1 = hash_file_content(str(path))
        h2 = hash_file_content(str(path))
        assert h1 == h2
        assert len(h1) == 64


def test_hash_file_content_detects_changes():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.json"
        path.write_text('{"key":"value"}', encoding="utf-8")
        h1 = hash_file_content(str(path))
        path.write_text('{"key":"other"}', encoding="utf-8")
        h2 = hash_file_content(str(path))
        assert h1 != h2
