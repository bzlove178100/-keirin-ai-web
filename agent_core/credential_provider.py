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
        if not provider_id.strip():
            raise ValueError("provider_id_required")
        normalized_caps = tuple(sorted({str(value).strip() for value in capabilities if str(value).strip()}))
        if not normalized_caps:
            raise ValueError("credential_capabilities_required")
        copied = {str(name): str(value) for name, value in secrets.items()}
        if not copied or any(not name.strip() or not value for name, value in copied.items()):
            raise ValueError("non_empty_runtime_secrets_required")

        self._provider_id = provider_id.strip()
        self._account_label = account_label.strip() if isinstance(account_label, str) and account_label.strip() else None
        self._capabilities = normalized_caps
        self._issued_at = issued_at
        self._expires_at = expires_at
        self._refresh_capable = bool(refresh_capable)
        self._secrets = MappingProxyType(copied)
        self._created_at = int(created_at)

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
        try:
            return self._secrets[name]
        except KeyError as exc:
            raise CredentialProviderError(f"credential_secret_not_available:{name}") from exc

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
        if not provider_id.strip():
            raise ValueError("provider_id_required")
        caps = tuple(sorted({str(value).strip() for value in capabilities if str(value).strip()}))
        if not caps:
            raise ValueError("credential_capabilities_required")
        copied = {str(name): str(value) for name, value in secrets.items()}
        if not copied or any(not name.strip() or not value for name, value in copied.items()):
            raise ValueError("non_empty_runtime_secrets_required")
        if issued_at is not None and expires_at is not None and int(expires_at) <= int(issued_at):
            raise ValueError("credential_expiry_must_follow_issue_time")

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
        if isinstance(minimum_ttl_seconds, bool) or minimum_ttl_seconds < 0:
            raise ValueError("minimum_ttl_seconds_must_be_non_negative")

        required = tuple(sorted({str(value).strip() for value in required_capabilities if str(value).strip()}))
        missing = tuple(value for value in required if value not in self._capabilities)
        if missing:
            raise CredentialScopeError("credential_capability_mismatch:" + ",".join(missing))

        now = int(time.time()) if now_epoch is None else int(now_epoch)
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
