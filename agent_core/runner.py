from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
import json
from typing import Any, Callable, Mapping

from .model import ActionResult, ArtifactUpdate, StepSpec, TaskSpec, TaskState
from .store import FileStateStore

Action = Callable[[dict[str, Any], dict[str, Any]], Any]


class BlockedAction(RuntimeError):
    """Raised by an action when a prerequisite or permission is missing."""


@dataclass(frozen=True)
class RunOutcome:
    task_id: str
    status: str
    completed_steps: tuple[str, ...]
    blocked_reason: str | None
    last_error: str | None
    executed_steps: tuple[str, ...]
    skipped_steps: tuple[str, ...]


class AgentRunner:
    """Sequential, resumable runner with explicit permission and verification gates.

    A terminal ``blocked`` or ``failed`` state is never retried automatically. This is
    deliberate: after an ambiguous side effect or failed verification, repeating the
    same action can create duplicate work. A future reconciliation operation must make
    the state safe before execution continues.
    """

    TERMINAL = {"completed", "blocked", "failed"}

    def __init__(self, store: FileStateStore, actions: Mapping[str, Action]):
        self.store = store
        self.actions = dict(actions)

    @staticmethod
    def _normalise_action_result(value: Any) -> ActionResult:
        if value is None:
            return ActionResult()
        if isinstance(value, ActionResult):
            return value
        if isinstance(value, dict):
            artifacts = tuple(
                item if isinstance(item, ArtifactUpdate) else ArtifactUpdate(**item)
                for item in value.get("artifacts", ())
            )
            return ActionResult(
                message=str(value.get("message") or ""),
                artifacts=artifacts,
                data=dict(value.get("data") or {}),
            )
        raise TypeError("unsupported_action_result")

    @staticmethod
    def _verification_passed(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, ActionResult):
            return value.data.get("verified") is True
        if isinstance(value, dict):
            return value.get("verified") is True
        return False

    def _outcome(
        self,
        state: TaskState,
        *,
        executed: list[str] | None = None,
        skipped: list[str] | None = None,
    ) -> RunOutcome:
        return RunOutcome(
            task_id=state.task_id,
            status=state.status,
            completed_steps=tuple(state.completed_steps),
            blocked_reason=state.blocked_reason,
            last_error=state.last_error,
            executed_steps=tuple(executed or ()),
            skipped_steps=tuple(skipped or ()),
        )

    def _block(self, state: TaskState, reason: str, *, step: StepSpec | None = None, error: str | None = None) -> None:
        state.status = "blocked"
        state.blocked_reason = reason
        state.last_error = error
        self.store.save_state(state)
        self.store.append_event(
            task_id=state.task_id,
            step_id=step.step_id if step else None,
            event_type="task_blocked",
            message=reason,
            data={"error": error} if error else {},
        )

    def run(self, spec: TaskSpec, *, context: dict[str, Any] | None = None) -> RunOutcome:
        # Detach mutable args/inputs from the caller before binding and execution.
        spec = TaskSpec.from_dict(json.loads(json.dumps(spec.to_dict(), allow_nan=False)))
        spec.validate()
        with self.store.task_lock(spec.task_id):
            return self._run_locked(spec, context=context)

    def _run_locked(self, spec: TaskSpec, *, context: dict[str, Any] | None = None) -> RunOutcome:
        existed = self.store.state_path(spec.task_id).exists()
        state = self.store.load_state(spec.task_id)
        if state.task_id != spec.task_id:
            raise ValueError("task_state_id_mismatch")

        fingerprint = spec.fingerprint()
        if existed and state.spec_fingerprint is None:
            raise ValueError("legacy_task_spec_requires_review")
        if state.spec_fingerprint is not None and state.spec_fingerprint != fingerprint:
            raise ValueError("task_spec_changed")
        if not existed:
            state.spec_fingerprint = fingerprint
            self.store.save_state(state)

        if state.status in self.TERMINAL:
            self.store.append_event(
                task_id=spec.task_id,
                event_type="terminal_resume_skipped",
                message=f"task already {state.status}; no action repeated",
            )
            return self._outcome(state)

        # Attempts are persisted before invoking a provider. If execution was
        # interrupted before completion was saved, the external outcome is unknown
        # even when the action is retry-safe: its verifier may have been interrupted.
        # Check the whole state before executing any earlier/new step in the spec.
        unresolved = sorted(step_id for step_id, count in state.attempts.items()
                            if count > 0 and step_id not in state.completed_steps)
        if unresolved:
            self._block(state, "interrupted_step_requires_reconciliation:" + ",".join(unresolved))
            return self._outcome(state)

        state.status = "running"
        state.blocked_reason = None
        state.last_error = None
        self.store.save_state(state)
        self.store.append_event(task_id=spec.task_id, event_type="task_started", message=spec.title)

        executed: list[str] = []
        skipped: list[str] = []
        base_context = dict(context or {})
        base_context["task_id"] = spec.task_id
        base_context["task_inputs"] = dict(spec.inputs)

        for step in spec.steps:
            if step.step_id in state.completed_steps:
                skipped.append(step.step_id)
                self.store.append_event(
                    task_id=spec.task_id,
                    step_id=step.step_id,
                    event_type="step_skipped_completed",
                    message="completed step was not repeated",
                )
                continue

            action = self.actions.get(step.action)
            if action is None:
                self._block(state, f"action_unavailable:{step.action}", step=step)
                return self._outcome(state, executed=executed, skipped=skipped)

            step_context = {
                **base_context,
                "task_inputs": deepcopy(spec.inputs),
                "step_id": step.step_id,
                "idempotency_key": f"{spec.task_id}:{step.step_id}",
            }

            result: ActionResult | None = None
            while True:
                attempt = state.attempts.get(step.step_id, 0) + 1
                state.attempts[step.step_id] = attempt
                self.store.save_state(state)
                self.store.append_event(
                    task_id=spec.task_id,
                    step_id=step.step_id,
                    event_type="step_started",
                    message=step.action,
                    data={"attempt": attempt, "retry_safe": step.retry_safe},
                )
                try:
                    result = self._normalise_action_result(action(deepcopy(step.args), deepcopy(step_context)))
                    break
                except BlockedAction as exc:
                    self._block(state, f"action_blocked:{exc}", step=step)
                    return self._outcome(state, executed=executed, skipped=skipped)
                except Exception as exc:  # action adapters may raise provider-specific exceptions
                    error = f"{type(exc).__name__}:{exc}"
                    state.last_error = error
                    self.store.append_event(
                        task_id=spec.task_id,
                        step_id=step.step_id,
                        event_type="step_error",
                        message=error,
                        data={"attempt": attempt},
                    )
                    if not step.retry_safe:
                        self._block(
                            state,
                            "action_error_requires_reconciliation",
                            step=step,
                            error=error,
                        )
                        return self._outcome(state, executed=executed, skipped=skipped)
                    if attempt >= step.max_attempts:
                        state.status = "failed"
                        state.blocked_reason = None
                        self.store.save_state(state)
                        self.store.append_event(
                            task_id=spec.task_id,
                            step_id=step.step_id,
                            event_type="task_failed",
                            message="retry-safe action exhausted configured attempts",
                            data={"error": error, "attempts": attempt},
                        )
                        return self._outcome(state, executed=executed, skipped=skipped)

            assert result is not None
            for artifact in result.artifacts:
                self.store.apply_artifact_update(state, artifact)
            self.store.save_state(state)

            if step.verify_action:
                verifier = self.actions.get(step.verify_action)
                if verifier is None:
                    self._block(state, f"verification_action_unavailable:{step.verify_action}", step=step)
                    return self._outcome(state, executed=executed, skipped=skipped)
                verify_args = {
                    "step_action": step.action,
                    "step_args": deepcopy(step.args),
                    "action_result": {
                        "message": result.message,
                        "data": dict(result.data),
                        "artifacts": [artifact.__dict__ for artifact in result.artifacts],
                    },
                }
                try:
                    verified = self._verification_passed(verifier(verify_args, step_context))
                except Exception as exc:
                    self._block(
                        state,
                        "verification_error_requires_reconciliation",
                        step=step,
                        error=f"{type(exc).__name__}:{exc}",
                    )
                    return self._outcome(state, executed=executed, skipped=skipped)
                if not verified:
                    self._block(state, f"verification_failed:{step.verify_action}", step=step)
                    return self._outcome(state, executed=executed, skipped=skipped)
                self.store.append_event(
                    task_id=spec.task_id,
                    step_id=step.step_id,
                    event_type="step_verified",
                    message=step.verify_action,
                )

            state.completed_steps.append(step.step_id)
            state.last_error = None
            self.store.save_state(state)
            executed.append(step.step_id)
            self.store.append_event(
                task_id=spec.task_id,
                step_id=step.step_id,
                event_type="step_completed",
                message=result.message,
            )

        state.status = "completed"
        state.blocked_reason = None
        state.last_error = None
        self.store.save_state(state)
        self.store.append_event(
            task_id=spec.task_id,
            event_type="task_completed",
            message="all configured steps completed and required verifications passed",
            data={"completion_conditions": list(spec.completion_conditions)},
        )
        return self._outcome(state, executed=executed, skipped=skipped)
