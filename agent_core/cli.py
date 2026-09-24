from __future__ import annotations

import argparse
import json
from pathlib import Path

from .model import TaskSpec
from .runtime import RuntimeManifest
from .store import FileStateStore


def _load_task(path: str) -> TaskSpec:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return TaskSpec.from_dict(payload)


def cmd_validate_task(args: argparse.Namespace) -> int:
    spec = _load_task(args.task)
    print(json.dumps(spec.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_validate_manifest(args: argparse.Namespace) -> int:
    manifest = RuntimeManifest.load(args.manifest)
    payload = {
        "schema_version": manifest.schema_version,
        "bindings": [
            {
                "provider": binding.provider,
                "action": binding.action,
                "access": binding.access,
                "required_permissions": list(binding.required_permissions),
                "supports_dry_run": binding.supports_dry_run,
                "description": binding.description,
            }
            for binding in manifest.bindings
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_show_state(args: argparse.Namespace) -> int:
    store = FileStateStore(args.state_dir)
    state = store.load_state(args.task_id)
    print(json.dumps(state.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_reconcile(args: argparse.Namespace) -> int:
    store = FileStateStore(args.state_dir)
    state = store.reconcile_blocked_step(
        args.task_id,
        step_id=args.step_id,
        resolution=args.resolution,
        note=args.note,
    )
    print(json.dumps(state.to_dict(), ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m agent_core.cli",
        description="Credential-free task/state utilities for the shared autonomous-agent runtime.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    validate_task = sub.add_parser("validate-task", help="Validate and normalize a TaskSpec JSON file.")
    validate_task.add_argument("--task", required=True)
    validate_task.set_defaults(func=cmd_validate_task)

    validate_manifest = sub.add_parser(
        "validate-manifest",
        help="Validate a credential-free runtime binding manifest.",
    )
    validate_manifest.add_argument("--manifest", required=True)
    validate_manifest.set_defaults(func=cmd_validate_manifest)

    show_state = sub.add_parser("show-state", help="Read a private task-state file.")
    show_state.add_argument("--state-dir", required=True)
    show_state.add_argument("--task-id", required=True)
    show_state.set_defaults(func=cmd_show_state)

    reconcile = sub.add_parser(
        "reconcile",
        help="Explicitly reconcile a blocked step after external verification.",
    )
    reconcile.add_argument("--state-dir", required=True)
    reconcile.add_argument("--task-id", required=True)
    reconcile.add_argument("--step-id", required=True)
    reconcile.add_argument(
        "--resolution",
        required=True,
        choices=("not_applied", "applied_and_verified", "needs_manual_action"),
    )
    reconcile.add_argument("--note", required=True)
    reconcile.set_defaults(func=cmd_reconcile)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
