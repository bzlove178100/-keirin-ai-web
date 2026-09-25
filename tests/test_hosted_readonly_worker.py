from __future__ import annotations

from dataclasses import replace
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_core.adapters import Capability, ToolRegistry  # noqa: E402
from agent_core.hosted_queue import HostedQueueLease  # noqa: E402
from agent_core.hosted_readonly_worker import (  # noqa: E402
    HostedExecutionNotAuthorized,
    HostedReadOnlyWorker,
)
from agent_core.model import ArtifactUpdate, StepSpec, TaskSpec, TaskState  # noqa: E402


class FakeActivity:
    def __init__(self):
        self.events: list[dict] = []

    def append(self, *, task_id, event_type, step_id=None, payload=None):
        event = {
            "task_id": task_id,
            "event_type": event_type,
            "step_id": step_id,
            "payload": dict(payload or {}),
        }
        self.events.append(event)
        return event


class FakeQueue:
    def __init__(self, lease: HostedQueueLease | None):
        self.current = lease
        self.claim_count = 0
        self.saves: list[dict] = []

    def claim(self, *, worker_id: str, lease_seconds: int = 120):
        self.claim_count += 1
        return self.current

    def save(
        self,
        spec,
        state,
        *,
        expected_revision,
        worker_id,
        lease_generation,
        lease_seconds=120,
    ):
        if self.current is None:
            raise AssertionError("no lease")
        if expected_revision != self.current.revision:
            raise RuntimeError("stale_revision")
        if worker_id != self.current.lease_owner or lease_generation != self.current.lease_generation:
            raise RuntimeError("stale_fence")
        self.saves.append(
            {
                "status": state.status,
                "revision": expected_revision,
                "completed_steps": list(state.completed_steps),
                "attempts": dict(state.attempts),
                "blocked_reason": state.blocked_reason,
            }
        )
        running = state.status == "running"
        self.current = replace(
            self.current,
            status=state.status,
            revision=expected_revision + 1,
            state=TaskState.from_dict(state.to_dict()),
            lease_owner=worker_id if running else None,
            lease_expires_at="2026-09-25T13:05:00+00:00" if running else None,
        )
        return self.current


class FakeAdapter:
    def __init__(self, capabilities, actions):
        self.name = "fake-adapter"
        self._capabilities = tuple(capabilities)
        self._actions = dict(actions)

    def capabilities(self):
        return self._capabilities

    def actions(self):
        return dict(self._actions)


def make_spec(*, action="github.read_main", verify_action=None) -> TaskSpec:
    allowed = [action]
    if verify_action:
        allowed.append(verify_action)
    return TaskSpec(
        task_id="readonly-worker-test",
        title="Read-only worker test",
        goal="Verify explicit hosted read-only execution gate",
        allowed_actions=tuple(allowed),
        steps=(
            StepSpec(
                step_id="read",
                action=action,
                verify_action=verify_action,
                retry_safe=True,
                max_attempts=2,
            ),
        ),
    )


def make_lease(spec: TaskSpec) -> HostedQueueLease:
    state = TaskState(
        task_id=spec.task_id,
        status="running",
        spec_fingerprint=spec.fingerprint(),
    )
    return HostedQueueLease(
        task_id=spec.task_id,
        status="running",
        revision=1,
        idempotency_key="readonly-worker-key",
        spec=spec,
        state=state,
        attempt_count=1,
        max_attempts=1,
        lease_owner="worker-1",
        lease_generation=1,
        lease_expires_at="2026-09-25T13:00:00+00:00",
        not_before="2026-09-25T12:00:00+00:00",
    )


