from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from .model import ArtifactState, ArtifactUpdate, TaskState, utc_now_iso

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_RECONCILIATION_RESOLUTIONS = {"not_applied", "applied_and_verified", "needs_manual_action"}


class FileStateStore:
    """Small local filesystem state store with atomic task-state writes.

    Runtime data belongs outside the repository. The caller chooses ``base_dir``.
    Activity events are append-only JSON Lines so an interrupted process does not
    require rewriting prior events.
    """

    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.states_dir = self.base_dir / "states"
        self.ledger_path = self.base_dir / "activity.jsonl"
        self.states_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_task_id(task_id: str) -> str:
        if not _SAFE_ID.fullmatch(task_id):
            raise ValueError("unsafe_task_id")
        return task_id

    def state_path(self, task_id: str) -> Path:
        return self.states_dir / f"{self._safe_task_id(task_id)}.json"

    def load_state(self, task_id: str) -> TaskState:
        path = self.state_path(task_id)
        if not path.exists():
            return TaskState(task_id=task_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        state = TaskState.from_dict(payload)
        if state.task_id != task_id:
            raise ValueError("task_state_id_mismatch")
        return state

    def save_state(self, state: TaskState) -> None:
        path = self.state_path(state.task_id)
        state.touch()
        encoded = json.dumps(state.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def apply_artifact_update(self, state: TaskState, update: ArtifactUpdate) -> ArtifactState:
        update.validate()
        existing = state.artifacts.get(update.artifact_id)
        if existing is None:
            existing = ArtifactState(artifact_id=update.artifact_id, kind=update.kind)
            state.artifacts[update.artifact_id] = existing
        existing.merge(update)
        return existing

    def reconcile_blocked_step(
        self,
        task_id: str,
        *,
        step_id: str,
        resolution: str,
        note: str,
        artifact_updates: tuple[ArtifactUpdate, ...] = (),
    ) -> TaskState:
        """Explicitly reconcile a blocked step before any further execution.

        ``not_applied`` means the caller verified that the prior action did not take
        effect; the step may be attempted again on the next run.

        ``applied_and_verified`` means the caller verified the side effect and its
        intended result; the step is marked completed and will be skipped on resume.

        ``needs_manual_action`` keeps the task blocked and records why automation must
        not continue.
        """

        if resolution not in _RECONCILIATION_RESOLUTIONS:
            raise ValueError("invalid_reconciliation_resolution")
        if not step_id.strip():
            raise ValueError("step_id_required")
        if not note.strip():
            raise ValueError("reconciliation_note_required")

        state = self.load_state(task_id)
        if state.status != "blocked":
            raise ValueError("task_not_blocked")

        for update in artifact_updates:
            self.apply_artifact_update(state, update)

        record = {
            "timestamp": utc_now_iso(),
            "step_id": step_id,
            "resolution": resolution,
            "note": note,
            "previous_blocked_reason": state.blocked_reason,
            "previous_last_error": state.last_error,
        }
        state.reconciliations.append(record)

        if resolution == "not_applied":
            state.status = "pending"
            state.blocked_reason = None
            state.last_error = None
            state.attempts.pop(step_id, None)
        elif resolution == "applied_and_verified":
            if step_id not in state.completed_steps:
                state.completed_steps.append(step_id)
            state.status = "pending"
            state.blocked_reason = None
            state.last_error = None
        else:
            state.status = "blocked"

        self.save_state(state)
        self.append_event(
            task_id=task_id,
            step_id=step_id,
            event_type="step_reconciled",
            message=resolution,
            data={"note": note},
        )
        return state

    def append_event(
        self,
        *,
        task_id: str,
        event_type: str,
        message: str = "",
        step_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._safe_task_id(task_id)
        event = {
            "timestamp": utc_now_iso(),
            "task_id": task_id,
            "step_id": step_id,
            "event_type": event_type,
            "message": message,
            "data": dict(data or {}),
        }
        self.base_dir.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return event

    def load_events(self, task_id: str | None = None) -> list[dict[str, Any]]:
        if not self.ledger_path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line in self.ledger_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if task_id is None or event.get("task_id") == task_id:
                events.append(event)
        return events
