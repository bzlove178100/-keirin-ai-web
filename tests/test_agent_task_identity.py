from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_core import AgentRunner, FileStateStore, StepSpec, TaskSpec


def task():
    return TaskSpec("identity-test", "Identity", "Preserve task meaning", ("work",),
                    (StepSpec("one", "work", args={"nested": {"value": 1}}),),
                    inputs={"nested": {"value": 1}})


class TaskIdentityTest(unittest.TestCase):
    def test_definition_changes_rejected_even_after_completion(self):
        spec = task()
        variants = [replace(spec, inputs={"nested": {"value": 2}}),
                    replace(spec, steps=(StepSpec("one", "work", args={"other": 2}),)),
                    replace(spec, allowed_actions=("work", "extra")),
                    replace(spec, goal="Changed goal"),
                    replace(spec, steps=(StepSpec("one", "work", retry_safe=True),))]
        with TemporaryDirectory() as tmp:
            calls = []
            store = FileStateStore(tmp)
            runner = AgentRunner(store, {"work": lambda a, c: calls.append(1)})
            runner.run(spec)
            before = store.state_path(spec.task_id).read_bytes()
            for changed in variants:
                with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, "task_spec_changed"):
                    runner.run(changed)
                self.assertEqual(store.state_path(spec.task_id).read_bytes(), before)
            self.assertEqual(calls, [1])
            self.assertEqual(runner.run(spec).status, "completed")

    def test_key_order_is_stable_and_nonfinite_inputs_rejected(self):
        a = replace(task(), inputs={"a": 1, "b": 2})
        b = replace(task(), inputs={"b": 2, "a": 1})
        self.assertEqual(a.fingerprint(), b.fingerprint())
        with TemporaryDirectory() as tmp:
            store = FileStateStore(tmp)
            with self.assertRaises(ValueError):
                AgentRunner(store, {}).run(replace(a, inputs={"value": float("nan")}))
            self.assertFalse(store.state_path(a.task_id).exists())

    def test_legacy_state_not_silently_bound(self):
        with TemporaryDirectory() as tmp:
            store = FileStateStore(tmp)
            store.save_state(store.load_state("identity-test"))
            before = store.state_path("identity-test").read_bytes()
            with self.assertRaisesRegex(ValueError, "legacy_task_spec_requires_review"):
                AgentRunner(store, {}).run(task())
            self.assertEqual(store.state_path("identity-test").read_bytes(), before)

    def test_action_mutation_does_not_change_caller_or_later_step_inputs(self):
        with TemporaryDirectory() as tmp:
            spec = task()
            spec = replace(spec, steps=spec.steps + (StepSpec("two", "work"),))
            seen = []

            def work(args, context):
                seen.append(context["task_inputs"]["nested"]["value"])
                context["task_inputs"]["nested"]["value"] = 9
                if "nested" in args:
                    args["nested"]["value"] = 9

            self.assertEqual(AgentRunner(FileStateStore(tmp), {"work": work}).run(spec).status, "completed")
            self.assertEqual(seen, [1, 1])
            self.assertEqual(spec.inputs["nested"]["value"], 1)
            self.assertEqual(spec.steps[0].args["nested"]["value"], 1)

    def test_crashed_state_remains_bound_to_original_spec(self):
        with TemporaryDirectory() as tmp:
            def crash(a, c):
                raise SystemExit()
            store = FileStateStore(tmp)
            runner = AgentRunner(store, {"work": crash})
            with self.assertRaises(SystemExit):
                runner.run(task())
            self.assertEqual(store.load_state("identity-test").spec_fingerprint, task().fingerprint())
            with self.assertRaisesRegex(ValueError, "task_spec_changed"):
                runner.run(replace(task(), inputs={"changed": True}))
            self.assertEqual(runner.run(task()).status, "blocked")


if __name__ == "__main__":
    unittest.main()
