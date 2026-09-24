from __future__ import annotations

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "supabase" / "schema" / "agent_runtime_state_v1.sql"


class HostedAgentStateSchemaDesignTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = SCHEMA_PATH.read_text(encoding="utf-8")
        cls.normalized = re.sub(r"\s+", " ", cls.sql.lower())

    def test_design_is_not_an_applyable_migration(self):
        self.assertIn("design only / not deployed", self.sql.lower())
        self.assertTrue(str(SCHEMA_PATH).endswith("supabase/schema/agent_runtime_state_v1.sql"))
        self.assertNotIn("supabase/migrations", str(SCHEMA_PATH))
        self.assertRegex(self.normalized, r"\bbegin;")
        self.assertRegex(self.normalized, r"\brollback;")
        self.assertNotRegex(self.normalized, r"\bcommit;")

    def test_queue_states_and_idempotency_are_explicit(self):
        for status in ("queued", "running", "blocked", "completed", "failed"):
            self.assertIn(f"'{status}'", self.sql)
        self.assertIn("idempotency_key text not null", self.normalized)
        self.assertIn("unique (user_id, idempotency_key)", self.normalized)
        self.assertIn("primary key (user_id, task_id)", self.normalized)

    def test_owner_scoped_rls_is_present(self):
        self.assertIn("alter table public.agent_tasks enable row level security", self.normalized)
        self.assertIn("alter table public.agent_task_events enable row level security", self.normalized)
        self.assertGreaterEqual(self.normalized.count("user_id = auth.uid()"), 5)
        self.assertGreaterEqual(self.normalized.count("p.role = 'owner'"), 5)
        self.assertGreaterEqual(self.normalized.count("p.plan = 'owner'"), 5)
        self.assertIn("to authenticated", self.normalized)

    def test_activity_ledger_is_append_only_by_policy(self):
        event_policy_section = self.normalized.split("create policy agent_task_events_owner_select", 1)[1]
        self.assertIn("create policy agent_task_events_owner_insert", event_policy_section)
        self.assertNotIn("create policy agent_task_events_owner_update", event_policy_section)
        self.assertNotIn("create policy agent_task_events_owner_delete", event_policy_section)

    def test_no_service_role_or_secret_material_is_part_of_design(self):
        forbidden = (
            "service_role_key",
            "supabase_service_role_key",
            "bearer ey",
            "api_key =",
            "password =",
        )
        for value in forbidden:
            self.assertNotIn(value, self.normalized)
        self.assertIn("no service-role bypass is part of this design", self.sql.lower())

    def test_existing_keirin_tables_are_not_referenced_for_writes(self):
        self.assertNotIn("race_predictions", self.normalized)
        self.assertNotIn("insert into public.user_profiles", self.normalized)
        self.assertNotIn("update public.user_profiles", self.normalized)


if __name__ == "__main__":
    unittest.main()
