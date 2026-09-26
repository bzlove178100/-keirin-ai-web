from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_core.hosted_activity import HostedActivityClient  # noqa: E402
from agent_core.hosted_queue import HostedQueueClient  # noqa: E402
from agent_core.hosted_recovery import HostedRecoveryInspector, HostedRecoveryIntegrityError  # noqa: E402
from agent_core.model import StepSpec, TaskSpec, TaskState  # noqa: E402

NOW = datetime(2026, 9, 26, 2, 30, tzinfo=timezone.utc)


def make_spec() -> TaskSpec:
    return TaskSpec(
        task_id="recovery-test",
        title="Recovery test",
        goal="Inspect durable state without replay",
        allowed_actions=("github.read_main", "github.verify_ci"),
        steps=(StepSpec("read", "github.read_main", verify_action="github.verify_ci"),),
    )


def make_row(*, status: str, revision: int = 7, generation: int = 2,
             attempt_count: int = 1, expires: str | None = None) -> dict:
    spec = make_spec()
    state_status = "pending" if status == "queued" else status
    state = TaskState(
        task_id=spec.task_id,
        status=state_status,
        spec_fingerprint=spec.fingerprint(),
    )
    return {
        "task_id": spec.task_id,
        "schema_version": "agent-task-v1",
        "status": status,
        "idempotency_key": "recovery-key",
        "spec": spec.to_dict(),
        "state": state.to_dict(),
        "blocked_reason": state.blocked_reason,
        "last_error": state.last_error,
        "revision": revision,
        "spec_fingerprint": spec.fingerprint(),
        "not_before": "2026-09-26T01:00:00+00:00",
        "attempt_count": attempt_count,
        "max_attempts": 2,
        "lease_owner": "worker-1" if status == "running" else None,
        "lease_generation": generation,
        "lease_expires_at": expires if status == "running" else None,
        "created_at": "2026-09-26T01:00:00+00:00",
        "updated_at": "2026-09-26T02:00:00+00:00",
    }


def evidence_event(event_id: int, event_type: str, *, generation: int = 2,
                   revision: int = 5, verified: bool | None = None) -> dict:
    spec = make_spec()
    evidence = {"observed_sha": "a" * 40}
    if verified is not None:
        evidence["verified"] = verified
    return {
        "event_id": event_id,
        "task_id": spec.task_id,
        "event_type": event_type,
        "step_id": "read",
        "payload": {
            "spec_fingerprint": spec.fingerprint(),
            "lease_generation": generation,
            "revision": revision,
            "evidence": evidence,
        },
        "created_at": f"2026-09-26T02:0{event_id}:00+00:00",
    }


class Transport:
    def __init__(self, row: dict, events: list[dict]):
        self.row = deepcopy(row)
        self.events = deepcopy(events)
        self.calls: list[str] = []

    def __call__(self, mode: str, payload: dict):
        self.calls.append(mode)
        if mode == "checkpoint_get":
            return {"success": True, "checkpoint": deepcopy(self.row)}
        if mode == "event_list":
            after = payload.get("after_event_id")
            rows = [event for event in self.events if after is None or event["event_id"] > after]
            return {"success": True, "events": deepcopy(rows[: payload.get("limit", 100)])}
        raise AssertionError(f"unexpected mutating mode: {mode}")


def inspector(row, events):
    transport = Transport(row, events)
    return (
        HostedRecoveryInspector(
            queue=HostedQueueClient(transport),
            activity=HostedActivityClient(transport),
            utcnow=lambda: NOW,
        ),
        transport,
    )


class HostedRecoveryInspectorTest(unittest.TestCase):
    def test_completed_verified_is_never_retry_signal(self):
        events = [
            evidence_event(1, "github_observation"),
            evidence_event(2, "github_verification", revision=6, verified=True),
        ]
        recovery, transport = inspector(make_row(status="completed"), events)
        report = recovery.inspect(make_spec())
        self.assertEqual(report.classification, "completed_verified_no_reexecution")
        self.assertTrue(report.verified)
        self.assertFalse(report.reexecution_allowed)
        self.assertFalse(report.may_reconcile_expired_to_blocked)
        self.assertEqual(transport.calls, ["checkpoint_get", "event_list"])

    def test_expired_running_with_observation_requires_reconciliation_not_replay(self):
        row = make_row(status="running", expires="2026-09-26T02:00:00+00:00")
        recovery, transport = inspector(row, [evidence_event(1, "github_observation")])
        report = recovery.inspect(make_spec())
        self.assertEqual(report.classification, "running_expired_with_observation_only")
        self.assertTrue(report.lease_expired)
        self.assertTrue(report.may_reconcile_expired_to_blocked)
        self.assertFalse(report.reexecution_allowed)
        self.assertEqual(transport.calls, ["checkpoint_get", "event_list"])

    def test_expired_running_with_verified_evidence_remains_no_replay(self):
        row = make_row(status="running", expires="2026-09-26T02:00:00+00:00")
        recovery, _ = inspector(row, [
            evidence_event(1, "github_observation"),
            evidence_event(2, "github_verification", verified=True),
        ])
        report = recovery.inspect(make_spec())
        self.assertEqual(report.classification, "running_expired_with_verified_evidence")
        self.assertTrue(report.may_reconcile_expired_to_blocked)
        self.assertFalse(report.reexecution_allowed)

    def test_active_running_is_do_not_touch(self):
        row = make_row(status="running", expires="2026-09-26T03:00:00+00:00")
        recovery, _ = inspector(row, [])
        report = recovery.inspect(make_spec())
        self.assertEqual(report.classification, "running_active_do_not_touch")
        self.assertFalse(report.lease_expired)
        self.assertFalse(report.may_reconcile_expired_to_blocked)
        self.assertFalse(report.reexecution_allowed)

    def test_queued_unstarted_is_only_state_marked_reexecution_allowed(self):
        row = make_row(status="queued", attempt_count=0, generation=0)
        recovery, _ = inspector(row, [])
        report = recovery.inspect(make_spec())
        self.assertEqual(report.classification, "queued_unstarted")
        self.assertTrue(report.reexecution_allowed)
        self.assertIsNone(report.lease_expired)

    def test_blocked_and_failed_never_allow_automatic_replay(self):
        for status in ("blocked", "failed"):
            with self.subTest(status=status):
                recovery, _ = inspector(make_row(status=status), [])
                report = recovery.inspect(make_spec())
                self.assertFalse(report.reexecution_allowed)
                self.assertIn("requires_explicit_reconciliation", report.classification)

    def test_future_generation_evidence_fails_closed(self):
        recovery, _ = inspector(
            make_row(status="completed", generation=2),
            [evidence_event(1, "github_observation", generation=3)],
        )
        with self.assertRaisesRegex(HostedRecoveryIntegrityError, "evidence_from_future_lease_generation"):
            recovery.inspect(make_spec())

    def test_fingerprint_mismatch_fails_closed(self):
        event = evidence_event(1, "github_observation")
        event["payload"]["spec_fingerprint"] = "sha256-v1:" + "0" * 64
        recovery, _ = inspector(make_row(status="completed"), [event])
        with self.assertRaisesRegex(HostedRecoveryIntegrityError, "evidence_spec_fingerprint_mismatch"):
            recovery.inspect(make_spec())


if __name__ == "__main__":
    unittest.main()
