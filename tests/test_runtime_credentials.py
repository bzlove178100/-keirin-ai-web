from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_core.runtime_credentials import (  # noqa: E402
    AUTHORIZATION_ENV,
    AUTHORIZED_INSTANCE_ENV,
    GITHUB_TOKEN_ENV,
    OWNER_BEARER_ENV,
    PROJECT_URL_ENV,
    PUBLISHABLE_KEY_ENV,
    inspect_runtime_credentials,
)

TOKEN = "0123456789abcdef"
NOW = 1_800_000_000


def _b64(value: dict) -> str:
    raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def jwt_with_exp(exp: int) -> str:
    return f"{_b64({'alg': 'none'})}.{_b64({'exp': exp})}.signature-fixture"


def valid_env(*, bearer: str | None = None) -> dict[str, str]:
    return {
        AUTHORIZATION_ENV: "true",
        AUTHORIZED_INSTANCE_ENV: TOKEN,
        PROJECT_URL_ENV: "https://example.supabase.co",
        PUBLISHABLE_KEY_ENV: "publishable-secret-fixture",
        OWNER_BEARER_ENV: bearer or jwt_with_exp(NOW + 3600),
        GITHUB_TOKEN_ENV: "github-secret-fixture",
    }


class RuntimeCredentialPreflightTest(unittest.TestCase):
    def test_manual_ready_report_contains_no_secret_values(self):
        env = valid_env()
        report = inspect_runtime_credentials(env, instance_token=TOKEN, now_epoch=NOW)
        self.assertTrue(report.manual_ready)
        self.assertFalse(report.long_lived_ready)
        self.assertEqual(report.project_host, "example.supabase.co")
        self.assertTrue(report.owner_bearer_expiry_known)
        self.assertEqual(report.owner_bearer_seconds_remaining, 3600)
        self.assertIn("refresh_provider_unconfigured", report.warnings)

        rendered = json.dumps(report.to_safe_dict(), sort_keys=True)
        for secret in (
            env[PUBLISHABLE_KEY_ENV],
            env[OWNER_BEARER_ENV],
            env[GITHUB_TOKEN_ENV],
        ):
            self.assertNotIn(secret, rendered)

    def test_missing_values_fail_closed_by_name_only(self):
        report = inspect_runtime_credentials(
            {
                AUTHORIZATION_ENV: "true",
                AUTHORIZED_INSTANCE_ENV: TOKEN,
                PROJECT_URL_ENV: "https://example.supabase.co",
            },
            instance_token=TOKEN,
            now_epoch=NOW,
        )
        self.assertFalse(report.manual_ready)
        self.assertEqual(
            report.missing,
            (PUBLISHABLE_KEY_ENV, OWNER_BEARER_ENV, GITHUB_TOKEN_ENV),
        )

    def test_exact_instance_authorization_mismatch_fails_before_readiness(self):
        env = valid_env()
        env[AUTHORIZED_INSTANCE_ENV] = "fedcba9876543210"
        report = inspect_runtime_credentials(env, instance_token=TOKEN, now_epoch=NOW)
        self.assertFalse(report.manual_ready)
        self.assertFalse(report.exact_instance_authorized)
        self.assertIn("single_run_instance_authorization_mismatch", report.invalid)

    def test_insecure_or_non_origin_project_url_is_rejected(self):
        for url in (
            "http://example.supabase.co",
            "https://example.supabase.co/rest/v1",
            "https://user:pass@example.supabase.co",
            "https://example.supabase.co?x=1",
        ):
            with self.subTest(url=url):
                env = valid_env()
                env[PROJECT_URL_ENV] = url
                report = inspect_runtime_credentials(env, instance_token=TOKEN, now_epoch=NOW)
                self.assertFalse(report.manual_ready)
                self.assertIsNone(report.project_host)

    def test_expired_or_too_short_known_owner_session_is_rejected(self):
        expired = inspect_runtime_credentials(
            valid_env(bearer=jwt_with_exp(NOW - 1)),
            instance_token=TOKEN,
            now_epoch=NOW,
        )
        self.assertFalse(expired.manual_ready)
        self.assertIn("owner_bearer_expired", expired.invalid)

        short = inspect_runtime_credentials(
            valid_env(bearer=jwt_with_exp(NOW + 299)),
            instance_token=TOKEN,
            now_epoch=NOW,
            minimum_known_ttl_seconds=300,
        )
        self.assertFalse(short.manual_ready)
        self.assertIn("owner_bearer_ttl_below_minimum", short.invalid)

    def test_unknown_expiry_can_support_manual_run_but_not_long_lived_host(self):
        env = valid_env(bearer="opaque-owner-token-fixture")
        report = inspect_runtime_credentials(env, instance_token=TOKEN, now_epoch=NOW)
        self.assertTrue(report.manual_ready)
        self.assertFalse(report.long_lived_ready)
        self.assertFalse(report.owner_bearer_expiry_known)
        self.assertIn("owner_bearer_expiry_unknown", report.warnings)

    def test_long_lived_ready_requires_refresh_provider_and_known_valid_expiry(self):
        report = inspect_runtime_credentials(
            valid_env(),
            instance_token=TOKEN,
            now_epoch=NOW,
            refresh_provider_configured=True,
        )
        self.assertTrue(report.manual_ready)
        self.assertTrue(report.long_lived_ready)
        self.assertNotIn("refresh_provider_unconfigured", report.warnings)


if __name__ == "__main__":
    unittest.main()
