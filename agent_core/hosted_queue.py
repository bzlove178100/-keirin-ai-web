from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .model import TaskSpec, TaskState

QueueTransport = Callable[[str, dict[str, Any]], Mapping[str, Any]]

_FORBIDDEN_KEYS = {
    "token",
    "access_token",
    "refresh_token",
    "password",
    "secret",
    "service_role",
    "service_role_key",
    "api_key",
    "apikey",
    "authorization",
}


class HostedQueueError(RuntimeError):
    """Base error for provider-neutral hosted queue coordination."""


class HostedQueueConflict(HostedQueueError):
    """Raised when a revision, worker or fencing token is stale/invalid."""


class HostedQueueIntegrityError(HostedQueueError):
    """Raised when a remote lease/checkpoint violates the queue contract."""


@dataclass(frozen=True)
class HostedQueueLease:
    task_id: str
    status: str
    revision: int
    idempotency_key: str
    spec: TaskSpec
    state: TaskState
    attempt_count: int
    max_attempts: int
    lease_owner: str | None
    lease_generation: int
    lease_expires_at: str | None
    not_before: str
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def fenced(self) -> bool:
        return self.status == "running" and self.lease_owner is not None and self.lease_expires_at is not None


def _forbidden_secret_path(value: Any, path: str = "$") -> str | None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            if key_text.lower() in _FORBIDDEN_KEYS:
                return f"{path}.{key_text}"
            found = _forbidden_secret_path(child, f"{path}.{key_text}")
            if found:
                return found
        return None
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            found = _forbidden_secret_path(child, f"{path}[{index}]")
            if found:
                return found
    return None


