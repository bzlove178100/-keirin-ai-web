from __future__ import annotations

from agent_core.single_run_host import (
    AUTHORIZATION_ENV,
    GITHUB_TOKEN_ENV,
    OWNER_BEARER_ENV,
    PROJECT_URL_ENV,
    PUBLISHABLE_KEY_ENV,
    run_once,
)

__all__ = [
    "AUTHORIZATION_ENV",
    "GITHUB_TOKEN_ENV",
    "OWNER_BEARER_ENV",
    "PROJECT_URL_ENV",
    "PUBLISHABLE_KEY_ENV",
    "run_once",
]


if __name__ == "__main__":
    raise SystemExit(run_once())
