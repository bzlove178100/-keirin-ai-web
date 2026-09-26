from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "agent-manual-one-shot.yml"


class ManualOneShotWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_manual_dispatch_only_no_schedule_or_push_trigger(self):
        self.assertIn("workflow_dispatch:", self.text)
        self.assertNotIn("schedule:", self.text)
        self.assertNotIn("cron:", self.text)
        self.assertNotIn("\n  push:", self.text)
        self.assertNotIn("\n  pull_request:", self.text)

    def test_permissions_are_read_only(self):
        self.assertIn("permissions:\n  contents: read\n  actions: read", self.text)
        self.assertNotIn("contents: write", self.text)
        self.assertNotIn("actions: write", self.text)
        self.assertNotIn("id-token: write", self.text)

    def test_concurrency_and_timeout_are_bounded(self):
        self.assertIn("group: keirin-agent-trusted-one-shot", self.text)
        self.assertIn("cancel-in-progress: false", self.text)
        self.assertIn("timeout-minutes: 5", self.text)

    def test_exact_instance_authorization_is_bound_to_dispatch_input(self):
        self.assertIn('KEIRIN_AGENT_SINGLE_RUN_AUTHORIZED: "true"', self.text)
        self.assertIn("KEIRIN_AGENT_SINGLE_RUN_INSTANCE_TOKEN: ${{ inputs.instance_token }}", self.text)
        self.assertIn('if [ "$MANUAL_CONFIRMATION" != "RUN_EXACTLY_ONCE" ]', self.text)
        self.assertIn("^[0-9a-f]{16}$", self.text)

    def test_runtime_secrets_are_references_not_committed_values(self):
        self.assertIn("SUPABASE_PROJECT_URL: ${{ vars.SUPABASE_PROJECT_URL }}", self.text)
        self.assertIn("SUPABASE_PUBLISHABLE_KEY: ${{ secrets.SUPABASE_PUBLISHABLE_KEY }}", self.text)
        self.assertIn("SUPABASE_OWNER_BEARER_TOKEN: ${{ secrets.SUPABASE_OWNER_BEARER_TOKEN }}", self.text)
        self.assertIn("GITHUB_TOKEN: ${{ github.token }}", self.text)
        self.assertNotIn("service_role", self.text.lower())

    def test_entrypoint_is_one_shot_exact_instance_host(self):
        self.assertIn("python tools/run_hosted_repository_once.py", self.text)
        self.assertIn("--execute-once", self.text)
        self.assertIn('--instance-token "$INSTANCE_TOKEN"', self.text)
        self.assertIn('--worker-id "$WORKER_ID"', self.text)
        self.assertIn("--lease-seconds 180", self.text)
        self.assertNotIn("while true", self.text.lower())


if __name__ == "__main__":
    unittest.main()
