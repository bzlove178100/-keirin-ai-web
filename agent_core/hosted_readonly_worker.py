from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .adapters import ToolRegistry
from .hosted_activity import HostedActivityClient
from .hosted_queue import HostedQueueClient, HostedQueueLease
from .model import ActionResult, ArtifactState, ArtifactUpdate, TaskSpec, TaskState
from .runner import AgentRunner, RunOutcome


class HostedExecutionNotAuthorized(RuntimeError):
    """Raised before queue claim when hosted execution has not been activated."""


@dataclass(frozen=True)
class HostedReadOnlyWorkerResult:
    claimed: bool
    task_id: str | None
    execution_enabled: bool
    outcome: RunOutcome | None = None
    blocked_reason: str | None = None


class _ExistingStatePath:
    def exists(self) -> bool:
        return True


class HostedLeaseStateStore:
    """Duck-typed AgentRunner store backed by one fenced hosted queue lease.

    Every state save is a revision-CAS queue save using the current worker/fencing
    identity. There is no local distributed lock: the database lease and generation
    token are the lock/fence. Activity remains append-only through HostedActivityClient.
    """

    def __init__(
        self,
        *,
        queue: HostedQueueClient,
        activity: HostedActivityClient,
        lease: HostedQueueLease,
        worker_id: str,
        lease_seconds: int,
    ) -> None:
        self.queue = queue
        self.activity = activity
        self.lease = lease
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds

    def state_path(self, task_id: str) -> _ExistingStatePath:
        if task_id != self.lease.task_id:
            raise ValueError("task_state_id_mismatch")
        return _ExistingStatePath()

    @contextmanager
    def task_lock(self, task_id: str):
        if task_id != self.lease.task_id:
            raise ValueError("task_state_id_mismatch")
        yield

    def load_state(self, task_id: str) -> TaskState:
        if task_id != self.lease.task_id:
            raise ValueError("task_state_id_mismatch")
        return TaskState.from_dict(deepcopy(self.lease.state.to_dict()))

    def save_state(self, state: TaskState) -> None:
        if state.task_id != self.lease.task_id:
            raise ValueError("task_state_id_mismatch")
        state.touch()
        self.lease = self.queue.save(
            self.lease.spec,
            state,
            expected_revision=self.lease.revision,
            worker_id=self.worker_id,
            lease_generation=self.lease.lease_generation,
            lease_seconds=self.lease_seconds,
        )

    def apply_artifact_update(self, state: TaskState, update: ArtifactUpdate) -> ArtifactState:
        update.validate()
        existing = state.artifacts.get(update.artifact_id)
        if existing is None:
            existing = ArtifactState(artifact_id=update.artifact_id, kind=update.kind)
            state.artifacts[update.artifact_id] = existing
        existing.merge(update)
        return existing

    def append_event(
        self,
        *,
        task_id: str,
        event_type: str,
        message: str = "",
        step_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> Any:
        if task_id != self.lease.task_id:
            raise ValueError("activity_task_id_mismatch")
        return self.activity.append(
            task_id=task_id,
            event_type=event_type,
            step_id=step_id,
            payload={"message": message, "data": dict(data or {})},
        )


class HostedReadOnlyWorker:
    """Execution preparation for read-only tasks with an explicit activation gate.

    Construction defaults to execution disabled. ``run_next`` refuses before queue
    claim unless the host explicitly sets ``execution_authorized=True``. Even when
    authorized, every task action and verifier must be registered as ``read``. This
    class does not activate a scheduler, provider credentials or an always-on worker.
    """

    def __init__(
        self,
        *,
        queue: HostedQueueClient,
        activity: HostedActivityClient,
        registry: ToolRegistry,
        execution_authorized: bool = False,
    ) -> None:
        self.queue = queue
        self.activity = activity
        self.registry = registry
        self.execution_authorized = execution_authorized

    @staticmethod
    def _used_actions(spec: TaskSpec) -> set[str]:
        return {
            action
            for step in spec.steps
            for action in (step.action, step.verify_action)
            if action
        }

    def _preflight(self, spec: TaskSpec) -> tuple[tuple[str, ...], tuple[str, ...]]:
        spec.validate()
        used = self._used_actions(spec)
        registered = set(self.registry.actions())
        missing = tuple(sorted(used - registered))
        non_read: list[str] = []
        for action in sorted(used & registered):
            capability = self.registry.capability(action)
            if capability is None or capability.access != "read":
                non_read.append(action)
        return missing, tuple(non_read)

    @staticmethod
    def _artifact_updates(value: Any) -> tuple[ArtifactUpdate | Mapping[str, Any], ...]:
        if isinstance(value, ActionResult):
            return tuple(value.artifacts)
        if isinstance(value, Mapping):
            raw = value.get("artifacts", ())
            if isinstance(raw, (list, tuple)):
                return tuple(raw)
        return ()

    @classmethod
    def _assert_read_only_result(cls, value: Any) -> Any:
        for raw in cls._artifact_updates(value):
            if isinstance(raw, ArtifactUpdate):
                update = raw
                flags = (
                    update.created,
                    update.persistent_saved,
                    update.device_saved,
                    update.ui_loaded,
                )
            elif isinstance(raw, Mapping):
                flags = tuple(
                    raw.get(name)
                    for name in ("created", "persistent_saved", "device_saved", "ui_loaded")
                )
            else:
                raise RuntimeError("read_only_action_returned_invalid_artifact_update")
            if any(flag is True for flag in flags):
                raise RuntimeError("read_only_action_reported_write_artifact")
        return value

    def _scope_failure(self, lease: HostedQueueLease) -> str | None:
        return None

    def _guarded_actions(self, store: HostedLeaseStateStore | None = None) -> dict[str, Any]:
        guarded: dict[str, Any] = {}
        for action, implementation in self.registry.actions().items():
            capability = self.registry.capability(action)
            if capability is None or capability.access != "read":
                continue

            def wrap(args, context, *, _implementation=implementation):
                return self._assert_read_only_result(_implementation(args, context))

            guarded[action] = wrap
        return guarded

    def _release_blocked(
        self,
        lease: HostedQueueLease,
        *,
        worker_id: str,
        lease_seconds: int,
        reason: str,
    ) -> HostedQueueLease:
        state = TaskState.from_dict(deepcopy(lease.state.to_dict()))
        state.status = "blocked"
        state.blocked_reason = reason
        state.last_error = None
        state.touch()
        released = self.queue.save(
            lease.spec,
            state,
            expected_revision=lease.revision,
            worker_id=worker_id,
            lease_generation=lease.lease_generation,
            lease_seconds=lease_seconds,
        )
        if released.status != "blocked" or released.lease_owner is not None:
            raise RuntimeError("read_only_worker_failed_to_release_lease")
        self.activity.append(
            task_id=lease.task_id,
            event_type="readonly_worker_blocked",
            payload={
                "worker_id": worker_id,
                "revision": released.revision,
                "lease_generation": released.lease_generation,
                "reason": reason,
            },
        )
        return released

    def run_next(
        self,
        *,
        worker_id: str,
        lease_seconds: int = 120,
    ) -> HostedReadOnlyWorkerResult:
        if self.execution_authorized is not True:
            raise HostedExecutionNotAuthorized("hosted_readonly_execution_not_authorized")

        lease = self.queue.claim(worker_id=worker_id, lease_seconds=lease_seconds)
        if lease is None:
            return HostedReadOnlyWorkerResult(
                claimed=False,
                task_id=None,
                execution_enabled=True,
                blocked_reason="queue_empty",
            )

        self.activity.append(
            task_id=lease.task_id,
            event_type="readonly_worker_claimed",
            payload={
                "worker_id": worker_id,
                "revision": lease.revision,
                "lease_generation": lease.lease_generation,
            },
        )

        scope_failure = self._scope_failure(lease)
        if scope_failure:
            self._release_blocked(lease, worker_id=worker_id, lease_seconds=lease_seconds, reason=scope_failure)
            return HostedReadOnlyWorkerResult(True, lease.task_id, True, blocked_reason=scope_failure)

        missing, non_read = self._preflight(lease.spec)
        if missing:
            reason = "preflight_missing_actions:" + ",".join(missing)
            self._release_blocked(
                lease,
                worker_id=worker_id,
                lease_seconds=lease_seconds,
                reason=reason,
            )
            return HostedReadOnlyWorkerResult(True, lease.task_id, True, blocked_reason=reason)
        if non_read:
            reason = "readonly_worker_forbidden_actions:" + ",".join(non_read)
            self._release_blocked(
                lease,
                worker_id=worker_id,
                lease_seconds=lease_seconds,
                reason=reason,
            )
            return HostedReadOnlyWorkerResult(True, lease.task_id, True, blocked_reason=reason)

        store = HostedLeaseStateStore(
            queue=self.queue,
            activity=self.activity,
            lease=lease,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
        )
        outcome = AgentRunner(store, self._guarded_actions(store)).run(lease.spec)
        return HostedReadOnlyWorkerResult(
            claimed=True,
            task_id=lease.task_id,
            execution_enabled=True,
            outcome=outcome,
            blocked_reason=outcome.blocked_reason,
        )
