from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_core.hosted_checkpoint import (  # noqa: E402
    HostedCheckpointClient,
    HostedCheckpointConflict,
    HostedCheckpointIntegrityError,
)
from agent_core.model import StepSpec, TaskSpec, TaskState  # noqa: E402


def make_spec(*, title: str = "Hosted checkpoint test") -> TaskSpec:
    return TaskSpec(
        task_id="hosted-checkpoint-test",
        title=title,
        goal="verify strict remote state binding",
        allowed_actions=("github.read_main",),
        steps=(StepSpec("read", "github.read_main", retry_safe=True, max_attempts=2),),
        inputs={"repository": "owner/repo", "nested": {"value": 1}},
        completion_conditions=("state remains bound to original task definition",),
    )


class FakeCheckpointTransport:
    def __init__(self):
        self.rows: dict[str, dict] = {}
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, mode: str, payload: dict):
        payload = deepcopy(payload)
        self.calls.append((mode, payload))
        if mode == "checkpoint_create":
            task = deepcopy(payload["task"])
            state = deepcopy(payload["state"])
            task_id = task["task_id"]
            if task_id in self.rows:
                return {"success": False, "error": "duplicate", "backend_code": "23505"}
            row = {
                "task_id": task_id,
                "schema_version": "agent-task-state-v1",
                "status": "queued",
                "idempotency_key": payload["idempotency_key"],
                "spec": task,
                "state": state,
                "blocked_reason": None,
                "last_error": None,
                "revision": 0,
                "spec_fingerprint": state["spec_fingerprint"],
                "created_at": "2026-09-25T11:00:00+00:00",
                "updated_at": "2026-09-25T11:00:00+00:00",
            }
            self.rows[task_id] = row
            return {"success": True, "checkpoint": deepcopy(row), "saved": True, "state_persisted": True}
        if mode == "checkpoint_get":
            row = self.rows.get(payload["task_id"])
            if row is None:
                return {"success": False, "error": "Checkpoint not found"}
            return {"success": True, "checkpoint": deepcopy(row), "state_persisted": True}
        if mode == "checkpoint_save":
            row = self.rows[payload["task_id"]]
            if payload["expected_revision"] != row["revision"]:
                return {
                    "success": False,
                    "error": "checkpoint_conflict_or_not_accessible",
                    "backend_code": "40001",
                }
            row["revision"] += 1
            row["status"] = payload["status"]
            row["state"] = deepcopy(payload["state"])
            row["blocked_reason"] = row["state"].get("blocked_reason")
            row["last_error"] = row["state"].get("last_error")
            return {
                "success": True,
                "checkpoint": deepcopy(row),
                "revision": row["revision"],
                "saved": True,
                "state_persisted": True,
            }
        if mode == "checkpoint_list":
            rows = list(self.rows.values())
            if payload.get("status"):
                rows = [row for row in rows if row["status"] == payload["status"]]
            return {
                "success": True,
                "checkpoints": [
                    {
                        key: deepcopy(row.get(key))
                        for key in (
                            "task_id", "status", "revision", "idempotency_key",
                            "blocked_reason", "last_error", "created_at", "updated_at",
                        )
                    }
                    for row in rows[: payload["limit"]]
                ],
            }
        raise AssertionError(f"unexpected mode: {mode}")


