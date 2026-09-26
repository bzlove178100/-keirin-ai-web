from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .model import TaskSpec, TaskState

CheckpointTransport = Callable[[str, dict[str, Any]], Mapping[str, Any]]


class HostedCheckpointError(RuntimeError):
    """Base error for the provider-neutral hosted checkpoint client."""


class HostedCheckpointConflict(HostedCheckpointError):
    """Raised when compare-and-swap or uniqueness rejects a checkpoint write."""


class HostedCheckpointNotFound(HostedCheckpointError):
    """Raised only when the hosted checkpoint API confirms a task is absent."""


class HostedCheckpointIntegrityError(HostedCheckpointError):
    """Raised when persisted state no longer matches its immutable TaskSpec."""


@dataclass(frozen=True)
class HostedCheckpointRecord:
    task_id: str
    status: str
    revision: int
    idempotency_key: str
    spec: TaskSpec
    state: TaskState
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True)
class HostedCheckpointSummary:
    task_id: str
    status: str
    revision: int
    idempotency_key: str
    blocked_reason: str | None = None
    last_error: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class HostedCheckpointClient:
    """Strict client for the owner-only hosted checkpoint API.

    Authentication and HTTP transport belong to the host. This client only maps the
    shared ``TaskSpec``/``TaskState`` model to checkpoint modes and verifies every
    returned full checkpoint before it is accepted for resume.

    It intentionally does not execute tasks, claim queue leases, or own credentials.
    """

    _ROW_STATUSES = {"queued", "running", "blocked", "completed", "failed"}

    def __init__(self, transport: CheckpointTransport):
        self._transport = transport

    @staticmethod
    def _detached_spec(spec: TaskSpec) -> TaskSpec:
        return TaskSpec.from_dict(json.loads(json.dumps(spec.to_dict(), ensure_ascii=False, allow_nan=False)))

    @staticmethod
    def _detached_state(state: TaskState) -> TaskState:
        return TaskState.from_dict(json.loads(json.dumps(state.to_dict(), ensure_ascii=False, allow_nan=False)))

    @staticmethod
    def _error_from_response(response: Mapping[str, Any]) -> HostedCheckpointError:
        message = str(response.get("error") or "hosted_checkpoint_request_failed")
        backend_code = str(response.get("backend_code") or "")
        backend_status = response.get("backend_status")
        if backend_status == 404 or message == "Checkpoint not found":
            return HostedCheckpointNotFound(message)
        if backend_code in {"40001", "23505"} or "checkpoint_conflict" in message or message == "duplicate":
            return HostedCheckpointConflict(message)
        return HostedCheckpointError(message)

    def _request(self, mode: str, payload: dict[str, Any]) -> Mapping[str, Any]:
        response = self._transport(mode, dict(payload))
        if not isinstance(response, Mapping):
            raise HostedCheckpointError("invalid_hosted_checkpoint_response")
        if response.get("success") is not True:
            raise self._error_from_response(response)
        return response

    @staticmethod
    def _validate_state_for_spec(spec: TaskSpec, state: TaskState, *, initial: bool = False) -> TaskState:
        detached = HostedCheckpointClient._detached_state(state)
        fingerprint = spec.fingerprint()
        if detached.task_id != spec.task_id:
            raise HostedCheckpointIntegrityError("task_state_id_mismatch")
        if detached.spec_fingerprint is None:
            detached.spec_fingerprint = fingerprint
        elif detached.spec_fingerprint != fingerprint:
            raise HostedCheckpointIntegrityError("task_spec_changed")
        if initial and detached.status != "pending":
            raise HostedCheckpointIntegrityError("initial_state_must_be_pending")
        return detached

    @staticmethod
    def _parse_revision(value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise HostedCheckpointIntegrityError("invalid_checkpoint_revision")
        return value

    @classmethod
    def _parse_full_record(cls, checkpoint: Any, expected_spec: TaskSpec) -> HostedCheckpointRecord:
        if not isinstance(checkpoint, Mapping):
            raise HostedCheckpointIntegrityError("checkpoint_object_required")
        task_id = checkpoint.get("task_id")
        if task_id != expected_spec.task_id:
            raise HostedCheckpointIntegrityError("checkpoint_task_id_mismatch")
        status = checkpoint.get("status")
        if status not in cls._ROW_STATUSES:
            raise HostedCheckpointIntegrityError("invalid_checkpoint_status")
        revision = cls._parse_revision(checkpoint.get("revision"))
        idempotency_key = checkpoint.get("idempotency_key")
        if not isinstance(idempotency_key, str) or not idempotency_key:
            raise HostedCheckpointIntegrityError("invalid_checkpoint_idempotency_key")

        raw_spec = checkpoint.get("spec")
        raw_state = checkpoint.get("state")
        if not isinstance(raw_spec, dict) or not isinstance(raw_state, dict):
            raise HostedCheckpointIntegrityError("checkpoint_spec_state_required")
        try:
            stored_spec = TaskSpec.from_dict(dict(raw_spec))
            stored_state = TaskState.from_dict(dict(raw_state))
        except (KeyError, TypeError, ValueError) as exc:
            raise HostedCheckpointIntegrityError("invalid_checkpoint_model") from exc

        expected_dict = expected_spec.to_dict()
        if stored_spec.to_dict() != expected_dict:
            raise HostedCheckpointIntegrityError("task_spec_changed")
        fingerprint = expected_spec.fingerprint()
        if checkpoint.get("spec_fingerprint") != fingerprint:
            raise HostedCheckpointIntegrityError("checkpoint_spec_fingerprint_mismatch")
        if stored_state.spec_fingerprint != fingerprint:
            raise HostedCheckpointIntegrityError("state_spec_fingerprint_mismatch")
        if stored_state.task_id != expected_spec.task_id:
            raise HostedCheckpointIntegrityError("task_state_id_mismatch")

        expected_state_status = "pending" if status == "queued" else status
        if stored_state.status != expected_state_status:
            raise HostedCheckpointIntegrityError("checkpoint_state_status_mismatch")

        return HostedCheckpointRecord(
            task_id=expected_spec.task_id,
            status=str(status),
            revision=revision,
            idempotency_key=idempotency_key,
            spec=stored_spec,
            state=stored_state,
            created_at=checkpoint.get("created_at") if isinstance(checkpoint.get("created_at"), str) else None,
            updated_at=checkpoint.get("updated_at") if isinstance(checkpoint.get("updated_at"), str) else None,
        )

    def create(
        self,
        spec: TaskSpec,
        *,
        state: TaskState | None = None,
        idempotency_key: str | None = None,
    ) -> HostedCheckpointRecord:
        spec = self._detached_spec(spec)
        spec.validate()
        state = self._validate_state_for_spec(spec, state or TaskState(task_id=spec.task_id), initial=True)
        key = (idempotency_key or spec.task_id).strip()
        if not key:
            raise ValueError("idempotency_key_required")
        response = self._request(
            "checkpoint_create",
            {
                "task": spec.to_dict(),
                "state": state.to_dict(),
                "idempotency_key": key,
            },
        )
        return self._parse_full_record(response.get("checkpoint"), spec)

    def get(self, spec: TaskSpec) -> HostedCheckpointRecord:
        spec = self._detached_spec(spec)
        spec.validate()
        response = self._request("checkpoint_get", {"task_id": spec.task_id})
        return self._parse_full_record(response.get("checkpoint"), spec)

    def load_state(self, spec: TaskSpec) -> TaskState:
        """Load state only after strict TaskSpec/fingerprint verification."""
        return self.get(spec).state

    def save(self, spec: TaskSpec, state: TaskState, *, expected_revision: int) -> HostedCheckpointRecord:
        spec = self._detached_spec(spec)
        spec.validate()
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 0:
            raise ValueError("expected_revision_must_be_non_negative_integer")
        state = self._validate_state_for_spec(spec, state)
        if state.status == "pending":
            raise ValueError("pending_state_cannot_be_saved_after_creation")
        response = self._request(
            "checkpoint_save",
            {
                "task_id": spec.task_id,
                "expected_revision": expected_revision,
                "status": state.status,
                "state": state.to_dict(),
            },
        )
        record = self._parse_full_record(response.get("checkpoint"), spec)
        if record.revision != expected_revision + 1:
            raise HostedCheckpointIntegrityError("checkpoint_revision_increment_mismatch")
        return record

    def list(self, *, status: str | None = None, limit: int = 20) -> tuple[HostedCheckpointSummary, ...]:
        if status is not None and status not in self._ROW_STATUSES:
            raise ValueError("invalid_checkpoint_status")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("checkpoint_list_limit_out_of_range")
        payload: dict[str, Any] = {"limit": limit}
        if status is not None:
            payload["status"] = status
        response = self._request("checkpoint_list", payload)
        rows = response.get("checkpoints")
        if not isinstance(rows, list):
            raise HostedCheckpointIntegrityError("checkpoint_list_required")
        summaries: list[HostedCheckpointSummary] = []
        seen: set[str] = set()
        for row in rows:
            if not isinstance(row, Mapping):
                raise HostedCheckpointIntegrityError("invalid_checkpoint_summary")
            task_id = row.get("task_id")
            row_status = row.get("status")
            key = row.get("idempotency_key")
            if not isinstance(task_id, str) or not task_id or task_id in seen:
                raise HostedCheckpointIntegrityError("invalid_or_duplicate_checkpoint_task_id")
            if row_status not in self._ROW_STATUSES:
                raise HostedCheckpointIntegrityError("invalid_checkpoint_status")
            if not isinstance(key, str) or not key:
                raise HostedCheckpointIntegrityError("invalid_checkpoint_idempotency_key")
            seen.add(task_id)
            summaries.append(
                HostedCheckpointSummary(
                    task_id=task_id,
                    status=str(row_status),
                    revision=self._parse_revision(row.get("revision")),
                    idempotency_key=key,
                    blocked_reason=row.get("blocked_reason") if isinstance(row.get("blocked_reason"), str) else None,
                    last_error=row.get("last_error") if isinstance(row.get("last_error"), str) else None,
                    created_at=row.get("created_at") if isinstance(row.get("created_at"), str) else None,
                    updated_at=row.get("updated_at") if isinstance(row.get("updated_at"), str) else None,
                )
            )
        return tuple(summaries)
