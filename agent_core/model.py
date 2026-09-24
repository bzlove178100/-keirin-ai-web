from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

TASK_SCHEMA_VERSION = "agent-task-v1"
STATE_SCHEMA_VERSION = "agent-task-state-v1"
ARTIFACT_SCHEMA_VERSION = "agent-artifact-state-v1"

TaskStatus = Literal["pending", "running", "completed", "blocked", "failed"]
ReconciliationResolution = Literal["not_applied", "applied_and_verified", "needs_manual_action"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class StepSpec:
    step_id: str
    action: str
    args: dict[str, Any] = field(default_factory=dict)
    verify_action: str | None = None
    retry_safe: bool = False
    max_attempts: int = 1

    def validate(self) -> None:
        if not self.step_id.strip():
            raise ValueError("step_id_required")
        if not self.action.strip():
            raise ValueError("action_required")
        if self.max_attempts < 1:
            raise ValueError("max_attempts_must_be_positive")
        if not self.retry_safe and self.max_attempts != 1:
            raise ValueError("unsafe_retry_requires_single_attempt")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StepSpec":
        return cls(
            step_id=str(payload["step_id"]),
            action=str(payload["action"]),
            args=dict(payload.get("args") or {}),
            verify_action=(str(payload["verify_action"]) if payload.get("verify_action") is not None else None),
            retry_safe=bool(payload.get("retry_safe", False)),
            max_attempts=int(payload.get("max_attempts", 1)),
        )


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    title: str
    goal: str
    allowed_actions: tuple[str, ...]
    steps: tuple[StepSpec, ...]
    inputs: dict[str, Any] = field(default_factory=dict)
    completion_conditions: tuple[str, ...] = field(default_factory=tuple)
    schema_version: str = TASK_SCHEMA_VERSION

    def validate(self) -> None:
        if self.schema_version != TASK_SCHEMA_VERSION:
            raise ValueError("task_schema_mismatch")
        if not self.task_id.strip():
            raise ValueError("task_id_required")
        if not self.title.strip():
            raise ValueError("title_required")
        if not self.goal.strip():
            raise ValueError("goal_required")
        if not self.steps:
            raise ValueError("at_least_one_step_required")
        allowed = set(self.allowed_actions)
        if len(allowed) != len(self.allowed_actions):
            raise ValueError("duplicate_allowed_action")
        seen: set[str] = set()
        for step in self.steps:
            step.validate()
            if step.step_id in seen:
                raise ValueError("duplicate_step_id")
            seen.add(step.step_id)
            if step.action not in allowed:
                raise ValueError(f"action_not_allowed:{step.action}")
            if step.verify_action and step.verify_action not in allowed:
                raise ValueError(f"verification_action_not_allowed:{step.verify_action}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "title": self.title,
            "goal": self.goal,
            "allowed_actions": list(self.allowed_actions),
            "steps": [step.to_dict() for step in self.steps],
            "inputs": dict(self.inputs),
            "completion_conditions": list(self.completion_conditions),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TaskSpec":
        spec = cls(
            task_id=str(payload["task_id"]),
            title=str(payload["title"]),
            goal=str(payload["goal"]),
            allowed_actions=tuple(str(value) for value in payload.get("allowed_actions") or ()),
            steps=tuple(StepSpec.from_dict(item) for item in payload.get("steps") or ()),
            inputs=dict(payload.get("inputs") or {}),
            completion_conditions=tuple(str(value) for value in payload.get("completion_conditions") or ()),
            schema_version=str(payload.get("schema_version") or ""),
        )
        spec.validate()
        return spec


@dataclass
class ArtifactState:
    artifact_id: str
    kind: str
    locator: str | None = None
    created: bool = False
    verified: bool = False
    persistent_saved: bool = False
    device_saved: bool = False
    ui_loaded: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str = ARTIFACT_SCHEMA_VERSION

    def merge(self, update: "ArtifactUpdate") -> None:
        if update.kind and self.kind != update.kind:
            raise ValueError("artifact_kind_conflict")
        if update.locator is not None:
            self.locator = update.locator
        for name in ("created", "verified", "persistent_saved", "device_saved", "ui_loaded"):
            value = getattr(update, name)
            if value is not None:
                setattr(self, name, bool(value))
        if update.metadata:
            self.metadata.update(update.metadata)


@dataclass(frozen=True)
class ArtifactUpdate:
    artifact_id: str
    kind: str
    locator: str | None = None
    created: bool | None = None
    verified: bool | None = None
    persistent_saved: bool | None = None
    device_saved: bool | None = None
    ui_loaded: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.artifact_id.strip():
            raise ValueError("artifact_id_required")
        if not self.kind.strip():
            raise ValueError("artifact_kind_required")


@dataclass(frozen=True)
class ActionResult:
    message: str = ""
    artifacts: tuple[ArtifactUpdate, ...] = field(default_factory=tuple)
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskState:
    task_id: str
    status: TaskStatus = "pending"
    completed_steps: list[str] = field(default_factory=list)
    attempts: dict[str, int] = field(default_factory=dict)
    blocked_reason: str | None = None
    last_error: str | None = None
    artifacts: dict[str, ArtifactState] = field(default_factory=dict)
    reconciliations: list[dict[str, Any]] = field(default_factory=list)
    updated_at: str = field(default_factory=utc_now_iso)
    schema_version: str = STATE_SCHEMA_VERSION

    def touch(self) -> None:
        self.updated_at = utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["artifacts"] = {key: asdict(value) for key, value in self.artifacts.items()}
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TaskState":
        if payload.get("schema_version") != STATE_SCHEMA_VERSION:
            raise ValueError("state_schema_mismatch")
        artifacts = {
            key: ArtifactState(**value)
            for key, value in dict(payload.get("artifacts") or {}).items()
        }
        return cls(
            task_id=str(payload["task_id"]),
            status=payload.get("status", "pending"),
            completed_steps=list(payload.get("completed_steps") or []),
            attempts={str(k): int(v) for k, v in dict(payload.get("attempts") or {}).items()},
            blocked_reason=payload.get("blocked_reason"),
            last_error=payload.get("last_error"),
            artifacts=artifacts,
            reconciliations=list(payload.get("reconciliations") or []),
            updated_at=str(payload.get("updated_at") or utc_now_iso()),
            schema_version=str(payload.get("schema_version")),
        )
