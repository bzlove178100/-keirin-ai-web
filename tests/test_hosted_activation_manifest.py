from __future__ import annotations

from copy import deepcopy
import json
import sys
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
