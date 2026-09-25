from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_core.hosted_queue import (  # noqa: E402
    HostedQueueClient,
    HostedQueueConflict,
    HostedQueueIntegrityError,
)
from agent_core.model import StepSpec, TaskSpec, TaskState  # noqa: E402


def make_spec(task_id: str = "queue-task-1") -> TaskSpec:
    return TaskSpec(
        task_id=task_id,
        title="Queue task",
        goal="Verify fenced hosted queue coordination",
        allowed_actions=("github.read_main",),
        steps=(StepSpec(step_id="read", action="github.read_main"),),
    )


def pending_state(spec: TaskSpec) -> TaskState:
    return TaskState(task_id=spec.task_id, status="pending", spec_fingerprint=spec.fingerprint())


class FakeQueueTransport:
    def __init__(self, spec: TaskSpec):
        self.spec = spec
        self.row = {
            "task_id": spec.task_id,
            "status": "queued",
            "revision": 0,
            "idempotency_key": spec.task_id,
            "spec": spec.to_dict(),
            "state": pending_state(spec).to_dict(),
            "spec_fingerprint": spec.fingerprint(),
            "attempt_count": 0,
            "max_attempts": 2,
            "lease_owner": None,
            "lease_generation": 0,
            "lease_expires_at": None,
            "not_before": "2026-09-25T12:00:00+00:00",
            "created_at": "2026-09-25T12:00:00+00:00",
            "updated_at": "2026-09-25T12:00:00+00:00",
        }
        self.calls: list[tuple[str, dict]] = []
        self.expired = False

    def __call__(self, mode: str, payload: dict):
        payload = deepcopy(payload)
        self.calls.append((mode, payload))
        row = self.row
        if mode == "queue_claim":
            if row["status"] != "queued" or row["attempt_count"] >= row["max_attempts"]:
                return {"success": True, "claimed": False, "lease": None}
            row["status"] = "running"
            row["revision"] += 1
            row["attempt_count"] += 1
            row["lease_owner"] = payload["worker_id"]
            row["lease_generation"] += 1
            row["lease_expires_at"] = "2026-09-25T12:02:00+00:00"
            row["state"]["status"] = "running"
            row["state"]["blocked_reason"] = None
            row["state"]["last_error"] = None
            return {"success": True, "claimed": True, "lease": deepcopy(row)}

        if mode == "queue_save":
            if (
                row["status"] != "running"
                or payload["expected_revision"] != row["revision"]
                or payload["worker_id"] != row["lease_owner"]
                or payload["lease_generation"] != row["lease_generation"]
                or self.expired
            ):
                return {"success": False, "error": "lease_conflict_or_expired", "backend_code": "40001"}
            row["revision"] += 1
            row["status"] = payload["status"]
            row["state"] = deepcopy(payload["state"])
            if row["status"] == "running":
                row["lease_expires_at"] = "2026-09-25T12:04:00+00:00"
            else:
                row["lease_owner"] = None
                row["lease_expires_at"] = None
            return {"success": True, "lease": deepcopy(row)}

        if mode == "queue_reconcile_expired":
            if (
                row["status"] != "running"
                or payload["expected_revision"] != row["revision"]
                or payload["lease_generation"] != row["lease_generation"]
                or not self.expired
            ):
                return {
                    "success": False,
                    "error": "expired_lease_conflict_or_not_accessible",
                    "backend_code": "40001",
                }
            row["revision"] += 1
            row["status"] = "blocked"
            row["state"] = deepcopy(payload["state"])
            if not row["state"].get("blocked_reason"):
                row["state"]["blocked_reason"] = "expired_lease_requires_reconciliation"
            row["lease_owner"] = None
            row["lease_expires_at"] = None
            return {"success": True, "lease": deepcopy(row)}

        raise AssertionError(f"unexpected mode: {mode}")


