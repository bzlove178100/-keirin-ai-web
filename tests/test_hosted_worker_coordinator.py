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
from agent_core.hosted_worker import HostedWorkerCoordinator  # noqa: E402
from agent_core.model import StepSpec, TaskSpec, TaskState  # noqa: E402


class FakeAdapter:
    def __init__(self, action: str, access: str, calls: list[str]):
        self.name = f"fake-{action}"
        self.action = action
        self.access = access
        self.calls = calls

    def capabilities(self):
        return (Capability(action=self.action, access=self.access),)

    def actions(self):
        def invoke(args, context):
            self.calls.append(self.action)
            return {"message": "should not execute"}

        return {self.action: invoke}


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
    def __init__(self, lease: HostedQueueLease | None, *, fail_save: bool = False):
        self.lease = lease
        self.fail_save = fail_save
        self.claims: list[tuple[str, int]] = []
        self.saves: list[dict] = []

    def claim(self, *, worker_id: str, lease_seconds: int = 120):
        self.claims.append((worker_id, lease_seconds))
        return self.lease

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
        self.saves.append(
            {
                "task_id": spec.task_id,
                "status": state.status,
                "blocked_reason": state.blocked_reason,
                "expected_revision": expected_revision,
                "worker_id": worker_id,
                "lease_generation": lease_generation,
                "lease_seconds": lease_seconds,
            }
        )
        if self.fail_save:
            raise RuntimeError("simulated_queue_save_failure")
        assert self.lease is not None
        return replace(
            self.lease,
            status=state.status,
            revision=expected_revision + 1,
            state=state,
            lease_owner=None,
            lease_expires_at=None,
        )


def make_spec(action: str) -> TaskSpec:
    return TaskSpec(
        task_id="worker-test-task",
        title="Worker coordinator test",
        goal="Verify fail-closed hosted coordination",
        allowed_actions=(action,),
        steps=(StepSpec(step_id="one", action=action),),
    )


def make_lease(action: str) -> HostedQueueLease:
    spec = make_spec(action)
    state = TaskState(
        task_id=spec.task_id,
        status="running",
        spec_fingerprint=spec.fingerprint(),
    )
    return HostedQueueLease(
        task_id=spec.task_id,
        status="running",
        revision=1,
        idempotency_key="worker-test-key",
        spec=spec,
        state=state,
        attempt_count=1,
        max_attempts=1,
        lease_owner="worker-1",
        lease_generation=1,
        lease_expires_at="2026-09-25T13:00:00+00:00",
        not_before="2026-09-25T12:00:00+00:00",
    )


class HostedWorkerCoordinatorTest(unittest.TestCase):
    def test_empty_queue_does_not_emit_or_execute(self):
        calls: list[str] = []
        registry = ToolRegistry()
        registry.register(FakeAdapter("github.read_main", "read", calls))
        queue = FakeQueue(None)
        activity = FakeActivity()
        result = HostedWorkerCoordinator(queue=queue, activity=activity, registry=registry).inspect_next(
            worker_id="worker-1"
        )
        self.assertFalse(result.claimed)
        self.assertFalse(result.execution_enabled)
        self.assertEqual(result.blocked_reason, "queue_empty")
        self.assertEqual(activity.events, [])
        self.assertEqual(queue.saves, [])
        self.assertEqual(calls, [])

    def test_ready_read_task_is_released_blocked_without_execution(self):
        calls: list[str] = []
        registry = ToolRegistry()
        registry.register(FakeAdapter("github.read_main", "read", calls))
        queue = FakeQueue(make_lease("github.read_main"))
        activity = FakeActivity()
        result = HostedWorkerCoordinator(queue=queue, activity=activity, registry=registry).inspect_next(
            worker_id="worker-1", lease_seconds=90, allowed_access=("read",)
        )
        self.assertTrue(result.claimed)
        self.assertTrue(result.ready)
        self.assertFalse(result.execution_enabled)
        self.assertEqual(result.blocked_reason, "hosted_task_execution_not_activated")
        self.assertEqual(queue.saves[0]["status"], "blocked")
        self.assertEqual(queue.saves[0]["lease_generation"], 1)
        self.assertEqual([event["event_type"] for event in activity.events], [
            "worker_preflight_started",
            "worker_preflight_blocked",
        ])
        self.assertEqual(calls, [], "coordinator must never invoke task actions")

    def test_missing_action_is_fail_closed(self):
        registry = ToolRegistry()
        queue = FakeQueue(make_lease("provider.missing"))
        activity = FakeActivity()
        result = HostedWorkerCoordinator(queue=queue, activity=activity, registry=registry).inspect_next(
            worker_id="worker-1"
        )
        self.assertFalse(result.ready)
        self.assertEqual(result.missing_actions, ("provider.missing",))
        self.assertEqual(result.blocked_reason, "preflight_missing_actions:provider.missing")
        self.assertEqual(queue.saves[0]["status"], "blocked")

    def test_write_or_execute_action_is_forbidden_under_read_only_policy(self):
        for access in ("write", "execute"):
            with self.subTest(access=access):
                calls: list[str] = []
                action = f"provider.{access}"
                registry = ToolRegistry()
                registry.register(FakeAdapter(action, access, calls))
                queue = FakeQueue(make_lease(action))
                activity = FakeActivity()
                result = HostedWorkerCoordinator(queue=queue, activity=activity, registry=registry).inspect_next(
                    worker_id="worker-1", allowed_access=("read",)
                )
                self.assertFalse(result.ready)
                self.assertEqual(result.forbidden_actions, (action,))
                self.assertEqual(result.blocked_reason, f"preflight_forbidden_actions:{action}")
                self.assertEqual(calls, [])

    def test_failed_release_is_not_reported_as_blocked_success(self):
        calls: list[str] = []
        registry = ToolRegistry()
        registry.register(FakeAdapter("github.read_main", "read", calls))
        queue = FakeQueue(make_lease("github.read_main"), fail_save=True)
        activity = FakeActivity()
        coordinator = HostedWorkerCoordinator(queue=queue, activity=activity, registry=registry)
        with self.assertRaisesRegex(RuntimeError, "simulated_queue_save_failure"):
            coordinator.inspect_next(worker_id="worker-1")
        self.assertEqual([event["event_type"] for event in activity.events], ["worker_preflight_started"])
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
