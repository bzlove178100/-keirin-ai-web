from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

from .activation import TRUSTED_TASK_FINGERPRINT, TRUSTED_TASK_ID
from .model import TaskSpec

TRUSTED_RUN_ID_PREFIX = TRUSTED_TASK_ID + "."
_INSTANCE_TOKEN_RE = re.compile(r"^[0-9a-f]{16,32}$")


@dataclass(frozen=True)
class TrustedRunInstance:
    task_id: str
    instance_token: str
    instance_fingerprint: str
    template_fingerprint: str


def trusted_status_template_spec(*, repo_root: str | Path | None = None) -> TaskSpec:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[1]
    path = root / "agent_core/examples/keirin_readonly_status_task.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    spec = TaskSpec.from_dict(payload)
    if spec.task_id != TRUSTED_TASK_ID or spec.fingerprint() != TRUSTED_TASK_FINGERPRINT:
        raise ValueError("trusted_status_template_changed")
    return spec


def _instance_token(task_id: str) -> str:
    if not isinstance(task_id, str) or not task_id.startswith(TRUSTED_RUN_ID_PREFIX):
        raise ValueError("trusted_run_instance_id_required")
    token = task_id[len(TRUSTED_RUN_ID_PREFIX):]
    if not _INSTANCE_TOKEN_RE.fullmatch(token):
        raise ValueError("invalid_trusted_run_instance_token")
    return token


def build_trusted_status_run_spec(instance_token: str, *, repo_root: str | Path | None = None) -> TaskSpec:
    if not isinstance(instance_token, str) or not _INSTANCE_TOKEN_RE.fullmatch(instance_token):
        raise ValueError("invalid_trusted_run_instance_token")
    template = trusted_status_template_spec(repo_root=repo_root)
    payload = template.to_dict()
    payload["task_id"] = TRUSTED_RUN_ID_PREFIX + instance_token
    return TaskSpec.from_dict(payload)


def validate_trusted_status_run_spec(spec: TaskSpec, *, repo_root: str | Path | None = None) -> TrustedRunInstance:
    candidate = TaskSpec.from_dict(spec.to_dict())
    token = _instance_token(candidate.task_id)
    template = trusted_status_template_spec(repo_root=repo_root)

    canonical_payload = candidate.to_dict()
    canonical_payload["task_id"] = TRUSTED_TASK_ID
    canonical = TaskSpec.from_dict(canonical_payload)
    if canonical.to_dict() != template.to_dict():
        raise ValueError("trusted_run_instance_scope_mismatch")
    if canonical.fingerprint() != TRUSTED_TASK_FINGERPRINT:
        raise ValueError("trusted_run_instance_template_fingerprint_mismatch")

    return TrustedRunInstance(
        task_id=candidate.task_id,
        instance_token=token,
        instance_fingerprint=candidate.fingerprint(),
        template_fingerprint=canonical.fingerprint(),
    )


def is_trusted_status_run_spec(spec: TaskSpec, *, repo_root: str | Path | None = None) -> bool:
    try:
        validate_trusted_status_run_spec(spec, repo_root=repo_root)
    except (KeyError, TypeError, ValueError):
        return False
    return True
