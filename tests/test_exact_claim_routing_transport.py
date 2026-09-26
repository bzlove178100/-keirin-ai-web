from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_core.hosted_transport import ExactClaimRoutingTransport, SupabaseEdgeTransport  # noqa: E402


class Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append({
            "url": url,
            "headers": dict(headers),
            "body": json.loads(body),
            "timeout": timeout,
        })
        return {"success": True, "claimed": False, "lease": None}


class ExactClaimRoutingTransportTest(unittest.TestCase):
    def make_router(self, recorder):
        common = {
            "project_url": "https://example.supabase.co",
            "publishable_key": "publishable-fixture-value",
            "bearer_token": "owner-fixture-value",
            "requester": recorder,
        }
        return ExactClaimRoutingTransport(
            default_transport=SupabaseEdgeTransport(function_slug="agent-runtime-dev", **common),
            exact_claim_transport=SupabaseEdgeTransport(function_slug="agent-exact-claim-dev", **common),
        )

    def test_only_exact_claim_uses_narrow_edge_function(self):
        recorder = Recorder()
        router = self.make_router(recorder)

        router("queue_claim_task", {
            "task_id": "keirin-readonly-status-check.0123456789abcdef",
            "worker_id": "worker-a",
            "lease_seconds": 120,
        })
        router("queue_save", {"task_id": "x"})

        self.assertTrue(recorder.calls[0]["url"].endswith("/functions/v1/agent-exact-claim-dev"))
        self.assertTrue(recorder.calls[1]["url"].endswith("/functions/v1/agent-runtime-dev"))
        self.assertEqual(recorder.calls[0]["body"]["mode"], "queue_claim_task")
        self.assertEqual(recorder.calls[1]["body"]["mode"], "queue_save")

    def test_router_repr_never_contains_runtime_credentials(self):
        recorder = Recorder()
        text = repr(self.make_router(recorder))
        self.assertNotIn("publishable-fixture-value", text)
        self.assertNotIn("owner-fixture-value", text)

    def test_same_function_for_both_routes_is_rejected(self):
        recorder = Recorder()
        common = {
            "project_url": "https://example.supabase.co",
            "publishable_key": "publishable-fixture-value",
            "bearer_token": "owner-fixture-value",
            "function_slug": "agent-runtime-dev",
            "requester": recorder,
        }
        with self.assertRaisesRegex(ValueError, "exact_claim_transport_must_be_separate"):
            ExactClaimRoutingTransport(
                default_transport=SupabaseEdgeTransport(**common),
                exact_claim_transport=SupabaseEdgeTransport(**common),
            )


if __name__ == "__main__":
    unittest.main()
