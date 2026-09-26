from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_core.exact_task_queue import ExactTaskQueueClient  # noqa: E402
from agent_core.hosted_queue import HostedQueueIntegrityError  # noqa: E402
from agent_core.model import StepSpec, TaskSpec, TaskState  # noqa: E402


def make_spec(task_id="keirin-readonly-status-check.0123456789abcdef"):
    return TaskSpec(
        task_id=task_id,
        title="Exact task",
        goal="Claim only the requested task",
        allowed_actions=("github.read_main",),
        steps=(StepSpec(step_id="read", action="github.read_main"),),
    )


class FakeExactTransport:
    def __init__(self, spec):
        self.spec = spec
        self.calls = []
        self.row = {
            "task_id": spec.task_id,
            "status": "queued",
            "revision": 0,
            "idempotency_key": spec.task_id,
            "spec": spec.to_dict(),
            "state": TaskState(
                task_id=spec.task_id,
                status="pending",
                spec_fingerprint=spec.fingerprint(),
            ).to_dict(),
            "spec_fingerprint": spec.fingerprint(),
            "attempt_count": 0,
            "max_attempts": 1,
            "lease_owner": None,
            "lease_generation": 0,
            "lease_expires_at": None,
            "not_before": "2026-09-26T03:00:00+00:00",
            "created_at": "2026-09-26T03:00:00+00:00",
            "updated_at": "2026-09-26T03:00:00+00:00",
        }

    def __call__(self, mode, payload):
        self.calls.append((mode, deepcopy(payload)))
        if mode != "queue_claim_task":
            raise AssertionError(f"unexpected mode:{mode}")
        if payload["task_id"] != self.row["task_id"]:
            return {"success": True, "claimed": False, "lease": None}
        if self.row["status"] != "queued":
            return {"success": True, "claimed": False, "lease": None}
        self.row["status"] = "running"
        self.row["revision"] = 1
        self.row["attempt_count"] = 1
        self.row["lease_owner"] = payload["worker_id"]
        self.row["lease_generation"] = 1
        self.row["lease_expires_at"] = "2026-09-26T03:02:00+00:00"
        self.row["state"]["status"] = "running"
        return {"success": True, "claimed": True, "lease": deepcopy(self.row)}


class ExactTaskQueueClientTest(unittest.TestCase):
    def test_claim_sends_exact_task_id_and_returns_bound_lease(self):
        spec = make_spec()
        transport = FakeExactTransport(spec)
        lease = ExactTaskQueueClient(transport).claim_task(spec, worker_id="worker-one", lease_seconds=120)
        self.assertIsNotNone(lease)
        assert lease is not None
        self.assertEqual(lease.task_id, spec.task_id)
        self.assertEqual(lease.spec.to_dict(), spec.to_dict())
        self.assertEqual(lease.lease_owner, "worker-one")
        self.assertEqual(lease.attempt_count, 1)
        self.assertEqual(transport.calls[0], (
            "queue_claim_task",
            {"task_id": spec.task_id, "worker_id": "worker-one", "lease_seconds": 120},
        ))

    def test_nonmatching_target_is_not_consumed(self):
        stored = make_spec()
        requested = make_spec("keirin-readonly-status-check.1111111111111111")
        transport = FakeExactTransport(stored)
        lease = ExactTaskQueueClient(transport).claim_task(requested, worker_id="worker-one")
        self.assertIsNone(lease)
        self.assertEqual(transport.row["status"], "queued")
        self.assertEqual(transport.row["attempt_count"], 0)

    def test_remote_spec_mismatch_fails_closed(self):
        spec = make_spec()
        transport = FakeExactTransport(spec)
        transport.row["spec"]["goal"] = "tampered"
        with self.assertRaisesRegex(HostedQueueIntegrityError, "task_spec_changed"):
            ExactTaskQueueClient(transport).claim_task(spec, worker_id="worker-one")

    def test_invalid_inputs_fail_before_transport(self):
        spec = make_spec()
        transport = FakeExactTransport(spec)
        client = ExactTaskQueueClient(transport)
        with self.assertRaisesRegex(ValueError, "invalid_worker_id"):
            client.claim_task(spec, worker_id="../bad")
        with self.assertRaisesRegex(ValueError, "invalid_lease_seconds"):
            client.claim_task(spec, worker_id="worker-one", lease_seconds=5)
        self.assertEqual(transport.calls, [])

    def test_completed_task_is_never_reclaimed(self):
        spec = make_spec()
        transport = FakeExactTransport(spec)
        transport.row["status"] = "completed"
        transport.row["state"]["status"] = "completed"
        lease = ExactTaskQueueClient(transport).claim_task(spec, worker_id="worker-one")
        self.assertIsNone(lease)
        self.assertEqual(transport.row["status"], "completed")


if __name__ == "__main__":
    unittest.main()
