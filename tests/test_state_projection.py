"""Tests for CFA State Projection Protocol."""

from cfa.context import ContextRegistry
from cfa.partial_execution import FailurePolicy, PartialExecutionState, PublishState
from cfa.sandbox import ExecutionMetrics, SandboxOutcome, SandboxResult, StepOutcome, StepResult
from cfa.state_projection import ProjectionResult, StateProjectionProtocol
from cfa.types import Fault, FaultFamily, FaultSeverity, PolicyAction
from conftest import make_signature


def _make_exec_state(
    publish_state: PublishState,
    committed: list[str] | None = None,
    quarantined: list[str] | None = None,
    rows: int = 100_000,
    cost: float = 5.0,
) -> PartialExecutionState:
    state = PartialExecutionState(plan_signature_hash="test_hash")
    state.publish_state = publish_state
    state.committed_steps = committed or []
    state.quarantined_steps = quarantined or []
    state.sandbox_result = SandboxResult(
        outcome=SandboxOutcome.COMPLETED,
        aggregate_metrics=ExecutionMetrics(
            rows_output=rows, cost_dbu=cost, duration_seconds=2.5
        ),
    )
    if publish_state == PublishState.ROLLED_BACK:
        state.faults = [Fault(
            code="TEST_FAULT", family=FaultFamily.RUNTIME, severity=FaultSeverity.HIGH,
            stage="test", message="Test rollback reason", mandatory_action=PolicyAction.BLOCK,
        )]
    return state


class TestProjectPublished:
    def test_projects_published_datasets(self):
        reg = ContextRegistry()
        protocol = StateProjectionProtocol(reg)
        sig = make_signature()

        exec_state = _make_exec_state(PublishState.PUBLISHED, committed=["extract", "load"])
        result = protocol.project(sig, exec_state)

        assert result.projected
        assert result.projection_type == "full"
        assert result.snapshot_version != ""
        ds_state = reg.get_dataset_state(sig.target_dataset_name)
        assert ds_state is not None
        assert ds_state["state"] == "published"
        for ds in sig.datasets:
            assert reg.get_dataset_state(ds.name) is None

    def test_published_includes_metrics(self):
        reg = ContextRegistry()
        protocol = StateProjectionProtocol(reg)
        sig = make_signature()

        exec_state = _make_exec_state(PublishState.PUBLISHED, rows=50_000, cost=3.0)
        protocol.project(sig, exec_state)

        ds_state = reg.get_dataset_state(sig.target_dataset_name)
        assert ds_state["metrics"]["rows_output"] == 50_000
        assert ds_state["metrics"]["cost_dbu"] == 3.0


class TestProjectDegraded:
    def test_projects_degraded_state(self):
        reg = ContextRegistry()
        protocol = StateProjectionProtocol(reg)
        sig = make_signature()

        exec_state = _make_exec_state(
            PublishState.DEGRADED,
            committed=["extract"],
            quarantined=["load"],
        )
        result = protocol.project(sig, exec_state)

        assert result.projection_type == "degraded"
        ds_state = reg.get_dataset_state(sig.target_dataset_name)
        assert ds_state["state"] == "degraded"
        assert "load" in ds_state["quarantined_steps"]


class TestProjectQuarantined:
    def test_projects_quarantined_state(self):
        reg = ContextRegistry()
        protocol = StateProjectionProtocol(reg)
        sig = make_signature()

        exec_state = _make_exec_state(
            PublishState.QUARANTINED, quarantined=["extract", "load"]
        )
        result = protocol.project(sig, exec_state)

        assert result.projection_type == "quarantine"
        ds_state = reg.get_dataset_state(sig.target_dataset_name)
        assert ds_state["state"] == "quarantined"


class TestProjectRolledBack:
    def test_rollback_does_not_project_context_state(self):
        reg = ContextRegistry()
        protocol = StateProjectionProtocol(reg)
        sig = make_signature()

        exec_state = _make_exec_state(PublishState.ROLLED_BACK)
        result = protocol.project(sig, exec_state)

        assert result.projection_type == "rollback"
        assert not result.projected
        assert result.audit_only
        assert reg.get_dataset_state(sig.target_dataset_name) is None

    def test_preserves_existing_state_on_rollback(self):
        reg = ContextRegistry()
        reg.set_dataset_state("silver_nfe", {"state": "published", "rows": 1000})
        protocol = StateProjectionProtocol(reg)
        sig = make_signature()

        exec_state = _make_exec_state(PublishState.ROLLED_BACK)
        protocol.project(sig, exec_state)

        # Should NOT overwrite existing published state
        ds_state = reg.get_dataset_state("silver_nfe")
        assert ds_state["state"] == "published"


class TestProjectCommittedNotPublished:
    def test_projects_committed_not_published(self):
        reg = ContextRegistry()
        protocol = StateProjectionProtocol(reg)
        sig = make_signature()

        exec_state = _make_exec_state(
            PublishState.COMMITTED_NOT_PUBLISHED,
            committed=["extract"],
            quarantined=["load"],
        )
        result = protocol.project(sig, exec_state)

        assert result.projection_type == "partial"
        ds_state = reg.get_dataset_state(sig.target_dataset_name)
        assert ds_state["state"] == "committed_not_published"


class TestSnapshotCreation:
    def test_snapshot_created_on_projection(self):
        reg = ContextRegistry()
        protocol = StateProjectionProtocol(reg)
        sig = make_signature()

        exec_state = _make_exec_state(PublishState.PUBLISHED)
        result = protocol.project(sig, exec_state)

        assert result.snapshot_version in reg.list_snapshots()

    def test_snapshot_is_restorable(self):
        reg = ContextRegistry()
        protocol = StateProjectionProtocol(reg)
        sig = make_signature()

        exec_state = _make_exec_state(PublishState.PUBLISHED)
        result = protocol.project(sig, exec_state)

        # Mutate
        reg.set_dataset_state(sig.target_dataset_name, {"state": "quarantined"})
        assert reg.get_dataset_state(sig.target_dataset_name)["state"] == "quarantined"

        # Restore
        assert reg.restore_snapshot(result.snapshot_version)
        assert reg.get_dataset_state(sig.target_dataset_name)["state"] == "published"
