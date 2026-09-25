from __future__ import annotations

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DESIGN_V1 = ROOT / "supabase" / "schema" / "agent_runtime_state_v1.sql"
DESIGN_V2 = ROOT / "supabase" / "schema" / "agent_runtime_checkpoints_v2.sql"
ACTIVATION = ROOT / "supabase" / "migrations" / "20260925103650_agent_runtime_checkpoints_activation.sql"
FOLLOWUP = ROOT / "supabase" / "migrations" / "20260925110207_agent_runtime_checkpoint_rpc_and_rls_optimization.sql"


def normalized(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8").lower())


class HostedAgentStateSchemaTest(unittest.TestCase):
    def test_archived_designs_remain_rollback_only(self):
        for path in (DESIGN_V1, DESIGN_V2):
            sql = path.read_text(encoding="utf-8").lower()
            compact = normalized(path)
            self.assertIn("design only / not deployed", sql)
            self.assertRegex(compact, r"\bbegin;")
            self.assertRegex(compact, r"\brollback;")
            self.assertNotRegex(compact, r"\bcommit;")
            self.assertNotIn("supabase/migrations", str(path))

    def test_authorized_activation_migration_is_recorded(self):
        sql = normalized(ACTIVATION)
        self.assertTrue(ACTIVATION.exists())
        self.assertNotRegex(sql, r"\brollback;")
        self.assertIn("create table if not exists public.agent_tasks", sql)
        self.assertIn("create table if not exists public.agent_task_events", sql)
        self.assertIn("alter table public.agent_tasks enable row level security", sql)
        self.assertIn("alter table public.agent_task_events enable row level security", sql)
        self.assertIn("spec_fingerprint text not null", sql)
        self.assertIn("revision bigint not null default 0", sql)
        self.assertIn("checkpoint_conflict_or_not_accessible", sql)
        self.assertNotIn("security definer", sql)

    def test_queue_states_identity_and_append_only_event_grants_are_explicit(self):
        sql = normalized(ACTIVATION)
        for status in ("queued", "running", "blocked", "completed", "failed"):
            self.assertIn(f"'{status}'", sql)
        self.assertIn("idempotency_key text not null", sql)
        self.assertIn("unique (user_id, idempotency_key)", sql)
        self.assertIn("primary key (user_id, task_id)", sql)
        self.assertIn("grant select, insert, update on public.agent_tasks to authenticated", sql)
        self.assertIn("grant select, insert on public.agent_task_events to authenticated", sql)
        self.assertNotIn("grant update on public.agent_task_events", sql)
        self.assertNotIn("grant delete on public.agent_task_events", sql)

    def test_owner_scoped_rls_and_followup_optimization_are_recorded(self):
        activation = normalized(ACTIVATION)
        followup = normalized(FOLLOWUP)
        self.assertGreaterEqual(activation.count("p.role = 'owner'"), 5)
        self.assertGreaterEqual(activation.count("p.plan = 'owner'"), 5)
        self.assertGreaterEqual(followup.count("user_id = (select auth.uid())"), 5)
        self.assertGreaterEqual(followup.count("p.user_id = (select auth.uid())"), 5)
        self.assertIn("to authenticated", followup)

    def test_followup_adds_owner_derived_create_rpc_and_metadata_sync(self):
        sql = normalized(FOLLOWUP)
        self.assertIn("create or replace function public.agent_create_checkpoint", sql)
        self.assertIn("v_user_id uuid := (select auth.uid())", sql)
        self.assertIn("security invoker", sql)
        self.assertIn("grant execute on function public.agent_create_checkpoint", sql)
        self.assertIn("blocked_reason = nullif(p_state->>'blocked_reason','')", sql)
        self.assertIn("last_error = nullif(p_state->>'last_error','')", sql)
        self.assertIn("checkpoint_conflict_or_not_accessible", sql)

    def test_agent_migrations_do_not_write_keirin_or_profile_data(self):
        combined = normalized(ACTIVATION) + " " + normalized(FOLLOWUP)
        forbidden = (
            "insert into public.race_predictions",
            "update public.race_predictions",
            "delete from public.race_predictions",
            "insert into public.user_profiles",
            "update public.user_profiles",
            "delete from public.user_profiles",
            "service_role_key",
            "supabase_service_role_key",
            "bearer ey",
        )
        for value in forbidden:
            self.assertNotIn(value, combined)


if __name__ == "__main__":
    unittest.main()
