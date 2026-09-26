from __future__ import annotations

import time
from types import MappingProxyType
from typing import Iterable, Mapping, Protocol


class CredentialProviderError(RuntimeError):
    """Fail-closed credential provider boundary error."""


class CredentialScopeError(CredentialProviderError):
    """Requested capability is outside the provider's configured scope."""


class CredentialLifetimeError(CredentialProviderError):
    """Credential lifetime is unknown/insufficient for the requested operation."""


class CredentialRevokedError(CredentialProviderError):
    """Credential source was intentionally revoked/disabled."""


def _seconds(value: object, error: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(error)
    return value


def _capabilities(values: Iterable[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError("credential_capabilities_must_be_collection")
    try:
        items = tuple(values)
    except TypeError:
        raise ValueError("credential_capabilities_must_be_collection") from None
    if not items or any(not isinstance(v, str) or not v.strip() for v in items):
        raise ValueError("credential_capabilities_required")
    return tuple(sorted({v.strip() for v in items}))


def _copy_secrets(secrets: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(secrets, Mapping) or not secrets:
        raise ValueError("non_empty_runtime_secrets_required")
    if any(not isinstance(name, str) or not name.strip()
           or not isinstance(value, str) or not value.strip()
           for name, value in secrets.items()):
        raise ValueError("non_empty_runtime_secrets_required")
    return dict(secrets)


def _validate_times(issued_at: int | None, expires_at: int | None) -> None:
    if issued_at is not None:
        _seconds(issued_at, "credential_issue_time_invalid")
    if expires_at is not None:
        _seconds(expires_at, "credential_expiry_invalid")
    if issued_at is not None and expires_at is not None and expires_at <= issued_at:
        raise ValueError("credential_expiry_must_follow_issue_time")


class CredentialSnapshot:
    """Short-lived in-memory credential view with explicitly redacted metadata output.

    Secret values are intentionally inaccessible to repr/metadata serialization and are
    available only through ``secret(name)`` for a provider adapter that already passed
    capability preflight.
    """

    __slots__ = (
        "_provider_id",
        "_account_label",
        "_capabilities",
        "_issued_at",
        "_expires_at",
        "_refresh_capable",
        "_secrets",
        "_created_at",
    )

    def __init__(
        self,
        *,
        provider_id: str,
        account_label: str | None,
        capabilities: Iterable[str],
        secrets: Mapping[str, str],
        issued_at: int | None,
        expires_at: int | None,
        refresh_capable: bool,
        created_at: int,
    ) -> None:
        if not isinstance(provider_id, str) or not provider_id.strip():
            raise ValueError("provider_id_required")
        normalized_caps = _capabilities(capabilities)
        copied = _copy_secrets(secrets)
        _validate_times(issued_at, expires_at)

        self._provider_id = provider_id.strip()
        self._account_label = account_label.strip() if isinstance(account_label, str) and account_label.strip() else None
        self._capabilities = normalized_caps
        self._issued_at = issued_at
        self._expires_at = expires_at
        self._refresh_capable = bool(refresh_capable)
        self._secrets = MappingProxyType(copied)
        self._created_at = _seconds(created_at, "credential_snapshot_time_invalid")

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def account_label(self) -> str | None:
        return self._account_label

    @property
    def capabilities(self) -> tuple[str, ...]:
        return self._capabilities

    @property
    def issued_at(self) -> int | None:
        return self._issued_at

    @property
    def expires_at(self) -> int | None:
        return self._expires_at

    @property
    def refresh_capable(self) -> bool:
        return self._refresh_capable

    @property
    def secret_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._secrets))

    def secret(self, name: str) -> str:
        if not isinstance(name, str) or name not in self._secrets:
            # Never echo an untrusted lookup value (it may itself be a secret).
            raise CredentialProviderError("credential_secret_not_available")
        return self._secrets[name]

    def to_safe_dict(self) -> dict[str, object]:
        expires_in = None if self._expires_at is None else self._expires_at - self._created_at
        return {
            "provider_id": self._provider_id,
            "account_label": self._account_label,
            "capabilities": list(self._capabilities),
            "issued_at": self._issued_at,
            "expires_at": self._expires_at,
            "expires_in_seconds_at_snapshot": expires_in,
            "refresh_capable": self._refresh_capable,
            "secret_names": list(self.secret_names),
        }

    def __repr__(self) -> str:
        return (
            "CredentialSnapshot("
            f"provider_id={self._provider_id!r}, "
            f"account_label={self._account_label!r}, "
            f"capabilities={self._capabilities!r}, "
            f"expires_at={self._expires_at!r}, "
            f"refresh_capable={self._refresh_capable!r}, "
            "secrets='<redacted>')"
        )


class CredentialProvider(Protocol):
    @property
    def refresh_capable(self) -> bool:
        ...

    def snapshot(
        self,
        required_capabilities: Iterable[str],
        *,
        minimum_ttl_seconds: int = 300,
        require_known_expiry: bool = False,
        now_epoch: int | None = None,
    ) -> CredentialSnapshot:
        ...


class StaticInMemoryCredentialProvider:
    """Manual-host credential provider with no persistence and no refresh behavior.

    This class intentionally cannot refresh itself. It is suitable for a bounded manual
    one-shot host where credentials are injected by the runtime and destroyed with the
    process. A long-lived host must use a separate refresh-capable provider.
    """

    def __init__(
        self,
        *,
        provider_id: str,
        capabilities: Iterable[str],
        secrets: Mapping[str, str],
        account_label: str | None = None,
        issued_at: int | None = None,
        expires_at: int | None = None,
    ) -> None:
        if not isinstance(provider_id, str) or not provider_id.strip():
            raise ValueError("provider_id_required")
        caps = _capabilities(capabilities)
        copied = _copy_secrets(secrets)
        _validate_times(issued_at, expires_at)

        self._provider_id = provider_id.strip()
        self._account_label = account_label.strip() if isinstance(account_label, str) and account_label.strip() else None
        self._capabilities = caps
        self._secrets = copied
        self._issued_at = int(issued_at) if issued_at is not None else None
        self._expires_at = int(expires_at) if expires_at is not None else None
        self._revoked = False

    @property
    def refresh_capable(self) -> bool:
        return False

    def revoke(self) -> None:
        self._revoked = True
        self._secrets.clear()

    def snapshot(
        self,
        required_capabilities: Iterable[str],
        *,
        minimum_ttl_seconds: int = 300,
        require_known_expiry: bool = False,
        now_epoch: int | None = None,
    ) -> CredentialSnapshot:
        if self._revoked:
            raise CredentialRevokedError("credential_provider_revoked")
        _seconds(minimum_ttl_seconds, "minimum_ttl_seconds_must_be_non_negative_integer")
        if type(require_known_expiry) is not bool:
            raise ValueError("require_known_expiry_must_be_boolean")

        required = _capabilities(required_capabilities)
        missing = tuple(value for value in required if value not in self._capabilities)
        if missing:
            raise CredentialScopeError("credential_capability_mismatch")

        now = int(time.time()) if now_epoch is None else _seconds(now_epoch, "credential_now_invalid")
        if self._issued_at is not None and self._issued_at > now:
            raise CredentialLifetimeError("credential_not_yet_valid")
        if self._expires_at is None:
            if require_known_expiry:
                raise CredentialLifetimeError("credential_expiry_unknown")
        else:
            remaining = self._expires_at - now
            if remaining <= 0:
                raise CredentialLifetimeError("credential_expired")
            if remaining < minimum_ttl_seconds:
                raise CredentialLifetimeError("credential_ttl_below_minimum")

        return CredentialSnapshot(
            provider_id=self._provider_id,
            account_label=self._account_label,
            capabilities=self._capabilities,
            secrets=self._secrets,
            issued_at=self._issued_at,
            expires_at=self._expires_at,
            refresh_capable=self.refresh_capable,
            created_at=now,
        )
