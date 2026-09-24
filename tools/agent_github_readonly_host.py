from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_core import BoundRuntime, RuntimeManifest  # noqa: E402
from agent_core.adapters import Capability  # noqa: E402


class GitHubReadOnlyBridge:
    """GitHub Actions host bridge with read-only repository/actions access.

    The workflow supplies the ephemeral ``GITHUB_TOKEN``. The token is never written to
    task state, output JSON, artifacts or the repository.
    """

    def __init__(
        self,
        *,
        token: str,
        api_get: Callable[[str], Any] | None = None,
        required_workflows: tuple[str, ...] = (
            "keirin-ai regression",
            "collection progress UI regression",
        ),
    ) -> None:
        if not token.strip():
            raise ValueError("github_token_required")
        self._token = token
        self._api_get_override = api_get
        self.required_workflows = required_workflows
        self.audit: list[dict[str, Any]] = []

    def _api_get(self, path: str) -> Any:
        if self._api_get_override is not None:
            return self._api_get_override(path)
        request = Request(
            f"https://api.github.com{path}",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "User-Agent": "keirin-ai-agent-readonly-worker",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"github_read_failed:{exc.code}:{body}") from exc

    @staticmethod
    def _repository(context: dict[str, Any]) -> str:
        repository = str((context.get("task_inputs") or {}).get("repository") or "").strip()
        if not repository or "/" not in repository:
            raise ValueError("repository_input_required")
        return repository

    def invoke(self, *, capability: Capability, args: dict[str, Any], context: dict[str, Any]) -> Any:
        self.audit.append(
            {
                "action": capability.action,
                "access": capability.access,
                "required_permissions": list(capability.required_permissions),
            }
        )
        if capability.access != "read":
            return {"blocked_reason": f"read_only_worker_forbids:{capability.action}"}
        if capability.action == "github.read_main":
            return self._read_main(args=args, context=context)
        if capability.action == "github.verify_ci":
            return self._verify_ci(args=args, context=context)
        return {"blocked_reason": f"unsupported_read_action:{capability.action}"}

    def _read_main(self, *, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        repository = self._repository(context)
        ref = str(args.get("ref") or "main")
        required_files = [str(value) for value in args.get("required_files") or ()]
        if not required_files:
            raise ValueError("required_files_missing")

        files: dict[str, dict[str, Any]] = {}
        for file_path in required_files:
            encoded_path = quote(file_path, safe="/")
            query = urlencode({"ref": ref})
            payload = self._api_get(f"/repos/{repository}/contents/{encoded_path}?{query}")
            if not isinstance(payload, dict) or payload.get("type") != "file":
                raise RuntimeError(f"github_file_not_resolved:{file_path}")
            content = payload.get("content")
            encoding = payload.get("encoding")
            decoded_text: str | None = None
            if encoding == "base64" and isinstance(content, str):
                decoded_text = base64.b64decode(content).decode("utf-8")
                if not decoded_text.strip():
                    raise RuntimeError(f"github_file_empty:{file_path}")
            files[file_path] = {
                "sha": payload.get("sha"),
                "size": payload.get("size"),
                "verified_nonempty_text": decoded_text is not None,
            }

        return {
            "message": f"verified {len(files)} required files on {ref}",
            "data": {
                "repository": repository,
                "ref": ref,
                "files": files,
            },
        }

    def _verify_ci(self, *, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        repository = self._repository(context)
        ref = "main"
        query = urlencode({"branch": ref, "status": "completed", "per_page": 50})
        payload = self._api_get(f"/repos/{repository}/actions/runs?{query}")
        runs = payload.get("workflow_runs") if isinstance(payload, dict) else None
        if not isinstance(runs, list):
            raise RuntimeError("github_actions_runs_missing")

        latest_by_name: dict[str, dict[str, Any]] = {}
        for run in runs:
            if not isinstance(run, dict):
                continue
            name = str(run.get("name") or "")
            if name in self.required_workflows and name not in latest_by_name:
                latest_by_name[name] = run

        workflow_state: dict[str, dict[str, Any]] = {}
        verified = True
        for name in self.required_workflows:
            run = latest_by_name.get(name)
            if run is None:
                verified = False
                workflow_state[name] = {"found": False, "conclusion": None, "run_id": None}
                continue
            conclusion = str(run.get("conclusion") or "")
            if conclusion != "success":
                verified = False
            workflow_state[name] = {
                "found": True,
                "conclusion": conclusion,
                "run_id": run.get("id"),
                "head_sha": run.get("head_sha"),
                "created_at": run.get("created_at"),
            }

        return {
            "message": "existing main CI verified" if verified else "required main CI is not fully successful",
            "data": {
                "verified": verified,
                "repository": repository,
                "ref": ref,
                "workflows": workflow_state,
            },
        }


def runtime_manifest() -> RuntimeManifest:
    return RuntimeManifest.from_dict(
        {
            "schema_version": "agent-runtime-bindings-v1",
            "bindings": [
                {
                    "provider": "github-actions",
                    "action": "github.read_main",
                    "access": "read",
                    "required_permissions": ["contents:read"],
                    "supports_dry_run": True,
                    "description": "Live GitHub Actions binding for repository contents read.",
                },
                {
                    "provider": "github-actions",
                    "action": "github.verify_ci",
                    "access": "read",
                    "required_permissions": ["actions:read"],
                    "supports_dry_run": True,
                    "description": "Live GitHub Actions binding for existing workflow-run verification.",
                },
            ],
        }
    )


def run_worker(*, token: str, repository: str, state_dir: str | Path, task_path: str | Path) -> dict[str, Any]:
    bridge = GitHubReadOnlyBridge(token=token)
    runtime = BoundRuntime(manifest=runtime_manifest(), bridge=bridge, state_dir=state_dir)
    outcome = runtime.run_task_file(task_path, allowed_access={"read"})
    return {
        "task_id": outcome.task_id,
        "status": outcome.status,
        "completed_steps": list(outcome.completed_steps),
        "executed_steps": list(outcome.executed_steps),
        "skipped_steps": list(outcome.skipped_steps),
        "blocked_reason": outcome.blocked_reason,
        "last_error": outcome.last_error,
        "repository": repository,
        "capability_audit": bridge.audit,
    }


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required")
    if not repository:
        raise SystemExit("GITHUB_REPOSITORY is required")

    state_dir = Path(os.environ.get("AGENT_STATE_DIR") or os.environ.get("RUNNER_TEMP") or "/tmp") / "keirin-agent-state"
    task_path = Path(
        os.environ.get("AGENT_TASK_FILE")
        or ROOT / "agent_core" / "examples" / "keirin_readonly_status_task.json"
    )
    result = run_worker(
        token=token,
        repository=repository,
        state_dir=state_dir,
        task_path=task_path,
    )
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    print(encoded)

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write("## Shared agent read-only runtime smoke\n\n")
            handle.write("```json\n")
            handle.write(encoded)
            handle.write("\n```\n")

    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
