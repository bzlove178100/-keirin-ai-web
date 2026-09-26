from __future__ import annotations

import io
import json
import traceback
import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_core.hosted_transport import HostedTransportError, SupabaseEdgeTransport, _RejectRedirects  # noqa: E402


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

    def make_transport(self, **kwargs):
        return SupabaseEdgeTransport(
            project_url="https://example.supabase.co",
            publishable_key="publishable-test-value",
            bearer_token="owner-jwt-test-value",
            **kwargs,
        )

    def test_invalid_timeout_and_url_credentials(self):
        for timeout in (True, 0, -1, float("nan"), float("inf")):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                self.make_transport(timeout_seconds=timeout)
        for url in ("https://owner:secret@example.supabase.co", "https://example.supabase.co\n"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                SupabaseEdgeTransport(project_url=url, publishable_key="pk", bearer_token="jwt")
        with self.assertRaisesRegex(ValueError, "invalid_credential_header"):
            SupabaseEdgeTransport(project_url="https://example.supabase.co", publishable_key="pk", bearer_token="jwt\r\nx: y")

    def test_http_failure_cannot_override_failure_or_status(self):
        opener = Mock()
        opener.open.side_effect = HTTPError(
            "https://example.supabase.co", 409, "Conflict", {},
            io.BytesIO(b'{"success":true,"backend_status":200,"backend_code":"40001","error":"queue_conflict"}'),
        )
        with patch("agent_core.hosted_transport.build_opener", return_value=opener):
            result = self.make_transport()("queue_save", {})
        self.assertIs(result["success"], False)
        self.assertEqual(result["backend_status"], 409)
        self.assertEqual(result["backend_code"], "40001")
        opener.open.assert_called_once()

    def test_redirects_are_not_followed(self):
        request = Request("https://example.supabase.co", data=b"{}", headers={"Authorization": "Bearer secret"})
        opener = build_opener(_RejectRedirects())
        for code in (301, 302, 303, 307, 308):
            with self.subTest(code=code), self.assertRaises(HTTPError):
                opener.error(
                    "http", request, io.BytesIO(b""), code, "redirect",
                    {"location": "https://other.example/collect"},
                )

    def test_credential_echo_in_payload_or_response_is_rejected(self):
        requester = Mock(return_value={"error": "echo owner-jwt-test-value"})
        transport = self.make_transport(requester=requester)
        with self.assertRaisesRegex(ValueError, "credentials_forbidden_in_payload"):
            transport("event_append", {"event": {"note": "owner-jwt-test-value"}})
        requester.assert_not_called()
        with self.assertRaisesRegex(HostedTransportError, "credentials_forbidden_in_response"):
            transport("event_list", {})

    def test_requester_error_is_sanitized_and_not_retried(self):
        requester = Mock(side_effect=URLError("Authorization: owner-jwt-test-value"))
        try:
            self.make_transport(requester=requester)("queue_save", {})
        except HostedTransportError:
            rendered = traceback.format_exc()
        else:
            self.fail("error expected")
        self.assertNotIn("owner-jwt-test-value", rendered)
        requester.assert_called_once()

    def test_malformed_responses_fail_closed(self):
        for raw in (b"not json", b"[]", b"\xff"):
            response = Mock()
            response.read.return_value = raw
            opener = Mock()
            opener.open.return_value.__enter__ = Mock(return_value=response)
            opener.open.return_value.__exit__ = Mock(return_value=False)
            with self.subTest(raw=raw), patch("agent_core.hosted_transport.build_opener", return_value=opener):
                with self.assertRaises(HostedTransportError):
                    self.make_transport()("event_list", {})

    def test_non_json_http_error_does_not_expose_raw_body(self):
        opener = Mock()
        opener.open.side_effect = HTTPError(
            "https://example.supabase.co", 502, "Bad Gateway", {},
            io.BytesIO(b"internal proxy detail owner-jwt-test-value"),
        )
        with patch("agent_core.hosted_transport.build_opener", return_value=opener):
            result = self.make_transport()("queue_save", {})
        self.assertEqual(result, {"success": False, "error": "HTTP 502", "backend_status": 502})


if __name__ == "__main__":
    unittest.main()
