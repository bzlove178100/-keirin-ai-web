from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Mapping

ActivityTransport = Callable[[str, dict[str, Any]], Mapping[str, Any]]

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


class HostedActivityError(RuntimeError):
    """Base error for the provider-neutral hosted activity client."""


class HostedActivityIntegrityError(HostedActivityError):
    """Raised when a remote activity record fails the shared contract."""


@dataclass(frozen=True)
class HostedActivityEvent:
    event_id: int
    task_id: str
    event_type: str
    step_id: str | None
    payload: dict[str, Any]
    created_at: str


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


class HostedActivityClient:
    """Append/read client for the owner-only hosted activity ledger.

    Authentication and transport stay with the host. This class validates payloads
    before dispatch and fails closed on malformed records returned by the host.
    It does not mutate task checkpoints or execute tasks.
    """

    def __init__(self, transport: ActivityTransport):
        self._transport = transport

    @staticmethod
    def _valid_task_id(task_id: str) -> bool:
        if not isinstance(task_id, str) or not task_id or len(task_id) > 128:
            return False
        first = task_id[0]
        if not first.isascii() or not first.isalnum():
            return False
        return all(ch.isascii() and (ch.isalnum() or ch in "._-") for ch in task_id)

    @staticmethod
    def _validate_event_type(event_type: str) -> str:
        if not isinstance(event_type, str):
            raise ValueError("event_type_required")
        value = event_type.strip()
        if not value or len(value) > 128:
            raise ValueError("invalid_event_type")
        return value

    @staticmethod
    def _validate_step_id(step_id: str | None) -> str | None:
        if step_id is None:
            return None
        if not isinstance(step_id, str):
            raise ValueError("invalid_step_id")
        value = step_id.strip()
        if not value or len(value) > 128:
            raise ValueError("invalid_step_id")
        return value

    @staticmethod
    def _validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("event_payload_must_be_object")
        detached = deepcopy(payload)
        secret_path = _forbidden_secret_path(detached)
        if secret_path:
            raise ValueError(f"event_payload_contains_forbidden_secret:{secret_path}")
        return detached

    @staticmethod
    def _parse_event(value: Any, *, expected_task_id: str | None = None) -> HostedActivityEvent:
        if not isinstance(value, Mapping):
            raise HostedActivityIntegrityError("activity_event_object_required")
        event_id = value.get("event_id")
        task_id = value.get("task_id")
        event_type = value.get("event_type")
        step_id = value.get("step_id")
        payload = value.get("payload")
        created_at = value.get("created_at")
        if isinstance(event_id, bool) or not isinstance(event_id, int) or event_id <= 0:
            raise HostedActivityIntegrityError("invalid_activity_event_id")
        if not isinstance(task_id, str) or not HostedActivityClient._valid_task_id(task_id):
            raise HostedActivityIntegrityError("invalid_activity_task_id")
        if expected_task_id is not None and task_id != expected_task_id:
            raise HostedActivityIntegrityError("activity_task_id_mismatch")
        if not isinstance(event_type, str) or not event_type.strip() or len(event_type) > 128:
            raise HostedActivityIntegrityError("invalid_activity_event_type")
        if step_id is not None and (not isinstance(step_id, str) or not step_id.strip() or len(step_id) > 128):
            raise HostedActivityIntegrityError("invalid_activity_step_id")
        if not isinstance(payload, dict):
            raise HostedActivityIntegrityError("invalid_activity_payload")
        if _forbidden_secret_path(payload):
            raise HostedActivityIntegrityError("activity_payload_contains_forbidden_secret")
        if not isinstance(created_at, str) or not created_at:
            raise HostedActivityIntegrityError("invalid_activity_created_at")
        return HostedActivityEvent(
            event_id=event_id,
            task_id=task_id,
            event_type=event_type.strip(),
            step_id=step_id.strip() if isinstance(step_id, str) else None,
            payload=deepcopy(payload),
            created_at=created_at,
        )

    def _request(self, mode: str, payload: dict[str, Any]) -> Mapping[str, Any]:
        response = self._transport(mode, deepcopy(payload))
        if not isinstance(response, Mapping):
            raise HostedActivityError("invalid_hosted_activity_response")
        if response.get("success") is not True:
            raise HostedActivityError(str(response.get("error") or "hosted_activity_request_failed"))
        return response

    def append(
        self,
        *,
        task_id: str,
        event_type: str,
        step_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> HostedActivityEvent:
        if not self._valid_task_id(task_id):
            raise ValueError("invalid_task_id")
        event_type = self._validate_event_type(event_type)
        step_id = self._validate_step_id(step_id)
        clean_payload = self._validate_payload(payload or {})
        response = self._request(
            "event_append",
            {
                "task_id": task_id,
                "event_type": event_type,
                "step_id": step_id,
                "payload": clean_payload,
            },
        )
        return self._parse_event(response.get("event"), expected_task_id=task_id)

    def list(
        self,
        *,
        task_id: str,
        after_event_id: int | None = None,
        limit: int = 100,
    ) -> tuple[HostedActivityEvent, ...]:
        if not self._valid_task_id(task_id):
            raise ValueError("invalid_task_id")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
            raise ValueError("activity_list_limit_out_of_range")
        if after_event_id is not None and (
            isinstance(after_event_id, bool) or not isinstance(after_event_id, int) or after_event_id < 0
        ):
            raise ValueError("invalid_after_event_id")
        request: dict[str, Any] = {"task_id": task_id, "limit": limit}
        if after_event_id is not None:
            request["after_event_id"] = after_event_id
        response = self._request("event_list", request)
        rows = response.get("events")
        if not isinstance(rows, list):
            raise HostedActivityIntegrityError("activity_event_list_required")
        events = tuple(self._parse_event(row, expected_task_id=task_id) for row in rows)
        event_ids = [event.event_id for event in events]
        if event_ids != sorted(event_ids) or len(event_ids) != len(set(event_ids)):
            raise HostedActivityIntegrityError("activity_event_order_or_duplicate_error")
        if after_event_id is not None and any(event_id <= after_event_id for event_id in event_ids):
            raise HostedActivityIntegrityError("activity_event_cursor_violation")
        return events
