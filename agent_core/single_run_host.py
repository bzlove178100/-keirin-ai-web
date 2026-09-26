from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Mapping

from .activation import load_hosted_activation_manifest
from .trusted_run_instance import build_trusted_status_run_spec, validate_trusted_status_run_spec

AUTHORIZATION_ENV = "KEIRIN_AGENT_SINGLE_RUN_AUTHORIZED"
PROJECT_URL_ENV = "SUPABASE_PROJECT_URL"
PUBLISHABLE_KEY_ENV = "SUPABASE_PUBLISHABLE_KEY"
OWNER_BEARER_ENV = "SUPABASE_OWNER_BEARER_TOKEN"
GITHUB_TOKEN_ENV = "GITHUB_TOKEN"


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "")
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"missing_runtime_secret:{name}")
    return value.strip()


def _safe_report(result: Any, recovery: Any, *, interrupted: bool) -> dict[str, Any]:
    outcome = getattr(result, "outcome", None) if result is not None else None
    return {
        "interrupted": interrupted,
        "claimed": bool(getattr(result, "claimed", False)) if result is not None else None,
        "task_id": getattr(result, "task_id", None) if result is not None else getattr(recovery, "task_id", None),
        "execution_enabled": bool(getattr(result, "execution_enabled", False)) if result is not None else True,
        "outcome_status": getattr(outcome, "status", None),
        "blocked_reason": getattr(result, "blocked_reason", None) if result is not None else None,
        "recovery_classification": getattr(recovery, "classification", None),
        "checkpoint_status": getattr(recovery, "checkpoint_status", None),
        "verified": getattr(recovery, "verified", None),
        "reexecution_allowed": getattr(recovery, "reexecution_allowed", None),
    }


def run_once(
    argv: list[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    worker_factory=None,
    recovery_factory=None,
    interrupted_type=None,
    trusted_spec_factory=None,
) -> int:
    """Execute one explicitly authorized read-only hosted run instance, then inspect it.

    The committed activation manifest remains closed. A runtime-only authorization
    signal, explicit CLI execution flag and a fresh trusted instance token are all
    required. The worker is permanently bound to the resulting exact TaskSpec before
    any queue claim, so a completed template task or unrelated FIFO row cannot be
    consumed by this entrypoint.
    """
    parser = argparse.ArgumentParser(description="Run exactly one authorized hosted read-only repository task instance.")
    parser.add_argument("--execute-once", action="store_true")
    parser.add_argument("--instance-token", required=True)
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--lease-seconds", type=int, default=180)
    args = parser.parse_args(argv)

    runtime_env = dict(os.environ if env is None else env)
    if not args.execute_once:
        raise RuntimeError("single_run_cli_flag_required")
    if runtime_env.get(AUTHORIZATION_ENV) != "true":
        raise RuntimeError("single_run_runtime_authorization_required")
    if not 60 <= args.lease_seconds <= 3600:
        raise RuntimeError("lease_seconds_out_of_single_run_range")

    root = Path(__file__).resolve().parents[1]
    manifest_path = root / "agent_core/examples/hosted_readonly_single_run_activation.json"
    manifest = load_hosted_activation_manifest(manifest_path, repo_root=root)
    if manifest.activation_enabled or manifest.scheduler_enabled or manifest.recurrence_enabled:
        raise RuntimeError("committed_manifest_must_remain_closed")
    if manifest.mode != "single_run" or manifest.max_tasks != 1 or manifest.allowed_access != ("read",):
        raise RuntimeError("single_run_manifest_scope_invalid")

    if trusted_spec_factory is None:
        target_spec = build_trusted_status_run_spec(args.instance_token, repo_root=root)
    else:
        target_spec = trusted_spec_factory()
    validate_trusted_status_run_spec(target_spec, repo_root=root)

    project_url = _required(runtime_env, PROJECT_URL_ENV)
    publishable_key = _required(runtime_env, PUBLISHABLE_KEY_ENV)
    owner_bearer = _required(runtime_env, OWNER_BEARER_ENV)
    github_token = _required(runtime_env, GITHUB_TOKEN_ENV)

    if worker_factory is None or recovery_factory is None or interrupted_type is None:
        from tools.agent_hosted_repository_worker import HostedRunInterrupted
        from tools.prepare_exact_run_instance_worker import prepare_exact_run_instance_worker
        from tools.prepare_hosted_recovery import prepare_hosted_recovery

        worker_factory = worker_factory or prepare_exact_run_instance_worker
        recovery_factory = recovery_factory or prepare_hosted_recovery
        interrupted_type = interrupted_type or HostedRunInterrupted

    worker = worker_factory(
        project_url=project_url,
        publishable_key=publishable_key,
        owner_bearer_token=owner_bearer,
        github_token=github_token,
        execution_authorized=True,
        target_spec=target_spec,
    )

    try:
        result = worker.run_next(worker_id=args.worker_id, lease_seconds=args.lease_seconds)
    except interrupted_type:
        recovery = recovery_factory(
            project_url=project_url,
            publishable_key=publishable_key,
            owner_bearer_token=owner_bearer,
        ).inspect(target_spec)
        print(json.dumps(_safe_report(None, recovery, interrupted=True), ensure_ascii=False, sort_keys=True))
        return 2

    recovery = recovery_factory(
        project_url=project_url,
        publishable_key=publishable_key,
        owner_bearer_token=owner_bearer,
    ).inspect(target_spec)
    print(json.dumps(_safe_report(result, recovery, interrupted=False), ensure_ascii=False, sort_keys=True))
    return 0 if getattr(recovery, "classification", "").startswith("completed_") else 1
