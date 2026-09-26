from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sys
import traceback
import tempfile
import unittest
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, build_opener
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent_core.adapters import Capability
from tools.agent_github_sha_bridge import ShaPinnedGitHubReadOnlyBridge, _WORKFLOWS, _NoRedirect

SHA = "a" * 40
REPO = "bzlove178100/-keirin-ai-web"
CONTEXT = {"task_inputs": {"repository": REPO}}
ARGS = {"ref": "main", "required_files": ["AGENTS.md", "WORK_STATUS.md", "AI_AGENT_REQUIREMENTS.md"]}


class API:
    def __init__(self):
        self.calls = []
        self.main_sha = SHA
        self.file_override = {}
        self.runs = [{"id": n, "workflow_id": wid, "path": path, "head_sha": SHA,
                      "head_branch": "main", "event": "push", "run_number": 1,
                      "run_attempt": 1, "status": "completed", "conclusion": "success"}
                     for n, (path, wid) in enumerate(_WORKFLOWS.items(), 1)]
        self.total_override = None

    def __call__(self, path):
        self.calls.append(path)
        if path.endswith("/commits/main"):
            return {"sha": self.main_sha}
        if "/contents/" in path:
            self_query = parse_qs(urlparse(path).query)
            assert self_query == {"ref": [SHA]}, self_query
            name = path.split("/contents/")[1].split("?")[0]
            raw = b"# required file\n"
            return {"path": name, "type": "file", "encoding": "base64", "size": len(raw),
                    "sha": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest(),
                    "content": base64.b64encode(raw).decode(), **self.file_override}
        if "/actions/runs?" in path:
            query = parse_qs(urlparse(path).query)
            assert query["head_sha"] == [SHA] and "status" not in query
            page = int(query["page"][0])
            return {"total_count": len(self.runs) if self.total_override is None else self.total_override,
                    "workflow_runs": deepcopy(self.runs[(page-1)*100:page*100])}
        raise AssertionError(path)