class HostedQueueClient:
    """Strict client for queue claim/fencing/reconciliation modes.

    The host owns authentication and transport. This client never executes task
    actions. Claiming only establishes durable ownership/fencing metadata; actual
    execution remains a separate authorization and worker concern.
    """

    _ROW_STATUSES = {"queued", "running", "blocked", "completed", "failed"}
    _SAVE_STATUSES = {"running", "blocked", "completed", "failed"}

    def __init__(self, transport: QueueTransport):
        self._transport = transport

    @staticmethod
    def _valid_worker_id(worker_id: str) -> bool:
        if not isinstance(worker_id, str) or not worker_id or len(worker_id) > 128:
            return False
        first = worker_id[0]
        if not first.isascii() or not first.isalnum():
            return False
        return all(ch.isascii() and (ch.isalnum() or ch in "._:-") for ch in worker_id)

    @staticmethod
    def _valid_lease_seconds(value: int) -> bool:
        return type(value) is int and 15 <= value <= 3600

    @staticmethod
    def _parse_int(value: Any, *, name: str, minimum: int = 0) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise HostedQueueIntegrityError(f"invalid_{name}")
        return value

    @staticmethod
    def _clean_state(spec: TaskSpec, state: TaskState) -> TaskState:
        detached = TaskState.from_dict(deepcopy(state.to_dict()))
        fingerprint = spec.fingerprint()
        if detached.task_id != spec.task_id:
            raise HostedQueueIntegrityError("task_state_id_mismatch")
        if detached.spec_fingerprint != fingerprint:
            raise HostedQueueIntegrityError("task_spec_changed")
        secret_path = _forbidden_secret_path(detached.to_dict())
        if secret_path:
            raise HostedQueueIntegrityError(f"state_contains_forbidden_secret:{secret_path}")
        return detached

    @staticmethod
    def _parse_lease(value: Any, *, expected_spec: TaskSpec | None = None) -> HostedQueueLease:
        if not isinstance(value, Mapping):
            raise HostedQueueIntegrityError("queue_lease_object_required")
        task_id = value.get("task_id")
        status = value.get("status")
        if not isinstance(task_id, str) or not task_id:
            raise HostedQueueIntegrityError("invalid_queue_task_id")
        if status not in HostedQueueClient._ROW_STATUSES:
            raise HostedQueueIntegrityError("invalid_queue_status")

        raw_spec = value.get("spec")
        raw_state = value.get("state")
        if not isinstance(raw_spec, dict) or not isinstance(raw_state, dict):
            raise HostedQueueIntegrityError("queue_spec_state_required")
        try:
            spec = TaskSpec.from_dict(deepcopy(raw_spec))
            state = TaskState.from_dict(deepcopy(raw_state))
        except (KeyError, TypeError, ValueError) as exc:
            raise HostedQueueIntegrityError("invalid_queue_model") from exc

        if spec.task_id != task_id or state.task_id != task_id:
            raise HostedQueueIntegrityError("queue_task_identity_mismatch")
        if expected_spec is not None and spec.to_dict() != expected_spec.to_dict():
            raise HostedQueueIntegrityError("task_spec_changed")
        fingerprint = spec.fingerprint()
        if value.get("spec_fingerprint") != fingerprint or state.spec_fingerprint != fingerprint:
            raise HostedQueueIntegrityError("queue_spec_fingerprint_mismatch")
        expected_state_status = "pending" if status == "queued" else status
        if state.status != expected_state_status:
            raise HostedQueueIntegrityError("queue_state_status_mismatch")
        secret_path = _forbidden_secret_path({"spec": raw_spec, "state": raw_state})
        if secret_path:
            raise HostedQueueIntegrityError(f"queue_record_contains_forbidden_secret:{secret_path}")

        revision = HostedQueueClient._parse_int(value.get("revision"), name="queue_revision")
        attempt_count = HostedQueueClient._parse_int(value.get("attempt_count"), name="attempt_count")
        max_attempts = HostedQueueClient._parse_int(value.get("max_attempts"), name="max_attempts", minimum=1)
        generation = HostedQueueClient._parse_int(value.get("lease_generation"), name="lease_generation")
        if attempt_count > max_attempts:
            raise HostedQueueIntegrityError("attempt_budget_exceeded")
        key = value.get("idempotency_key")
        if not isinstance(key, str) or not key:
            raise HostedQueueIntegrityError("invalid_queue_idempotency_key")
        not_before = value.get("not_before")
        if not isinstance(not_before, str) or not not_before:
            raise HostedQueueIntegrityError("invalid_not_before")

        lease_owner = value.get("lease_owner")
        lease_expires_at = value.get("lease_expires_at")
        if status == "running":
            if not isinstance(lease_owner, str) or not HostedQueueClient._valid_worker_id(lease_owner):
                raise HostedQueueIntegrityError("invalid_lease_owner")
            if generation < 1:
                raise HostedQueueIntegrityError("invalid_lease_generation")
            if not isinstance(lease_expires_at, str) or not lease_expires_at:
                raise HostedQueueIntegrityError("invalid_lease_expiry")
        else:
            if lease_owner is not None or lease_expires_at is not None:
                raise HostedQueueIntegrityError("terminal_or_queued_lease_not_cleared")

        return HostedQueueLease(
            task_id=task_id,
            status=str(status),
            revision=revision,
            idempotency_key=key,
            spec=spec,
            state=state,
            attempt_count=attempt_count,
            max_attempts=max_attempts,
            lease_owner=lease_owner if isinstance(lease_owner, str) else None,
            lease_generation=generation,
            lease_expires_at=lease_expires_at if isinstance(lease_expires_at, str) else None,
            not_before=not_before,
            created_at=value.get("created_at") if isinstance(value.get("created_at"), str) else None,
            updated_at=value.get("updated_at") if isinstance(value.get("updated_at"), str) else None,
        )

    @staticmethod
    def _error_from_response(response: Mapping[str, Any]) -> HostedQueueError:
        message = str(response.get("error") or "hosted_queue_request_failed")
        backend_code = str(response.get("backend_code") or "")
        if backend_code == "40001" or "conflict" in message or "expired" in message:
            return HostedQueueConflict(message)
        return HostedQueueError(message)

    def _request(self, mode: str, payload: dict[str, Any]) -> Mapping[str, Any]:
        response = self._transport(mode, deepcopy(payload))
        if not isinstance(response, Mapping):
            raise HostedQueueError("invalid_hosted_queue_response")
        if response.get("success") is not True:
            raise self._error_from_response(response)
        return response

    def inspect(self, spec: TaskSpec) -> HostedQueueLease:
        """Read one durable queue/checkpoint row without claiming, saving, or requeueing it."""
        spec = TaskSpec.from_dict(deepcopy(spec.to_dict()))
        spec.validate()
        response = self._request("checkpoint_get", {"task_id": spec.task_id})
        return self._parse_lease(response.get("checkpoint"), expected_spec=spec)

    def claim(self, *, worker_id: str, lease_seconds: int = 120) -> HostedQueueLease | None:
        if not self._valid_worker_id(worker_id):
            raise ValueError("invalid_worker_id")
        if not self._valid_lease_seconds(lease_seconds):
            raise ValueError("invalid_lease_seconds")
        response = self._request(
            "queue_claim",
            {"worker_id": worker_id, "lease_seconds": lease_seconds},
        )
        claimed = response.get("claimed")
        lease = response.get("lease")
        if claimed is False and lease is None:
            return None
        if claimed is not True:
            raise HostedQueueIntegrityError("queue_claim_flag_mismatch")
        record = self._parse_lease(lease)
        if record.status != "running" or record.lease_owner != worker_id:
            raise HostedQueueIntegrityError("queue_claim_identity_mismatch")
        if record.revision < 1 or record.attempt_count < 1:
            raise HostedQueueIntegrityError("queue_claim_counters_not_advanced")
        return record

    def save(
        self,
        spec: TaskSpec,
        state: TaskState,
        *,
        expected_revision: int,
        worker_id: str,
        lease_generation: int,
        lease_seconds: int = 120,
    ) -> HostedQueueLease:
        spec = TaskSpec.from_dict(deepcopy(spec.to_dict()))
        spec.validate()
        state = self._clean_state(spec, state)
        if state.status not in self._SAVE_STATUSES:
            raise ValueError("invalid_leased_checkpoint_status")
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("expected_revision_must_be_non_negative_integer")
        if not self._valid_worker_id(worker_id):
            raise ValueError("invalid_worker_id")
        if type(lease_generation) is not int or lease_generation < 1:
            raise ValueError("invalid_lease_generation")
        if not self._valid_lease_seconds(lease_seconds):
            raise ValueError("invalid_lease_seconds")
        response = self._request(
            "queue_save",
            {
                "task_id": spec.task_id,
                "expected_revision": expected_revision,
                "worker_id": worker_id,
                "lease_generation": lease_generation,
                "status": state.status,
                "state": state.to_dict(),
                "lease_seconds": lease_seconds,
            },
        )
        record = self._parse_lease(response.get("lease"), expected_spec=spec)
        if record.revision != expected_revision + 1:
            raise HostedQueueIntegrityError("queue_revision_increment_mismatch")
        if record.lease_generation != lease_generation:
            raise HostedQueueIntegrityError("queue_fencing_generation_changed")
        if state.status == "running":
            if record.lease_owner != worker_id or not record.fenced:
                raise HostedQueueIntegrityError("running_lease_not_preserved")
        elif record.lease_owner is not None or record.lease_expires_at is not None:
            raise HostedQueueIntegrityError("terminal_lease_not_released")
        return record

    def reconcile_expired(
        self,
        spec: TaskSpec,
        state: TaskState,
        *,
        expected_revision: int,
        lease_generation: int,
    ) -> HostedQueueLease:
        spec = TaskSpec.from_dict(deepcopy(spec.to_dict()))
        spec.validate()
        state = self._clean_state(spec, state)
        if state.status != "blocked":
            raise ValueError("blocked_state_required")
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("expected_revision_must_be_non_negative_integer")
        if type(lease_generation) is not int or lease_generation < 1:
            raise ValueError("invalid_lease_generation")
        response = self._request(
            "queue_reconcile_expired",
            {
                "task_id": spec.task_id,
                "expected_revision": expected_revision,
                "lease_generation": lease_generation,
                "state": state.to_dict(),
            },
        )
        record = self._parse_lease(response.get("lease"), expected_spec=spec)
        if record.status != "blocked":
            raise HostedQueueIntegrityError("expired_reconciliation_not_blocked")
        if record.revision != expected_revision + 1:
            raise HostedQueueIntegrityError("queue_revision_increment_mismatch")
        if record.lease_generation != lease_generation:
            raise HostedQueueIntegrityError("queue_fencing_generation_changed")
        if record.lease_owner is not None or record.lease_expires_at is not None:
            raise HostedQueueIntegrityError("expired_lease_not_cleared")
        return record
