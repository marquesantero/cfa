"""
CFA Audit Trail
================
Append-only, causally ordered record of all decision events.

Phase 1: in-memory list.
Phase 4: persistent backend (JSON Lines file, extensible to S3/Kafka/OpenLineage).

Properties (Invariant I5):
- Immutable after write
- Causal ordering per intent_id
- Complete per intent (start and end recorded)
- Cryptographic hash chain for tamper detection
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .types import _utcnow


@dataclass
class AuditEvent:
    """Single typed event in the audit trail."""

    intent_id: str
    stage: str
    event_type: str
    outcome: str
    policy_bundle_version: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: _utcnow().isoformat())
    event_hash: str = ""
    previous_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── Audit Storage Backend ───────────────────────────────────────────────────


class AuditStorageBackend(ABC):
    """Extension point: pluggable persistence for audit events."""

    @abstractmethod
    def append(self, event: AuditEvent) -> None: ...

    @abstractmethod
    def load_all(self) -> list[AuditEvent]: ...

    @abstractmethod
    def load_by_intent(self, intent_id: str) -> list[AuditEvent]: ...


class InMemoryAuditStorage(AuditStorageBackend):
    """In-memory storage for testing."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> None:
        self._events.append(event)

    def load_all(self) -> list[AuditEvent]:
        return list(self._events)

    def load_by_intent(self, intent_id: str) -> list[AuditEvent]:
        return [e for e in self._events if e.intent_id == intent_id]


class JsonLinesAuditStorage(AuditStorageBackend):
    """
    JSON Lines file-based persistent audit storage.
    Each line is a JSON-serialized AuditEvent.
    Append-only — never modifies existing lines (Invariant I5).
    """

    def __init__(self, file_path: str | Path) -> None:
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: AuditEvent) -> None:
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), default=str) + "\n")

    def load_all(self) -> list[AuditEvent]:
        if not self.file_path.exists():
            return []
        events = []
        for line in self.file_path.read_text(encoding="utf-8").strip().splitlines():
            if line:
                data = json.loads(line)
                events.append(AuditEvent(**data))
        return events

    def load_by_intent(self, intent_id: str) -> list[AuditEvent]:
        return [e for e in self.load_all() if e.intent_id == intent_id]


# ── Audit Trail ─────────────────────────────────────────────────────────────


class AuditTrail:
    """
    Append-only audit trail with hash chain.

    Two consumption modes (per whitepaper):
    - Operational (engineering): JSON, debugging, tuning
    - Regulatory (audit): normalized + cryptographic hash chain

    The hash chain ensures tamper detection: each event's hash
    includes the previous event's hash, creating a causal chain.
    """

    def __init__(self, storage: AuditStorageBackend | None = None) -> None:
        self._storage = storage or InMemoryAuditStorage()
        self._last_hash = ""
        # Restore hash chain from existing events
        existing = self._storage.load_all()
        if existing:
            self._last_hash = existing[-1].event_hash

    def record(
        self,
        intent_id: str,
        stage: str,
        event_type: str,
        outcome: str,
        policy_bundle_version: str = "",
        **details: Any,
    ) -> AuditEvent:
        event = AuditEvent(
            intent_id=intent_id,
            stage=stage,
            event_type=event_type,
            outcome=outcome,
            policy_bundle_version=policy_bundle_version,
            details=details,
            previous_hash=self._last_hash,
        )
        # Compute hash chain
        event.event_hash = self._compute_hash(event)
        self._last_hash = event.event_hash
        self._storage.append(event)
        return event

    def get_events_for_intent(self, intent_id: str) -> list[AuditEvent]:
        return self._storage.load_by_intent(intent_id)

    def get_all_events(self) -> list[AuditEvent]:
        return self._storage.load_all()

    @property
    def event_count(self) -> int:
        return len(self._storage.load_all())

    def verify_chain(self) -> bool:
        """Verify the integrity of the hash chain. Returns True if valid."""
        events = self._storage.load_all()
        prev_hash = ""
        for event in events:
            if event.previous_hash != prev_hash:
                return False
            expected = self._compute_hash(event)
            if event.event_hash != expected:
                return False
            prev_hash = event.event_hash
        return True

    @staticmethod
    def _compute_hash(event: AuditEvent) -> str:
        payload = json.dumps({
            "intent_id": event.intent_id,
            "stage": event.stage,
            "event_type": event.event_type,
            "outcome": event.outcome,
            "timestamp": event.timestamp,
            "previous_hash": event.previous_hash,
            "details": event.details,
        }, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]
