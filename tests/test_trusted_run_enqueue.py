from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_core.hosted_checkpoint import (  # noqa: E402
    HostedCheckpointClient,
    HostedCheckpointConflict,
    HostedCheckpointNotFound,
)
from agent_core.trusted_run_enqueue import TrustedRunAlreadyUsed, TrustedRunEnqueuer  # noqa: E402
from agent_core.trusted_run_instance import build_trusted_status_run_spec, trusted_status_template_spec  # noqa: E402

TOKEN = "0123456789abcdef"


class FakeTransport:
    def __init__(self):
        self.rows = {}
        self.calls = []
        self.concurrent_create = False

    @staticmethod
    def row_for(spec):
        return {
            "task_id": spec.task_id,
            "status": "queued",
            "revision": 0,
            "idempotency_key": spec.task_id,
            "spec": spec.to_dict(),
            "state": {
                "schema_version": "agent-task-state-v1",
                "task_id": spec.task_id,
                "status": "pending",
                "spec_fingerprint": spec.fingerprint(),
                "completed_steps": [],
                "attempts": {},
                "artifacts": {},
                "blocked_reason": None,
                "last_error": None,
                "reconciliations": [],
            },
            "spec_fingerprint": spec.fingerprint(),
            "created_at": "2026-09-26T04:00:00+00:00",
            "updated_at": "2026-09-26T04:00:00+00:00",
        }

    def __call__(self, mode, payload):
        self.calls.append((mode, deepcopy(payload)))
        if mode == "checkpoint_get":
            row = self.rows.get(payload["task_id"])
            if row is None:
                return {"success": False, "error": "Checkpoint not found", "backend_status": 404}
            return {"success": True, "checkpoint": deepcopy(row)}
        if mode == "checkpoint_create":
            task_id = payload["task"]["task_id"]
            from agent_core.model import TaskSpec
            spec = TaskSpec.from_dict(payload["task"])
            if self.concurrent_create and task_id not in self.rows:
                self.rows[task_id] = self.row_for(spec)
                return {"success": False, "error": "duplicate key", "backend_code": "23505"}
            if task_id in self.rows:
                return {"success": False, "error": "duplicate key", "backend_code": "23505"}
            row = self.row_for(spec)
            self.rows[task_id] = row
            return {"success": True, "checkpoint": deepcopy(row)}
        raise AssertionError(f"unexpected mode:{mode}")


class TrustedRunEnqueueTest(unittest.TestCase):
    def spec(self):
        return build_trusted_status_run_spec(TOKEN, repo_root=ROOT)

    def test_missing_and_duplicate_errors_are_distinct(self):
        transport = FakeTransport()
        client = HostedCheckpointClient(transport)
        spec = self.spec()
        with self.assertRaises(HostedCheckpointNotFound):
            client.get(spec)
        transport.rows[spec.task_id] = transport.row_for(spec)
        with self.assertRaises(HostedCheckpointConflict):
            client.create(spec, idempotency_key=spec.task_id)

    def test_first_call_creates_pristine_queue_row_and_second_call_is_idempotent(self):
        transport = FakeTransport()
        enqueuer = TrustedRunEnqueuer(HostedCheckpointClient(transport))
        spec = self.spec()

        first = enqueuer.ensure_queued(spec)
        second = enqueuer.ensure_queued(spec)

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.record.task_id, spec.task_id)
        self.assertEqual(second.record.status, "queued")
        self.assertEqual(second.record.revision, 0)
        self.assertEqual([mode for mode, _ in transport.calls], [
            "checkpoint_get", "checkpoint_create", "checkpoint_get",
        ])
        self.assertFalse(any(mode.startswith("queue_") for mode, _ in transport.calls))

    def test_concurrent_identical_create_is_re_read_and_accepted_only_if_pristine(self):
        transport = FakeTransport()
        transport.concurrent_create = True
        spec = self.spec()
        result = TrustedRunEnqueuer(HostedCheckpointClient(transport)).ensure_queued(spec)
        self.assertFalse(result.created)
        self.assertEqual(result.record.status, "queued")
        self.assertEqual([mode for mode, _ in transport.calls], [
            "checkpoint_get", "checkpoint_create", "checkpoint_get",
        ])

    def test_consumed_instance_is_never_silently_reused(self):
        transport = FakeTransport()
        spec = self.spec()
        row = transport.row_for(spec)
        row["status"] = "completed"
        row["revision"] = 6
        row["state"]["status"] = "completed"
        row["state"]["completed_steps"] = ["read-current-state"]
        transport.rows[spec.task_id] = row

        with self.assertRaisesRegex(TrustedRunAlreadyUsed, "already_used:completed"):
            TrustedRunEnqueuer(HostedCheckpointClient(transport)).ensure_queued(spec)
        self.assertEqual([mode for mode, _ in transport.calls], ["checkpoint_get"])

    def test_template_identity_is_rejected_before_any_transport_io(self):
        transport = FakeTransport()
        with self.assertRaisesRegex(ValueError, "trusted_run_instance_id_required"):
            TrustedRunEnqueuer(HostedCheckpointClient(transport)).ensure_queued(
                trusted_status_template_spec(repo_root=ROOT)
            )
        self.assertEqual(transport.calls, [])


if __name__ == "__main__":
    unittest.main()
