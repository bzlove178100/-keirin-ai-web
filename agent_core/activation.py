from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .model import TaskSpec

ACTIVATION_SCHEMA_VERSION = "agent-host-activation-v1"
TRUSTED_REPOSITORY = "bzlove178100/-keirin-ai-web"
TRUSTED_TASK_FILE = "agent_core/examples/keirin_readonly_status_task.json"
TRUSTED_TASK_ID = "keirin-readonly-status-check"
TRUSTED_TASK_FINGERPRINT = "sha256-v1:f9af0209ae2545d096d9c04cf4cfe5d434b90407bfc6aaa73ca0c6445d749403"
TRUSTED_ACTIONS = ("github.read_main", "github.verify_ci")
TRUSTED_GITHUB_PERMISSIONS = ("actions:read", "contents:read")


@dataclass(frozen=True)
class HostedActivationManifest:
    schema_version: str
    activation_enabled: bool
    mode: str
    max_tasks: int
    scheduler_enabled: bool
    recurrence_enabled: bool
    allowed_access: tuple[str, ...]
    repository: str
    task_file: str
    task_id: str
    task_fingerprint: str
    actions: tuple[str, ...]
    github_permissions: tuple[str, ...]
    safety: dict[str, bool]

    @property
    def live_execution_authorized(self) -> bool:
        # A committed manifest is never the user's live authorization signal.
        return False


def _bool(value: Any, name: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{name}_must_be_boolean")
    return value


def _string_tuple(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"invalid_{name}")
    result = tuple(value)
    if len(result) != len(set(result)):
        raise ValueError(f"duplicate_{name}")
    return result


def _trusted_task(repo_root: Path, task_file: str) -> TaskSpec:
    if task_file != TRUSTED_TASK_FILE:
        raise ValueError("untrusted_task_file")
    root = repo_root.resolve()
    path = (root / task_file).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("task_file_outside_repository") from exc
    if not path.is_file():
        raise ValueError("trusted_task_file_missing")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return TaskSpec.from_dict(payload)


def validate_hosted_activation_manifest(payload: dict[str, Any], *, repo_root: str | Path) -> HostedActivationManifest:
    if not isinstance(payload, dict):
        raise ValueError("activation_manifest_object_required")
    if payload.get("schema_version") != ACTIVATION_SCHEMA_VERSION:
        raise ValueError("activation_schema_mismatch")

    activation_enabled = _bool(payload.get("activation_enabled"), "activation_enabled")
    scheduler_enabled = _bool(payload.get("scheduler_enabled"), "scheduler_enabled")
    recurrence_enabled = _bool(payload.get("recurrence_enabled"), "recurrence_enabled")
    if activation_enabled:
        raise ValueError("committed_activation_must_be_disabled")
    if scheduler_enabled or recurrence_enabled:
        raise ValueError("scheduler_or_recurrence_forbidden")
    if payload.get("mode") != "single_run":
        raise ValueError("single_run_mode_required")
    if type(payload.get("max_tasks")) is not int or payload.get("max_tasks") != 1:
        raise ValueError("max_tasks_must_equal_one")

    allowed_access = _string_tuple(payload.get("allowed_access"), "allowed_access")
    if allowed_access != ("read",):
        raise ValueError("read_only_access_required")
    repository = payload.get("repository")
    if repository != TRUSTED_REPOSITORY:
        raise ValueError("repository_scope_mismatch")
    task_file = payload.get("task_file")
    if not isinstance(task_file, str):
        raise ValueError("task_file_required")
    task_id = payload.get("task_id")
    if task_id != TRUSTED_TASK_ID:
        raise ValueError("task_id_scope_mismatch")
    task_fingerprint = payload.get("task_fingerprint")
    if task_fingerprint != TRUSTED_TASK_FINGERPRINT:
        raise ValueError("task_fingerprint_scope_mismatch")

    actions = _string_tuple(payload.get("actions"), "actions")
    if actions != TRUSTED_ACTIONS:
        raise ValueError("action_scope_mismatch")
    github_permissions = tuple(sorted(_string_tuple(payload.get("github_permissions"), "github_permissions")))
    if github_permissions != TRUSTED_GITHUB_PERMISSIONS:
        raise ValueError("github_permission_scope_mismatch")

    safety = payload.get("safety")
    required_safety = {
        "github_write_enabled": False,
        "production_prediction_enabled": False,
        "keirin_prediction_db_write_enabled": False,
        "external_keirin_auto_fetch_enabled": False,
        "provider_generation_enabled": False,
        "report_delivery_enabled": False,
    }
    if not isinstance(safety, dict) or safety != required_safety:
        raise ValueError("activation_safety_contract_mismatch")

    spec = _trusted_task(Path(repo_root), task_file)
    if spec.task_id != task_id:
        raise ValueError("manifest_task_id_does_not_match_task")
    if spec.fingerprint() != task_fingerprint or spec.fingerprint() != TRUSTED_TASK_FINGERPRINT:
        raise ValueError("manifest_task_fingerprint_does_not_match_task")
    used_actions = tuple(dict.fromkeys(
        action
        for step in spec.steps
        for action in (step.action, step.verify_action)
        if action
    ))
    if used_actions != actions or tuple(spec.allowed_actions) != actions:
        raise ValueError("manifest_actions_do_not_match_task")
    if spec.inputs.get("repository") != repository:
        raise ValueError("manifest_repository_does_not_match_task")
    for key in ("production_prediction_enabled", "db_write_enabled", "external_fetch_enabled"):
        if spec.inputs.get(key) is not False:
            raise ValueError(f"trusted_task_safety_input_not_false:{key}")

    return HostedActivationManifest(
        schema_version=ACTIVATION_SCHEMA_VERSION,
        activation_enabled=activation_enabled,
        mode="single_run",
        max_tasks=1,
        scheduler_enabled=scheduler_enabled,
        recurrence_enabled=recurrence_enabled,
        allowed_access=allowed_access,
        repository=repository,
        task_file=task_file,
        task_id=task_id,
        task_fingerprint=task_fingerprint,
        actions=actions,
        github_permissions=github_permissions,
        safety=dict(safety),
    )


def load_hosted_activation_manifest(path: str | Path, *, repo_root: str | Path) -> HostedActivationManifest:
    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return validate_hosted_activation_manifest(payload, repo_root=repo_root)
