from __future__ import annotations

import json
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_core.hosted_transport import SupabaseEdgeTransport  # noqa: E402


class SupabaseEdgeTransportTest(unittest.TestCase):
    def test_credentials_stay_in_headers_and_repr_is_redacted(self):
        seen = {}

        def requester(url, headers, body, timeout):
            seen.update({"url": url, "headers": dict(headers), "body": body, "timeout": timeout})
            return {"success": True, "mode": "event_list", "events": []}

        transport = SupabaseEdgeTransport(
            project_url="https://example.supabase.co",
            publishable_key="publishable-test-value",
            bearer_token="owner-jwt-test-value",
            requester=requester,
        )
        response = transport("event_list", {"task_id": "task-1", "limit": 20})
        self.assertTrue(response["success"])
        self.assertEqual(seen["url"], "https://example.supabase.co/functions/v1/agent-runtime-dev")
        self.assertEqual(seen["headers"]["apikey"], "publishable-test-value")
        self.assertEqual(seen["headers"]["Authorization"], "Bearer owner-jwt-test-value")
        payload = json.loads(seen["body"].decode("utf-8"))
        self.assertEqual(payload, {"mode": "event_list", "task_id": "task-1", "limit": 20})
        encoded = seen["body"].decode("utf-8")
        self.assertNotIn("publishable-test-value", encoded)
        self.assertNotIn("owner-jwt-test-value", encoded)
        rendered = repr(transport)
        self.assertNotIn("publishable-test-value", rendered)
        self.assertNotIn("owner-jwt-test-value", rendered)
        self.assertIn("<redacted>", rendered)

    def test_payload_cannot_override_mode(self):
        transport = SupabaseEdgeTransport(
            project_url="https://example.supabase.co",
            publishable_key="pk",
            bearer_token="jwt",
            requester=lambda *args: {"success": True},
        )
        with self.assertRaisesRegex(ValueError, "payload_must_not_override_mode"):
            transport("queue_claim", {"mode": "checkpoint_list"})

    def test_configuration_is_fail_closed(self):
        cases = (
            ({"project_url": "http://example.supabase.co", "publishable_key": "pk", "bearer_token": "jwt"}, "https_project_url_required"),
            ({"project_url": "https://example.supabase.co/path", "publishable_key": "pk", "bearer_token": "jwt"}, "project_url_must_not_include_path"),
            ({"project_url": "https://example.supabase.co", "publishable_key": "", "bearer_token": "jwt"}, "publishable_key_required"),
            ({"project_url": "https://example.supabase.co", "publishable_key": "pk", "bearer_token": ""}, "bearer_token_required"),
            ({"project_url": "https://example.supabase.co", "publishable_key": "pk", "bearer_token": "jwt", "function_slug": "../escape"}, "invalid_function_slug"),
        )
        for kwargs, error in cases:
            with self.subTest(error=error):
                with self.assertRaisesRegex(ValueError, error):
                    SupabaseEdgeTransport(**kwargs)

    def test_response_is_detached_from_requester_object(self):
        remote = {"success": True, "checkpoint": {"state": {"status": "running"}}}
        transport = SupabaseEdgeTransport(
            project_url="https://example.supabase.co",
            publishable_key="pk",
            bearer_token="jwt",
            requester=lambda *args: remote,
        )
        response = transport("checkpoint_get", {"task_id": "task-1"})
        response["checkpoint"]["state"]["status"] = "corrupted-locally"
        self.assertEqual(remote["checkpoint"]["state"]["status"], "running")


if __name__ == "__main__":
    unittest.main()
