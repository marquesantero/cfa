"""
CFA Context Registry
====================
Live model of the environment state.
Not an execution log — represents "what state is the data in right now".

Phase 1: in-memory implementation.
Phase 4: persistent backend (JSON file) + snapshot versioning.

The Context Registry is consulted before every intent (Invariant I3)
and updated after every execution (Invariant I4).
"""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .types import _utcnow


# ── Storage Backend ─────────────────────────────────────────────────────────


class ContextStorageBackend(ABC):
    """Extension point: pluggable persistence for the Context Registry."""

    @abstractmethod
    def load(self) -> dict[str, Any]:
        """Load full state from storage. Returns empty dict if no state exists."""
        ...

    @abstractmethod
    def save(self, state: dict[str, Any]) -> None:
        """Persist full state to storage."""
        ...

    @abstractmethod
    def save_snapshot(self, version_id: str, state: dict[str, Any]) -> None:
        """Save a versioned snapshot (Invariant I8 — reproducibility)."""
        ...

    @abstractmethod
    def load_snapshot(self, version_id: str) -> dict[str, Any] | None:
        """Load a specific snapshot by version_id."""
        ...

    @abstractmethod
    def list_snapshots(self) -> list[str]:
        """List all available snapshot version_ids."""
        ...


class InMemoryContextStorage(ContextStorageBackend):
    """In-memory storage for testing."""

    def __init__(self) -> None:
        self._state: dict[str, Any] = {}
        self._snapshots: dict[str, dict[str, Any]] = {}

    def load(self) -> dict[str, Any]:
        return dict(self._state)

    def save(self, state: dict[str, Any]) -> None:
        self._state = dict(state)

    def save_snapshot(self, version_id: str, state: dict[str, Any]) -> None:
        self._snapshots[version_id] = dict(state)

    def load_snapshot(self, version_id: str) -> dict[str, Any] | None:
        return self._snapshots.get(version_id)

    def list_snapshots(self) -> list[str]:
        return list(self._snapshots.keys())


class JsonFileContextStorage(ContextStorageBackend):
    """
    JSON file-based persistent storage.
    - Current state: {base_path}/context_state.json
    - Snapshots: {base_path}/snapshots/{version_id}.json
    """

    def __init__(self, base_path: str | Path) -> None:
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._snapshots_dir = self.base_path / "snapshots"
        self._snapshots_dir.mkdir(exist_ok=True)

    def _state_file(self) -> Path:
        return self.base_path / "context_state.json"

    def load(self) -> dict[str, Any]:
        path = self._state_file()
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def save(self, state: dict[str, Any]) -> None:
        self._state_file().write_text(
            json.dumps(state, indent=2, default=str), encoding="utf-8"
        )

    def save_snapshot(self, version_id: str, state: dict[str, Any]) -> None:
        path = self._snapshots_dir / f"{version_id}.json"
        path.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")

    def load_snapshot(self, version_id: str) -> dict[str, Any] | None:
        path = self._snapshots_dir / f"{version_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list_snapshots(self) -> list[str]:
        return sorted(p.stem for p in self._snapshots_dir.glob("*.json"))


# ── Context Registry ────────────────────────────────────────────────────────


@dataclass
class ContextRegistry:
    """
    Context Registry for the CFA Kernel.

    Consulted by the Intent Normalizer before every intent (Invariant I3).
    Updated by the State Projection Protocol after every execution (Invariant I4).

    Supports pluggable persistence backends and snapshot versioning.
    """

    _datasets: dict[str, dict[str, Any]] = field(default_factory=dict)
    _execution_history: list[dict[str, Any]] = field(default_factory=list)
    _version_id: str = "v_initial"
    _storage: ContextStorageBackend = field(default_factory=InMemoryContextStorage)

    def __post_init__(self) -> None:
        # Try to restore from persistent storage
        saved = self._storage.load()
        if saved:
            self._datasets = saved.get("datasets", {})
            self._execution_history = saved.get("execution_history", [])
            self._version_id = saved.get("version_id", self._version_id)

    @property
    def version_id(self) -> str:
        return self._version_id

    def get_environment_state(self) -> dict[str, Any]:
        return {
            "datasets": dict(self._datasets),
            "execution_history": list(self._execution_history),
            "version_id": self._version_id,
        }

    def get_dataset_state(self, name: str) -> dict[str, Any] | None:
        return self._datasets.get(name)

    def set_dataset_state(self, name: str, state: dict[str, Any]) -> None:
        self._datasets[name] = state
        self._bump_version()
        self._persist()

    def record_execution(
        self, intent_id: str, outcome: str, signature_hash: str
    ) -> None:
        self._execution_history.append(
            {
                "intent_id": intent_id,
                "outcome": outcome,
                "signature_hash": signature_hash,
                "timestamp": _utcnow().isoformat(),
                "version_id": self._version_id,
            }
        )
        self._persist()

    def snapshot(self) -> str:
        """Create a versioned snapshot of the current state (Invariant I8)."""
        state = self.get_environment_state()
        self._storage.save_snapshot(self._version_id, state)
        return self._version_id

    def restore_snapshot(self, version_id: str) -> bool:
        """Restore state from a specific snapshot. Returns False if not found."""
        saved = self._storage.load_snapshot(version_id)
        if saved is None:
            return False
        self._datasets = saved.get("datasets", {})
        self._execution_history = saved.get("execution_history", [])
        self._version_id = saved.get("version_id", version_id)
        self._persist()
        return True

    def list_snapshots(self) -> list[str]:
        return self._storage.list_snapshots()

    def _bump_version(self) -> None:
        self._version_id = f"v_{uuid.uuid4().hex[:8]}"

    def _persist(self) -> None:
        self._storage.save(self.get_environment_state())
