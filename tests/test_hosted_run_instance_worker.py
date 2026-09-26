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

from agent_core.hosted_readonly_worker import HostedExecutionNotAuthorized  # noqa: E402
from agent_core.hosted_transport import SupabaseEdgeTransport  # noqa: E402
from agent_core.model import TaskSpec  # noqa: E402
from agent_core.trusted_run_instance import build_trusted_status_run_spec  # noqa: E402
from test_agent_github_sha_bridge import API  # noqa: E402
from test_hosted_activity_client import FakeActivityTransport  # noqa: E402
from test_hosted_queue_client import FakeQueueTransport  # noqa: E402
from tools.agent_hosted_repository_worker import (  # noqa: E402
    HostedRepositoryStatusWorker,
    prepare_repository_worker,
    trusted_status_spec,
)

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)
TOKEN = "0123456789abcdef"


class ExactEdge:
    def __init__(self, stored_spec):
        self.queue = FakeQueueTransport(stored_spec)
        self.activity = FakeActivityTransport()
        self.calls = []

    def request(self, _url, _headers, body, _timeout):
        payload = json.loads(body)
        mode = payload.pop("mode")
        self.calls.append(mode)
        if mode == "queue_claim_task":
            if payload.get("task_id") != self.queue.row["task_id"]:
                return {"success": True, "claimed": False, "lease": None}
            return self.queue(
                "queue_claim",
                {"worker_id": payload["worker_id"], "lease_seconds": payload["lease_seconds"]},
            )
        if mode.startswith("queue_"):
            return self.queue(mode, payload)
        return self.activity(mode, payload)

    def transport(self):
        return SupabaseEdgeTransport(
            project_url="https://example.supabase.co",
            publishable_key="publishable-fixture-value",
            bearer_token="owner-fixture-value",
            requester=self.request,
        )


class HostedRunInstanceWorkerTest(unittest.TestCase):
    def make_worker(self, spec, edge, *, authorized=True, api=None):
        return HostedRepositoryStatusWorker(
            transport=edge.transport(),
            github_token="github-fixture-value",
            execution_authorized=authorized,
            api_get=api or API(),
            utcnow=lambda: NOW,
            target_spec=spec,
        )

    def test_exact_trusted_instance_completes_without_fifo_claim(self):
        spec = build_trusted_status_run_spec(TOKEN, repo_root=ROOT)
        edge = ExactEdge(spec)
        api = API()
        worker = self.make_worker(spec, edge, api=api)

        result = worker.run_next(worker_id="worker-instance")

        self.assertEqual(result.outcome.status, "completed")
        self.assertEqual(worker.claim_mode, "exact_trusted_run_instance")
        self.assertEqual(worker.expected_task_id, spec.task_id)
        self.assertEqual(edge.calls.count("queue_claim_task"), 1)
        self.assertEqual(edge.calls.count("queue_claim"), 0)
        self.assertEqual(edge.queue.row["status"], "completed")
        self.assertIsNone(edge.queue.row["lease_owner"])
        observations = [
            row for rows in edge.activity.rows.values() for row in rows
            if row["event_type"] == "github_observation"
        ]
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0]["payload"]["spec_fingerprint"], spec.fingerprint())

    def test_unrelated_fifo_row_is_not_claimed_or_blocked(self):
        target = build_trusted_status_run_spec(TOKEN, repo_root=ROOT)
        unrelated = build_trusted_status_run_spec("1" * 16, repo_root=ROOT)
        edge = ExactEdge(unrelated)
        api = API()
        worker = self.make_worker(target, edge, api=api)

        result = worker.run_next(worker_id="worker-instance")

        self.assertFalse(result.claimed)
        self.assertEqual(edge.queue.row["status"], "queued")
        self.assertEqual(edge.queue.row["attempt_count"], 0)
        self.assertEqual(api.calls, [])
        self.assertEqual(edge.calls, ["queue_claim_task"])

    def test_instance_mode_remains_closed_before_any_io(self):
        spec = build_trusted_status_run_spec(TOKEN, repo_root=ROOT)
        edge = ExactEdge(spec)
        api = API()
        worker = prepare_repository_worker(
            project_url="https://example.supabase.co",
            publishable_key="publishable-fixture-value",
            owner_bearer_token="owner-fixture-value",
            github_token="github-fixture-value",
            requester=edge.request,
            api_get=api,
            target_spec=spec,
        )
        with self.assertRaises(HostedExecutionNotAuthorized):
            worker.run_next(worker_id="worker-instance")
        self.assertEqual(edge.calls, [])
        self.assertEqual(api.calls, [])

    def test_template_task_cannot_be_supplied_as_fresh_target_instance(self):
        edge = ExactEdge(trusted_status_spec())
        with self.assertRaisesRegex(ValueError, "trusted_run_instance_id_required"):
            self.make_worker(trusted_status_spec(), edge)
        self.assertEqual(edge.calls, [])

    def test_scope_modified_instance_is_rejected_before_io(self):
        valid = build_trusted_status_run_spec(TOKEN, repo_root=ROOT)
        payload = deepcopy(valid.to_dict())
        payload["goal"] = "broadened goal"
        changed = TaskSpec.from_dict(payload)
        edge = ExactEdge(changed)
        with self.assertRaisesRegex(ValueError, "trusted_run_instance_scope_mismatch"):
            self.make_worker(changed, edge)
        self.assertEqual(edge.calls, [])


if __name__ == "__main__":
    unittest.main()
