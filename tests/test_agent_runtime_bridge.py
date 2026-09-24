from __future__ import annotations

from datetime import datetime, time, timezone
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_core.adapters import Capability, ToolRegistry  # noqa: E402
from agent_core.delivery import BridgeReportDelivery  # noqa: E402
from agent_core.model import TaskSpec  # noqa: E402
from agent_core.provider_adapters import FileArtifactAdapter, ReadOnlySupabaseStatusAdapter  # noqa: E402
from agent_core.runtime import BoundRuntime, RuntimeManifest  # noqa: E402
from agent_core.runtime_bridge import BridgeToolAdapter  # noqa: E402
from agent_core.scheduling import DailySchedule  # noqa: E402


class FakeBridge:
    def __init__(self):
        self.calls = []

    def invoke(self, *, capability, args, context):
        self.calls.append((capability, dict(args), dict(context)))
        if capability.action == "github.verify_ci":
            return {"data": {"verified": True, "conclusion": "success"}}
        if capability.action == "report.deliver":
            return {"delivered": True, "destination": "configured-by-host", "message_id": "m-1"}
        return {"message": f"called {capability.action}", "data": {"ok": True}}


class AgentRuntimeBridgeTest(unittest.TestCase):
    def test_runtime_manifest_rejects_credential_fields(self):
        with self.assertRaisesRegex(ValueError, "credentials_forbidden_in_binding:token"):
            RuntimeManifest.from_dict(
                {
                    "schema_version": "agent-runtime-bindings-v1",
                    "bindings": [
                        {
                            "provider": "github",
                            "action": "github.read_main",
                            "access": "read",
                            "token": "must-not-be-here",
                        }
                    ],
                }
            )

    def test_runtime_manifest_example_is_read_only(self):
        manifest = RuntimeManifest.load(ROOT / "agent_core" / "examples" / "runtime_bindings_readonly.json")
        self.assertTrue(manifest.bindings)
        self.assertEqual({binding.access for binding in manifest.bindings}, {"read"})

    def test_bound_runtime_executes_readonly_task_through_host_bridge(self):
        bridge = FakeBridge()
        manifest = RuntimeManifest.from_dict(
            {
                "schema_version": "agent-runtime-bindings-v1",
                "bindings": [
                    {
                        "provider": "github",
                        "action": "github.read_main",
                        "access": "read",
                        "required_permissions": ["contents:read"],
                        "supports_dry_run": True,
                    },
                    {
                        "provider": "github",
                        "action": "github.verify_ci",
                        "access": "read",
                        "required_permissions": ["actions:read"],
                        "supports_dry_run": True,
                    },
                ],
            }
        )
        with TemporaryDirectory() as tmp:
            runtime = BoundRuntime(manifest=manifest, bridge=bridge, state_dir=tmp)
            task_path = ROOT / "agent_core" / "examples" / "keirin_readonly_status_task.json"
            report = runtime.preflight_task_file(task_path, allowed_access={"read"})
            self.assertTrue(report.ready)
            outcome = runtime.run_task_file(task_path, allowed_access={"read"})
            self.assertEqual(outcome.status, "completed")
        self.assertEqual([call[0].action for call in bridge.calls], ["github.read_main", "github.verify_ci"])

    def test_provider_adapter_access_classification_is_explicit(self):
        bridge = FakeBridge()
        supabase = ReadOnlySupabaseStatusAdapter(bridge)
        self.assertEqual({cap.access for cap in supabase.capabilities()}, {"read"})
        files = FileArtifactAdapter(bridge)
        access = {cap.action: cap.access for cap in files.capabilities()}
        self.assertEqual(access["files.read_artifact"], "read")
        self.assertEqual(access["files.verify_artifact"], "read")
        self.assertEqual(access["files.write_artifact"], "write")

    def test_registry_can_forbid_write_capability_for_readonly_runtime(self):
        registry = ToolRegistry()
        registry.register(FileArtifactAdapter(FakeBridge()))
        registry.require_read_only(["files.read_artifact"])
        with self.assertRaisesRegex(ValueError, "non_read_action_forbidden:files.write_artifact"):
            registry.require_read_only(["files.write_artifact"])

    def test_bridge_report_delivery_has_no_embedded_destination(self):
        bridge = FakeBridge()
        delivery = BridgeReportDelivery(bridge=bridge)
        result = delivery.deliver(report_text="report body", metadata={"date": "2026-09-24"})
        self.assertTrue(result["delivered"])
        self.assertEqual(result["destination"], "configured-by-host")
        capability, args, context = bridge.calls[-1]
        self.assertEqual(capability.access, "write")
        self.assertNotIn("destination", args)
        self.assertEqual(context["operation"], "report_delivery")

    def test_2100_schedule_contract_is_disabled_until_configured(self):
        disabled = DailySchedule(timezone="Asia/Tokyo", local_time=time(21, 0), enabled=False)
        now = datetime(2026, 9, 24, 12, 30, tzinfo=timezone.utc)  # 21:30 JST
        self.assertFalse(disabled.is_due(now))

        enabled = DailySchedule(timezone="Asia/Tokyo", local_time=time(21, 0), enabled=True)
        self.assertTrue(enabled.is_due(now))
        self.assertFalse(enabled.is_due(now, last_run_date="2026-09-24"))

    def test_bridge_adapter_reports_blocked_provider_state(self):
        class BlockedBridge:
            def invoke(self, *, capability, args, context):
                return {"blocked_reason": "authorization_required"}

        adapter = BridgeToolAdapter(
            name="blocked",
            bridge=BlockedBridge(),
            capabilities=(Capability(action="x.read", access="read"),),
        )
        action = adapter.actions()["x.read"]
        from agent_core.runner import BlockedAction

        with self.assertRaisesRegex(BlockedAction, "authorization_required"):
            action({}, {})


if __name__ == "__main__":
    unittest.main()
