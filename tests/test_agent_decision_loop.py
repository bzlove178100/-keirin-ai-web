"""Scripted model responses + real filesystem tools; NOT live AI qualification."""
from dataclasses import replace
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_core.adapters import ToolRegistry
from agent_core.decision_loop import DecisionLoop, Goal, ModelUnavailable
from agent_core.document_task import DocumentTools, run_document_task
from agent_core.store import FileStateStore


GOOD = "## Summary\nSynthetic task: prepare an internal report.\n\n## Next action\nReview the report.\n"


def tool(name, **args):
    return {"kind": "tool", "action": "document." + name, "args": args}


def finish():
    return {"kind": "finish", "report": "The private report passed the structural check."}


class ScriptedModel:
    def __init__(self, *decisions):
        self.decisions = iter(decisions)
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        return next(self.decisions)


class DecisionLoopTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source.txt"
        self.source.write_text("Synthetic task: prepare an internal report.")
        self.output = self.root / "report.md"
        self.adapter = DocumentTools(self.source, self.output, ("Summary", "Next action"))
        self.registry = ToolRegistry()
        self.registry.register(self.adapter)
        self.store = FileStateStore(self.root / "state")
        self.goal = Goal("test-task", "Summarize the supplied synthetic source.",
                         tuple(self.registry.actions()), "document.inspect_report", {},
                         self.adapter.binding() + ":scripted-model",
                         required_actions=("document.read_source", "document.write_report"))

    def loop(self, model):
        return DecisionLoop(store=self.store, registry=self.registry, model=model)

    def complete_model(self):
        return ScriptedModel(tool("read_source"), tool("write_report", content=GOOD), finish())

    def test_real_files_flow_and_result_feedback(self):
        model = self.complete_model()
        out = self.loop(model).run(self.goal)
        self.assertEqual(out["status"], "completed")
        self.assertEqual(self.output.read_text(), GOOD)
        self.assertEqual(len(model.requests), 3)
        self.assertIn("Synthetic task", model.requests[1]["observations"][0]["result"]["data"]["text"])
        self.assertTrue(out["observations"][-1]["result"]["data"]["verified"])

    def test_completion_requires_host_check_and_repair_feedback(self):
        model = ScriptedModel(tool("read_source"), tool("write_report", content="## Summary\nOnly summary."),
                              finish(), tool("write_report", content=GOOD), finish())
        out = self.loop(model).run(self.goal)
        self.assertEqual(out["status"], "completed")
        feedback = model.requests[3]["observations"][-1]
        self.assertTrue(feedback["completion_rejected"])
        self.assertEqual(feedback["result"]["data"]["missing"], ["Next action"])

    def test_preexisting_report_does_not_fake_read_or_generation(self):
        self.output.write_text(GOOD)
        out = self.loop(ScriptedModel(finish())).run(replace(self.goal, max_decisions=1))
        self.assertEqual(out["reason"], "decision_limit")
        self.assertEqual(out["observations"][0]["missing_required_actions"],
                         ["document.read_source", "document.write_report"])

    def test_duplicate_submission_does_not_call_model_or_write(self):
        self.loop(self.complete_model()).run(self.goal)
        before = self.output.stat().st_mtime_ns
        model = ScriptedModel()
        out = self.loop(model).run(self.goal)
        self.assertEqual(out["status"], "completed")
        self.assertEqual(model.requests, [])
        self.assertEqual(self.output.stat().st_mtime_ns, before)

    def test_clean_pause_new_instance_resumes_with_observation(self):
        first = self.loop(ScriptedModel(tool("read_source"))).run(self.goal, pause_after=1)
        self.assertEqual(first["status"], "pending")
        model = ScriptedModel(tool("write_report", content=GOOD), finish())
        out = self.loop(model).run(self.goal)
        self.assertEqual(out["status"], "completed")
        self.assertEqual(out["model_calls"], 3)
        self.assertEqual(model.requests[0]["observations"][0]["action"], "document.read_source")

    def test_completed_child_recovered_when_parent_checkpoint_interrupted(self):
        original = self.store.save_state
        def crash_after_child(state):
            journal = state.artifacts["decision_journal"].metadata
            if len(journal["observations"]) == 2 and journal["pending"] is None:
                raise KeyboardInterrupt()
            original(state)
        self.store.save_state = crash_after_child
        with self.assertRaises(KeyboardInterrupt):
            self.loop(self.complete_model()).run(self.goal)
        before = self.output.stat().st_mtime_ns
        self.store.save_state = original
        out = self.loop(ScriptedModel(finish())).run(self.goal)
        self.assertEqual(out["status"], "completed")
        self.assertEqual(self.output.stat().st_mtime_ns, before)

    def test_interruption_after_effect_blocks_without_repeating(self):
        original = self.adapter.write_report
        count = []
        def crash(args, context):
            count.append(1)
            original(args, context)
            raise KeyboardInterrupt()
        self.registry._actions["document.write_report"] = crash
        with self.assertRaises(KeyboardInterrupt):
            self.loop(self.complete_model()).run(self.goal)
        out = self.loop(ScriptedModel()).run(self.goal)
        self.assertEqual(out["reason"], "tool_requires_reconciliation")
        self.assertEqual(count, [1])

    def test_interrupted_model_not_silently_called_again(self):
        def crash(request):
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.loop(crash).run(self.goal)
        model = ScriptedModel()
        out = self.loop(model).run(self.goal)
        self.assertEqual(out["reason"], "interrupted_model_requires_reconciliation")
        self.assertEqual(model.requests, [])

    def test_changed_task_and_tool_binding_are_rejected(self):
        self.loop(ScriptedModel(tool("read_source"))).run(self.goal, pause_after=1)
        for goal in [replace(self.goal, instruction="different"), replace(self.goal, binding="different"),
                     replace(self.goal, max_decisions=9)]:
            with self.subTest(goal=goal):
                with self.assertRaisesRegex(ValueError, "task_spec_changed"):
                    self.loop(ScriptedModel()).run(goal)

    def test_scope_and_invalid_model_outputs_do_not_write(self):
        values = [{"kind": "tool", "action": "shell", "args": {}},
                  tool("write_report", path="/tmp/outside", content=GOOD),
                  {"kind": "finish", "report": "ok", "verified": True},
                  ["not an object"], {"kind": "tool", "action": "document.read_source", "args": []},
                  {"kind": "stop", "secret": "must not persist"},
                  tool("write_report", content=float("nan"))]
        for i, value in enumerate(values):
            with self.subTest(value=value):
                out = self.loop(ScriptedModel(value)).run(replace(self.goal, task_id=f"invalid-{i}"))
                self.assertEqual(out["status"], "blocked")
                self.assertFalse(self.output.exists())

    def test_missing_model_is_truthfully_blocked(self):
        out = self.loop(None).run(self.goal)
        self.assertEqual(out["reason"], "model_unavailable")
        self.assertEqual(out["model_calls"], 0)
        self.assertFalse(self.output.exists())

    def test_missing_model_resume_after_host_review(self):
        loop = self.loop(None)
        loop.run(self.goal)
        loop.resume_after_review(self.goal, expected_reason="model_unavailable",
                                 note="Scripted model test binding supplied; no live provider.")
        self.assertEqual(self.loop(self.complete_model()).run(self.goal)["status"], "completed")

    def test_ambiguous_child_needs_explicit_reconciliation(self):
        def fail(args, context):
            raise RuntimeError("connection lost")
        self.registry._actions["document.read_source"] = fail
        loop = self.loop(ScriptedModel(tool("read_source")))
        loop.run(self.goal)
        with self.assertRaisesRegex(ValueError, "child_reconciliation_required"):
            loop.resume_after_review(self.goal, expected_reason="tool_requires_reconciliation", note="Reviewed")
        states = list(loop.child_store.states_dir.glob("*.json"))
        child_id = json.loads(states[0].read_text())["task_id"]
        loop.child_store.reconcile_blocked_step(child_id, step_id="invoke", resolution="not_applied",
                                                note="Test read failed before doing anything.")
        loop.resume_after_review(self.goal, expected_reason="tool_requires_reconciliation", note="Child reviewed.")
        self.registry._actions["document.read_source"] = self.adapter.read_source
        out = self.loop(ScriptedModel(tool("write_report", content=GOOD), finish())).run(self.goal)
        self.assertEqual(out["status"], "completed")

    def test_interrupted_model_needs_review_before_resume(self):
        def crash(request):
            raise KeyboardInterrupt()
        loop = self.loop(crash)
        with self.assertRaises(KeyboardInterrupt):
            loop.run(self.goal)
        loop.run(self.goal)
        with self.assertRaisesRegex(ValueError, "model_call_review_required"):
            loop.resume_after_review(self.goal, expected_reason="interrupted_model_requires_reconciliation", note="Reviewed")
        loop.resume_after_review(self.goal, expected_reason="interrupted_model_requires_reconciliation",
                                 note="Test-only call had no external effect.", model_call_resolved=True)
        self.assertEqual(self.loop(self.complete_model()).run(self.goal)["status"], "completed")

    def test_existing_dict_action_result_contract(self):
        self.registry._actions["document.read_source"] = lambda args, context: {
            "message": "Read", "data": {"text": "Synthetic input"}}
        model = self.complete_model()
        self.assertEqual(self.loop(model).run(self.goal)["status"], "completed")
        self.assertEqual(model.requests[1]["observations"][0]["result"]["data"]["text"], "Synthetic input")

    def test_auth_limit_timeout_and_untrusted_model_error(self):
        for code in ["authentication_required", "usage_limit", "model_timeout", "unknown"]:
            def fail(request):
                if code == "unknown":
                    raise RuntimeError("SECRET-TEST-VALUE")
                raise ModelUnavailable(code)
            out = self.loop(fail).run(replace(self.goal, task_id="failure-" + code))
            self.assertEqual(out["reason"], code if code != "unknown" else "model_error_redacted")
        for file in self.store.base_dir.rglob("*.json*"):
            self.assertNotIn("SECRET-TEST-VALUE", file.read_text())

    def test_tool_error_redacted_no_automatic_retry(self):
        count = []
        def fail(args, context):
            count.append(1)
            raise RuntimeError("SECRET-TEST-VALUE")
        self.registry._actions["document.read_source"] = fail
        model = ScriptedModel(tool("read_source"))
        loop = self.loop(model)
        self.assertEqual(loop.run(self.goal)["reason"], "tool_requires_reconciliation")
        loop.run(self.goal)
        self.assertEqual(count, [1])
        for file in self.store.base_dir.rglob("*.json*"):
            self.assertNotIn("SECRET-TEST-VALUE", file.read_text())

    def test_stop_and_decision_limit(self):
        self.assertEqual(self.loop(ScriptedModel()).run(self.goal, should_stop=lambda: True)["reason"], "operator_stop")
        goal = replace(self.goal, task_id="limit", max_decisions=1)
        self.assertEqual(self.loop(ScriptedModel(tool("read_source"))).run(goal)["reason"], "decision_limit")

    def test_duplicate_write_and_model_requested_stop(self):
        model = ScriptedModel(tool("write_report", content=GOOD), tool("write_report", content=GOOD))
        self.assertEqual(self.loop(model).run(self.goal)["reason"], "duplicate_write_decision")
        self.assertEqual(self.loop(ScriptedModel({"kind": "stop"})).run(
            replace(self.goal, task_id="stop"))["reason"], "model_requested_stop")

    def test_mutable_model_request_cannot_change_host_scope(self):
        def model(request):
            request["tools"].append({"action": "shell"})
            return {"kind": "tool", "action": "shell", "args": {}}
        self.assertEqual(self.loop(model).run(self.goal)["reason"], "invalid_model_decision")

    def test_nonread_completion_verifier_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "non_read_action_forbidden"):
            self.loop(None).run(replace(self.goal, completion_action="document.write_report"))

    def test_lock_prevents_concurrent_model_calls(self):
        model = ScriptedModel()
        with self.store.task_lock(self.goal.task_id):
            with self.assertRaisesRegex(RuntimeError, "task_already_running"):
                self.loop(model).run(self.goal)
        self.assertEqual(model.requests, [])

    def test_changed_source_and_symlink_cannot_be_consumed(self):
        self.source.write_text("Changed.")
        self.assertEqual(self.loop(ScriptedModel(tool("read_source"))).run(self.goal)["reason"], "tool_requires_reconciliation")
        self.output.symlink_to(self.source)
        with self.assertRaises(ValueError):
            DocumentTools(self.source, self.output, ("Summary",))

    def test_empty_sections_fail_verification(self):
        self.output.write_text("## Summary\n\n## Next action\nDo this.\n")
        self.assertFalse(self.adapter.inspect_report({}, {}).data["verified"])

    def test_document_entrypoint_uses_existing_loop(self):
        out = run_document_task(task_id="entry", source=self.source, output=self.output,
                                state_dir=self.root / "entry-state", model=self.complete_model(),
                                model_binding="scripted-test-only")
        self.assertEqual(out["status"], "completed")


if __name__ == "__main__":
    unittest.main()
