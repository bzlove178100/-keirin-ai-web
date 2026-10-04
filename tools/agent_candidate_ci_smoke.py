"""Exercise the read-only runtime against this Actions run's commit, never old main.

This CI entry point is separate from live main health/hosted activation verification.
Required sibling workflows must actually complete successfully; pending runs are
bounded waits, and failed/missing/stale runs never count as successful evidence.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_core import BoundRuntime
from tools.agent_github_readonly_host import GitHubReadOnlyBridge, runtime_manifest
from tools.agent_github_sha_bridge import ShaPinnedGitHubReadOnlyBridge

REPOSITORY = "bzlove178100/-keirin-ai-web"
REQUIRED = {
    ".github/workflows/regression.yml": 365001481,
    ".github/workflows/collection-progress-ui-regression.yml": 365889130,
}


class CandidateBridge(ShaPinnedGitHubReadOnlyBridge):
    def __init__(self, *, token, run_id, api_get=None, monotonic=time.monotonic, sleep=time.sleep):
        super().__init__(token=token, api_get=api_get)
        if not re.fullmatch(r"[1-9][0-9]*", str(run_id)):
            raise ValueError("candidate_run_id_invalid")
        run = self._api_get(f"/repos/{REPOSITORY}/actions/runs/{run_id}")
        if (not isinstance(run, dict) or run.get("id") != int(run_id)
                or run.get("workflow_id") != 365961402
                or run.get("path") != ".github/workflows/agent-runtime-readonly.yml"
                or run.get("event") not in ("pull_request", "push", "workflow_dispatch")
                or (run.get("repository") or {}).get("full_name") != REPOSITORY
                or (run.get("head_repository") or {}).get("full_name") != REPOSITORY
                or not re.fullmatch(r"[0-9a-f]{40}", str(run.get("head_sha")))
                or not isinstance(run.get("head_branch"), str) or not run["head_branch"]):
            raise ValueError("candidate_run_scope_invalid")
        # A manual check on main consumes the main push's results, not a dispatch
        # of sibling workflows. Manual branch checks cannot claim main evidence.
        if run["event"] != "pull_request" and run["head_branch"] != "main":
            raise ValueError("candidate_main_branch_required")
        self.sha = run["head_sha"]
        self.branch = run["head_branch"]
        self.event = "pull_request" if run["event"] == "pull_request" else "push"
        self.monotonic, self.sleep = monotonic, sleep
        self.ci_evidence = None

    def _required_files(self, args):
        if args.get("ref") != self.sha:
            raise ValueError("candidate_file_ref_invalid")
        return super()._required_files(dict(args, ref="main"))

    def _read_main(self, *, args, context):
        self._repository(context)
        required = self._required_files(args)
        return GitHubReadOnlyBridge._read_main(self, args={"ref": self.sha, "required_files": required}, context=context)

    def _snapshot(self):
        query = urlencode({"head_sha": self.sha, "event": self.event, "per_page": 100})
        payload = self._api_get(f"/repos/{REPOSITORY}/actions/runs?{query}")
        if (not isinstance(payload, dict) or not isinstance(payload.get("workflow_runs"), list)
                or type(payload.get("total_count")) is not int
                or not 0 <= payload["total_count"] <= 100
                or len(payload["workflow_runs"]) != payload["total_count"]):
            raise RuntimeError("candidate_runs_incomplete")
        states = {}
        for path, workflow_id in REQUIRED.items():
            matches = [r for r in payload["workflow_runs"] if isinstance(r, dict)
                and r.get("workflow_id") == workflow_id and r.get("path") == path
                and r.get("head_sha") == self.sha and r.get("head_branch") == self.branch
                and r.get("event") == self.event
                and (r.get("repository") or {}).get("full_name") == REPOSITORY
                and (r.get("head_repository") or {}).get("full_name") == REPOSITORY]
            if any(any(type(r.get(k)) is not int or r[k] <= 0
                       for k in ("id", "run_number", "run_attempt")) for r in matches):
                raise RuntimeError("candidate_run_identity_invalid")
            latest = max(matches, key=lambda r: (r["run_number"], r["run_attempt"], r["id"]), default=None)
            states[path] = None if latest is None else {k: latest.get(k) for k in
                ("id", "run_attempt", "head_sha", "status", "conclusion")}
        return states

    def _verify_ci(self, *, args, context):
        self._repository(context)
        evidence = (args.get("action_result") or {}).get("data") or {}
        required = self._required_files(args.get("step_args") or {})
        if (args.get("step_action") != "github.read_main" or evidence.get("ref") != self.sha
                or evidence.get("repository") != REPOSITORY
                or set(evidence.get("files") or {}) != set(required)
                or any(f.get("verified_nonempty_text") is not True for f in evidence["files"].values())):
            raise RuntimeError("candidate_observation_required")
        deadline = self.monotonic() + 600
        while True:
            states = self._snapshot()
            verified = all(r and r["status"] == "completed" and r["conclusion"] == "success" for r in states.values())
            failed = any(r and r["status"] == "completed" and r["conclusion"] != "success" for r in states.values())
            if verified or failed or self.monotonic() >= deadline:
                self.ci_evidence = {"message": "candidate CI verified" if verified else "candidate CI not successful",
                        "data": {"verified": verified, "repository": REPOSITORY,
                                 "head_sha": self.sha, "event": self.event, "workflows": states}}
                return self.ci_evidence
            self.sleep(min(15, max(0, deadline - self.monotonic())))


def main():
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("GITHUB_REPOSITORY") != REPOSITORY:
        raise SystemExit("candidate_smoke_requires_repository_actions")
    bridge = CandidateBridge(token=os.environ.get("GITHUB_TOKEN", ""), run_id=os.environ.get("GITHUB_RUN_ID", ""))
    with tempfile.TemporaryDirectory(prefix="candidate-runtime-") as directory:
        runtime = BoundRuntime(manifest=runtime_manifest(), bridge=bridge, state_dir=directory)
        task = json.loads((ROOT / "agent_core/examples/keirin_readonly_status_task.json").read_text())
        task.update(task_id="candidate-ci-" + bridge.sha, title="Candidate read-only runtime CI",
                    goal="Read candidate files and verify CI at the same commit; no main-health or activation claim",
                    completion_conditions=["candidate files read at pinned SHA", "required candidate CI succeeded", "read-only access"])
        task["steps"][0]["args"]["ref"] = bridge.sha
        task["steps"][0]["max_attempts"] = 1
        task_path = Path(directory) / "candidate.json"
        task_path.write_text(json.dumps(task))
        result = runtime.run_task_file(task_path, allowed_access={"read"})
        print(json.dumps({"status": result.status, "blocked_reason": result.blocked_reason,
                          "candidate_sha": bridge.sha, "candidate_event": bridge.event,
                          "capability_audit": bridge.audit, "ci_evidence": bridge.ci_evidence}, ensure_ascii=False), flush=True)
        return 0 if result.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
