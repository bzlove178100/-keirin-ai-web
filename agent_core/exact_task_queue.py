from __future__ import annotations

from copy import deepcopy

from .hosted_queue import HostedQueueClient, HostedQueueIntegrityError, HostedQueueLease
from .model import TaskSpec


class ExactTaskQueueClient(HostedQueueClient):
    """Queue client that claims only one already-known immutable TaskSpec.

    This is intentionally separate from FIFO ``claim``. A bounded trusted host must
    not claim an unrelated task and only then discover that the task is outside its
    scope. The backend mode is expected to map to the owner-scoped
    ``agent_claim_task(task_id, worker_id, lease_seconds)`` RPC.
    """

    def claim_task(
        self,
        spec: TaskSpec,
        *,
        worker_id: str,
        lease_seconds: int = 120,
    ) -> HostedQueueLease | None:
        spec = TaskSpec.from_dict(deepcopy(spec.to_dict()))
        spec.validate()
        if not self._valid_worker_id(worker_id):
            raise ValueError("invalid_worker_id")
        if not self._valid_lease_seconds(lease_seconds):
            raise ValueError("invalid_lease_seconds")

        response = self._request(
            "queue_claim_task",
            {
                "task_id": spec.task_id,
                "worker_id": worker_id,
                "lease_seconds": lease_seconds,
            },
        )
        claimed = response.get("claimed")
        lease = response.get("lease")
        if claimed is False and lease is None:
            return None
        if claimed is not True:
            raise HostedQueueIntegrityError("queue_claim_flag_mismatch")

        record = self._parse_lease(lease, expected_spec=spec)
        if record.task_id != spec.task_id:
            raise HostedQueueIntegrityError("exact_task_claim_identity_mismatch")
        if record.status != "running" or record.lease_owner != worker_id:
            raise HostedQueueIntegrityError("queue_claim_identity_mismatch")
        if record.revision < 1 or record.attempt_count < 1:
            raise HostedQueueIntegrityError("queue_claim_counters_not_advanced")
        return record


class BoundExactTaskQueueClient(ExactTaskQueueClient):
    """Drop-in hosted queue client permanently bound to one immutable TaskSpec.

    ``HostedReadOnlyWorker`` calls ``queue.claim(...)``. Binding the spec here lets the
    existing worker use the exact-task backend primitive without giving it a FIFO
    fallback. The target cannot be swapped after construction.
    """

    def __init__(self, transport, target_spec: TaskSpec):
        super().__init__(transport)
        self._target_spec = TaskSpec.from_dict(deepcopy(target_spec.to_dict()))
        self._target_spec.validate()

    @property
    def target_spec(self) -> TaskSpec:
        return TaskSpec.from_dict(deepcopy(self._target_spec.to_dict()))

    def claim(self, *, worker_id: str, lease_seconds: int = 120) -> HostedQueueLease | None:
        return self.claim_task(
            self._target_spec,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
        )
