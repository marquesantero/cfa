"""Tests for CFA Context Registry."""

from cfa.context import ContextRegistry


class TestContextRegistry:
    def test_initial_version(self):
        reg = ContextRegistry()
        assert reg.version_id == "v_initial"

    def test_version_bumps_on_set(self):
        reg = ContextRegistry()
        reg.set_dataset_state("ds1", {"state": "committed"})
        assert reg.version_id != "v_initial"

    def test_get_dataset_state(self):
        reg = ContextRegistry()
        reg.set_dataset_state("ds1", {"state": "committed", "rows": 1000})
        state = reg.get_dataset_state("ds1")
        assert state is not None
        assert state["state"] == "committed"

    def test_get_missing_dataset_returns_none(self):
        reg = ContextRegistry()
        assert reg.get_dataset_state("nonexistent") is None

    def test_record_execution(self):
        reg = ContextRegistry()
        reg.record_execution("intent_1", "approved", "hash_abc")
        env = reg.get_environment_state()
        assert len(env["execution_history"]) == 1
        assert env["execution_history"][0]["intent_id"] == "intent_1"

    def test_environment_state_snapshot(self):
        reg = ContextRegistry()
        reg.set_dataset_state("ds1", {"state": "committed"})
        env = reg.get_environment_state()
        assert "ds1" in env["datasets"]
        assert env["version_id"] == reg.version_id