class ShaBridgeTests(unittest.TestCase):
    def setUp(self):
        self.api = API()
        self.bridge = ShaPinnedGitHubReadOnlyBridge(token="test-token-not-real", api_get=self.api)

    def read(self):
        return self.bridge.invoke(capability=Capability("github.read_main", "read"), args=ARGS, context=CONTEXT)

    def verify(self, observation=None, bridge=None):
        observation = self.read() if observation is None else observation
        return (bridge or self.bridge).invoke(capability=Capability("github.verify_ci", "read"),
            args={"step_action": "github.read_main", "step_args": ARGS, "action_result": observation}, context=CONTEXT)["data"]

    def test_same_sha_success_and_detached_observation(self):
        observation = json.loads(json.dumps(self.read()))
        fresh_bridge = ShaPinnedGitHubReadOnlyBridge(token="test-token-not-real", api_get=self.api)
        result = self.verify(observation, fresh_bridge)
        self.assertTrue(result["verified"])
        self.assertEqual(result["observed_sha"], SHA)
        self.assertEqual(len(result["workflows"]), 4)
        self.assertEqual(sum("/commits/main" in p for p in self.api.calls), 2)
        result["files"].clear()
        self.assertEqual(len(observation["data"]["files"]), 3)

    def test_real_runner_passes_observation_to_verifier(self):
        from agent_core import BoundRuntime
        from tools.agent_github_readonly_host import runtime_manifest
        with tempfile.TemporaryDirectory() as state_dir:
            runtime = BoundRuntime(manifest=runtime_manifest(), bridge=self.bridge, state_dir=state_dir)
            result = runtime.run_task_file(ROOT / "agent_core/examples/keirin_readonly_status_task.json", allowed_access={"read"})
            self.assertEqual(result.status, "completed")

    def test_old_sha_success_does_not_count(self):
        self.api.runs[0]["head_sha"] = "b" * 40
        self.assertFalse(self.verify()["verified"])

    def test_latest_run_failure_or_pending_is_not_hidden(self):
        for status, conclusion in [("queued", None), ("in_progress", None), ("completed", "failure"),
                                   ("completed", "cancelled"), ("completed", "skipped")]:
            with self.subTest(status=status, conclusion=conclusion):
                self.api = API()
                self.bridge = ShaPinnedGitHubReadOnlyBridge(token="test-token-not-real", api_get=self.api)
                newer = dict(self.api.runs[0], id=20, run_number=2, status=status, conclusion=conclusion)
                self.api.runs.append(newer)  # Deliberately not ordered newest first.
                self.assertFalse(self.verify()["verified"])

    def test_rerun_attempt_is_checked(self):
        self.api.runs[0].update(run_attempt=2, status="in_progress", conclusion=None)
        self.assertFalse(self.verify()["verified"])

    def test_workflow_name_cannot_spoof_identity(self):
        self.api.runs[0].update(workflow_id=999, name="keirin-ai regression")
        self.assertFalse(self.verify()["verified"])

    def test_wrong_path_or_event_or_branch_is_not_evidence(self):
        for field, value in [("path", "other.yml"), ("event", "pull_request"), ("head_branch", "other")]:
            with self.subTest(field=field):
                old = self.api.runs[0][field]
                self.api.runs[0][field] = value
                self.assertFalse(self.verify()["verified"])
                self.api.runs[0][field] = old

    def test_main_movement_fails(self):
        observation = self.read()
        self.api.main_sha = "b" * 40
        result = self.verify(observation)
        self.assertFalse(result["verified"])
        self.assertEqual(result["reason"], "main_changed")
        self.assertEqual(result["observed_sha"], SHA)

    def test_paginates_before_selecting_latest(self):
        self.api.runs.extend(dict(self.api.runs[1], id=n, workflow_id=999) for n in range(10, 106))
        self.api.runs.append(dict(self.api.runs[0], id=200, run_number=2, status="queued", conclusion=None))
        self.assertFalse(self.verify()["verified"])
        self.assertTrue(any("page=2" in p for p in self.api.calls))

    def test_incomplete_or_over_cap_pagination_fails(self):
        for total in (5, 1001):
            self.api.total_override = total
            with self.subTest(total=total), self.assertRaisesRegex(RuntimeError, "pagination"):
                self.verify()

    def test_invalid_file_fails(self):
        for override in [{"encoding": "none"}, {"content": "not-base64!"}, {"content": ""},
                         {"sha": ""}, {"sha": "b"*40}, {"size": 999}, {"type": "dir"}]:
            self.api.file_override = override
            with self.subTest(override=override), self.assertRaises(RuntimeError):
                self.read()

    def test_missing_or_tampered_observation_fails_without_api(self):
        observation = self.read()
        observation["data"]["repository"] = "other/repo"
        self.api.calls.clear()
        with self.assertRaisesRegex(RuntimeError, "observation"):
            self.verify(observation)
        self.assertEqual(self.api.calls, [])

    def test_repository_and_write_scope_fail_without_api(self):
        with self.assertRaises(ValueError):
            self.bridge.invoke(capability=Capability("github.read_main", "read"), args=ARGS,
                               context={"task_inputs": {"repository": "other/repo"}})
        result = self.bridge.invoke(capability=Capability("github.write_file", "write"), args={}, context=CONTEXT)
        self.assertIn("blocked_reason", result)
        self.assertEqual(self.api.calls, [])

    def test_provider_exception_has_no_token_in_traceback(self):
        def failing(path):
            raise RuntimeError("test-token-not-real")
        self.bridge = ShaPinnedGitHubReadOnlyBridge(token="test-token-not-real", api_get=failing)
        try:
            self.read()
        except RuntimeError:
            self.assertNotIn("test-token-not-real", traceback.format_exc())
        else:
            self.fail("exception expected")

    def test_redirects_are_rejected(self):
        opener = build_opener(_NoRedirect())
        for code in (301, 302, 303, 307, 308):
            with self.subTest(code=code), self.assertRaises(HTTPError):
                opener.error("http", Request("https://api.github.com"), io.BytesIO(), code,
                             "redirect", {"location": "https://other.example"})


if __name__ == "__main__":
    unittest.main()
