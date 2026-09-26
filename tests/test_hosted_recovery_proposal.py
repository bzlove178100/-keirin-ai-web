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

NOW = datetime(2026, 9, 26, 3, 0, tzinfo=timezone.utc)


def spec() -> TaskSpec:
    return TaskSpec(
        task_id="proposal-test",
        title="Recovery proposal test",
        goal="Propose without mutating",
        allowed_actions=("github.read_main", "github.verify_ci"),
        steps=(StepSpec("read", "github.read_main", verify_action="github.verify_ci"),),
    )


def row(status: str, *, revision=8, generation=3, attempts=1, expires=None):
    s = spec()
    state = TaskState(
        task_id=s.task_id,
        status="pending" if status == "queued" else status,
        spec_fingerprint=s.fingerprint(),
    )
    return {
        "task_id": s.task_id,
        "schema_version": "agent-task-v1",
        "status": status,
        "idempotency_key": "proposal-key",
        "spec": s.to_dict(),
        "state": state.to_dict(),
        "revision": revision,
        "spec_fingerprint": s.fingerprint(),
        "not_before": "2026-09-26T01:00:00+00:00",
        "attempt_count": attempts,
        "max_attempts": 2,
        "lease_owner": "worker-1" if status == "running" else None,
        "lease_generation": generation,
        "lease_expires_at": expires if status == "running" else None,
        "created_at": "2026-09-26T01:00:00+00:00",
        "updated_at": "2026-09-26T02:00:00+00:00",
    }


def event(event_id, event_type, *, generation=3, revision=6, verified=None):
    s = spec()
    evidence = {"observed_sha": "a" * 40}
    if verified is not None:
        evidence["verified"] = verified
    return {
        "event_id": event_id,
        "task_id": s.task_id,
        "event_type": event_type,
        "step_id": "read",
        "payload": {
            "spec_fingerprint": s.fingerprint(),
            "lease_generation": generation,
            "revision": revision,
            "evidence": evidence,
        },
        "created_at": "2026-09-26T02:00:00+00:00",
    }


class Transport:
    def __init__(self, rows, events=()):
        self.rows = [deepcopy(value) for value in rows]
        self.events = [deepcopy(value) for value in events]
        self.calls = []
        self.get_index = 0

    def __call__(self, mode, payload):
        self.calls.append(mode)
        if mode == "checkpoint_get":
            index = min(self.get_index, len(self.rows) - 1)
            self.get_index += 1
            return {"success": True, "checkpoint": deepcopy(self.rows[index])}
        if mode == "event_list":
            after = payload.get("after_event_id")
            items = [item for item in self.events if after is None or item["event_id"] > after]
            return {"success": True, "events": deepcopy(items[: payload.get("limit", 200)])}
        raise AssertionError(f"proposal must not mutate: {mode}")


def recovery(rows, events=()):
    transport = Transport(rows, events)
    inspector = HostedRecoveryInspector(
        queue=HostedQueueClient(transport),
        activity=HostedActivityClient(transport),
        utcnow=lambda: NOW,
    )
    return inspector, transport


class HostedRecoveryProposalTest(unittest.TestCase):
    def test_expired_running_proposes_exact_reconcile_without_mutation(self):
        r = row("running", expires="2026-09-26T02:30:00+00:00")
        inspector, transport = recovery([r, r], [event(1, "github_observation")])
        proposal = inspector.propose(spec())
        self.assertEqual(proposal.proposed_action, "reconcile_expired_to_blocked")
        self.assertEqual(proposal.expected_revision, 8)
        self.assertEqual(proposal.lease_generation, 3)
        self.assertFalse(proposal.automatic_execution_allowed)
        self.assertEqual(proposal.blocked_state["status"], "blocked")
        self.assertEqual(proposal.blocked_state["blocked_reason"], "expired_lease_requires_reconciliation")
        self.assertEqual(proposal.blocked_state["spec_fingerprint"], spec().fingerprint())
        self.assertEqual(transport.calls, ["checkpoint_get", "event_list", "checkpoint_get", "event_list"])
        self.assertNotIn("queue_reconcile_expired", transport.calls)

    def test_snapshot_change_between_reads_fails_closed(self):
        first = row("running", revision=8, expires="2026-09-26T02:30:00+00:00")
        second = row("completed", revision=9, expires=None)
        inspector, _ = recovery([first, second], [event(1, "github_observation")])
        with self.assertRaisesRegex(HostedRecoveryIntegrityError, "recovery_snapshot_changed"):
            inspector.propose(spec())

    def test_completed_is_no_reexecution_even_with_verified_evidence(self):
        r = row("completed")
        inspector, _ = recovery([r, r], [
            event(1, "github_observation"),
            event(2, "github_verification", revision=7, verified=True),
        ])
        proposal = inspector.propose(spec())
        self.assertEqual(proposal.proposed_action, "no_reexecution")
        self.assertFalse(proposal.automatic_execution_allowed)
        self.assertIsNone(proposal.blocked_state)

    def test_active_running_is_do_not_touch(self):
        r = row("running", expires="2026-09-26T04:00:00+00:00")
        inspector, _ = recovery([r, r])
        proposal = inspector.propose(spec())
        self.assertEqual(proposal.proposed_action, "do_not_touch")
        self.assertFalse(proposal.automatic_execution_allowed)

    def test_unstarted_queue_only_proposes_first_execution_eligibility(self):
        r = row("queued", attempts=0, generation=0)
        inspector, _ = recovery([r, r])
        proposal = inspector.propose(spec())
        self.assertEqual(proposal.proposed_action, "eligible_for_first_execution")
        self.assertFalse(proposal.automatic_execution_allowed)
        self.assertIsNone(proposal.blocked_state)

    def test_blocked_requires_manual_reconciliation(self):
        r = row("blocked")
        inspector, _ = recovery([r, r])
        proposal = inspector.propose(spec())
        self.assertEqual(proposal.proposed_action, "manual_reconciliation_required")
        self.assertFalse(proposal.automatic_execution_allowed)


if __name__ == "__main__":
    unittest.main()
