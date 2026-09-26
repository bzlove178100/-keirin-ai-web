from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol

_SAFE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]{0,127}$")
_SAFE_CODE_RE = re.compile(r"^[a-z][a-z0-9_.:-]{0,127}$")


@dataclass(frozen=True, slots=True)
class ActionDiagnosticEvent:
    """Persistence-independent diagnostic metadata for one action/verifier failure.

    This object intentionally has no exception message/repr, task inputs, action args,
    result payload, credential snapshot or provider response. It is suitable for an
    explicitly injected host-only ephemeral sink while durable task/activity state keeps
    using fixed/redacted error classifications.
    """

    task_id: str
    step_id: str
    action: str
    phase: str
    attempt: int
    retry_safe: bool
    classification: str
    exception_type: str

    def __post_init__(self) -> None:
        for value, error in (
            (self.task_id, "diagnostic_task_id_invalid"),
            (self.step_id, "diagnostic_step_id_invalid"),
            (self.action, "diagnostic_action_invalid"),
        ):
            if not isinstance(value, str) or not value or len(value) > 256:
                raise ValueError(error)
        if self.phase not in {"action", "verification"}:
            raise ValueError("diagnostic_phase_invalid")
        if type(self.attempt) is not int or self.attempt < 1:
            raise ValueError("diagnostic_attempt_invalid")
        if type(self.retry_safe) is not bool:
            raise ValueError("diagnostic_retry_safe_invalid")
        if not isinstance(self.classification, str) or not _SAFE_CODE_RE.fullmatch(self.classification):
            raise ValueError("diagnostic_classification_invalid")
        if not isinstance(self.exception_type, str) or not _SAFE_NAME_RE.fullmatch(self.exception_type):
            raise ValueError("diagnostic_exception_type_invalid")

    def to_safe_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "step_id": self.step_id,
            "action": self.action,
            "phase": self.phase,
            "attempt": self.attempt,
            "retry_safe": self.retry_safe,
            "classification": self.classification,
            "exception_type": self.exception_type,
        }


class ActionDiagnosticSink(Protocol):
    """Explicit host-only, non-durable failure observation boundary."""

    def emit(self, event: ActionDiagnosticEvent) -> None:
        ...


class CollectingDiagnosticSink:
    """In-memory reference/test sink; not a persistent production telemetry backend."""

    def __init__(self) -> None:
        self.events: list[ActionDiagnosticEvent] = []

    def emit(self, event: ActionDiagnosticEvent) -> None:
        if type(event) is not ActionDiagnosticEvent:
            raise ValueError("diagnostic_event_required")
        self.events.append(event)

    def clear(self) -> None:
        self.events.clear()
