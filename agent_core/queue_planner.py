"""Pure hosted queue planning. No claims, writes, tool calls or task execution.

A proposal is stale immediately: a future worker must atomically claim the exact
owner/task/revision and repeat authorization/preflight before running anything.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


def _aware(value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone_aware_timestamp_required")


@dataclass(frozen=True)
class QueueEntry:
    owner_id: str
    task_id: str
    idempotency_key: str
    revision: int
    status: str
    created_at: datetime
    not_before: datetime
    attempts: int = 0
    max_attempts: int = 1
    lease_expires_at: datetime | None = None

    def validate(self) -> None:
        for value in (self.owner_id, self.task_id, self.idempotency_key):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("queue_identity_required")
        if self.status not in {"queued", "running", "blocked", "completed", "failed"}:
            raise ValueError("invalid_queue_status")
        for value in (self.revision, self.attempts, self.max_attempts):
            if type(value) is not int or value < 0:
                raise ValueError("invalid_queue_counter")
        if self.max_attempts < 1 or self.attempts > self.max_attempts:
            raise ValueError("invalid_attempt_budget")
        _aware(self.created_at)
        _aware(self.not_before)
        if self.lease_expires_at is not None:
            _aware(self.lease_expires_at)
            if self.status != "running":
                raise ValueError("lease_requires_running_status")


@dataclass(frozen=True)
class QueueDecision:
    owner_id: str
    task_id: str
    expected_revision: int
    disposition: str
    reason: str


@dataclass(frozen=True)
class QueuePlan:
    decisions: tuple[QueueDecision, ...]
    # These are invariants of this planner, not activation options.
    @property
    def execution_enabled(self) -> bool:
        return False

    @property
    def persistence_enabled(self) -> bool:
        return False


def plan_queue(entries: Iterable[QueueEntry], *, owner_id: str,
               now: datetime, capacity: int = 1) -> QueuePlan:
    """Propose FIFO claims within one trusted host-supplied owner scope.

    Running tasks occupy capacity. An expired/missing lease is ambiguous and
    requires reconciliation; it is never automatically retried or reclaimed.
    All such tasks still occupy capacity until reconciliation is persisted.
    """
    _aware(now)
    if not isinstance(owner_id, str) or not owner_id.strip():
        raise ValueError("owner_scope_required")
    if type(capacity) is not int or capacity < 1:
        raise ValueError("positive_capacity_required")
    rows = tuple(entries)
    ids: set[str] = set()
    keys: set[str] = set()
    for row in rows:
        row.validate()
        if row.owner_id != owner_id:
            raise ValueError("queue_owner_scope_mismatch")
        if row.task_id in ids or row.idempotency_key in keys:
            raise ValueError("duplicate_queue_identity")
        ids.add(row.task_id)
        keys.add(row.idempotency_key)
    slots = max(0, capacity - sum(row.status == "running" for row in rows))
    decisions = []
    for row in sorted(rows, key=lambda item: (item.created_at, item.task_id)):
        if row.status in {"completed", "blocked", "failed"}:
            disposition, reason = "skip", "terminal_state"
        elif row.status == "running":
            if row.lease_expires_at is None or row.lease_expires_at <= now:
                disposition, reason = "reconcile", "running_outcome_unknown"
            else:
                disposition, reason = "wait", "active_lease"
        elif row.attempts >= row.max_attempts:
            disposition, reason = "reconcile", "attempt_budget_exhausted"
        elif row.created_at > now or row.not_before > now:
            disposition, reason = "wait", "not_due"
        elif slots == 0:
            disposition, reason = "wait", "capacity_exhausted"
        else:
            disposition, reason = "propose_claim", "requires_atomic_claim_and_preflight"
            slots -= 1
        decisions.append(QueueDecision(owner_id, row.task_id, row.revision,
                                       disposition, reason))
    return QueuePlan(tuple(decisions))
