from __future__ import annotations

from datetime import date
from decimal import Decimal
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_core import (  # noqa: E402
    ActionResult,
    AgentOrchestrator,
    AgentRunner,
    CallableReadOnlyGitHubAdapter,
    FileStateStore,
    RevenueMetric,
    StepSpec,
    TaskSpec,
    ToolRegistry,
    build_activity_report,
)


class AgentOrchestrationTest(unittest.TestCase):
    def test_reconcile_not_applied_allows_explicit_retry(self):
        with TemporaryDirectory() as tmp:
            store = FileStateStore(tmp)
            calls = {"count": 0}

            def action(args, context):
                calls["count"] += 1
                if calls["count"] == 1:
                    raise RuntimeError("ambiguous provider error")
                return ActionResult(message="second explicit attempt completed")

            spec = TaskSpec(
                task_id="RECON-1",
                title="reconcile retry",
                goal="retry only after explicit no-side-effect reconciliation",
                allowed_actions=("write",),
                steps=(StepSpec("write", "write"),),
            )
            runner = AgentRunner(store, {"write": action})
            blocked = runner.run(spec)
            self.assertEqual(blocked.status, "blocked")
            self.assertEqual(calls["count"], 1)

            state = store.reconcile_blocked_step(
                "RECON-1",
                step_id="write",
                resolution="not_applied",
                note="provider audit confirmed no write occurred",
            )
            self.assertEqual(state.status, "pending")
            completed = runner.run(spec)
            self.assertEqual(completed.status, "completed")
            self.assertEqual(calls["count"], 2)
            self.assertEqual(store.load_state("RECON-1").reconciliations[-1]["resolution"], "not_applied")

    def test_reconcile_applied_and_verified_skips_duplicate_action(self):
        with TemporaryDirectory() as tmp:
            store = FileStateStore(tmp)
            calls = {"count": 0}

            def action(args, context):
                calls["count"] += 1
                raise RuntimeError("response lost after possible side effect")

            spec = TaskSpec(
                task_id="RECON-2",
                title="reconcile applied",
                goal="do not duplicate a verified side effect",
                allowed_actions=("write",),
                steps=(StepSpec("write", "write"),),
            )
            runner = AgentRunner(store, {"write": action})
            self.assertEqual(runner.run(spec).status, "blocked")
            store.reconcile_blocked_step(
                "RECON-2",
                step_id="write",
                resolution="applied_and_verified",
                note="remote state confirms intended change exists exactly once",
            )
            outcome = runner.run(spec)
            self.assertEqual(outcome.status, "completed")
            self.assertEqual(outcome.skipped_steps, ("write",))
            self.assertEqual(calls["count"], 1)

    def test_manual_reconciliation_keeps_task_blocked(self):
        with TemporaryDirectory() as tmp:
            store = FileStateStore(tmp)
            spec = TaskSpec(
                task_id="RECON-3",
                title="manual",
                goal="remain blocked",
                allowed_actions=("missing",),
                steps=(StepSpec("one", "missing"),),
            )
            AgentRunner(store, {}).run(spec)
            state = store.reconcile_blocked_step(
                "RECON-3",
                step_id="one",
                resolution="needs_manual_action",
                note="human authentication is required",
            )
            self.assertEqual(state.status, "blocked")

    def test_read_only_github_adapter_runs_through_preflight(self):
        reads: list[tuple[str, str, str]] = []

        def file_reader(repo, path, ref):
            reads.append((repo, path, ref))
            return {"path": path, "ref": ref, "content": "ok"}

        def ci_reader(repo, ref):
            return {"status": "completed", "conclusion": "success"}

        registry = ToolRegistry()
        registry.register(CallableReadOnlyGitHubAdapter(file_reader=file_reader, ci_reader=ci_reader))
        self.assertEqual({item["access"] for item in registry.describe()}, {"read"})

        spec = TaskSpec(
            task_id="GH-READ-1",
            title="read current GitHub state",
            goal="verify required repository files and existing CI without writes",
            allowed_actions=("github.read_main", "github.verify_ci"),
            inputs={"repository": "owner/repo"},
            steps=(
                StepSpec(
                    "read",
                    "github.read_main",
                    args={"required_files": ["AGENTS.md", "WORK_STATUS.md"], "ref": "main"},
                    verify_action="github.verify_ci",
                    retry_safe=True,
                    max_attempts=2,
                ),
            ),
        )
        with TemporaryDirectory() as tmp:
            orchestrator = AgentOrchestrator(registry=registry, store=FileStateStore(tmp))
            preflight = orchestrator.preflight(spec, allowed_access={"read"})
            self.assertTrue(preflight.ready)
            outcome = orchestrator.run(spec, allowed_access={"read"})
            self.assertEqual(outcome.status, "completed")
        self.assertEqual(
            reads,
            [
                ("owner/repo", "AGENTS.md", "main"),
                ("owner/repo", "WORK_STATUS.md", "main"),
            ],
        )

    def test_orchestrator_preflight_stops_before_partial_execution(self):
        registry = ToolRegistry()
        registry.register(
            CallableReadOnlyGitHubAdapter(
                file_reader=lambda repo, path, ref: "ok",
                ci_reader=lambda repo, ref: True,
            )
        )
        spec = TaskSpec(
            task_id="PREFLIGHT-1",
            title="missing later action",
            goal="fail before any step executes",
            allowed_actions=("github.read_main", "later.write"),
            inputs={"repository": "owner/repo"},
            steps=(
                StepSpec("read", "github.read_main", args={"required_files": ["AGENTS.md"]}),
                StepSpec("write", "later.write"),
            ),
        )
        with TemporaryDirectory() as tmp:
            store = FileStateStore(tmp)
            orchestrator = AgentOrchestrator(registry=registry, store=store)
            report = orchestrator.preflight(spec)
            self.assertFalse(report.ready)
            self.assertEqual(report.missing_actions, ("later.write",))
            with self.assertRaisesRegex(ValueError, "preflight_missing_actions:later.write"):
                orchestrator.run(spec)
            self.assertFalse(store.state_path("PREFLIGHT-1").exists())

    def test_unknown_revenue_never_defaults_to_zero(self):
        unknown = RevenueMetric.unknown("売上データ源が未接続")
        self.assertIn("未取得", unknown.display())
        self.assertNotIn("¥0", unknown.display())
        with self.assertRaisesRegex(ValueError, "unknown_revenue_must_not_have_amount"):
            RevenueMetric(status="unknown", amount=Decimal("0"), note="bad").validate()
        with self.assertRaisesRegex(ValueError, "known_revenue_requires_source"):
            RevenueMetric(status="known", amount=Decimal("100")).validate()

    def test_daily_report_uses_asia_tokyo_activity_and_unknown_sales(self):
        events = [
            {
                "timestamp": "2026-09-24T11:59:00+00:00",
                "task_id": "TASK-A",
                "event_type": "task_started",
                "message": "GitHub状態確認",
            },
            {
                "timestamp": "2026-09-24T12:01:00+00:00",
                "task_id": "TASK-A",
                "event_type": "task_completed",
                "message": "検証完了",
            },
        ]
        report = build_activity_report(
            report_date=date(2026, 9, 24),
            events=events,
            daily_sales=RevenueMetric.unknown("データ源未確定"),
            monthly_sales=RevenueMetric.unknown("データ源未確定"),
            next_actions=("共通ツールルーターを実装",),
        )
        rendered = report.render_japanese()
        self.assertIn("21:00 日次報告（Asia/Tokyo）", rendered)
        self.assertIn("当日の売上: 未取得", rendered)
        self.assertIn("GitHub状態確認", rendered)
        self.assertIn("TASK-A: 検証完了", rendered)
        self.assertNotIn("当日の売上: ¥0", rendered)


if __name__ == "__main__":
    unittest.main()
