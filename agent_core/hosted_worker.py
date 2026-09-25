from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .adapters import ToolRegistry
from .hosted_activity import HostedActivityClient
from .hosted_queue import HostedQueueClient, HostedQueueLease
from .model import TaskState


@dataclass(frozen=True)
class HostedWorkerDecision:
    claimed: bool
    task_id: str | None
    revision: int | None
    lease_generation: int | None
    ready: bool
    execution_enabled: bool
    missing_actions: tuple[str, ...] = ()
    forbidden_actions: tuple[str, ...] = ()
    blocked_reason: str | None = None


class HostedWorkerCoordinator:
    """Compose durable queue ownership and capability preflight without execution.

    This is deliberately a fail-closed coordinator, not an always-on worker. It may
    claim one due task to prove queue ownership/fencing, but it never invokes a task
    action. Every claim is durably released as ``blocked`` before returning so an
    inspection cannot leave ambiguous running work behind.
    """

    EXECUTION_BLOCK_REASON = "hosted_task_execution_not_activated"

    def __init__(
        self,
        *,
        queue: HostedQueueClient,
        activity: HostedActivityClient,
        registry: ToolRegistry,
    ) -> None:
        self.queue = queue
        self.activity = activity
        self.registry = registry

    @staticmethod
    def _used_actions(lease: HostedQueueLease) -> set[str]:
        return {
            action
            for step in lease.spec.steps
            for action in (step.action, step.verify_action)
            if action
        }

    def _preflight(
        self,
        lease: HostedQueueLease,
        *,
        allowed_access: Iterable[str],
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        lease.spec.validate()
        used = self._used_actions(lease)
        registered = set(self.registry.actions())
        missing = tuple(sorted(used - registered))
        allowed = set(allowed_access)
        forbidden: list[str] = []
        for action in sorted(used & registered):
            capability = self.registry.capability(action)
            if capability is None or capability.access not in allowed:
                forbidden.append(action)
        return missing, tuple(forbidden)

    @staticmethod
    def _blocked_state(lease: HostedQueueLease, reason: str) -> TaskState:
        state = TaskState.from_dict(lease.state.to_dict())
        state.status = "blocked"
        state.blocked_reason = reason
        state.last_error = None
        state.touch()
        return state

    def inspect_next(
        self,
        *,
        worker_id: str,
        lease_seconds: int = 120,
        allowed_access: Iterable[str] = ("read",),
    ) -> HostedWorkerDecision:
        """Claim/preflight one due task, then release it without executing actions."""
        lease = self.queue.claim(worker_id=worker_id, lease_seconds=lease_seconds)
        if lease is None:
            return HostedWorkerDecision(
                claimed=False,
                task_id=None,
                revision=None,
                lease_generation=None,
                ready=False,
                execution_enabled=False,
                blocked_reason="queue_empty",
            )

        self.activity.append(
            task_id=lease.task_id,
            event_type="worker_preflight_started",
            payload={
                "worker_id": worker_id,
                "revision": lease.revision,
                "lease_generation": lease.lease_generation,
            },
        )

        missing, forbidden = self._preflight(lease, allowed_access=allowed_access)
        if missing:
            reason = "preflight_missing_actions:" + ",".join(missing)
        elif forbidden:
            reason = "preflight_forbidden_actions:" + ",".join(forbidden)
        else:
            reason = self.EXECUTION_BLOCK_REASON

        blocked_state = self._blocked_state(lease, reason)
        released = self.queue.save(
            lease.spec,
            blocked_state,
            expected_revision=lease.revision,
            worker_id=worker_id,
            lease_generation=lease.lease_generation,
            lease_seconds=lease_seconds,
        )
        if released.status != "blocked" or released.lease_owner is not None:
            raise RuntimeError("worker_preflight_failed_to_release_lease")

        self.activity.append(
            task_id=lease.task_id,
            event_type="worker_preflight_blocked",
            payload={
                "worker_id": worker_id,
                "revision": released.revision,
                "lease_generation": released.lease_generation,
                "reason": reason,
                "missing_actions": list(missing),
                "forbidden_actions": list(forbidden),
                "execution_enabled": False,
            },
        )

        return HostedWorkerDecision(
            claimed=True,
            task_id=lease.task_id,
            revision=released.revision,
            lease_generation=released.lease_generation,
            ready=not missing and not forbidden,
            execution_enabled=False,
            missing_actions=missing,
            forbidden_actions=forbidden,
            blocked_reason=reason,
        )
