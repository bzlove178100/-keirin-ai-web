from __future__ import annotations

from dataclasses import dataclass

from .hosted_checkpoint import (
    HostedCheckpointClient,
    HostedCheckpointConflict,
    HostedCheckpointNotFound,
    HostedCheckpointRecord,
)
from .model import TaskSpec
from .trusted_run_instance import validate_trusted_status_run_spec


class TrustedRunAlreadyUsed(RuntimeError):
    """Raised when a run-instance identity is no longer a pristine queued task."""


@dataclass(frozen=True)
class TrustedRunEnqueueResult:
    record: HostedCheckpointRecord
    created: bool


class TrustedRunEnqueuer:
    """Create or verify exactly one pristine trusted run-instance checkpoint.

    This helper never claims a queue lease and never executes provider actions. A
    repeated call is idempotent only while the exact immutable task remains queued at
    revision zero with its pending state and task-id idempotency key. Any running,
    blocked, failed or completed record is treated as consumed and fails closed.
    Database persistence additionally enforces at most one active trusted status-run
    instance per owner, so concurrent coordinators cannot activate distinct run IDs.
    """

    def __init__(self, checkpoints: HostedCheckpointClient):
        self.checkpoints = checkpoints

    @staticmethod
    def _assert_pristine(record: HostedCheckpointRecord, spec: TaskSpec) -> HostedCheckpointRecord:
        if record.task_id != spec.task_id or record.spec.to_dict() != spec.to_dict():
            raise TrustedRunAlreadyUsed("trusted_run_instance_identity_mismatch")
        if record.idempotency_key != spec.task_id:
            raise TrustedRunAlreadyUsed("trusted_run_instance_idempotency_mismatch")
        if record.status != "queued" or record.revision != 0 or record.state.status != "pending":
            raise TrustedRunAlreadyUsed(f"trusted_run_instance_already_used:{record.status}")
        if record.state.attempts or record.state.completed_steps:
            raise TrustedRunAlreadyUsed("trusted_run_instance_has_prior_progress")
        return record

    def ensure_queued(self, spec: TaskSpec) -> TrustedRunEnqueueResult:
        spec = TaskSpec.from_dict(spec.to_dict())
        validate_trusted_status_run_spec(spec)

        try:
            existing = self.checkpoints.get(spec)
        except HostedCheckpointNotFound:
            try:
                created = self.checkpoints.create(spec, idempotency_key=spec.task_id)
            except HostedCheckpointConflict as conflict:
                # Either an identical concurrent creator won, or the database-level
                # single-active guard rejected this distinct fresh instance because
                # another trusted run is already queued/running. Re-read only this
                # exact identity; absence means a different active run owns the slot.
                try:
                    existing = self.checkpoints.get(spec)
                except HostedCheckpointNotFound as missing:
                    raise TrustedRunAlreadyUsed("another_trusted_run_instance_is_active") from conflict
                return TrustedRunEnqueueResult(self._assert_pristine(existing, spec), False)
            return TrustedRunEnqueueResult(self._assert_pristine(created, spec), True)

        return TrustedRunEnqueueResult(self._assert_pristine(existing, spec), False)
