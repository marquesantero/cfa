"""Tests for CFA SQLite storage."""

import tempfile
from pathlib import Path

from cfa.audit.trail import AuditEvent
from cfa.storage import SqliteAuditStorage, SqliteContextStorage, SqliteStorage


def _temp_store():
    tmp = tempfile.mkdtemp()
    path = Path(tmp) / "test.db"
    store = SqliteStorage(path)
    store.ensure_schema()
    return store, tmp


def test_ensure_schema():
    store, tmp = _temp_store()
    store.close()
    assert Path(tmp, "test.db").exists()


def test_audit_roundtrip():
    store, tmp = _temp_store()
    event = AuditEvent(intent_id="i1", stage="policy", event_type="eval", outcome="approved")
    store.audit_append(event)
    events = store.audit_load_all()
    assert len(events) == 1
    assert events[0].intent_id == "i1"
    by_intent = store.audit_load_by_intent("i1")
    assert len(by_intent) == 1
    store.close()


def test_execution_record_roundtrip():
    store, tmp = _temp_store()
    store.execution_append({
        "signature_hash": "abc123", "timestamp": "2026-01-01T00:00:00",
        "success": True, "replanned": False, "cost_dbu": 5.0,
        "duration_seconds": 10.0, "faults": ["FAULT_X"],
        "schema_match": True, "pii_exposure": False,
        "policy_compliant": True, "layer_adherent": True,
    })
    records = store.execution_load_all()
    assert len(records) == 1
    assert records[0]["signature_hash"] == "abc123"
    store.close()


def test_skill_roundtrip():
    store, tmp = _temp_store()
    store.skill_upsert("hash_a", {"state": "active", "generation_metadata": {}, "consecutive_inactive_windows": 0, "history": [{"from": "candidate", "to": "active"}]})
    skills = store.skill_load_all()
    assert len(skills) == 1
    assert skills[0]["state"] == "active"
    store.close()


def test_context_roundtrip():
    store, tmp = _temp_store()
    store.context_save({"datasets": {"nfe": {"state": "published"}}, "version_id": "v1"})
    state = store.context_load()
    assert state["version_id"] == "v1"
    store.close()


def test_metrics_roundtrip():
    store, tmp = _temp_store()
    store.metric_upsert("cfa_policy_total", 1.0, "counter", {"decision": "approved"})
    store.metric_upsert("cfa_policy_total", 1.0, "counter", {"decision": "blocked"})
    store.metric_upsert("cfa_policy_total", 1.0, "counter", {"decision": "approved"})
    metrics = store.metric_get_all()
    assert metrics["cfa_policy_total"]["value"] == 3.0
    store.close()


def test_sqlite_adapter_for_audit():
    store, tmp = _temp_store()
    adapter = SqliteAuditStorage(store)
    event = AuditEvent(intent_id="i1", stage="s", event_type="e", outcome="o")
    adapter.append(event)
    assert len(adapter.load_all()) == 1
    store.close()


def test_sqlite_adapter_for_context():
    store, tmp = _temp_store()
    adapter = SqliteContextStorage(store)
    adapter.save({"k": "v"})
    assert adapter.load()["k"] == "v"
    store.close()


def test_promotion_engine_with_sqlite_storage():
    from cfa.observability.indices import ExecutionRecord
    from cfa.observability.promotion import PromotionEngine, PromotionPolicy
    from cfa.types import _utcnow

    store, tmp = _temp_store()
    engine = PromotionEngine(
        policy=PromotionPolicy(min_executions=2, evaluation_window_days=1),
        storage=store,
    )
    for _ in range(3):
        engine.record_execution(ExecutionRecord(
            signature_hash="hash_a", timestamp=_utcnow(),
            success=True, cost_dbu=1.0, duration_seconds=5.0,
        ))
    skill, scores = engine.evaluate("hash_a")
    assert scores.execution_count == 3
    assert skill.state.value in ("active", "candidate")
    loaded = store.skill_load("hash_a")
    assert loaded is not None
    records = store.execution_load_by_hash("hash_a")
    assert len(records) == 3
    store.close()


def test_sqlite_storage_stats():
    from cfa.audit.trail import AuditEvent
    store, tmp = _temp_store()
    store.audit_append(AuditEvent(intent_id="i1", stage="s", event_type="e", outcome="approved"))
    store.execution_append({"signature_hash": "abc", "timestamp": "2026-01-01T00:00:00", "success": True, "replanned": False, "cost_dbu": 5.0, "duration_seconds": 10.0, "faults": [], "schema_match": True, "pii_exposure": False, "policy_compliant": True, "layer_adherent": True})
    from cfa.storage import _sqlite_storage_stats
    stats = _sqlite_storage_stats(store)
    assert stats.backend == "sqlite"
    assert stats.audit_events_count == 1
    assert stats.execution_records_count == 1
    store.close()


def test_sqlite_storage_cleanup():
    from cfa.audit.trail import AuditEvent
    store, tmp = _temp_store()
    store.audit_append(AuditEvent(intent_id="i1", stage="s", event_type="e", outcome="approved", timestamp="2024-01-01T00:00:00"))
    store.audit_append(AuditEvent(intent_id="i2", stage="s", event_type="e", outcome="approved", timestamp="2026-06-01T00:00:00"))
    from cfa.storage import _sqlite_storage_cleanup
    deleted = _sqlite_storage_cleanup(store, "2025-01-01T00:00:00")
    assert deleted == 1
    remaining = store.audit_load_all()
    assert len(remaining) == 1
    assert remaining[0].intent_id == "i2"
    store.close()


def test_cli_storage_stats(capsys):
    import tempfile
    tmp = tempfile.mkdtemp()
    db_path = str(Path(tmp) / "test.db")
    from cfa.storage import SqliteStorage
    store = SqliteStorage(db_path)
    store.ensure_schema()
    store.audit_append(AuditEvent(intent_id="i1", stage="s", event_type="e", outcome="approved"))
    store.close()

    from cfa.cli import main
    code = main(["storage", "stats", "--db", db_path, "--format", "json"])
    import json
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["audit_events_count"] == 1


def test_cli_storage_cleanup(capsys):
    import tempfile
    tmp = tempfile.mkdtemp()
    db_path = str(Path(tmp) / "test.db")
    from cfa.storage import SqliteStorage
    store = SqliteStorage(db_path)
    store.ensure_schema()
    store.audit_append(AuditEvent(intent_id="i1", stage="s", event_type="e", outcome="approved", timestamp="2024-01-01T00:00:00"))
    store.close()

    from cfa.cli import main
    code = main(["storage", "cleanup", "--db", db_path, "--retention", "365"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Cleaned up" in out
