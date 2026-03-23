"""Tests for CFA Audit Trail — persistent backends and hash chain."""

import tempfile
from pathlib import Path

from cfa.audit import (
    AuditEvent,
    AuditTrail,
    InMemoryAuditStorage,
    JsonLinesAuditStorage,
)


class TestInMemoryAuditStorage:
    def test_append_and_load(self):
        storage = InMemoryAuditStorage()
        event = AuditEvent(
            intent_id="i1", stage="policy", event_type="eval", outcome="approved"
        )
        storage.append(event)
        assert len(storage.load_all()) == 1
        assert storage.load_all()[0].intent_id == "i1"

    def test_load_by_intent(self):
        storage = InMemoryAuditStorage()
        storage.append(AuditEvent(intent_id="i1", stage="s", event_type="e", outcome="o"))
        storage.append(AuditEvent(intent_id="i2", stage="s", event_type="e", outcome="o"))
        assert len(storage.load_by_intent("i1")) == 1
        assert len(storage.load_by_intent("i2")) == 1


class TestJsonLinesAuditStorage:
    def test_append_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            storage = JsonLinesAuditStorage(path)
            event = AuditEvent(
                intent_id="i1", stage="policy", event_type="eval", outcome="approved"
            )
            storage.append(event)
            events = storage.load_all()
            assert len(events) == 1
            assert events[0].intent_id == "i1"

    def test_append_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            storage = JsonLinesAuditStorage(path)
            storage.append(AuditEvent(intent_id="i1", stage="s", event_type="e", outcome="o"))
            storage.append(AuditEvent(intent_id="i2", stage="s", event_type="e", outcome="o"))
            assert len(storage.load_all()) == 2

    def test_persistence_across_instances(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            s1 = JsonLinesAuditStorage(path)
            s1.append(AuditEvent(intent_id="i1", stage="s", event_type="e", outcome="o"))
            s2 = JsonLinesAuditStorage(path)
            assert len(s2.load_all()) == 1

    def test_load_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            storage = JsonLinesAuditStorage(path)
            assert storage.load_all() == []


class TestAuditTrailHashChain:
    def test_hash_chain_builds(self):
        trail = AuditTrail()
        e1 = trail.record("i1", "policy", "eval", "approved")
        e2 = trail.record("i1", "decision", "final", "approved")
        assert e1.event_hash != ""
        assert e2.previous_hash == e1.event_hash

    def test_hash_chain_verifies(self):
        trail = AuditTrail()
        trail.record("i1", "policy", "eval", "approved")
        trail.record("i1", "decision", "final", "approved")
        trail.record("i2", "policy", "eval", "blocked")
        assert trail.verify_chain()

    def test_empty_chain_verifies(self):
        trail = AuditTrail()
        assert trail.verify_chain()

    def test_hash_chain_continues_from_persistent_storage(self):
        storage = InMemoryAuditStorage()
        trail1 = AuditTrail(storage=storage)
        e1 = trail1.record("i1", "policy", "eval", "approved")

        # New trail from same storage — should continue chain
        trail2 = AuditTrail(storage=storage)
        e2 = trail2.record("i2", "policy", "eval", "blocked")
        assert e2.previous_hash == e1.event_hash
        assert trail2.verify_chain()

    def test_event_count(self):
        trail = AuditTrail()
        assert trail.event_count == 0
        trail.record("i1", "s", "e", "o")
        trail.record("i1", "s", "e", "o")
        assert trail.event_count == 2

    def test_get_events_for_intent(self):
        trail = AuditTrail()
        trail.record("i1", "s", "e", "o")
        trail.record("i2", "s", "e", "o")
        trail.record("i1", "s2", "e2", "o2")
        assert len(trail.get_events_for_intent("i1")) == 2
        assert len(trail.get_events_for_intent("i2")) == 1


class TestAuditTrailWithJsonLines:
    def test_full_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            storage = JsonLinesAuditStorage(path)
            trail = AuditTrail(storage=storage)
            trail.record("i1", "policy", "eval", "approved", policy_bundle_version="v1.0")
            trail.record("i1", "decision", "final", "approved")

            # Reload from file
            storage2 = JsonLinesAuditStorage(path)
            trail2 = AuditTrail(storage=storage2)
            assert trail2.event_count == 2
            assert trail2.verify_chain()
