"""
CFA Storage
===========
Portable storage for all CFA governance data.

Backends:
    SqliteStorage      — SQLite (stdlib), recommended for production
    JsonLinesStorage   — JSONL files, zero-dependency alternative

Both backends share the same management interface: stats(), cleanup(), vacuum().
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from cfa.audit.context import ContextStorageBackend
from cfa.audit.trail import AuditEvent, AuditStorageBackend

SCHEMA_VERSION = 1

_DDL = """
CREATE TABLE IF NOT EXISTS _schema (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    intent_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    event_type TEXT NOT NULL,
    outcome TEXT NOT NULL,
    policy_bundle_version TEXT NOT NULL DEFAULT '',
    details_json TEXT NOT NULL DEFAULT '{}',
    timestamp TEXT NOT NULL,
    event_hash TEXT NOT NULL DEFAULT '',
    previous_hash TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_audit_intent ON audit_events(intent_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_events(timestamp);

CREATE TABLE IF NOT EXISTS execution_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signature_hash TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    success INTEGER NOT NULL DEFAULT 1,
    replanned INTEGER NOT NULL DEFAULT 0,
    cost_dbu REAL NOT NULL DEFAULT 0.0,
    duration_seconds REAL NOT NULL DEFAULT 0.0,
    faults_json TEXT NOT NULL DEFAULT '[]',
    schema_match INTEGER NOT NULL DEFAULT 1,
    pii_exposure INTEGER NOT NULL DEFAULT 0,
    policy_compliant INTEGER NOT NULL DEFAULT 1,
    layer_adherent INTEGER NOT NULL DEFAULT 1,
    max_expected_duration REAL NOT NULL DEFAULT 300.0,
    max_expected_cost REAL NOT NULL DEFAULT 50.0
);

CREATE INDEX IF NOT EXISTS idx_exec_sig_hash ON execution_records(signature_hash);
CREATE INDEX IF NOT EXISTS idx_exec_timestamp ON execution_records(timestamp);

CREATE TABLE IF NOT EXISTS skill_records (
    signature_hash TEXT PRIMARY KEY,
    state TEXT NOT NULL DEFAULT 'candidate',
    generation_metadata_json TEXT NOT NULL DEFAULT '{}',
    last_evaluation TEXT,
    demotion_reason TEXT NOT NULL DEFAULT '',
    consecutive_inactive_windows INTEGER NOT NULL DEFAULT 0,
    history_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS context_state (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS metrics (
    metric_key TEXT PRIMARY KEY,
    metric_type TEXT NOT NULL DEFAULT 'counter',
    value REAL NOT NULL DEFAULT 0.0,
    labels_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class SqliteStorage:
    """Unified SQLite storage for all CFA governance data.

    Usage::

        store = SqliteStorage("cfa.db")
        store.ensure_schema()

        # Audit
        store.audit_append(event)
        events = store.audit_load_all()

        # Execution records (lifecycle)
        store.execution_append(record)
        records = store.execution_load_by_hash(signature_hash)

        # Skills
        store.skill_upsert(signature_hash, skill_data)
        skills = store.skill_load_all()

        # Context
        store.context_save(state_dict)
        state = store.context_load()

        # Metrics
        store.metric_upsert("cfa_policy_evaluations_total", 1, {"decision": "approved"})
    """

    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)
        self._local = threading.local()

    @property
    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self._path))
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    # ── Schema ────────────────────────────────────────────────────────────

    def ensure_schema(self) -> None:
        conn = self._conn
        conn.executescript(_DDL)
        current = conn.execute(
            "SELECT MAX(version) FROM _schema"
        ).fetchone()[0] or 0
        if current < SCHEMA_VERSION:
            conn.execute(
                "INSERT OR REPLACE INTO _schema (version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
            conn.commit()

    # ── Audit ─────────────────────────────────────────────────────────────

    def audit_append(self, event: AuditEvent) -> None:
        conn = self._conn
        conn.execute(
            """INSERT INTO audit_events
               (intent_id, stage, event_type, outcome, policy_bundle_version,
                details_json, timestamp, event_hash, previous_hash)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                event.intent_id, event.stage, event.event_type, event.outcome,
                event.policy_bundle_version,
                json.dumps(event.details, default=str),
                event.timestamp, event.event_hash, event.previous_hash,
            ),
        )
        conn.commit()

    def audit_load_all(self) -> list[AuditEvent]:
        rows = self._conn.execute(
            "SELECT * FROM audit_events ORDER BY id"
        ).fetchall()
        return [_row_to_audit_event(r) for r in rows]

    def audit_load_by_intent(self, intent_id: str) -> list[AuditEvent]:
        rows = self._conn.execute(
            "SELECT * FROM audit_events WHERE intent_id = ? ORDER BY id",
            (intent_id,),
        ).fetchall()
        return [_row_to_audit_event(r) for r in rows]

    def audit_count(self) -> int:
        return self._conn.execute(
            "SELECT COUNT(*) FROM audit_events"
        ).fetchone()[0]

    # ── Execution Records (Lifecycle) ─────────────────────────────────────

    def execution_append(self, record_dict: dict[str, Any]) -> None:
        conn = self._conn
        conn.execute(
            """INSERT INTO execution_records
               (signature_hash, timestamp, success, replanned, cost_dbu,
                duration_seconds, faults_json, schema_match, pii_exposure,
                policy_compliant, layer_adherent, max_expected_duration,
                max_expected_cost)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                record_dict.get("signature_hash", ""),
                record_dict.get("timestamp", ""),
                int(record_dict.get("success", True)),
                int(record_dict.get("replanned", False)),
                float(record_dict.get("cost_dbu", 0.0)),
                float(record_dict.get("duration_seconds", 0.0)),
                json.dumps(record_dict.get("faults", [])),
                int(record_dict.get("schema_match", True)),
                int(record_dict.get("pii_exposure", False)),
                int(record_dict.get("policy_compliant", True)),
                int(record_dict.get("layer_adherent", True)),
                float(record_dict.get("max_expected_duration", 300.0)),
                float(record_dict.get("max_expected_cost", 50.0)),
            ),
        )
        conn.commit()

    def execution_load_all(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM execution_records ORDER BY id"
        ).fetchall()
        return [_row_to_exec_dict(r) for r in rows]

    def execution_load_by_hash(self, signature_hash: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM execution_records WHERE signature_hash = ? ORDER BY id",
            (signature_hash,),
        ).fetchall()
        return [_row_to_exec_dict(r) for r in rows]

    def execution_count_by_outcome(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT outcome, COUNT(*) as cnt FROM audit_events WHERE event_type='policy_evaluation' GROUP BY outcome"
        ).fetchall()
        return {r["outcome"]: r["cnt"] for r in rows}

    # ── Skills ────────────────────────────────────────────────────────────

    def skill_upsert(self, signature_hash: str, skill_data: dict[str, Any]) -> None:
        conn = self._conn
        conn.execute(
            """INSERT OR REPLACE INTO skill_records
               (signature_hash, state, generation_metadata_json,
                last_evaluation, demotion_reason, consecutive_inactive_windows, history_json)
               VALUES (?,?,?,?,?,?,?)""",
            (
                signature_hash,
                skill_data.get("state", "candidate"),
                json.dumps(skill_data.get("generation_metadata", {})),
                skill_data.get("last_evaluation", ""),
                skill_data.get("demotion_reason", ""),
                skill_data.get("consecutive_inactive_windows", 0),
                json.dumps(skill_data.get("history", [])),
            ),
        )
        conn.commit()

    def skill_load_all(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM skill_records ORDER BY signature_hash"
        ).fetchall()
        return [_row_to_skill_dict(r) for r in rows]

    def skill_load(self, signature_hash: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM skill_records WHERE signature_hash = ?",
            (signature_hash,),
        ).fetchone()
        return _row_to_skill_dict(row) if row else None

    # ── Context ───────────────────────────────────────────────────────────

    def context_save(self, state: dict[str, Any]) -> None:
        conn = self._conn
        for key, value in state.items():
            conn.execute(
                """INSERT OR REPLACE INTO context_state (key, value_json)
                   VALUES (?,?)""",
                (key, json.dumps(value, default=str)),
            )
        conn.commit()

    def context_load(self) -> dict[str, Any]:
        rows = self._conn.execute(
            "SELECT key, value_json FROM context_state"
        ).fetchall()
        result: dict[str, Any] = {}
        for r in rows:
            try:
                result[r["key"]] = json.loads(r["value_json"])
            except (json.JSONDecodeError, TypeError):
                result[r["key"]] = r["value_json"]
        return result

    def context_save_snapshot(self, version_id: str, state: dict[str, Any]) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO context_state (key, value_json)
               VALUES (?,?)""",
            (f"_snapshot_{version_id}", json.dumps(state, default=str)),
        )
        self._conn.commit()

    def context_load_snapshot(self, version_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT value_json FROM context_state WHERE key = ?",
            (f"_snapshot_{version_id}",),
        ).fetchone()
        if row:
            try:
                return json.loads(row["value_json"])
            except (json.JSONDecodeError, TypeError):
                pass
        return None

    def context_list_snapshots(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT key FROM context_state WHERE key LIKE '_snapshot_%'"
        ).fetchall()
        return [r["key"].replace("_snapshot_", "") for r in rows]

    # ── Metrics ───────────────────────────────────────────────────────────

    def metric_upsert(
        self, key: str, delta: float = 0.0, metric_type: str = "counter",
        labels: dict[str, str] | None = None,
    ) -> None:
        conn = self._conn
        labels_json = json.dumps(labels or {})
        existing = conn.execute(
            "SELECT value FROM metrics WHERE metric_key = ?", (key,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE metrics SET value = value + ?, updated_at = datetime('now') WHERE metric_key = ?",
                (delta, key),
            )
        else:
            conn.execute(
                """INSERT INTO metrics (metric_key, metric_type, value, labels_json)
                   VALUES (?,?,?,?)""",
                (key, metric_type, delta, labels_json),
            )
        conn.commit()

    def metric_get_all(self) -> dict[str, dict[str, Any]]:
        rows = self._conn.execute("SELECT * FROM metrics").fetchall()
        result: dict[str, dict[str, Any]] = {}
        for r in rows:
            result[r["metric_key"]] = {
                "type": r["metric_type"],
                "value": r["value"],
                "labels": json.loads(r["labels_json"]) if r["labels_json"] else {},
            }
        return result

    # ── Maintenance ───────────────────────────────────────────────────────

    def close(self) -> None:
        if hasattr(self._local, "conn") and self._local.conn:
            try:
                self._local.conn.execute("PRAGMA journal_mode=DELETE")
                self._local.conn.commit()
            except Exception:
                pass
            self._local.conn.close()
            self._local.conn = None

    def vacuum(self) -> None:
        self._conn.execute("VACUUM")


# ── SQLite-backed storage adapters ──────────────────────────────────────────


class SqliteAuditStorage(AuditStorageBackend):
    """AuditStorageBackend backed by SqliteStorage."""

    def __init__(self, store: SqliteStorage) -> None:
        self._store = store

    def append(self, event: AuditEvent) -> None:
        self._store.audit_append(event)

    def load_all(self) -> list[AuditEvent]:
        return self._store.audit_load_all()

    def load_by_intent(self, intent_id: str) -> list[AuditEvent]:
        return self._store.audit_load_by_intent(intent_id)


class SqliteContextStorage(ContextStorageBackend):
    """ContextStorageBackend backed by SqliteStorage."""

    def __init__(self, store: SqliteStorage) -> None:
        self._store = store

    def load(self) -> dict[str, Any]:
        return self._store.context_load()

    def save(self, state: dict[str, Any]) -> None:
        self._store.context_save(state)

    def save_snapshot(self, version_id: str, state: dict[str, Any]) -> None:
        self._store.context_save_snapshot(version_id, state)

    def load_snapshot(self, version_id: str) -> dict[str, Any] | None:
        return self._store.context_load_snapshot(version_id)

    def list_snapshots(self) -> list[str]:
        return self._store.context_list_snapshots()


# ── Helpers ─────────────────────────────────────────────────────────────────


def _row_to_audit_event(row: sqlite3.Row) -> AuditEvent:
    return AuditEvent(
        intent_id=row["intent_id"],
        stage=row["stage"],
        event_type=row["event_type"],
        outcome=row["outcome"],
        policy_bundle_version=row["policy_bundle_version"],
        details=json.loads(row["details_json"]) if row["details_json"] else {},
        timestamp=row["timestamp"],
        event_hash=row["event_hash"],
        previous_hash=row["previous_hash"],
    )


def _row_to_exec_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "signature_hash": row["signature_hash"],
        "timestamp": row["timestamp"],
        "success": bool(row["success"]),
        "replanned": bool(row["replanned"]),
        "cost_dbu": row["cost_dbu"],
        "duration_seconds": row["duration_seconds"],
        "faults": json.loads(row["faults_json"]) if row["faults_json"] else [],
        "schema_match": bool(row["schema_match"]),
        "pii_exposure": bool(row["pii_exposure"]),
        "policy_compliant": bool(row["policy_compliant"]),
        "layer_adherent": bool(row["layer_adherent"]),
        "max_expected_duration": row["max_expected_duration"],
        "max_expected_cost": row["max_expected_cost"],
    }


def _row_to_skill_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "signature_hash": row["signature_hash"],
        "state": row["state"],
        "generation_metadata": json.loads(row["generation_metadata_json"]) if row["generation_metadata_json"] else {},
        "last_evaluation": row["last_evaluation"],
        "demotion_reason": row["demotion_reason"],
        "consecutive_inactive_windows": row["consecutive_inactive_windows"],
        "history": json.loads(row["history_json"]) if row["history_json"] else [],
    }


# ── Storage Stats ───────────────────────────────────────────────────────────


@dataclass
class StorageStats:
    backend: str = ""
    path: str = ""
    file_size_bytes: int = 0
    audit_events_count: int = 0
    execution_records_count: int = 0
    skill_records_count: int = 0
    metrics_count: int = 0
    oldest_record: str = ""
    newest_record: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "path": self.path,
            "file_size_bytes": self.file_size_bytes,
            "audit_events_count": self.audit_events_count,
            "execution_records_count": self.execution_records_count,
            "skill_records_count": self.skill_records_count,
            "metrics_count": self.metrics_count,
            "oldest_record": self.oldest_record,
            "newest_record": self.newest_record,
        }


# ── SqliteStorage management methods ────────────────────────────────────────


def _sqlite_storage_stats(store: SqliteStorage) -> StorageStats:
    conn = store._conn
    stats = StorageStats(backend="sqlite", path=str(store._path))
    if store._path.exists():
        stats.file_size_bytes = store._path.stat().st_size
    stats.audit_events_count = conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
    stats.execution_records_count = conn.execute("SELECT COUNT(*) FROM execution_records").fetchone()[0]
    stats.skill_records_count = conn.execute("SELECT COUNT(*) FROM skill_records").fetchone()[0]
    stats.metrics_count = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
    oldest = conn.execute("SELECT MIN(timestamp) FROM audit_events").fetchone()[0]
    newest = conn.execute("SELECT MAX(timestamp) FROM audit_events").fetchone()[0]
    stats.oldest_record = oldest or ""
    stats.newest_record = newest or ""
    return stats


def _sqlite_storage_cleanup(store: SqliteStorage, before: str) -> int:
    conn = store._conn
    total = 0
    for table in ("audit_events", "execution_records"):
        assert table in ("audit_events", "execution_records")  # whitelist
        result = conn.execute(f"DELETE FROM {table} WHERE timestamp < ?", (before,))
        total += result.rowcount
    if total > 0:
        conn.commit()
    return total


# ── JsonLines Storage ───────────────────────────────────────────────────────


class JsonLinesStorage:
    """JSONL-file storage with the same management interface as SqliteStorage.

    Each domain writes to a separate .jsonl file inside a directory.
    No schema migrations needed — the format is append-only JSON lines.

    This is the zero-dependency alternative to SQLite.
    """

    def __init__(self, directory: str | Path) -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._dir

    def stats(self) -> StorageStats:
        stats = StorageStats(backend="jsonl", path=str(self._dir))
        total_size = 0
        for pattern, count_attr in [
            ("audit_*.jsonl", "audit_events_count"),
            ("execution_*.jsonl", "execution_records_count"),
            ("skills_*.jsonl", "skill_records_count"),
            ("metrics_*.jsonl", "metrics_count"),
        ]:
            count = 0
            for f in self._dir.glob(pattern):
                total_size += f.stat().st_size
                count += sum(1 for _ in _read_jsonl_lines(f))
            setattr(stats, count_attr, count)
        stats.file_size_bytes = total_size
        return stats

    def cleanup(self, before: str) -> int:
        total = 0
        before_dt = datetime.fromisoformat(before)
        for pattern in ("audit_*.jsonl", "execution_*.jsonl"):
            for f in self._dir.glob(pattern):
                lines = list(_read_jsonl_lines(f))
                kept = []
                for line in lines:
                    try:
                        ts = json.loads(line).get("timestamp", "")
                        if ts:
                            try:
                                record_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                                if record_dt < before_dt:
                                    total += 1
                                    continue
                            except (ValueError, TypeError):
                                pass
                    except json.JSONDecodeError:
                        pass
                    kept.append(line)
                if len(kept) < len(lines):
                    f.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
        return total

    def vacuum(self) -> None:
        pass


def _read_jsonl_lines(path: Path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            yield line
