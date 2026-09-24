from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_core import (  # noqa: E402
    ActionResult,
    AgentRunner,
    ArtifactUpdate,
    FileStateStore,
    StepSpec,
    TaskSpec,
)


def task(*steps: StepSpec, task_id: str = "TASK-001", allowed: tuple[str, ...] | None = None) -> TaskSpec:
    actions = allowed or tuple(
        dict.fromkeys(
            name
            for step in steps
            for name in (step.action, step.verify_action)
            if name
        )
    )
    return TaskSpec(
        task_id=task_id,
        title="test task",
        goal="verify safe resume semantics",
        allowed_actions=actions,
        steps=tuple(steps),
        completion_conditions=("all steps verified",),
    )


class AgentCoreTest(unittest.TestCase):
    def test_completed_task_is_not_repeated(self):
        with TemporaryDirectory() as tmp:
            store = FileStateStore(tmp)
            calls = {"work": 0, "verify": 0}

            def work(args, context):
                calls["work"] += 1
                self.assertEqual(context["idempotency_key"], "TASK-001:one")
                return ActionResult(message="done")

            def verify(args, context):
                calls["verify"] += 1
                return True

            spec = task(StepSpec("one", "work", verify_action="verify"))
            runner = AgentRunner(store, {"work": work, "verify": verify})
            first = runner.run(spec)
            second = runner.run(spec)

            self.assertEqual(first.status, "completed")
            self.assertEqual(first.executed_steps, ("one",))
            self.assertEqual(second.status, "completed")
            self.assertEqual(second.executed_steps, ())
            self.assertEqual(calls, {"work": 1, "verify": 1})
            self.assertIn("terminal_resume_skipped", [e["event_type"] for e in store.load_events("TASK-001")])

    def test_unavailable_action_blocks_without_execution(self):
        with TemporaryDirectory() as tmp:
            store = FileStateStore(tmp)
            spec = task(StepSpec("one", "missing"), allowed=("missing",))
            outcome = AgentRunner(store, {}).run(spec)
            self.assertEqual(outcome.status, "blocked")
            self.assertEqual(outcome.blocked_reason, "action_unavailable:missing")
            self.assertEqual(store.load_state("TASK-001").attempts, {})

    def test_failed_verification_does_not_repeat_side_effect(self):
        with TemporaryDirectory() as tmp:
            store = FileStateStore(tmp)
            calls = {"write": 0}

            def write(args, context):
                calls["write"] += 1
                return ActionResult(
                    message="artifact created",
                    artifacts=(
                        ArtifactUpdate(
                            artifact_id="artifact-1",
                            kind="json",
                            locator="private://artifact-1",
                            created=True,
                        ),
                    ),
                )

            spec = task(StepSpec("write", "write", verify_action="verify"))
            runner = AgentRunner(store, {"write": write, "verify": lambda args, context: False})
            first = runner.run(spec)
            second = runner.run(spec)

            self.assertEqual(first.status, "blocked")
            self.assertEqual(first.blocked_reason, "verification_failed:verify")
            self.assertEqual(second.status, "blocked")
            self.assertEqual(calls["write"], 1)

            artifact = store.load_state("TASK-001").artifacts["artifact-1"]
            self.assertTrue(artifact.created)
            self.assertFalse(artifact.verified)
            self.assertFalse(artifact.persistent_saved)
            self.assertFalse(artifact.device_saved)
            self.assertFalse(artifact.ui_loaded)

    def test_retry_safe_action_can_retry_with_same_idempotency_key(self):
        with TemporaryDirectory() as tmp:
            store = FileStateStore(tmp)
            calls: list[str] = []

            def flaky(args, context):
                calls.append(context["idempotency_key"])
                if len(calls) == 1:
                    raise RuntimeError("temporary")
                return ActionResult(message="recovered")

            spec = task(StepSpec("one", "flaky", retry_safe=True, max_attempts=2))
            outcome = AgentRunner(store, {"flaky": flaky}).run(spec)
            self.assertEqual(outcome.status, "completed")
            self.assertEqual(calls, ["TASK-001:one", "TASK-001:one"])
            self.assertEqual(store.load_state("TASK-001").attempts["one"], 2)

    def test_unsafe_action_error_requires_reconciliation(self):
        with TemporaryDirectory() as tmp:
            store = FileStateStore(tmp)
            calls = {"count": 0}

            def risky(args, context):
                calls["count"] += 1
                raise RuntimeError("unknown side effect state")

            spec = task(StepSpec("one", "risky"))
            runner = AgentRunner(store, {"risky": risky})
            first = runner.run(spec)
            second = runner.run(spec)
            self.assertEqual(first.status, "blocked")
            self.assertEqual(first.blocked_reason, "action_error_requires_reconciliation")
            self.assertEqual(second.status, "blocked")
            self.assertEqual(calls["count"], 1)

    def test_spec_rejects_duplicate_steps_and_unsafe_retry_config(self):
        duplicate = task(StepSpec("same", "a"), StepSpec("same", "a"), allowed=("a",))
        with self.assertRaisesRegex(ValueError, "duplicate_step_id"):
            duplicate.validate()
        unsafe = task(StepSpec("one", "a", retry_safe=False, max_attempts=2), allowed=("a",))
        with self.assertRaisesRegex(ValueError, "unsafe_retry_requires_single_attempt"):
            unsafe.validate()

    def test_store_rejects_path_traversal_task_id(self):
        with TemporaryDirectory() as tmp:
            store = FileStateStore(tmp)
            with self.assertRaisesRegex(ValueError, "unsafe_task_id"):
                store.load_state("../escape")


if __name__ == "__main__":
    unittest.main()
