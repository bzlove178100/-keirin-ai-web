from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_core.single_run_host import (  # noqa: E402
    AUTHORIZATION_ENV,
    AUTHORIZED_INSTANCE_ENV,
    GITHUB_TOKEN_ENV,
    OWNER_BEARER_ENV,
    PROJECT_URL_ENV,
    PUBLISHABLE_KEY_ENV,
    run_once,
)

__all__ = [
    "AUTHORIZATION_ENV",
    "AUTHORIZED_INSTANCE_ENV",
    "GITHUB_TOKEN_ENV",
    "OWNER_BEARER_ENV",
    "PROJECT_URL_ENV",
    "PUBLISHABLE_KEY_ENV",
    "run_once",
]


if __name__ == "__main__":
    raise SystemExit(run_once())
