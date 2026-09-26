from __future__ import annotations

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/agent-hosted-one-shot.yml"


class ManualHostedOneShotWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_manual_dispatch_is_the_only_trigger(self):
        text = self.text
        self.assertIn("\non:\n  workflow_dispatch:\n", text)
        for forbidden in (
            "\n  push:",
            "\n  pull_request:",
            "\n  schedule:",
            "\n  repository_dispatch:",
            "cron:",
        ):
            self.assertNotIn(forbidden, text)

    def test_explicit_authorization_and_fresh_identity_inputs_are_required(self):
        text = self.text
        self.assertIn("authorization_phrase:", text)
        self.assertIn("instance_token:", text)
        self.assertIn("worker_id:", text)
        self.assertIn('test "$AUTHORIZATION_PHRASE" = "AUTHORIZE_ONE_READONLY_RUN"', text)
        self.assertRegex(text, r"INSTANCE_TOKEN.*\\?n?.*\^\[0-9a-f\]\{16,32\}\\?\$|\^\[0-9a-f\]\{16,32\}\$" )

    def test_permissions_are_read_only_and_checkout_does_not_persist_credentials(self):
        text = self.text
        self.assertIn("permissions:\n  contents: read\n  actions: read", text)
        self.assertNotRegex(text, re.compile(r"permissions:[\s\S]{0,160}\bwrite\b"))
        self.assertIn("persist-credentials: false", text)

    def test_runtime_secrets_are_environment_only_and_fail_closed(self):
        text = self.text
        for name in (
            "SUPABASE_PROJECT_URL",
            "SUPABASE_PUBLISHABLE_KEY",
            "SUPABASE_OWNER_BEARER_TOKEN",
            "GITHUB_TOKEN",
        ):
            self.assertIn(name, text)
            self.assertIn(f'test -n "${name}"', text)
        self.assertIn('KEIRIN_AGENT_SINGLE_RUN_AUTHORIZED: "true"', text)
        self.assertNotIn("echo $SUPABASE_", text)
        self.assertNotIn("printenv", text)

    def test_enqueue_then_exactly_one_one_shot_host_invocation(self):
        text = self.text
        enqueue = "python tools/enqueue_trusted_run_instance.py"
        run_once = "python tools/run_hosted_repository_once.py"
        self.assertEqual(text.count(enqueue), 1)
        self.assertEqual(text.count(run_once), 1)
        self.assertLess(text.index(enqueue), text.index(run_once))
        self.assertIn("--execute-once", text)
        self.assertIn('--lease-seconds 180', text)
        self.assertIn("timeout-minutes: 10", text)

    def test_workflow_does_not_enable_keirin_or_recurring_side_effects(self):
        text = self.text.lower()
        for forbidden in (
            "race_predictions",
            "predict-race",
            "production_prediction_enabled=true",
            "external_keirin_auto_fetch_enabled=true",
            "report_delivery_enabled=true",
        ):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
