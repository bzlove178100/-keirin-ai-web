from __future__ import annotations

import argparse
import json
import os

from agent_core.hosted_checkpoint import HostedCheckpointClient
from agent_core.hosted_transport import SupabaseEdgeTransport
from agent_core.trusted_run_enqueue import TrustedRunEnqueuer
from agent_core.trusted_run_instance import build_trusted_status_run_spec

PROJECT_URL_ENV = "SUPABASE_PROJECT_URL"
PUBLISHABLE_KEY_ENV = "SUPABASE_PUBLISHABLE_KEY"
OWNER_BEARER_ENV = "SUPABASE_OWNER_BEARER_TOKEN"


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"missing_runtime_secret:{name}")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create or verify one pristine trusted run-instance checkpoint without claiming or executing it."
    )
    parser.add_argument("--instance-token", required=True)
    args = parser.parse_args(argv)

    spec = build_trusted_status_run_spec(args.instance_token)
    transport = SupabaseEdgeTransport(
        project_url=_required(PROJECT_URL_ENV),
        publishable_key=_required(PUBLISHABLE_KEY_ENV),
        bearer_token=_required(OWNER_BEARER_ENV),
        function_slug="agent-runtime-dev",
    )
    result = TrustedRunEnqueuer(HostedCheckpointClient(transport)).ensure_queued(spec)
    print(json.dumps({
        "task_id": result.record.task_id,
        "status": result.record.status,
        "revision": result.record.revision,
        "created": result.created,
        "claimed": False,
        "executed": False,
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
