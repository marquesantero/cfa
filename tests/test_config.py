"""Tests for CFA config and status."""

import json
import tempfile
from pathlib import Path

from cfa.config import CfaConfig


def test_config_defaults():
    config = CfaConfig()
    assert config.version == "1.0"
    assert config.storage.backend == "sqlite"
    assert config.storage.retention_days == 90
    assert config.defaults.backend == "pyspark"


def test_config_from_dict():
    config = CfaConfig._from_dict({
        "version": "1.0",
        "storage": {"backend": "jsonl", "path": "data/", "retention_days": 30},
        "defaults": {"catalog": "my_catalog.yaml", "policy_bundle": "my_policy.yaml", "backend": "dbt"},
    })
    assert config.storage.backend == "jsonl"
    assert config.storage.retention_days == 30
    assert config.defaults.catalog == "my_catalog.yaml"


def test_config_to_dict():
    config = CfaConfig()
    d = config.to_dict()
    assert d["version"] == "1.0"
    assert d["storage"]["backend"] == "sqlite"


def test_config_discover():
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "cfa.yaml").write_text(
            "version: \"1.0\"\nstorage:\n  backend: jsonl\n  path: test/\n  retention_days: 30\n"
            "defaults:\n  catalog: cat.yaml\n  policy_bundle: pol.yaml\n  backend: sql\n",
            encoding="utf-8",
        )
        config = CfaConfig.discover(tmp)
        assert config is not None
        assert config.storage.backend == "jsonl"
        assert config.defaults.backend == "sql"


def test_config_discover_none():
    config = CfaConfig.discover("/nonexistent")
    assert config is None


def test_cli_status_no_config(capsys):
    from cfa.cli import main
    main(["status", "--format", "json"])
    out = json.loads(capsys.readouterr().out)
    assert out["config_found"] is False


def test_cli_status_with_config(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        config_path = Path(tmp) / "cfa.yaml"
        config_path.write_text(
            "version: \"1.0\"\nstorage:\n  backend: sqlite\n  path: test.db\n  retention_days: 90\n"
            "defaults:\n  catalog: cat.yaml\n  policy_bundle: pol.yaml\n  backend: pyspark\n",
            encoding="utf-8",
        )
        from cfa.cli import main
        code = main(["status", "--config", str(config_path), "--format", "json"])
        out = json.loads(capsys.readouterr().out)
        assert code == 0
        assert out["config_found"] is True
        assert out["storage"]["backend"] == "sqlite"
