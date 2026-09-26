"""Strict, unactivated hosted GitHub observation binding.

Evidence is JSON-serializable and passed to verification via action_result. The
future hosted composition must persist it; this module does not start a worker.
"""
from __future__ import annotations

import base64
import binascii
from copy import deepcopy
import re
import json
import hashlib
from typing import Any
from urllib.parse import quote, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

from tools.agent_github_readonly_host import GitHubReadOnlyBridge

_SHA = re.compile(r"^[0-9a-f]{40}$")
_REPOSITORY = "bzlove178100/-keirin-ai-web"
# Reviewed repository workflow identities, not display names supplied by a task.
_WORKFLOWS = {
    ".github/workflows/regression.yml": 365001481,
    ".github/workflows/collection-progress-ui-regression.yml": 365889130,
    ".github/workflows/agent-checkpoint-postgres.yml": 366817234,
    ".github/workflows/agent-runtime-readonly.yml": 365961402,
}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ShaPinnedGitHubReadOnlyBridge(GitHubReadOnlyBridge):
    """Read main files and all four required CI workflows at one commit.

    This is separate from the legacy self-running smoke bridge: it must not wait
    on its own workflow result. Host composition/activation is intentionally absent.
    """

    def __init__(self, *, token: str, api_get=None):
        if not isinstance(token, str) or not token or any(ord(c) < 33 or ord(c) > 126 for c in token):
            raise ValueError("github_token_invalid")
        super().__init__(token=token, api_get=api_get)

    def _api_get(self, path: str) -> Any:
        # No raw provider error/headers may reach AgentRunner's durable last_error.
        try:
            if self._api_get_override is not None:
                result = self._api_get_override(path)
            else:
                request = Request(f"https://api.github.com{path}", headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {self._token}",
                    "User-Agent": "keirin-agent-sha-readonly",
                    "X-GitHub-Api-Version": "2022-11-28",
                }, method="GET")
                with build_opener(_NoRedirect()).open(request, timeout=20) as response:
                    result = json.loads(response.read().decode("utf-8"))
            if self._token in json.dumps(result, ensure_ascii=False):
                raise RuntimeError("credential_echo")
            return result
        except Exception:
            raise RuntimeError("github_read_failed") from None

    @staticmethod
    def _repository(context: dict[str, Any]) -> str:
        if (context.get("task_inputs") or {}).get("repository") != _REPOSITORY:
            raise ValueError("github_repository_outside_host_scope")
        return _REPOSITORY

    def _main_sha(self, repository: str) -> str:
        response = self._api_get(f"/repos/{repository}/commits/main")
        sha = response.get("sha") if isinstance(response, dict) else None
        if not isinstance(sha, str) or not _SHA.fullmatch(sha):
            raise RuntimeError("github_main_sha_invalid")
        return sha

    @staticmethod
    def _required_files(args: dict[str, Any]) -> list[str]:
        files = args.get("required_files")
        allowed = {"AGENTS.md", "AI_AGENT_REQUIREMENTS.md", "WORK_STATUS.md"}
        if (args.get("ref", "main") != "main" or not isinstance(files, list)
                or not files or any(not isinstance(p, str) or p not in allowed for p in files)
                or len(set(files)) != len(files)):
            raise ValueError("github_file_scope_invalid")
        return files

    def _read_main(self, *, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        repository = self._repository(context)
        required = self._required_files(args)
        sha = self._main_sha(repository)
        files = {}
        for path in required:
            response = self._api_get(
                f"/repos/{repository}/contents/{quote(path, safe='')}?{urlencode({'ref': sha})}"
            )
            if (not isinstance(response, dict) or response.get("type") != "file"
                    or response.get("path") != path or response.get("encoding") != "base64"
                    or not isinstance(response.get("sha"), str)
                    or not _SHA.fullmatch(response["sha"])
                    or not isinstance(response.get("content"), str)):
                raise RuntimeError("github_file_invalid")
            try:
                raw = base64.b64decode("".join(response["content"].split()), validate=True)
                text = raw.decode("utf-8")
            except (ValueError, binascii.Error, UnicodeDecodeError):
                raise RuntimeError("github_file_invalid_encoding") from None
            if not text.strip() or type(response.get("size")) is not int or response["size"] != len(raw):
                raise RuntimeError("github_file_empty_or_size_mismatch")
            blob_sha = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
            if response["sha"] != blob_sha:
                raise RuntimeError("github_blob_identity_mismatch")
            files[path] = {"sha": response["sha"], "size": len(raw), "verified_nonempty_text": True}
        return {"message": "required files observed at one commit", "data": {
            "repository": repository, "ref": "main", "observed_sha": sha, "files": files,
        }}

    def _verify_ci(self, *, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        repository = self._repository(context)
        result = args.get("action_result")
        evidence = result.get("data") if isinstance(result, dict) else None
        required = self._required_files(args.get("step_args") or {})
        if (args.get("step_action") != "github.read_main" or not isinstance(evidence, dict)
                or evidence.get("repository") != repository or evidence.get("ref") != "main"
                or not isinstance(evidence.get("observed_sha"), str)
                or not _SHA.fullmatch(evidence["observed_sha"])
                or not isinstance(evidence.get("files"), dict)
                or set(evidence["files"]) != set(required)):
            raise RuntimeError("github_observation_required")
        for item in evidence["files"].values():
            if (not isinstance(item, dict) or item.get("verified_nonempty_text") is not True
                    or not isinstance(item.get("sha"), str) or not _SHA.fullmatch(item["sha"])
                    or type(item.get("size")) is not int or item["size"] <= 0):
                raise RuntimeError("github_observation_invalid")
        sha = evidence["observed_sha"]
        runs = self._runs(repository, sha)
        states = {}
        for path, workflow_id in _WORKFLOWS.items():
            candidates = [r for r in runs if r.get("workflow_id") == workflow_id
                          and r.get("path") == path and r.get("head_sha") == sha
                          and r.get("head_branch") == "main" and r.get("event") == "push"]
            for run in candidates:
                if any(type(run.get(k)) is not int or run[k] <= 0
                       for k in ("id", "run_number", "run_attempt")):
                    raise RuntimeError("github_run_identity_invalid")
            latest = max(candidates, key=lambda r: (r["run_number"], r["run_attempt"], r["id"]), default=None)
            states[path] = {"workflow_id": workflow_id, "found": latest is not None,
                            "verified": latest is not None and latest.get("status") == "completed"
                            and latest.get("conclusion") == "success"}
            if latest:
                states[path].update({k: latest.get(k) for k in
                                    ("id", "run_attempt", "head_sha", "status", "conclusion")})
        current_sha = self._main_sha(repository)
        verified = current_sha == sha and all(s["verified"] for s in states.values())
        return {"message": "same-commit CI verified" if verified else "same-commit CI not verified",
                "data": {"verified": verified, "repository": repository, "observed_sha": sha,
                         "current_sha": current_sha,
                         "reason": "main_changed" if current_sha != sha else
                         ("verified" if verified else "required_ci_not_successful"),
                         "files": deepcopy(evidence["files"]), "workflows": states}}

    def _runs(self, repository: str, sha: str) -> list[dict[str, Any]]:
        runs = []
        total = None
        # GitHub caps filtered searches at 1,000 runs. Fail closed above that cap.
        for page in range(1, 11):
            query = urlencode({"head_sha": sha, "branch": "main", "event": "push",
                               "per_page": 100, "page": page})
            payload = self._api_get(f"/repos/{repository}/actions/runs?{query}")
            if not isinstance(payload, dict) or not isinstance(payload.get("workflow_runs"), list):
                raise RuntimeError("github_actions_runs_missing")
            count = payload.get("total_count")
            batch = payload["workflow_runs"]
            if (type(count) is not int or not 0 <= count <= 1000
                    or (total is not None and total != count) or len(batch) > 100
                    or any(not isinstance(r, dict) for r in batch)):
                raise RuntimeError("github_ci_pagination_inconsistent")
            total = count
            runs.extend(batch)
            ids = [r.get("id") for r in runs]
            if any(type(i) is not int for i in ids) or len(set(ids)) != len(ids) or len(runs) > total:
                raise RuntimeError("github_ci_pagination_inconsistent")
            if len(runs) == total:
                return runs
            if len(batch) < 100:
                raise RuntimeError("github_ci_pagination_incomplete")
        raise RuntimeError("github_ci_pagination_incomplete")
