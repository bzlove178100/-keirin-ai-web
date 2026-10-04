from __future__ import annotations

import base64
from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.agent_candidate_ci_smoke import CandidateBridge, REPOSITORY, REQUIRED
from tools import agent_candidate_ci_smoke as smoke

SHA = "a" * 40


def own_run():
    return dict(id=123, workflow_id=365961402, path=".github/workflows/agent-runtime-readonly.yml",
                event="pull_request", head_sha=SHA, head_branch="repair",
                repository={"full_name": REPOSITORY}, head_repository={"full_name": REPOSITORY})


def sibling_runs():
    return [dict(own_run(), id=200+i, workflow_id=wid, path=path, run_number=4, run_attempt=1,
                 status="completed", conclusion="success") for i, (path, wid) in enumerate(REQUIRED.items())]


class Tests(unittest.TestCase):
    def bridge(self, batches, own=None):
        self.calls, self.elapsed, self.sleeps = [], 0, []
        def api(path):
            self.calls.append(path)
            if path.endswith("/runs/123"):
                return own or own_run()
            if "/contents/" in path:
                return {"type": "file", "sha": "b" * 40, "size": 4, "encoding": "base64",
                        "content": base64.b64encode(b"text").decode()}
            if "/actions/runs?" in path:
                batch = batches.pop(0) if len(batches) > 1 else batches[0]
                return {"total_count": len(batch), "workflow_runs": batch}
            raise AssertionError(path)
        def sleep(seconds):
            self.sleeps.append(seconds)
            self.elapsed += seconds
        return CandidateBridge(token="synthetic-token", run_id=123, api_get=api,
                               monotonic=lambda: self.elapsed, sleep=sleep)

    def verify(self, bridge):
        context = {"task_inputs": {"repository": REPOSITORY}}
        args = {"ref": SHA, "required_files": ["AGENTS.md", "WORK_STATUS.md"]}
        result = bridge._read_main(args=args, context=context)
        return bridge._verify_ci(args={"step_action": "github.read_main", "step_args": args,
                                      "action_result": result}, context=context)["data"]["verified"]

    def test_candidate_success_reads_same_sha_and_never_queries_main(self):
        self.assertTrue(self.verify(self.bridge([sibling_runs()])))
        self.assertTrue(all("ref=" + SHA in p for p in self.calls if "/contents/" in p))
        self.assertTrue(all("head_sha=" + SHA in p and "status=completed" not in p
                            for p in self.calls if "/runs?" in p))
        self.assertFalse(any("main" in p for p in self.calls))

    def test_failed_sibling_fails_immediately(self):
        for conclusion in ("failure", "cancelled", "skipped", "timed_out", None):
            runs = sibling_runs()
            runs[0]["conclusion"] = conclusion
            self.assertFalse(self.verify(self.bridge([runs])))
            self.assertEqual(self.sleeps, [])

    def test_pending_newer_run_cannot_reuse_old_success(self):
        runs = sibling_runs()
        pending = dict(runs[0], id=300, run_number=5, status="in_progress", conclusion=None)
        bridge = self.bridge([runs + [pending], runs + [dict(pending, status="completed", conclusion="success")]])
        self.assertTrue(self.verify(bridge))
        self.assertEqual(self.sleeps, [15])

    def test_wrong_commit_event_branch_path_id_or_repository_never_pass(self):
        for field, value in (("head_sha", "b" * 40), ("event", "push"), ("head_branch", "main"),
                ("path", "other.yml"), ("workflow_id", 1),
                ("head_repository", {"full_name": "other/repo"}), ("repository", {"full_name": "other/repo"})):
            with self.subTest(field=field):
                runs = sibling_runs()
                runs[0][field] = value
                self.assertFalse(self.verify(self.bridge([runs])))
                self.assertEqual(self.elapsed, 600)

    def test_missing_and_pending_expire_without_success(self):
        for runs in ([], [dict(r, status="queued", conclusion=None) for r in sibling_runs()]):
            self.assertFalse(self.verify(self.bridge([runs])))
            self.assertEqual(self.elapsed, 600)

    def test_wrong_own_workflow_or_fork_is_rejected(self):
        for change in ({"workflow_id": 1}, {"head_repository": {"full_name": "fork/repo"}},
                       {"head_sha": "main"}, {"event": "workflow_dispatch"}):
            with self.assertRaises(ValueError):
                self.bridge([sibling_runs()], own=dict(own_run(), **change))

    def test_main_push_uses_same_commit_and_push_event(self):
        runs = [dict(r, event="push", head_branch="main") for r in sibling_runs()]
        bridge = self.bridge([runs], own=dict(own_run(), event="push", head_branch="main"))
        self.assertTrue(self.verify(bridge))
        self.assertEqual(bridge.event, "push")

    def test_mismatched_observation_ref_refused_before_ci(self):
        bridge = self.bridge([sibling_runs()])
        with self.assertRaisesRegex(ValueError, "candidate_file_ref_invalid"):
            bridge._read_main(args={"ref": "main", "required_files": ["AGENTS.md"]},
                              context={"task_inputs": {"repository": REPOSITORY}})

    def test_real_runtime_completes_only_with_candidate_success(self):
        for success in (True, False):
            runs = sibling_runs()
            if not success:
                runs[0]["conclusion"] = "failure"
            bridge = self.bridge([runs])
            with patch.object(smoke, "CandidateBridge", return_value=bridge), patch.dict(
                    smoke.os.environ, {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": REPOSITORY}), redirect_stdout(io.StringIO()):
                self.assertEqual(smoke.main(), 0 if success else 1)
            self.assertEqual([a["action"] for a in bridge.audit], ["github.read_main", "github.verify_ci"])
            self.assertTrue(all(a["access"] == "read" for a in bridge.audit))


if __name__ == "__main__":
    unittest.main()
