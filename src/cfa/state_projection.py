"""
CFA State Projection Protocol
==============================
Projects execution outcomes into the Context Registry.

After every execution (successful, partial, or failed), the State Projection
Protocol updates the Context Registry to reflect "what state is the data in now".

This is Invariant I4: Mandatory Projection — the Context Registry MUST be updated
after every execution. Invariant I6 (Safe Execution) takes precedence: if execution
was rolled back, the projection reflects that.

The protocol:
1. Reads execution outcome (PartialExecutionState or SandboxResult)
2. Projects dataset states (committed, quarantined, rolled_back, degraded)
3. Updates Context Registry with new dataset states
4. Takes a snapshot for reproducibility (Invariant I8)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .context import ContextRegistry
from .partial_execution import PartialExecutionState, PublishState
from .sandbox import SandboxResult, SandboxOutcome
from .types import StateSignature, _utcnow


# ── Projection Result ───────────────────────────────────────────────────────


@dataclass
class ProjectionResult:
    """Result of projecting execution state into the Context Registry."""

    projected: bool
    snapshot_version: str = ""
    dataset_states_updated: list[str] = None  # type: ignore[assignment]
    projection_type: str = ""  # "full", "partial", "rollback", "degraded"
    audit_only: bool = False

    def __post_init__(self) -> None:
        if self.dataset_states_updated is None:
            self.dataset_states_updated = []


# ── State Projection Protocol ───────────────────────────────────────────────


class StateProjectionProtocol:
    """
    Projects execution outcomes into the Context Registry (Invariant I4).

    Called by the Kernel after sandbox execution completes.
    Always creates a snapshot for reproducibility.
    """

    def __init__(self, context_registry: ContextRegistry) -> None:
        self.registry = context_registry

    def project(
        self,
        signature: StateSignature,
        execution_state: PartialExecutionState,
    ) -> ProjectionResult:
        """Project execution state into the Context Registry."""
        now = _utcnow().isoformat()
        target_scope = [signature.target_dataset_name]

        match execution_state.publish_state:
            case PublishState.PUBLISHED:
                return self._project_published(signature, execution_state, target_scope, now)

            case PublishState.DEGRADED:
                return self._project_degraded(signature, execution_state, target_scope, now)

            case PublishState.COMMITTED_NOT_PUBLISHED:
                return self._project_committed_not_published(
                    signature, execution_state, target_scope, now
                )

            case PublishState.QUARANTINED:
                return self._project_quarantined(signature, execution_state, target_scope, now)

            case PublishState.ROLLED_BACK:
                return self._project_rolled_back(signature, execution_state, target_scope, now)

            case _:
                return ProjectionResult(projected=False, projection_type="unknown")

    def _project_published(
        self,
        signature: StateSignature,
        execution_state: PartialExecutionState,
        datasets: list[str],
        timestamp: str,
    ) -> ProjectionResult:
        metrics = {}
        if execution_state.sandbox_result:
            m = execution_state.sandbox_result.aggregate_metrics
            metrics = {
                "rows_output": m.rows_output,
                "cost_dbu": m.cost_dbu,
                "duration_seconds": m.duration_seconds,
            }

        for ds_name in datasets:
            self.registry.set_dataset_state(ds_name, {
                "state": "published",
                "signature_hash": signature.signature_hash,
                "target_layer": signature.target_layer.value,
                "last_updated": timestamp,
                "metrics": metrics,
            })

        snapshot_id = self.registry.snapshot()
        return ProjectionResult(
            projected=True,
            snapshot_version=snapshot_id,
            dataset_states_updated=datasets,
            projection_type="full",
        )

    def _project_degraded(
        self,
        signature: StateSignature,
        execution_state: PartialExecutionState,
        datasets: list[str],
        timestamp: str,
    ) -> ProjectionResult:
        updated = []
        for ds_name in datasets:
            self.registry.set_dataset_state(ds_name, {
                "state": "degraded",
                "signature_hash": signature.signature_hash,
                "target_layer": signature.target_layer.value,
                "last_updated": timestamp,
                "quarantined_steps": execution_state.quarantined_steps,
                "committed_steps": execution_state.committed_steps,
            })
            updated.append(ds_name)

        snapshot_id = self.registry.snapshot()
        return ProjectionResult(
            projected=True,
            snapshot_version=snapshot_id,
            dataset_states_updated=updated,
            projection_type="degraded",
        )

    def _project_committed_not_published(
        self,
        signature: StateSignature,
        execution_state: PartialExecutionState,
        datasets: list[str],
        timestamp: str,
    ) -> ProjectionResult:
        updated = []
        for ds_name in datasets:
            self.registry.set_dataset_state(ds_name, {
                "state": "committed_not_published",
                "signature_hash": signature.signature_hash,
                "target_layer": signature.target_layer.value,
                "last_updated": timestamp,
                "committed_steps": execution_state.committed_steps,
                "quarantined_steps": execution_state.quarantined_steps,
            })
            updated.append(ds_name)

        snapshot_id = self.registry.snapshot()
        return ProjectionResult(
            projected=True,
            snapshot_version=snapshot_id,
            dataset_states_updated=updated,
            projection_type="partial",
        )

    def _project_quarantined(
        self,
        signature: StateSignature,
        execution_state: PartialExecutionState,
        datasets: list[str],
        timestamp: str,
    ) -> ProjectionResult:
        updated = []
        for ds_name in datasets:
            self.registry.set_dataset_state(ds_name, {
                "state": "quarantined",
                "signature_hash": signature.signature_hash,
                "target_layer": signature.target_layer.value,
                "last_updated": timestamp,
                "quarantined_steps": execution_state.quarantined_steps,
            })
            updated.append(ds_name)

        snapshot_id = self.registry.snapshot()
        return ProjectionResult(
            projected=True,
            snapshot_version=snapshot_id,
            dataset_states_updated=updated,
            projection_type="quarantine",
        )

    def _project_rolled_back(
        self,
        signature: StateSignature,
        execution_state: PartialExecutionState,
        datasets: list[str],
        timestamp: str,
    ) -> ProjectionResult:
        return ProjectionResult(
            projected=False,
            snapshot_version="",
            dataset_states_updated=[],
            projection_type="rollback",
            audit_only=True,
        )
