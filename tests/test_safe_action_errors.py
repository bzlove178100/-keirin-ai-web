from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_core.model import ActionResult, StepSpec, TaskSpec  # noqa: E402
from agent_core.runner import AgentRunner, SafeActionError  # noqa: E402
from agent_core.store import FileStateStore  # noqa: E402

SECRET = "provider-exception-secret-fixture"


def spec(*, retry_safe=False, max_attempts=1, verify=False):
    allowed = ["work"]
    verify_action = None
    if verify:
        allowed.append("verify")
        verify_action = "verify"
    return TaskSpec(
        task_id="safe-action-error-task",
        title="Safe action error test",
        goal="Persist only safe error classifications",
        allowed_actions=tuple(allowed),
        steps=(
            StepSpec(
                step_id="work",
                action="work",
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


class SafeActionErrorTest(unittest.TestCase):
    def test_untyped_action_exception_message_is_redacted_from_state_and_events(self):
        def work(args, context):
            raise RuntimeError(f"transport payload included {SECRET}")

        with tempfile.TemporaryDirectory() as tmp:
            outcome = AgentRunner(FileStateStore(tmp), {"work": work}).run(spec())
            self.assertEqual(outcome.status, "blocked")
            self.assertEqual(outcome.blocked_reason, "action_error_requires_reconciliation")
            self.assertEqual(outcome.last_error, "UntrustedActionError:action_exception_redacted")
            persisted = runtime_text(tmp)
            self.assertNotIn(SECRET, persisted)
            self.assertNotIn("transport payload included", persisted)

    def test_safe_action_error_persists_only_validated_static_code(self):
        def work(args, context):
            raise SafeActionError("provider_timeout")

        with tempfile.TemporaryDirectory() as tmp:
            outcome = AgentRunner(FileStateStore(tmp), {"work": work}).run(spec())
            self.assertEqual(outcome.status, "blocked")
            self.assertEqual(outcome.last_error, "SafeActionError:provider_timeout")
            self.assertIn("SafeActionError:provider_timeout", runtime_text(tmp))

    def test_safe_action_error_rejects_payload_like_codes(self):
        for invalid in ("", "UPPERCASE", "has space", "secret=abc", "../escape", "x" * 129):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "safe_action_error_code_invalid"):
                    SafeActionError(invalid)

    def test_retry_safe_untyped_error_remains_retryable_but_payload_is_not_persisted(self):
        calls = 0

        def work(args, context):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError(SECRET)
            return ActionResult(message="recovered")

        with tempfile.TemporaryDirectory() as tmp:
            outcome = AgentRunner(FileStateStore(tmp), {"work": work}).run(
                spec(retry_safe=True, max_attempts=2)
            )
            self.assertEqual(outcome.status, "completed")
            self.assertEqual(calls, 2)
            self.assertNotIn(SECRET, runtime_text(tmp))
            self.assertIn("UntrustedActionError:action_exception_redacted", runtime_text(tmp))

    def test_untyped_verifier_exception_message_is_redacted(self):
        def work(args, context):
            return ActionResult(message="side effect happened")

        def verify(args, context):
            raise RuntimeError(f"verifier payload {SECRET}")

        with tempfile.TemporaryDirectory() as tmp:
            outcome = AgentRunner(FileStateStore(tmp), {"work": work, "verify": verify}).run(
                spec(verify=True)
            )
            self.assertEqual(outcome.status, "blocked")
            self.assertEqual(
                outcome.blocked_reason,
                "verification_error_requires_reconciliation",
            )
            self.assertEqual(
                outcome.last_error,
                "UntrustedActionError:verification_exception_redacted",
            )
            self.assertNotIn(SECRET, runtime_text(tmp))

    def test_typed_verifier_failure_persists_safe_code_only(self):
        def work(args, context):
            return ActionResult(message="side effect happened")

        def verify(args, context):
            raise SafeActionError("verification_provider_unavailable")

        with tempfile.TemporaryDirectory() as tmp:
            outcome = AgentRunner(FileStateStore(tmp), {"work": work, "verify": verify}).run(
                spec(verify=True)
            )
            self.assertEqual(outcome.status, "blocked")
            self.assertEqual(
                outcome.last_error,
                "SafeActionError:verification_provider_unavailable",
            )
            self.assertNotIn(SECRET, runtime_text(tmp))


if __name__ == "__main__":
    unittest.main()
