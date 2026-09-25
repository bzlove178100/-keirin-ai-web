from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_core.hosted_activity import (  # noqa: E402
    HostedActivityClient,
    HostedActivityError,
    HostedActivityIntegrityError,
)


class FakeActivityTransport:
    def __init__(self):
        self.rows: dict[str, list[dict]] = {}
        self.calls: list[tuple[str, dict]] = []
        self.next_id = 1

    def __call__(self, mode: str, payload: dict):
        payload = deepcopy(payload)
        self.calls.append((mode, payload))
        task_id = payload["task_id"]
        if mode == "event_append":
            row = {
                "event_id": self.next_id,
                "task_id": task_id,
                "event_type": payload["event_type"],
                "step_id": payload.get("step_id"),
                "payload": deepcopy(payload["payload"]),
                "created_at": f"2026-09-25T11:30:{self.next_id:02d}+00:00",
            }
            self.next_id += 1
            self.rows.setdefault(task_id, []).append(row)
            return {"success": True, "event": deepcopy(row), "event_persisted": True}
        if mode == "event_list":
            rows = self.rows.get(task_id, [])
            after = payload.get("after_event_id")
            if after is not None:
                rows = [row for row in rows if row["event_id"] > after]
            return {"success": True, "events": deepcopy(rows[: payload["limit"]])}
        raise AssertionError(f"unexpected mode: {mode}")


class HostedActivityClientTest(unittest.TestCase):
    def test_append_and_cursor_list_round_trip(self):
        transport = FakeActivityTransport()
        client = HostedActivityClient(transport)

        first = client.append(
            task_id="task-1",
            event_type="task_started",
            payload={"message": "start"},
        )
        second = client.append(
            task_id="task-1",
            event_type="step_completed",
            step_id="step-1",
            payload={"attempt": 1, "verified": True},
        )
        self.assertEqual(first.event_id, 1)
        self.assertEqual(second.event_id, 2)
        self.assertEqual(second.step_id, "step-1")

        all_events = client.list(task_id="task-1")
        self.assertEqual([event.event_id for event in all_events], [1, 2])
        after_first = client.list(task_id="task-1", after_event_id=1)
        self.assertEqual([event.event_id for event in after_first], [2])

    def test_secret_shaped_payload_is_rejected_before_transport(self):
        transport = FakeActivityTransport()
        client = HostedActivityClient(transport)
        with self.assertRaisesRegex(ValueError, "event_payload_contains_forbidden_secret"):
            client.append(
                task_id="task-1",
                event_type="provider_result",
                payload={"nested": {"api_key": "must-not-persist"}},
            )
        self.assertEqual(transport.calls, [])

    def test_input_bounds_fail_closed(self):
        client = HostedActivityClient(FakeActivityTransport())
        with self.assertRaisesRegex(ValueError, "invalid_task_id"):
            client.append(task_id="../escape", event_type="x")
        with self.assertRaisesRegex(ValueError, "invalid_event_type"):
            client.append(task_id="task-1", event_type="  ")
        with self.assertRaisesRegex(ValueError, "invalid_step_id"):
            client.append(task_id="task-1", event_type="x", step_id="")
        with self.assertRaisesRegex(ValueError, "activity_list_limit_out_of_range"):
            client.list(task_id="task-1", limit=201)
        with self.assertRaisesRegex(ValueError, "invalid_after_event_id"):
            client.list(task_id="task-1", after_event_id=-1)

    def test_remote_task_mismatch_and_secret_payload_are_rejected(self):
        transport = FakeActivityTransport()
        client = HostedActivityClient(transport)
        client.append(task_id="task-1", event_type="task_started")
        transport.rows["task-1"][0]["task_id"] = "task-2"
        with self.assertRaisesRegex(HostedActivityIntegrityError, "activity_task_id_mismatch"):
            client.list(task_id="task-1")

        transport.rows["task-1"][0]["task_id"] = "task-1"
        transport.rows["task-1"][0]["payload"] = {"password": "bad"}
        with self.assertRaisesRegex(HostedActivityIntegrityError, "activity_payload_contains_forbidden_secret"):
            client.list(task_id="task-1")

    def test_remote_order_and_cursor_violations_are_rejected(self):
        transport = FakeActivityTransport()
        client = HostedActivityClient(transport)
        client.append(task_id="task-1", event_type="one")
        client.append(task_id="task-1", event_type="two")
        transport.rows["task-1"].reverse()
        with self.assertRaisesRegex(HostedActivityIntegrityError, "activity_event_order_or_duplicate_error"):
            client.list(task_id="task-1")

        transport.rows["task-1"].sort(key=lambda row: row["event_id"])
        original = transport.__call__

        def bad_cursor(mode, payload):
            if mode == "event_list" and payload.get("after_event_id") is not None:
                response = original(mode, {**payload, "after_event_id": None})
                return response
            return original(mode, payload)

        with self.assertRaisesRegex(HostedActivityIntegrityError, "activity_event_cursor_violation"):
            HostedActivityClient(bad_cursor).list(task_id="task-1", after_event_id=1)

    def test_remote_failure_is_not_treated_as_success(self):
        def fail(mode, payload):
            return {"success": False, "error": "owner access required"}

        client = HostedActivityClient(fail)
        with self.assertRaisesRegex(HostedActivityError, "owner access required"):
            client.append(task_id="task-1", event_type="task_started")


if __name__ == "__main__":
    unittest.main()