class HostedCheckpointClientTest(unittest.TestCase):
    def test_create_get_and_save_strict_round_trip(self):
        transport = FakeCheckpointTransport()
        client = HostedCheckpointClient(transport)
        spec = make_spec()

        created = client.create(spec)
        self.assertEqual(created.status, "queued")
        self.assertEqual(created.revision, 0)
        self.assertEqual(created.state.status, "pending")
        self.assertEqual(created.state.spec_fingerprint, spec.fingerprint())

        loaded = client.get(spec)
        self.assertEqual(loaded.spec.to_dict(), spec.to_dict())
        self.assertEqual(client.load_state(spec).spec_fingerprint, spec.fingerprint())

        state = loaded.state
        state.status = "blocked"
        state.blocked_reason = "manual_auth_required"
        state.last_error = "provider_not_connected"
        saved = client.save(spec, state, expected_revision=0)
        self.assertEqual(saved.revision, 1)
        self.assertEqual(saved.status, "blocked")
        self.assertEqual(saved.state.blocked_reason, "manual_auth_required")

        self.assertEqual(
            [mode for mode, _ in transport.calls],
            ["checkpoint_create", "checkpoint_get", "checkpoint_get", "checkpoint_save"],
        )

    def test_changed_task_definition_is_rejected_before_resume(self):
        transport = FakeCheckpointTransport()
        client = HostedCheckpointClient(transport)
        original = make_spec()
        client.create(original)

        changed = make_spec(title="Changed after persistence")
        with self.assertRaisesRegex(HostedCheckpointIntegrityError, "task_spec_changed"):
            client.get(changed)

    def test_forged_or_corrupted_persisted_fingerprint_is_rejected(self):
        transport = FakeCheckpointTransport()
        client = HostedCheckpointClient(transport)
        spec = make_spec()
        client.create(spec)
        transport.rows[spec.task_id]["spec_fingerprint"] = "sha256-v1:" + "0" * 64

        with self.assertRaisesRegex(HostedCheckpointIntegrityError, "checkpoint_spec_fingerprint_mismatch"):
            client.get(spec)

    def test_state_fingerprint_is_bound_before_create_and_save(self):
        transport = FakeCheckpointTransport()
        client = HostedCheckpointClient(transport)
        spec = make_spec()

        bad = TaskState(task_id=spec.task_id, spec_fingerprint="sha256-v1:" + "f" * 64)
        with self.assertRaisesRegex(HostedCheckpointIntegrityError, "task_spec_changed"):
            client.create(spec, state=bad)
        self.assertEqual(transport.calls, [])

        created = client.create(spec)
        created.state.status = "running"
        created.state.spec_fingerprint = "sha256-v1:" + "e" * 64
        with self.assertRaisesRegex(HostedCheckpointIntegrityError, "task_spec_changed"):
            client.save(spec, created.state, expected_revision=0)
        self.assertEqual([mode for mode, _ in transport.calls], ["checkpoint_create"])

    def test_stale_revision_surfaces_as_conflict(self):
        transport = FakeCheckpointTransport()
        client = HostedCheckpointClient(transport)
        spec = make_spec()
        created = client.create(spec)
        state = created.state
        state.status = "running"
        client.save(spec, state, expected_revision=0)

        state.status = "blocked"
        with self.assertRaisesRegex(HostedCheckpointConflict, "checkpoint_conflict"):
            client.save(spec, state, expected_revision=0)

    def test_list_is_metadata_only_and_validated(self):
        transport = FakeCheckpointTransport()
        client = HostedCheckpointClient(transport)
        spec = make_spec()
        client.create(spec, idempotency_key="stable-idem")

        summaries = client.list(status="queued", limit=10)
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0].task_id, spec.task_id)
        self.assertEqual(summaries[0].idempotency_key, "stable-idem")
        self.assertEqual(summaries[0].revision, 0)

        with self.assertRaisesRegex(ValueError, "invalid_checkpoint_status"):
            client.list(status="pending")
        with self.assertRaisesRegex(ValueError, "checkpoint_list_limit_out_of_range"):
            client.list(limit=0)

    def test_invalid_remote_revision_and_state_status_fail_closed(self):
        transport = FakeCheckpointTransport()
        client = HostedCheckpointClient(transport)
        spec = make_spec()
        client.create(spec)

        transport.rows[spec.task_id]["revision"] = -1
        with self.assertRaisesRegex(HostedCheckpointIntegrityError, "invalid_checkpoint_revision"):
            client.get(spec)

        transport.rows[spec.task_id]["revision"] = 0
        transport.rows[spec.task_id]["status"] = "running"
        with self.assertRaisesRegex(HostedCheckpointIntegrityError, "checkpoint_state_status_mismatch"):
            client.get(spec)


if __name__ == "__main__":
    unittest.main()
