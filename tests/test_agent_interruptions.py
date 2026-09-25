from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_core import AgentRunner, FileStateStore, StepSpec, TaskSpec


def task(*steps):
    return TaskSpec("interruption-test", "Test recovery", "Avoid duplicate work",
                    ("work", "verify", "next"), tuple(steps))


class InterruptedRunnerTest(unittest.TestCase):
    def test_crash_after_side_effect_never_repeats_before_reconciliation(self):
        for retry_safe in (False, True):
            with self.subTest(retry_safe=retry_safe), TemporaryDirectory() as tmp:
                calls = []

                def work(args, context):
                    calls.append(context["idempotency_key"])
                    raise SystemExit("process interrupted after external action")

                spec = task(StepSpec("one", "work", retry_safe=retry_safe))
                with self.assertRaises(SystemExit):
                    AgentRunner(FileStateStore(tmp), {"work": work}).run(spec)
                store = FileStateStore(tmp)
                self.assertEqual(store.load_state(spec.task_id).status, "running")
                outcome = AgentRunner(store, {"work": work}).run(spec)
                self.assertEqual(outcome.status, "blocked")
                self.assertIn("interrupted_step_requires_reconciliation", outcome.blocked_reason)
                self.assertEqual(len(calls), 1)
                store.reconcile_blocked_step(spec.task_id, step_id="one",
                                             resolution="applied_and_verified",
                                             note="Test host verified external result")
                self.assertEqual(AgentRunner(store, {"work": work}).run(spec).status, "completed")
                self.assertEqual(len(calls), 1)

    def test_crash_during_verifier_does_not_repeat_action(self):
        with TemporaryDirectory() as tmp:
            calls = []

            def verify(args, context):
                raise SystemExit("verification interrupted")

            spec = task(StepSpec("one", "work", verify_action="verify"))
            actions = {"work": lambda a, c: calls.append("work"), "verify": verify}
            with self.assertRaises(SystemExit):
                AgentRunner(FileStateStore(tmp), actions).run(spec)
            result = AgentRunner(FileStateStore(tmp), actions).run(spec)
            self.assertEqual(result.status, "blocked")
            self.assertEqual(calls, ["work"])

    def test_competing_runners_and_reconciliation_cannot_enter(self):
        with TemporaryDirectory() as tmp, ThreadPoolExecutor(max_workers=1) as pool:
            entered, release = Event(), Event()
            calls = []

            def work(args, context):
                calls.append("work")
                entered.set()
                if not release.wait(5):
                    raise RuntimeError("test barrier timeout")

            spec = task(StepSpec("one", "work"))
            future = pool.submit(AgentRunner(FileStateStore(tmp), {"work": work}).run, spec)
            try:
                self.assertTrue(entered.wait(5))
                other = FileStateStore(tmp)
                with self.assertRaisesRegex(RuntimeError, "task_already_running"):
                    AgentRunner(other, {"work": work}).run(spec)
                with self.assertRaisesRegex(RuntimeError, "task_already_running"):
                    other.reconcile_blocked_step(spec.task_id, step_id="one",
                                                  resolution="not_applied", note="test")
            finally:
                release.set()
            self.assertEqual(future.result(timeout=5).status, "completed")
            self.assertEqual(AgentRunner(FileStateStore(tmp), {"work": work}).run(spec).status, "completed")
            self.assertEqual(calls, ["work"])

    def test_crash_between_steps_resumes_only_unstarted_work(self):
        with TemporaryDirectory() as tmp:
            store = FileStateStore(tmp)
            state = store.load_state("interruption-test")
            state.status = "running"
            state.completed_steps = ["one"]
            state.attempts = {"one": 1}
            store.save_state(state)
            calls = []
            spec = task(StepSpec("one", "work"), StepSpec("two", "next"))
            result = AgentRunner(store, {"work": lambda a, c: calls.append("one"),
                                         "next": lambda a, c: calls.append("two")}).run(spec)
            self.assertEqual(result.status, "completed")
            self.assertEqual(calls, ["two"])

    def test_missing_attempted_step_still_blocks_before_any_new_work(self):
        with TemporaryDirectory() as tmp:
            store = FileStateStore(tmp)
            state = store.load_state("interruption-test")
            state.status = "running"
            state.attempts = {"old-step": 1}
            store.save_state(state)
            calls = []
            result = AgentRunner(store, {"work": lambda a, c: calls.append("new")}).run(
                task(StepSpec("new-step", "work")))
            self.assertEqual(result.status, "blocked")
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
