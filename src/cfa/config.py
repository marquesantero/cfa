"""CFA Configuration — centralized settings for all CFA commands."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class StorageConfig:
    backend: str = "sqlite"  # sqlite | jsonl
    path: str = "cfa.db"
    retention_days: int = 90


@dataclass
class DefaultsConfig:
    catalog: str = "catalog.yaml"
    policy_bundle: str = "policies/prod-v1.yaml"
    backend: str = "pyspark"


@dataclass
class CfaConfig:
    version: str = "1.0"
    storage: StorageConfig = field(default_factory=StorageConfig)
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)

    @classmethod
    def from_yaml(cls, path: str | Path) -> CfaConfig:
        raw = Path(path).read_text(encoding="utf-8")
        try:
            import yaml
            data = yaml.safe_load(raw)
        except ImportError:
            raise ImportError("PyYAML required for YAML config. Install: pip install pyyaml")
        return cls._from_dict(data or {}, str(path))

    @classmethod
    def from_json(cls, path: str | Path) -> CfaConfig:
        raw = Path(path).read_text(encoding="utf-8")
        data = json.loads(raw)
        return cls._from_dict(data, str(path))

    @classmethod
    def discover(cls, start: str | Path | None = None) -> CfaConfig | None:
        current = Path(start) if start else Path.cwd()
        for candidate in [current / "cfa.yaml", current / "cfa.yml", current / ".cfa" / "config.yaml"]:
            if candidate.exists():
                return cls.from_yaml(candidate)
        if (current / "cfa.json").exists():
            return cls.from_json(current / "cfa.json")
        return None

    @classmethod
    def _from_dict(cls, data: dict[str, Any], source: str = "") -> CfaConfig:
        storage_data = data.get("storage", {})
        storage = StorageConfig(
            backend=storage_data.get("backend", "sqlite"),
            path=storage_data.get("path", "cfa.db"),
            retention_days=storage_data.get("retention_days", 90),
        )
        defaults_data = data.get("defaults", {})
        defaults = DefaultsConfig(
            catalog=defaults_data.get("catalog", "catalog.yaml"),
            policy_bundle=defaults_data.get("policy_bundle", "policies/prod-v1.yaml"),
            backend=defaults_data.get("backend", "pyspark"),
        )
        return cls(version=data.get("version", "1.0"), storage=storage, defaults=defaults)

    def to_yaml(self) -> str:
        lines = [
            "# CFA Configuration",
            f"version: \"{self.version}\"",
            "",
            "storage:",
            f"  backend: {self.storage.backend}",
            f"  path: {self.storage.path}",
            f"  retention_days: {self.storage.retention_days}",
            "",
            "defaults:",
            f"  catalog: {self.defaults.catalog}",
            f"  policy_bundle: {self.defaults.policy_bundle}",
            f"  backend: {self.defaults.backend}",
        ]
        return "\n".join(lines) + "\n"

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "storage": {
                "backend": self.storage.backend,
                "path": self.storage.path,
                "retention_days": self.storage.retention_days,
            },
            "defaults": {
                "catalog": self.defaults.catalog,
                "policy_bundle": self.defaults.policy_bundle,
                "backend": self.defaults.backend,
            },
        }
