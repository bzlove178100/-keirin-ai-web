"""Access-only refresh boundary. No concrete secret store or network client is bound."""
from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
import time
from typing import Callable, Iterable, Protocol

from .credential_provider import (
    CredentialProviderError, CredentialRevokedError, CredentialScopeError,
    CredentialSnapshot, _capabilities, _seconds, _validate_times,
)


class CredentialAuthBlocked(CredentialProviderError):
    """Authentication needs explicit host remediation; never retry automatically."""


class CredentialRefreshInProgress(CredentialProviderError):
    """Another caller owns this provider's issuance/refresh boundary."""


@dataclass(frozen=True, slots=True)
class CredentialBinding:
    """Trusted, non-secret host configuration; never derive it from task input."""

    provider_id: str
    account_id: str
    capabilities: tuple[str, ...]

    def __post_init__(self) -> None:
        for value in (self.provider_id, self.account_id):
            if not isinstance(value, str) or not value.strip() or value != value.strip():
                raise ValueError('credential_identity_required')
        object.__setattr__(self, 'capabilities', _capabilities(self.capabilities))


@dataclass(frozen=True, slots=True, repr=False)
class AccessCredentialGrant:
    """Host-source result containing access material only, never refresh material.

    Do not use dataclasses.asdict or generic serialization on this object.
    Identity and times are untrusted until the provider checks them.
    """

    provider_id: str
    account_id: str
    capabilities: tuple[str, ...]
    access_token: str = field(repr=False)
    issued_at: int
    expires_at: int

    def __repr__(self) -> str:
        return 'AccessCredentialGrant(<redacted>)'


class HostCredentialSource(Protocol):
    """Host-only boundary owning secret-store access and refresh-token rotation.

    Implementations must check revocation, verify remote identity/scope and durably
    save any rotated refresh secret before returning an access-only grant. They must
    enforce bounded I/O and must not retry ambiguous refresh outcomes. No implementation
    is activated by this protocol. Runners/adapters must never receive this source.
    """

    def assert_available(self) -> None:
        """Raise CredentialRevokedError if disabled; other failures block auth."""
        ...

    def refresh_access(
        self, binding: CredentialBinding, *, minimum_ttl_seconds: int,
    ) -> AccessCredentialGrant:
        ...