class HostedReadOnlyWorkerTest(unittest.TestCase):
    def test_default_gate_refuses_before_queue_claim(self):
        spec = make_spec()
        queue = FakeQueue(make_lease(spec))
        activity = FakeActivity()
        registry = ToolRegistry()
        worker = HostedReadOnlyWorker(queue=queue, activity=activity, registry=registry)
        with self.assertRaisesRegex(HostedExecutionNotAuthorized, "hosted_readonly_execution_not_authorized"):
            worker.run_next(worker_id="worker-1")
        self.assertEqual(queue.claim_count, 0)
        self.assertEqual(queue.saves, [])
        self.assertEqual(activity.events, [])

    def test_authorized_read_only_action_and_verifier_complete_through_fenced_store(self):
        calls: list[str] = []

        def read(args, context):
            calls.append("read")
            return {"message": "read ok", "data": {"rows": 1}}

        def verify(args, context):
            calls.append("verify")
            return {"verified": True}

        spec = make_spec(verify_action="github.verify_ci")
        queue = FakeQueue(make_lease(spec))
        activity = FakeActivity()
        registry = ToolRegistry()
        registry.register(FakeAdapter(
            (
                Capability("github.read_main", "read"),
                Capability("github.verify_ci", "read"),
            ),
            {
                "github.read_main": read,
                "github.verify_ci": verify,
            },
        ))
        worker = HostedReadOnlyWorker(
            queue=queue,
            activity=activity,
            registry=registry,
            execution_authorized=True,
        )
        result = worker.run_next(worker_id="worker-1", lease_seconds=90)
        self.assertTrue(result.claimed)
        self.assertTrue(result.execution_enabled)
        self.assertIsNotNone(result.outcome)
        self.assertEqual(result.outcome.status, "completed")
        self.assertEqual(result.outcome.completed_steps, ("read",))
        self.assertEqual(calls, ["read", "verify"])
        self.assertEqual(queue.current.status, "completed")
        self.assertIsNone(queue.current.lease_owner)
        self.assertGreaterEqual(len(queue.saves), 4)
        event_types = [event["event_type"] for event in activity.events]
        self.assertIn("readonly_worker_claimed", event_types)
        self.assertIn("step_started", event_types)
        self.assertIn("step_verified", event_types)
        self.assertIn("task_completed", event_types)

    def test_non_read_action_is_blocked_without_invocation(self):
        calls: list[str] = []

        def write(args, context):
            calls.append("write")
            return {"message": "should not run"}

        spec = make_spec(action="files.write_artifact")
        queue = FakeQueue(make_lease(spec))
        activity = FakeActivity()
        registry = ToolRegistry()
        registry.register(FakeAdapter(
            (Capability("files.write_artifact", "write"),),
            {"files.write_artifact": write},
        ))
        result = HostedReadOnlyWorker(
            queue=queue,
            activity=activity,
            registry=registry,
            execution_authorized=True,
        ).run_next(worker_id="worker-1")
        self.assertIsNone(result.outcome)
        self.assertEqual(result.blocked_reason, "readonly_worker_forbidden_actions:files.write_artifact")
        self.assertEqual(calls, [])
        self.assertEqual(queue.current.status, "blocked")
        self.assertIsNone(queue.current.lease_owner)

    def test_missing_action_is_blocked_without_execution(self):
        spec = make_spec(action="provider.missing")
        queue = FakeQueue(make_lease(spec))
        activity = FakeActivity()
        result = HostedReadOnlyWorker(
            queue=queue,
            activity=activity,
            registry=ToolRegistry(),
            execution_authorized=True,
        ).run_next(worker_id="worker-1")
        self.assertEqual(result.blocked_reason, "preflight_missing_actions:provider.missing")
        self.assertEqual(queue.current.status, "blocked")

    def test_read_capability_cannot_report_write_artifact_as_success(self):
        calls: list[str] = []

        def inconsistent_read(args, context):
            calls.append("read")
            return {
                "message": "bad read contract",
                "artifacts": [
                    ArtifactUpdate(
                        artifact_id="a1",
                        kind="file",
                        created=True,
                    )
                ],
            }

        spec = make_spec()
        queue = FakeQueue(make_lease(spec))
        activity = FakeActivity()
        registry = ToolRegistry()
        registry.register(FakeAdapter(
            (Capability("github.read_main", "read"),),
            {"github.read_main": inconsistent_read},
        ))
        result = HostedReadOnlyWorker(
            queue=queue,
            activity=activity,
            registry=registry,
            execution_authorized=True,
        ).run_next(worker_id="worker-1")
        self.assertEqual(calls, ["read", "read"])
        self.assertIsNotNone(result.outcome)
        self.assertEqual(result.outcome.status, "failed")
        self.assertIn("read_only_action_reported_write_artifact", result.outcome.last_error or "")
        self.assertEqual(queue.current.status, "failed")
        self.assertIsNone(queue.current.lease_owner)


if __name__ == "__main__":
    unittest.main()
