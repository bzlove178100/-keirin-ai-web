from __future__ import annotations

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260925115914_agent_runtime_activity_event_rpc.sql"


class AgentActivityMigrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = MIGRATION.read_text(encoding="utf-8")
        cls.normalized = re.sub(r"\s+", " ", cls.sql.lower())

    def test_rpc_is_owner_scoped_through_invoker_rls(self):
        self.assertIn("create or replace function public.agent_append_event", self.normalized)
        self.assertIn("security invoker", self.normalized)
        self.assertIn("auth.uid()", self.normalized)
        self.assertIn("insert into public.agent_task_events", self.normalized)
        self.assertIn("grant execute on function public.agent_append_event", self.normalized)
        self.assertIn("to authenticated", self.normalized)
        self.assertNotIn("security definer", self.normalized)

    def test_rpc_validates_identity_and_payload_shape(self):
        self.assertIn("invalid_task_id", self.sql)
        self.assertIn("invalid_event_type", self.sql)
        self.assertIn("invalid_step_id", self.sql)
        self.assertIn("event_payload_must_be_object", self.sql)
        self.assertIn("jsonb_typeof(p_payload) <> 'object'", self.normalized)

    def test_activity_migration_does_not_touch_keirin_prediction_state(self):
        forbidden = (
            "race_predictions",
            "predict-race",
            "predict_engine",
            "production_prediction_enabled",
            "service_role_key",
            "supabase_service_role_key",
        )
        for value in forbidden:
            self.assertNotIn(value, self.normalized)

    def test_authenticated_access_is_rpc_only_boundary_not_privilege_escalation(self):
        self.assertIn(
            "revoke all on function public.agent_append_event(text,text,text,jsonb) from public, anon, authenticated",
            self.normalized,
        )
        self.assertIn(
            "grant execute on function public.agent_append_event(text,text,text,jsonb) to authenticated",
            self.normalized,
        )
        self.assertNotIn("grant all", self.normalized)

    def test_repo_filename_matches_applied_staging_migration(self):
        self.assertEqual(MIGRATION.name, "20260925115914_agent_runtime_activity_event_rpc.sql")
        self.assertIn("Applied to keirin-ai-staging as migration 20260925115914", self.sql)


if __name__ == "__main__":
    unittest.main()