class RefreshingCredentialProvider:
    """Single-process refresh ownership with terminal blocked/revoked states.

    Source ownership must be exclusive to this instance in a host. Distributed
    secret-store fencing, real authentication and runner wiring are not implemented.
    """

    def __init__(self, binding: CredentialBinding, source: HostCredentialSource | None,
                 *, clock: Callable[[], int] | None = None) -> None:
        if type(binding) is not CredentialBinding:
            raise ValueError('credential_binding_required')
        self._binding = binding
        self._source = source
        self._clock = clock or (lambda: int(time.time()))
        self._lock = Lock()
        self._busy = False
        self._state = 'unconfigured' if source is None else 'refresh_required'
        self._failure: str | None = None
        self._grant: AccessCredentialGrant | None = None
        self._generation = 0
        self._time_anchor: tuple[int, float] | None = None

    @property
    def refresh_capable(self) -> bool:
        # A capability description, not authorization or a readiness signal.
        return True

    def to_safe_dict(self) -> dict[str, object]:
        with self._lock:
            return {
                'provider_id': self._binding.provider_id,
                'account_id': self._binding.account_id,
                'capabilities': list(self._binding.capabilities),
                'state': self._state,
                'refresh_capable': True,
                'generation': self._generation,
                'failure': self._failure,
                'expires_at': self._grant.expires_at if self._grant else None,
            }

    def __repr__(self) -> str:
        return f'RefreshingCredentialProvider({self.to_safe_dict()!r})'

    def revoke(self) -> None:
        with self._lock:
            self._state = 'revoked'
            self._failure = 'credential_provider_revoked'
            self._grant = None

    def _assert_issuance_allowed(self) -> None:
        if self._state == 'revoked':
            raise CredentialRevokedError('credential_provider_revoked')
        if self._state in ('unconfigured', 'blocked_auth'):
            raise CredentialAuthBlocked('credential_auth_unavailable')
        if self._busy:
            raise CredentialRefreshInProgress('credential_refresh_in_progress')

    def _validate_grant(self, grant: AccessCredentialGrant, now: int, minimum: int) -> None:
        if type(grant) is not AccessCredentialGrant:
            raise ValueError('invalid_access_grant')
        if (grant.provider_id != self._binding.provider_id
                or grant.account_id != self._binding.account_id):
            raise ValueError('credential_identity_mismatch')
        if _capabilities(grant.capabilities) != self._binding.capabilities:
            raise ValueError('credential_scope_changed')
        if not isinstance(grant.access_token, str) or not grant.access_token.strip():
            raise ValueError('invalid_access_token')
        _seconds(grant.issued_at, 'invalid_issue_time')
        _seconds(grant.expires_at, 'invalid_expiry')
        _validate_times(grant.issued_at, grant.expires_at)
        if grant.issued_at > now or grant.expires_at <= now or grant.expires_at - now < minimum:
            raise ValueError('invalid_access_lifetime')

    def snapshot(self, required_capabilities: Iterable[str], *,
                 minimum_ttl_seconds: int = 300, require_known_expiry: bool = False,
                 now_epoch: int | None = None) -> CredentialSnapshot:
        required = _capabilities(required_capabilities)
        _seconds(minimum_ttl_seconds, 'invalid_minimum_ttl')
        if type(require_known_expiry) is not bool:
            raise ValueError('require_known_expiry_must_be_boolean')
        if now_epoch is not None:
            _seconds(now_epoch, 'invalid_now_epoch')
        if not set(required).issubset(self._binding.capabilities):
            raise CredentialScopeError('credential_capability_mismatch')

        with self._lock:
            self._assert_issuance_allowed()
            self._busy = True
            cached = self._grant
            source = self._source

        # I/O takes place outside the lock so local revoke can win during refresh.
        failure = None
        interrupted = None
        result = None
        refreshed = False
        try:
            start_monotonic = time.monotonic()
            start_epoch = (_seconds(self._clock(), 'invalid_clock')
                           if now_epoch is None else now_epoch)
            anchor = self._time_anchor or (start_epoch, start_monotonic)

            def current_time() -> int:
                nonlocal anchor
                monotonic_now = time.monotonic()
                floor = anchor[0] + max(0, int(monotonic_now - anchor[1]))
                wall = (_seconds(self._clock(), 'invalid_clock') if now_epoch is None
                        else start_epoch + max(0, int(monotonic_now - start_monotonic)))
                if wall > floor:
                    anchor = (wall, monotonic_now)
                    return wall
                return floor

            now = current_time()
            if source.assert_available() is not None:
                raise ValueError('invalid_source_availability')
            now = max(now, current_time())
            refresh_needed = (cached is None or cached.expires_at <= now
                              or cached.expires_at - now < minimum_ttl_seconds)
            if refresh_needed:
                with self._lock:
                    if self._state == 'revoked':
                        raise CredentialRevokedError('credential_provider_revoked')
                    self._state = 'refresh_required'
                    self._grant = None
                    self._state = 'refreshing'
                result = source.refresh_access(self._binding, minimum_ttl_seconds=minimum_ttl_seconds)
                refreshed = True
            else:
                result = cached
            # Recheck both source revocation and time AFTER possibly slow refresh I/O.
            if source.assert_available() is not None:
                raise ValueError('invalid_source_availability')
            now = max(now, current_time())
            self._validate_grant(result, now, minimum_ttl_seconds)
            # Copy/normalize all access fields, retaining no mutable source container.
            result = AccessCredentialGrant(
                self._binding.provider_id, self._binding.account_id,
                self._binding.capabilities, result.access_token, result.issued_at, result.expires_at,
            )
        except CredentialRevokedError:
            failure = 'credential_source_revoked'
        except BaseException as error:
            # Never keep/forward an exception containing provider payloads or secrets.
            failure = 'credential_refresh_failed'
            if isinstance(error, KeyboardInterrupt):
                interrupted = KeyboardInterrupt
            elif isinstance(error, SystemExit):
                interrupted = SystemExit

        # Raise outside the exception handler to avoid retaining secret-bearing context.
        with self._lock:
            self._busy = False
            if self._state == 'revoked' or failure == 'credential_source_revoked':
                self._state = 'revoked'
                self._failure = 'credential_source_revoked'
                self._grant = None
                raise CredentialRevokedError('credential_source_revoked')
            if failure:
                self._state = 'blocked_auth'
                self._failure = failure
                self._grant = None
                if interrupted:
                    raise interrupted('credential_refresh_interrupted')
                raise CredentialAuthBlocked('credential_refresh_failed')
            self._grant = result
            self._time_anchor = anchor
            if refreshed:
                self._generation += 1
            self._state = 'ready_rotated' if self._generation > 1 else 'ready'
            self._failure = None
            return CredentialSnapshot(
                provider_id=self._binding.provider_id, account_label=self._binding.account_id,
                capabilities=self._binding.capabilities, secrets={'access_token': result.access_token},
                issued_at=result.issued_at, expires_at=result.expires_at,
                refresh_capable=True, created_at=now,
            )
