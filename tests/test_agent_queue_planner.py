from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_core.queue_planner import QueueEntry, plan_queue

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def entry(task_id="task-1", **overrides):
    return replace(QueueEntry("owner-a", task_id, task_id, 3, "queued", NOW, NOW),
                   **overrides)


class QueuePlannerTest(unittest.TestCase):
    def plan(self, rows, **kwargs):
        return plan_queue(rows, owner_id="owner-a", now=NOW, **kwargs)

    def test_fifo_stable_order_and_no_mutation_or_execution(self):
        rows = [entry("b"), entry("a")]
        before = list(rows)
        plan = self.plan(rows)
        self.assertEqual(rows, before)
        self.assertEqual([d.task_id for d in plan.decisions], ["a", "b"])
        self.assertEqual([d.disposition for d in plan.decisions], ["propose_claim", "wait"])
        self.assertEqual(plan.decisions[0].expected_revision, 3)
        self.assertFalse(plan.execution_enabled)
        self.assertFalse(plan.persistence_enabled)
        self.assertEqual(plan, self.plan(reversed(rows)))

    def test_terminal_tasks_never_repeat(self):
        for status in ("completed", "blocked", "failed"):
            with self.subTest(status=status):
                self.assertEqual(self.plan([entry(status=status)]).decisions[0].disposition, "skip")

    def test_running_lease_never_reclaims_and_occupies_capacity(self):
        for expiry in (None, NOW, NOW - timedelta(seconds=1), NOW + timedelta(seconds=1)):
            with self.subTest(expiry=expiry):
                result = self.plan([entry("a", status="running", lease_expires_at=expiry), entry("b")])
                self.assertEqual(result.decisions[0].disposition,
                                 "wait" if expiry and expiry > NOW else "reconcile")
                self.assertEqual(result.decisions[1].reason, "capacity_exhausted")

    def test_future_and_exhausted_tasks_do_not_starve_due_task(self):
        result = self.plan([entry("a", not_before=NOW + timedelta(seconds=1)),
                            entry("b", attempts=1), entry("c")])
        self.assertEqual([d.disposition for d in result.decisions], ["wait", "reconcile", "propose_claim"])

    def test_owner_isolation_and_duplicate_rejection(self):
        for rows in ([entry(owner_id="other")], [entry(), entry()],
                     [entry(), entry("other", idempotency_key="task-1")]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.plan(rows)

    def test_invalid_input_fails_closed(self):
        for changes in ({"status": "pending"}, {"revision": True}, {"attempts": -1},
                        {"max_attempts": 0}, {"attempts": 2}, {"created_at": NOW.replace(tzinfo=None)},
                        {"lease_expires_at": NOW}, {"task_id": " "}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.plan([entry(**changes)])
        for capacity in (0, -1, True, 1.5):
            with self.subTest(capacity=capacity), self.assertRaises(ValueError):
                self.plan([], capacity=capacity)

    def test_timezone_equivalence_and_capacity(self):
        jst = timezone(timedelta(hours=9))
        rows = [entry("a", not_before=NOW.astimezone(jst)), entry("b"), entry("c")]
        result = self.plan(rows, capacity=2)
        self.assertEqual(sum(d.disposition == "propose_claim" for d in result.decisions), 2)
        with self.assertRaises(ValueError):
            plan_queue([], owner_id="owner-a", now=NOW.replace(tzinfo=None))


if __name__ == "__main__":
    unittest.main()
