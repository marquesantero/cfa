"""Tests for CFA Context Registry — persistent backends and snapshots."""

import tempfile
from pathlib import Path

from cfa.context import ContextRegistry, InMemoryContextStorage, JsonFileContextStorage


class TestInMemoryContextStorage:
    def test_save_and_load(self):
        storage = InMemoryContextStorage()
        storage.save({"datasets": {"nfe": {"state": "published"}}, "version_id": "v_1"})
        loaded = storage.load()
        assert loaded["datasets"]["nfe"]["state"] == "published"

    def test_snapshot_round_trip(self):
        storage = InMemoryContextStorage()
        state = {"datasets": {"nfe": {"state": "published"}}, "version_id": "v_1"}
        storage.save_snapshot("v_1", state)
        loaded = storage.load_snapshot("v_1")
        assert loaded is not None
        assert loaded["version_id"] == "v_1"

    def test_missing_snapshot_returns_none(self):
        storage = InMemoryContextStorage()
        assert storage.load_snapshot("nonexistent") is None

    def test_list_snapshots(self):
        storage = InMemoryContextStorage()
        storage.save_snapshot("v_1", {"a": 1})
        storage.save_snapshot("v_2", {"a": 2})
        assert set(storage.list_snapshots()) == {"v_1", "v_2"}


class TestJsonFileContextStorage:
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonFileContextStorage(tmp)
            storage.save({"datasets": {"nfe": {"state": "published"}}, "version_id": "v_1"})
            loaded = storage.load()
            assert loaded["datasets"]["nfe"]["state"] == "published"

    def test_load_empty_returns_empty_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonFileContextStorage(tmp)
            assert storage.load() == {}

    def test_snapshot_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonFileContextStorage(tmp)
            state = {"datasets": {"nfe": {"state": "committed"}}, "version_id": "v_abc"}
            storage.save_snapshot("v_abc", state)
            loaded = storage.load_snapshot("v_abc")
            assert loaded is not None
            assert loaded["version_id"] == "v_abc"

    def test_list_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonFileContextStorage(tmp)
            storage.save_snapshot("v_1", {"a": 1})
            storage.save_snapshot("v_2", {"a": 2})
            assert set(storage.list_snapshots()) == {"v_1", "v_2"}

    def test_persistence_across_instances(self):
        with tempfile.TemporaryDirectory() as tmp:
            s1 = JsonFileContextStorage(tmp)
            s1.save({"datasets": {"nfe": {"state": "published"}}, "version_id": "v_x"})
            s2 = JsonFileContextStorage(tmp)
            loaded = s2.load()
            assert loaded["version_id"] == "v_x"


class TestContextRegistryWithStorage:
    def test_restores_from_persistent_storage(self):
        storage = InMemoryContextStorage()
        storage.save({
            "datasets": {"nfe": {"state": "published"}},
            "execution_history": [],
            "version_id": "v_restored",
        })
        reg = ContextRegistry(_storage=storage)
        assert reg.version_id == "v_restored"
        assert reg.get_dataset_state("nfe")["state"] == "published"

    def test_snapshot_and_restore(self):
        reg = ContextRegistry()
        reg.set_dataset_state("nfe", {"state": "published", "rows": 1000})
        snap_v = reg.snapshot()

        # Mutate state
        reg.set_dataset_state("nfe", {"state": "quarantined"})
        assert reg.get_dataset_state("nfe")["state"] == "quarantined"

        # Restore snapshot
        assert reg.restore_snapshot(snap_v)
        assert reg.get_dataset_state("nfe")["state"] == "published"

    def test_restore_nonexistent_snapshot_returns_false(self):
        reg = ContextRegistry()
        assert reg.restore_snapshot("v_doesnt_exist") is False

    def test_list_snapshots_empty(self):
        reg = ContextRegistry()
        assert reg.list_snapshots() == []

    def test_persists_on_set_dataset_state(self):
        storage = InMemoryContextStorage()
        reg = ContextRegistry(_storage=storage)
        reg.set_dataset_state("nfe", {"state": "committed"})
        # Storage should have been updated
        loaded = storage.load()
        assert "nfe" in loaded["datasets"]

    def test_persists_on_record_execution(self):
        storage = InMemoryContextStorage()
        reg = ContextRegistry(_storage=storage)
        reg.record_execution("intent_1", "approved", "hash_abc")
        loaded = storage.load()
        assert len(loaded["execution_history"]) == 1

    def test_json_file_persistence_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage1 = JsonFileContextStorage(tmp)
            reg1 = ContextRegistry(_storage=storage1)
            reg1.set_dataset_state("nfe", {"state": "published"})
            v1 = reg1.version_id

            # New registry from same storage path
            storage2 = JsonFileContextStorage(tmp)
            reg2 = ContextRegistry(_storage=storage2)
            assert reg2.get_dataset_state("nfe")["state"] == "published"
            assert reg2.version_id == v1
