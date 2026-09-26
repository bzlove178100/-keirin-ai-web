from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_core.activation import (  # noqa: E402
    TRUSTED_TASK_FINGERPRINT,
    load_hosted_activation_manifest,
    validate_hosted_activation_manifest,
)
from agent_core.model import TaskSpec  # noqa: E402
from tools.agent_hosted_repository_worker import HostedRunInterrupted  # noqa: E402
from tools.run_hosted_repository_once import (  # noqa: E402
    AUTHORIZATION_ENV,
    GITHUB_TOKEN_ENV,
    OWNER_BEARER_ENV,
    PROJECT_URL_ENV,
    PUBLISHABLE_KEY_ENV,
    run_once,
)

MANIFEST = ROOT / "agent_core" / "examples" / "hosted_readonly_single_run_activation.json"
TASK = ROOT / "agent_core" / "examples" / "keirin_readonly_status_task.json"


def payload():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


class HostedActivationManifestTest(unittest.TestCase):
    def test_committed_manifest_is_closed_exact_single_run_scope(self):
        manifest = load_hosted_activation_manifest(MANIFEST, repo_root=ROOT)
        self.assertFalse(manifest.activation_enabled)
        self.assertFalse(manifest.live_execution_authorized)
        self.assertEqual(manifest.mode, "single_run")
        self.assertEqual(manifest.max_tasks, 1)
        self.assertFalse(manifest.scheduler_enabled)
        self.assertFalse(manifest.recurrence_enabled)
        self.assertEqual(manifest.allowed_access, ("read",))
        self.assertEqual(manifest.actions, ("github.read_main", "github.verify_ci"))
        self.assertEqual(manifest.github_permissions, ("actions:read", "contents:read"))
        self.assertTrue(all(value is False for value in manifest.safety.values()))

    def test_manifest_fingerprint_matches_exact_trusted_task(self):
        spec = TaskSpec.from_dict(json.loads(TASK.read_text(encoding="utf-8")))
        self.assertEqual(spec.fingerprint(), TRUSTED_TASK_FINGERPRINT)
        self.assertEqual(payload()["task_fingerprint"], spec.fingerprint())

    def test_manifest_cannot_enable_execution_scheduler_or_recurrence(self):
        for key in ("activation_enabled", "scheduler_enabled", "recurrence_enabled"):
            with self.subTest(key=key):
                value = payload()
                value[key] = True
                with self.assertRaises(ValueError):
                    validate_hosted_activation_manifest(value, repo_root=ROOT)

    def test_scope_expansion_is_rejected(self):
        mutations = [
            ("mode", "recurring"),
            ("max_tasks", 2),
            ("allowed_access", ["read", "write"]),
            ("repository", "other/repository"),
            ("task_file", "../outside.json"),
            ("task_id", "other-task"),
            ("task_fingerprint", "sha256-v1:" + "0" * 64),
            ("actions", ["github.read_main", "github.verify_ci", "github.write_file"]),
            ("github_permissions", ["contents:read", "actions:read", "contents:write"]),
        ]
        for key, replacement in mutations:
            with self.subTest(key=key):
                value = payload()
                value[key] = replacement
                with self.assertRaises(ValueError):
                    validate_hosted_activation_manifest(value, repo_root=ROOT)

    def test_safety_flags_cannot_be_flipped(self):
        for key in payload()["safety"]:
            with self.subTest(key=key):
                value = payload()
                value["safety"] = deepcopy(value["safety"])
                value["safety"][key] = True
                with self.assertRaisesRegex(ValueError, "activation_safety_contract_mismatch"):
                    validate_hosted_activation_manifest(value, repo_root=ROOT)

    def test_one_shot_host_requires_runtime_authorization_before_factory(self):
        called = False

        def worker_factory(**_kwargs):
            nonlocal called
            called = True
            raise AssertionError("worker factory must not be reached")

        with self.assertRaisesRegex(RuntimeError, "single_run_runtime_authorization_required"):
            run_once(
                ["--execute-once", "--worker-id", "worker-test"],
                env={},
                worker_factory=worker_factory,
            )
        self.assertFalse(called)

    def test_one_shot_host_success_is_single_run_and_redacts_runtime_secrets(self):
        captured = {}
        secrets = {
            AUTHORIZATION_ENV: "true",
            PROJECT_URL_ENV: "https://example.supabase.co",
            PUBLISHABLE_KEY_ENV: "publishable-fixture-value",
            OWNER_BEARER_ENV: "owner-fixture-value",
            GITHUB_TOKEN_ENV: "github-fixture-value",
        }

        class Worker:
            def run_next(self, *, worker_id, lease_seconds):
                captured["worker_id"] = worker_id
                captured["lease_seconds"] = lease_seconds
                return SimpleNamespace(
                    claimed=True,
                    task_id="keirin-readonly-status-check",
                    execution_enabled=True,
                    outcome=SimpleNamespace(status="completed"),
                    blocked_reason=None,
                )

        def worker_factory(**kwargs):
            captured["worker_kwargs"] = kwargs
            return Worker()

        recovery = SimpleNamespace(
            task_id="keirin-readonly-status-check",
            classification="completed_verified_no_reexecution",
            checkpoint_status="completed",
            verified=True,
            reexecution_allowed=False,
        )

        class Inspector:
            def inspect(self, spec):
                captured["recovery_task_id"] = spec.task_id
                return recovery

        def recovery_factory(**kwargs):
            captured["recovery_kwargs"] = kwargs
            return Inspector()

        stream = io.StringIO()
        with redirect_stdout(stream):
            code = run_once(
                ["--execute-once", "--worker-id", "worker-test", "--lease-seconds", "180"],
                env=secrets,
                worker_factory=worker_factory,
                recovery_factory=recovery_factory,
            )

        self.assertEqual(code, 0)
        self.assertEqual(captured["worker_id"], "worker-test")
        self.assertEqual(captured["lease_seconds"], 180)
        self.assertIs(captured["worker_kwargs"]["execution_authorized"], True)
        report = stream.getvalue()
        self.assertIn('"recovery_classification": "completed_verified_no_reexecution"', report)
        self.assertIn('"reexecution_allowed": false', report)
        for value in ("publishable-fixture-value", "owner-fixture-value", "github-fixture-value"):
            self.assertNotIn(value, report)

    def test_one_shot_host_interruption_stops_and_inspects_without_retry(self):
        secrets = {
            AUTHORIZATION_ENV: "true",
            PROJECT_URL_ENV: "https://example.supabase.co",
            PUBLISHABLE_KEY_ENV: "publishable-fixture-value",
            OWNER_BEARER_ENV: "owner-fixture-value",
            GITHUB_TOKEN_ENV: "github-fixture-value",
        }

        class Worker:
            def run_next(self, **_kwargs):
                raise HostedRunInterrupted("ambiguous")

        class Inspector:
            def inspect(self, _spec):
                return SimpleNamespace(
                    task_id="keirin-readonly-status-check",
                    classification="running_expired_with_observation_only",
                    checkpoint_status="running",
                    verified=None,
                    reexecution_allowed=False,
                )

        stream = io.StringIO()
        with redirect_stdout(stream):
            code = run_once(
                ["--execute-once", "--worker-id", "worker-test"],
                env=secrets,
                worker_factory=lambda **_kwargs: Worker(),
                recovery_factory=lambda **_kwargs: Inspector(),
            )

        self.assertEqual(code, 2)
        self.assertIn('"interrupted": true', stream.getvalue())
        self.assertIn('"reexecution_allowed": false', stream.getvalue())


if __name__ == "__main__":
    unittest.main()
