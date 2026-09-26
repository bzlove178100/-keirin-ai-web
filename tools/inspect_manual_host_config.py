from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_core.runtime_credentials import inspect_runtime_credentials  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect manual one-shot host runtime configuration without network I/O or secret output."
    )
    parser.add_argument("--instance-token", required=True)
    parser.add_argument("--minimum-known-ttl-seconds", type=int, default=300)
    parser.add_argument("--require-manual-ready", action="store_true")
    args = parser.parse_args(argv)

    report = inspect_runtime_credentials(
        os.environ,
        instance_token=args.instance_token,
        minimum_known_ttl_seconds=args.minimum_known_ttl_seconds,
        refresh_provider_configured=False,
    )
    print(json.dumps(report.to_safe_dict(), ensure_ascii=False, sort_keys=True))
    if args.require_manual_ready and not report.manual_ready:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