class HostedQueueClientTest(unittest.TestCase):
    def test_claim_establishes_revision_attempt_and_fence(self):
        spec = make_spec()
        transport = FakeQueueTransport(spec)
        client = HostedQueueClient(transport)

        lease = client.claim(worker_id="worker-a", lease_seconds=120)
        self.assertIsNotNone(lease)
        assert lease is not None
        self.assertEqual(lease.status, "running")
        self.assertEqual(lease.revision, 1)
        self.assertEqual(lease.attempt_count, 1)
        self.assertEqual(lease.lease_owner, "worker-a")
        self.assertEqual(lease.lease_generation, 1)
        self.assertTrue(lease.fenced)

        no_second_claim = client.claim(worker_id="worker-b", lease_seconds=120)
        self.assertIsNone(no_second_claim)

    def test_fenced_save_extends_running_lease_and_terminal_save_releases_it(self):
        spec = make_spec()
        transport = FakeQueueTransport(spec)
        client = HostedQueueClient(transport)
        lease = client.claim(worker_id="worker-a")
        assert lease is not None

        running = deepcopy(lease.state)
        running.status = "running"
        saved = client.save(
            spec,
            running,
            expected_revision=lease.revision,
            worker_id="worker-a",
            lease_generation=lease.lease_generation,
        )
        self.assertEqual(saved.revision, 2)
        self.assertEqual(saved.lease_owner, "worker-a")
        self.assertTrue(saved.fenced)

        completed = deepcopy(saved.state)
        completed.status = "completed"
        finished = client.save(
            spec,
            completed,
            expected_revision=saved.revision,
            worker_id="worker-a",
            lease_generation=saved.lease_generation,
        )
        self.assertEqual(finished.status, "completed")
        self.assertEqual(finished.revision, 3)
        self.assertIsNone(finished.lease_owner)
        self.assertIsNone(finished.lease_expires_at)

    def test_stale_worker_or_generation_is_conflict(self):
        spec = make_spec()
        transport = FakeQueueTransport(spec)
        client = HostedQueueClient(transport)
        lease = client.claim(worker_id="worker-a")
        assert lease is not None
        state = deepcopy(lease.state)
        state.status = "running"

        with self.assertRaises(HostedQueueConflict):
            client.save(
                spec,
                state,
                expected_revision=lease.revision,
                worker_id="worker-b",
                lease_generation=lease.lease_generation,
            )
        with self.assertRaises(HostedQueueConflict):
            client.save(
                spec,
                state,
                expected_revision=lease.revision,
                worker_id="worker-a",
                lease_generation=lease.lease_generation + 1,
            )

    def test_expired_lease_cannot_save_and_reconciliation_blocks_without_requeue(self):
        spec = make_spec()
        transport = FakeQueueTransport(spec)
        client = HostedQueueClient(transport)
        lease = client.claim(worker_id="worker-a")
        assert lease is not None
        transport.expired = True

        running = deepcopy(lease.state)
        running.status = "running"
        with self.assertRaises(HostedQueueConflict):
            client.save(
                spec,
                running,
                expected_revision=lease.revision,
                worker_id="worker-a",
                lease_generation=lease.lease_generation,
            )

        blocked = deepcopy(lease.state)
        blocked.status = "blocked"
        blocked.blocked_reason = "expired_lease_requires_reconciliation"
        reconciled = client.reconcile_expired(
            spec,
            blocked,
            expected_revision=lease.revision,
            lease_generation=lease.lease_generation,
        )
        self.assertEqual(reconciled.status, "blocked")
        self.assertEqual(reconciled.revision, lease.revision + 1)
        self.assertIsNone(reconciled.lease_owner)
        self.assertIsNone(reconciled.lease_expires_at)
        self.assertIsNone(client.claim(worker_id="worker-b"))

    def test_changed_or_corrupt_remote_spec_fails_closed(self):
        spec = make_spec()
        transport = FakeQueueTransport(spec)
        client = HostedQueueClient(transport)
        transport.row["spec_fingerprint"] = "sha256-v1:" + "0" * 64
        with self.assertRaisesRegex(HostedQueueIntegrityError, "queue_spec_fingerprint_mismatch"):
            client.claim(worker_id="worker-a")

    def test_secret_shaped_remote_state_fails_closed(self):
        spec = make_spec()
        transport = FakeQueueTransport(spec)
        transport.row["state"]["artifacts"] = {
            "bad": {
                "artifact_id": "bad",
                "kind": "test",
                "metadata": {"access_token": "must-not-persist"},
            }
        }
        with self.assertRaisesRegex(HostedQueueIntegrityError, "forbidden_secret"):
            HostedQueueClient(transport).claim(worker_id="worker-a")

    def test_input_bounds_are_enforced_before_transport(self):
        spec = make_spec()
        transport = FakeQueueTransport(spec)
        client = HostedQueueClient(transport)
        with self.assertRaisesRegex(ValueError, "invalid_worker_id"):
            client.claim(worker_id="../bad")
        with self.assertRaisesRegex(ValueError, "invalid_lease_seconds"):
            client.claim(worker_id="worker-a", lease_seconds=5)
        self.assertEqual(transport.calls, [])


if __name__ == "__main__":
    unittest.main()
