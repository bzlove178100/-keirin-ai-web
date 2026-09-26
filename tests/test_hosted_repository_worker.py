from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from test_hosted_queue_client import FakeQueueTransport
from test_hosted_activity_client import FakeActivityTransport
from test_agent_github_sha_bridge import API, SHA
from agent_core.hosted_readonly_worker import HostedExecutionNotAuthorized
from agent_core.hosted_transport import SupabaseEdgeTransport
from agent_core.model import TaskSpec
from tools.agent_hosted_repository_worker import (
    HostedRepositoryStatusWorker, HostedRunInterrupted, prepare_repository_worker, trusted_status_spec,
)

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)


class Edge:
    def __init__(self, spec=None):
        self.queue = FakeQueueTransport(spec or trusted_status_spec())
        self.activity = FakeActivityTransport()
        self.calls = []
        self.fail_event = None
        self.lost_save = False
        self.corrupt_ack = False

    def request(self, url, headers, body, timeout):
        payload = json.loads(body)
        mode = payload.pop("mode")
        self.calls.append(mode)
        if mode.startswith("queue_"):
            result = self.queue(mode, payload)
            if self.lost_save and mode == "queue_save" and self.queue.row["state"]["attempts"]:
                self.lost_save = False
                raise TimeoutError("response lost after commit")
            return result
        result = self.activity(mode, payload)
        if mode == "event_append" and payload["event_type"] == self.fail_event:
            raise TimeoutError("event committed but acknowledgement lost")
        if self.corrupt_ack and payload.get("event_type") == "github_observation":
            result["event"]["payload"]["evidence"]["observed_sha"] = "b" * 40
        return result

    def transport(self):
        return SupabaseEdgeTransport(project_url="https://example.supabase.co",
            publishable_key="publishable-fixture-value", bearer_token="owner-fixture-value", requester=self.request)


class HostedRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.edge = Edge()
        self.api = API()
        self.ticks = 0.0
        self.worker = self.make_worker()

    def make_worker(self, authorized=True):
        return HostedRepositoryStatusWorker(transport=self.edge.transport(), github_token="github-fixture-value",
            execution_authorized=authorized, api_get=self.api, clock=lambda: self.ticks, utcnow=lambda: NOW)

    def run_worker(self):
        return self.worker.run_next(worker_id="worker-1")

    def events(self, kind):
        return [r for rows in self.edge.activity.rows.values() for r in rows if r["event_type"] == kind]

    def test_factory_is_closed_and_zero_io(self):
        worker = prepare_repository_worker(project_url="https://example.supabase.co",
            publishable_key="publishable-fixture-value", owner_bearer_token="owner-fixture-value",
            github_token="github-fixture-value", requester=self.edge.request, api_get=self.api)
        with self.assertRaises(HostedExecutionNotAuthorized):
            worker.run_next(worker_id="worker-1")
        self.assertEqual(self.edge.calls, [])
        self.assertEqual(self.api.calls, [])

    def test_truthy_values_do_not_authorize(self):
        for value in ("true", "false", 1, None):
            with self.subTest(value=value), self.assertRaises(HostedExecutionNotAuthorized):
                self.make_worker(value).run_next(worker_id="worker-1")
        self.assertEqual(self.edge.calls, [])

    def test_full_composition_persists_evidence_then_completes(self):
        result = self.run_worker()
        self.assertEqual(result.outcome.status, "completed")
        self.assertIsNone(self.edge.queue.row["lease_owner"])
        self.assertEqual(self.edge.calls.count("queue_claim"), 1)
        self.assertEqual(len(self.events("github_observation")), 1)
        self.assertEqual(len(self.events("github_verification")), 1)
        observation = self.events("github_observation")[0]
        verified = self.events("github_verification")[0]
        self.assertLess(observation["event_id"], verified["event_id"])
        self.assertEqual(observation["payload"]["evidence"]["observed_sha"], SHA)
        self.assertTrue(verified["payload"]["evidence"]["verified"])
        self.assertEqual(observation["payload"]["spec_fingerprint"], trusted_status_spec().fingerprint())
        encoded = json.dumps([self.edge.queue.row, self.edge.activity.rows])
        for credential in ("owner-fixture-value", "publishable-fixture-value", "github-fixture-value"):
            self.assertNotIn(credential, encoded)
        self.assertIsNone(self.worker._bridge.guard)

    def test_saved_observation_survives_worker_replacement(self):
        self.edge.fail_event = "github_observation"
        with self.assertRaises(HostedRunInterrupted):
            self.run_worker()
        fresh = self.make_worker(False)
        events = fresh.activity.list(task_id=trusted_status_spec().task_id)
        observations = [e for e in events if e.event_type == "github_observation"]
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0].payload["evidence"]["observed_sha"], SHA)
        with self.assertRaises(HostedExecutionNotAuthorized):
            fresh.run_next(worker_id="worker-2")

    def test_same_worker_cannot_run_concurrently(self):
        self.worker._run_lock.acquire()
        try:
            with self.assertRaises(HostedRunInterrupted):
                self.run_worker()
            self.assertEqual(self.edge.calls, [])
        finally:
            self.worker._run_lock.release()

    def test_changed_task_is_blocked_before_provider(self):
        payload = trusted_status_spec().to_dict()
        payload["goal"] = "changed even though actions and repository match"
        self.edge = Edge(TaskSpec.from_dict(payload))
        self.worker = self.make_worker()
        result = self.run_worker()
        self.assertEqual(result.blocked_reason, "hosted_task_outside_trusted_scope")
        self.assertEqual(self.api.calls, [])
        self.assertEqual(self.edge.queue.row["status"], "blocked")

    def test_previous_attempt_is_not_replayed(self):
        self.edge.queue.row["state"]["attempts"] = {"read-current-state": 1}
        result = self.run_worker()
        self.assertEqual(result.blocked_reason, "hosted_prior_attempt_requires_reconciliation")
        self.assertEqual(self.api.calls, [])

    def test_lost_observation_ack_stops_without_retry(self):
        self.edge.fail_event = "github_observation"
        with self.assertRaises(HostedRunInterrupted):
            self.run_worker()
        self.assertEqual(len(self.events("github_observation")), 1)
        self.assertEqual(len(self.events("github_verification")), 0)
        self.assertFalse(any("/actions/runs" in p for p in self.api.calls))
        self.assertEqual(self.edge.queue.row["status"], "running")
        self.assertIsNone(self.worker._bridge.guard)

    def test_response_lost_after_fenced_save_is_not_reissued(self):
        original = self.api.__call__
        def api(path):
            self.edge.lost_save = True
            return original(path)
        self.worker._bridge._api_get_override = api
        with self.assertRaises(HostedRunInterrupted):
            self.run_worker()
        self.assertEqual(len(self.api.calls), 1)
        self.assertEqual(self.edge.calls[-1], "queue_save")
        self.assertEqual(len(self.events("github_observation")), 0)

    def test_expired_fence_stops_before_next_provider_request(self):
        def api(path):
            self.edge.queue.expired = True
            return self.api(path)
        self.worker._bridge._api_get_override = api
        with self.assertRaises(HostedRunInterrupted):
            self.run_worker()
        self.assertEqual(len(self.api.calls), 1)

    def test_short_lease_and_elapsed_deadline_stop(self):
        self.worker._utcnow = lambda: datetime(2026, 9, 25, 12, 3, 40, tzinfo=timezone.utc)
        with self.assertRaises(HostedRunInterrupted):
            self.run_worker()
        self.assertEqual(self.api.calls, [])
        self.setUp()
        def api(path):
            result = self.api(path)
            self.ticks = 181
            return result
        self.worker._bridge._api_get_override = api
        with self.assertRaises(HostedRunInterrupted):
            self.run_worker()
        self.assertEqual(len(self.api.calls), 1)

    def test_negative_ci_evidence_is_saved_but_never_completed(self):
        self.api.runs[0]["conclusion"] = "failure"
        result = self.run_worker()
        self.assertEqual(result.outcome.status, "blocked")
        self.assertFalse(self.events("github_verification")[0]["payload"]["evidence"]["verified"])

    def test_mismatched_ack_stops(self):
        self.edge.corrupt_ack = True
        with self.assertRaises(HostedRunInterrupted):
            self.run_worker()
        self.assertFalse(any("/actions/runs" in p for p in self.api.calls))


if __name__ == "__main__":
    unittest.main()
