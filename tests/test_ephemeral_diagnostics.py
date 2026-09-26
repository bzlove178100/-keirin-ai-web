from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_core.diagnostics import (  # noqa: E402
    ActionDiagnosticEvent,
    CollectingDiagnosticSink,
    safe_exception_type,
)
from agent_core.model import ActionResult, StepSpec, TaskSpec  # noqa: E402
from agent_core.runner import AgentRunner, SafeActionError  # noqa: E402
from agent_core.store import FileStateStore  # noqa: E402

SECRET = "ephemeral-diagnostic-secret-fixture"


def task(*, retry_safe=False, max_attempts=1, verify=False):
    allowed = ["provider.read"]
    verify_action = None
    if verify:
        allowed.append("provider.verify")
        verify_action = "provider.verify"
    return TaskSpec(
        task_id="diagnostic-task",
        title="Diagnostic task",
        goal="Prove host-only diagnostics do not weaken durable redaction",
        allowed_actions=tuple(allowed),
        steps=(
            StepSpec(
                step_id="read",
                action="provider.read",
                verify_action=verify_action,
                retry_safe=retry_safe,
                max_attempts=max_attempts,
            ),
        ),
    )


def runtime_text(base):
    chunks = []
    for path in Path(base).rglob("*"):
        if path.is_file():
            chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


class EphemeralDiagnosticsTest(unittest.TestCase):
    def test_untyped_action_failure_emits_metadata_only_and_persists_redacted_error(self):
        sink = CollectingDiagnosticSink()

        def action(args, context):
            raise RuntimeError(f"provider payload {SECRET}")

        with tempfile.TemporaryDirectory() as tmp:
            outcome = AgentRunner(
                FileStateStore(tmp),
                {"provider.read": action},
                diagnostic_sink=sink,
            ).run(task())
            self.assertEqual(outcome.status, "blocked")
            self.assertEqual(outcome.last_error, "UntrustedActionError:action_exception_redacted")
            self.assertNotIn(SECRET, runtime_text(tmp))

        self.assertEqual(len(sink.events), 1)
        event = sink.events[0]
        self.assertEqual(event.task_id, "diagnostic-task")
        self.assertEqual(event.step_id, "read")
        self.assertEqual(event.action, "provider.read")
        self.assertEqual(event.phase, "action")
        self.assertEqual(event.attempt, 1)
        self.assertFalse(event.retry_safe)
        self.assertEqual(event.classification, "action_exception_redacted")
        self.assertEqual(event.exception_type, "RuntimeError")
        rendered = repr(event) + json.dumps(event.to_safe_dict(), sort_keys=True)
        self.assertNotIn(SECRET, rendered)
        self.assertNotIn("provider payload", rendered)

    def test_safe_action_error_emits_safe_code_without_exception_message(self):
        sink = CollectingDiagnosticSink()

        def action(args, context):
            raise SafeActionError("provider_timeout")

        with tempfile.TemporaryDirectory() as tmp:
            outcome = AgentRunner(
                FileStateStore(tmp),
                {"provider.read": action},
                diagnostic_sink=sink,
            ).run(task())
            self.assertEqual(outcome.last_error, "SafeActionError:provider_timeout")

        self.assertEqual(len(sink.events), 1)
        self.assertEqual(sink.events[0].classification, "provider_timeout")
        self.assertEqual(sink.events[0].exception_type, "SafeActionError")

    def test_retry_emits_one_diagnostic_per_failed_attempt_without_changing_retry_policy(self):
        sink = CollectingDiagnosticSink()
        calls = 0

        def action(args, context):
            nonlocal calls
            calls += 1
            if calls < 3:
                raise RuntimeError(f"temporary {SECRET}")
            return ActionResult(message="recovered")

        with tempfile.TemporaryDirectory() as tmp:
            outcome = AgentRunner(
                FileStateStore(tmp),
                {"provider.read": action},
                diagnostic_sink=sink,
            ).run(task(retry_safe=True, max_attempts=3))
            self.assertEqual(outcome.status, "completed")
            self.assertEqual(calls, 3)
            self.assertNotIn(SECRET, runtime_text(tmp))

        self.assertEqual([event.attempt for event in sink.events], [1, 2])
        self.assertTrue(all(event.retry_safe for event in sink.events))

    def test_verifier_failure_emits_verification_event_without_result_or_payload(self):
        sink = CollectingDiagnosticSink()

        def action(args, context):
            return ActionResult(message="provider response", data={"public": "ok"})

        def verify(args, context):
            raise RuntimeError(f"verification response {SECRET}")

        with tempfile.TemporaryDirectory() as tmp:
            outcome = AgentRunner(
                FileStateStore(tmp),
                {"provider.read": action, "provider.verify": verify},
                diagnostic_sink=sink,
            ).run(task(verify=True))
            self.assertEqual(outcome.status, "blocked")
            self.assertEqual(
                outcome.last_error,
                "UntrustedActionError:verification_exception_redacted",
            )
            self.assertNotIn(SECRET, runtime_text(tmp))

        self.assertEqual(len(sink.events), 1)
        event = sink.events[0]
        self.assertEqual(event.phase, "verification")
        self.assertEqual(event.action, "provider.verify")
        self.assertFalse(event.retry_safe)
        self.assertEqual(event.classification, "verification_exception_redacted")
        self.assertNotIn(SECRET, json.dumps(event.to_safe_dict(), sort_keys=True))

    def test_sink_failure_is_best_effort_and_never_changes_task_semantics_or_persistence(self):
        class FailingSink:
            def emit(self, event):
                raise RuntimeError(f"diagnostic backend failed {SECRET}")

        def action(args, context):
            raise SafeActionError("provider_timeout")

        with tempfile.TemporaryDirectory() as tmp:
            outcome = AgentRunner(
                FileStateStore(tmp),
                {"provider.read": action},
                diagnostic_sink=FailingSink(),
            ).run(task())
            self.assertEqual(outcome.status, "blocked")
            self.assertEqual(outcome.last_error, "SafeActionError:provider_timeout")
            persisted = runtime_text(tmp)
            self.assertNotIn(SECRET, persisted)
            self.assertNotIn("diagnostic backend failed", persisted)

    def test_no_sink_remains_backward_compatible(self):
        def action(args, context):
            raise RuntimeError(SECRET)

        with tempfile.TemporaryDirectory() as tmp:
            outcome = AgentRunner(FileStateStore(tmp), {"provider.read": action}).run(task())
            self.assertEqual(outcome.status, "blocked")
            self.assertEqual(outcome.last_error, "UntrustedActionError:action_exception_redacted")
            self.assertNotIn(SECRET, runtime_text(tmp))

    def test_diagnostic_event_rejects_payload_like_classification(self):
        with self.assertRaisesRegex(ValueError, "diagnostic_classification_invalid"):
            ActionDiagnosticEvent(
                task_id="task",
                step_id="step",
                action="provider.read",
                phase="action",
                attempt=1,
                retry_safe=False,
                classification=f"secret={SECRET}",
                exception_type="RuntimeError",
            )

    def test_dynamic_invalid_exception_type_name_falls_back_without_message(self):
        Weird = type("invalid exception name with spaces", (RuntimeError,), {})
        error = Weird(SECRET)
        self.assertEqual(safe_exception_type(error), "Exception")
        self.assertNotIn(SECRET, safe_exception_type(error))


if __name__ == "__main__":
    unittest.main()
