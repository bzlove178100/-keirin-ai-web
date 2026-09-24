from __future__ import annotations

import base64
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_core.adapters import Capability  # noqa: E402
from tools.agent_github_readonly_host import GitHubReadOnlyBridge, runtime_manifest  # noqa: E402


class GitHubReadOnlyHostTest(unittest.TestCase):
    def test_reads_required_files_and_verifies_existing_ci(self):
        def fake_api(path: str):
            if "/contents/" in path:
                file_name = path.split("/contents/", 1)[1].split("?", 1)[0]
                text = f"# {file_name}\nverified content\n"
                return {
                    "type": "file",
                    "sha": f"sha-{file_name}",
                    "size": len(text),
                    "encoding": "base64",
                    "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
                }
            if "/actions/runs?" in path:
                return {
                    "workflow_runs": [
                        {
                            "id": 2,
                            "name": "keirin-ai regression",
                            "conclusion": "success",
                            "head_sha": "main-sha",
                            "created_at": "2026-09-24T10:00:00Z",
                        },
                        {
                            "id": 1,
                            "name": "collection progress UI regression",
                            "conclusion": "success",
                            "head_sha": "main-sha",
                            "created_at": "2026-09-24T09:59:00Z",
                        },
                    ]
                }
            raise AssertionError(f"unexpected path: {path}")

        bridge = GitHubReadOnlyBridge(token="test-token", api_get=fake_api)
        context = {"task_inputs": {"repository": "owner/repo"}}
        read_result = bridge.invoke(
            capability=Capability(action="github.read_main", access="read"),
            args={"ref": "main", "required_files": ["AGENTS.md", "WORK_STATUS.md"]},
            context=context,
        )
        self.assertTrue(read_result["data"]["files"]["AGENTS.md"]["verified_nonempty_text"])
        self.assertTrue(read_result["data"]["files"]["WORK_STATUS.md"]["verified_nonempty_text"])

        verify_result = bridge.invoke(
            capability=Capability(action="github.verify_ci", access="read"),
            args={},
            context=context,
        )
        self.assertTrue(verify_result["data"]["verified"])
        self.assertEqual(len(bridge.audit), 2)
        self.assertTrue(all(item["access"] == "read" for item in bridge.audit))

    def test_ci_verification_fails_closed_when_required_workflow_missing(self):
        bridge = GitHubReadOnlyBridge(
            token="test-token",
            api_get=lambda path: {
                "workflow_runs": [
                    {
                        "id": 1,
                        "name": "keirin-ai regression",
                        "conclusion": "success",
                    }
                ]
            },
        )
        result = bridge.invoke(
            capability=Capability(action="github.verify_ci", access="read"),
            args={},
            context={"task_inputs": {"repository": "owner/repo"}},
        )
        self.assertFalse(result["data"]["verified"])
        self.assertFalse(result["data"]["workflows"]["collection progress UI regression"]["found"])

    def test_write_capability_is_blocked_before_provider_call(self):
        calls = []
        bridge = GitHubReadOnlyBridge(token="test-token", api_get=lambda path: calls.append(path))
        result = bridge.invoke(
            capability=Capability(action="github.write_file", access="write"),
            args={},
            context={"task_inputs": {"repository": "owner/repo"}},
        )
        self.assertEqual(result["blocked_reason"], "read_only_worker_forbids:github.write_file")
        self.assertEqual(calls, [])

    def test_runtime_manifest_contains_only_read_bindings(self):
        manifest = runtime_manifest()
        self.assertEqual({binding.access for binding in manifest.bindings}, {"read"})
        self.assertEqual(
            {binding.action for binding in manifest.bindings},
            {"github.read_main", "github.verify_ci"},
        )


if __name__ == "__main__":
    unittest.main()
