from __future__ import annotations

from dataclasses import dataclass
import base64
import json
import time
from typing import Any, Mapping
from urllib.parse import urlparse

PROJECT_URL_ENV = "SUPABASE_PROJECT_URL"
PUBLISHABLE_KEY_ENV = "SUPABASE_PUBLISHABLE_KEY"
OWNER_BEARER_ENV = "SUPABASE_OWNER_BEARER_TOKEN"
GITHUB_TOKEN_ENV = "GITHUB_TOKEN"
AUTHORIZATION_ENV = "KEIRIN_AGENT_SINGLE_RUN_AUTHORIZED"
AUTHORIZED_INSTANCE_ENV = "KEIRIN_AGENT_SINGLE_RUN_INSTANCE_TOKEN"

_REQUIRED_SECRET_NAMES = (
    PROJECT_URL_ENV,
    PUBLISHABLE_KEY_ENV,
    OWNER_BEARER_ENV,
    GITHUB_TOKEN_ENV,
)


@dataclass(frozen=True)
class RuntimeCredentialPreflight:
    manual_ready: bool
    long_lived_ready: bool
    missing: tuple[str, ...]
    invalid: tuple[str, ...]
    warnings: tuple[str, ...]
    project_host: str | None
    owner_bearer_expiry_known: bool
    owner_bearer_expires_at: int | None
    owner_bearer_seconds_remaining: int | None
    refresh_provider_configured: bool
    exact_instance_authorized: bool

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "manual_ready": self.manual_ready,
            "long_lived_ready": self.long_lived_ready,
            "missing": list(self.missing),
            "invalid": list(self.invalid),
            "warnings": list(self.warnings),
            "project_host": self.project_host,
            "owner_bearer_expiry_known": self.owner_bearer_expiry_known,
            "owner_bearer_expires_at": self.owner_bearer_expires_at,
            "owner_bearer_seconds_remaining": self.owner_bearer_seconds_remaining,
            "refresh_provider_configured": self.refresh_provider_configured,
            "exact_instance_authorized": self.exact_instance_authorized,
        }


def _present(env: Mapping[str, str], name: str) -> bool:
    value = env.get(name, "")
    return isinstance(value, str) and bool(value.strip())


def _project_host(value: str) -> tuple[str | None, str | None]:
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or not parsed.netloc:
        return None, "https_project_url_required"
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return None, "project_url_origin_only"
    if parsed.path not in ("", "/"):
        return None, "project_url_origin_only"
    return parsed.netloc, None


def _decode_jwt_exp(token: str) -> tuple[bool, int | None]:
    parts = token.split(".")
    if len(parts) != 3:
        return False, None
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        raw = base64.urlsafe_b64decode((payload + padding).encode("ascii"))
        parsed = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return False, None
    exp = parsed.get("exp") if isinstance(parsed, dict) else None
    if isinstance(exp, bool) or not isinstance(exp, (int, float)):
        return False, None
    return True, int(exp)


def inspect_runtime_credentials(
    env: Mapping[str, str],
    *,
    instance_token: str,
    now_epoch: int | None = None,
    minimum_known_ttl_seconds: int = 300,
    refresh_provider_configured: bool = False,
) -> RuntimeCredentialPreflight:
    """Return a secret-free readiness report for the manual/long-lived host boundary.

    This function performs no network I/O and never returns credential values. A JWT
    `exp` claim is decoded only as an expiry diagnostic; signature/authenticity is not
    asserted here. Real authentication remains the responsibility of the owner-authenticated
    Supabase request path.
    """

    if not isinstance(instance_token, str) or not instance_token:
        raise ValueError("instance_token_required")
    if isinstance(minimum_known_ttl_seconds, bool) or minimum_known_ttl_seconds < 0:
        raise ValueError("minimum_known_ttl_seconds_must_be_non_negative")

    missing = tuple(name for name in _REQUIRED_SECRET_NAMES if not _present(env, name))
    invalid: list[str] = []
    warnings: list[str] = []
    project_host: str | None = None

    project_url = env.get(PROJECT_URL_ENV, "")
    if PROJECT_URL_ENV not in missing:
        project_host, project_error = _project_host(project_url)
        if project_error:
            invalid.append(project_error)

    exact_instance_authorized = (
        env.get(AUTHORIZATION_ENV) == "true"
        and isinstance(env.get(AUTHORIZED_INSTANCE_ENV), str)
        and env.get(AUTHORIZED_INSTANCE_ENV, "").strip() == instance_token
    )
    if env.get(AUTHORIZATION_ENV) != "true":
        invalid.append("single_run_runtime_authorization_required")
    elif not exact_instance_authorized:
        invalid.append("single_run_instance_authorization_mismatch")

    expiry_known = False
    expires_at: int | None = None
    seconds_remaining: int | None = None
    owner_bearer = env.get(OWNER_BEARER_ENV, "")
    if OWNER_BEARER_ENV not in missing:
        expiry_known, expires_at = _decode_jwt_exp(owner_bearer)
        if expiry_known and expires_at is not None:
            now = int(time.time()) if now_epoch is None else int(now_epoch)
            seconds_remaining = expires_at - now
            if seconds_remaining <= 0:
                invalid.append("owner_bearer_expired")
            elif seconds_remaining < minimum_known_ttl_seconds:
                invalid.append("owner_bearer_ttl_below_minimum")
        else:
            warnings.append("owner_bearer_expiry_unknown")

    if not refresh_provider_configured:
        warnings.append("refresh_provider_unconfigured")

    manual_ready = not missing and not invalid and exact_instance_authorized
    long_lived_ready = manual_ready and refresh_provider_configured and expiry_known

    return RuntimeCredentialPreflight(
        manual_ready=manual_ready,
        long_lived_ready=long_lived_ready,
        missing=missing,
        invalid=tuple(invalid),
        warnings=tuple(warnings),
        project_host=project_host,
        owner_bearer_expiry_known=expiry_known,
        owner_bearer_expires_at=expires_at,
        owner_bearer_seconds_remaining=seconds_remaining,
        refresh_provider_configured=refresh_provider_configured,
        exact_instance_authorized=exact_instance_authorized,
    )
