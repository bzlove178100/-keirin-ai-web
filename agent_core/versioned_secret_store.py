from __future__ import annotations

from dataclasses import dataclass, replace
from threading import Lock
from typing import Callable, Protocol
from uuid import uuid4

from .credential_provider import CredentialRevokedError, _capabilities, _seconds, _validate_times
from .refresh_credentials import (
    AccessCredentialGrant,
    CredentialAuthBlocked,
    CredentialBinding,
    CredentialRefreshInProgress,
)


class SecretStoreError(RuntimeError):
    """Base class for host-only secret-store coordination failures."""


class SecretStoreConflict(SecretStoreError):
    """Version-CAS rejected a stale writer; the caller must not retry blindly."""


class SecretStoreAmbiguousWrite(SecretStoreError):
    """The caller cannot tell whether a secret-store write committed."""


class RefreshExchangeRejected(RuntimeError):
    """Provider definitively rejected the refresh request.

    This exception means the caller knows the refresh request did not produce a usable
    rotated credential. Any other provider/transport exception is treated as ambiguous.
    """


class RefreshExchangeAmbiguous(RuntimeError):
    """Refresh request may have been applied but its outcome is unknown."""


@dataclass(frozen=True, slots=True, repr=False)
class RefreshSecretRecord:
    """Host-only refresh-secret state with durable version/fencing metadata.

    ``refresh_secret`` is deliberately excluded from repr/safe metadata. This record is
    not a task artifact and must never be serialized into TaskSpec/checkpoint/activity
    state by generic code.
    """

    binding: CredentialBinding
    version: int
    state: str
    refresh_secret: str | None
    refresh_generation: int = 0
    active_attempt_id: str | None = None
    last_attempt_id: str | None = None
    failure: str | None = None

    def __post_init__(self) -> None:
        if type(self.binding) is not CredentialBinding:
            raise ValueError("credential_binding_required")
        _seconds(self.version, "secret_store_version_invalid")
        _seconds(self.refresh_generation, "refresh_generation_invalid")
        if self.state not in {
            "ready",
            "refreshing",
            "blocked_auth",
            "blocked_ambiguous",
            "revoked",
        }:
            raise ValueError("secret_store_state_invalid")
        if self.state == "revoked":
            if self.refresh_secret is not None:
                raise ValueError("revoked_secret_must_be_cleared")
        elif not isinstance(self.refresh_secret, str) or not self.refresh_secret.strip():
            raise ValueError("refresh_secret_required")
        if self.state == "refreshing":
            if not isinstance(self.active_attempt_id, str) or not self.active_attempt_id:
                raise ValueError("refresh_attempt_required")
        elif self.active_attempt_id is not None:
            raise ValueError("active_attempt_only_while_refreshing")
        if self.last_attempt_id is not None and (
            not isinstance(self.last_attempt_id, str) or not self.last_attempt_id
        ):
            raise ValueError("last_attempt_invalid")
        if self.failure is not None and (
            not isinstance(self.failure, str) or not self.failure or len(self.failure) > 128
        ):
            raise ValueError("secret_store_failure_invalid")

    def to_safe_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.binding.provider_id,
            "account_id": self.binding.account_id,
            "capabilities": list(self.binding.capabilities),
            "version": self.version,
            "state": self.state,
            "refresh_generation": self.refresh_generation,
            "active_attempt_id": self.active_attempt_id,
            "last_attempt_id": self.last_attempt_id,
            "failure": self.failure,
            "refresh_secret_present": self.refresh_secret is not None,
        }

    def __repr__(self) -> str:
        return f"RefreshSecretRecord({self.to_safe_dict()!r}, refresh_secret='<redacted>')"


class VersionedSecretStore(Protocol):
    """Host-only store contract with strict version-CAS semantics."""

    def read(self, binding: CredentialBinding) -> RefreshSecretRecord:
        ...

    def compare_and_swap(
        self,
        binding: CredentialBinding,
        *,
        expected_version: int,
        replacement: RefreshSecretRecord,
    ) -> RefreshSecretRecord:
        ...


class InMemoryVersionedSecretStore:
    """Offline/reference store used for fault injection and contract tests only.

    It models the semantics a durable secret store must provide. It is not a production
    secret store and intentionally keeps refresh material only in process memory.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._records: dict[tuple[str, str, tuple[str, ...]], RefreshSecretRecord] = {}

    @staticmethod
    def _key(binding: CredentialBinding) -> tuple[str, str, tuple[str, ...]]:
        if type(binding) is not CredentialBinding:
            raise ValueError("credential_binding_required")
        return (binding.provider_id, binding.account_id, binding.capabilities)

    def seed(self, binding: CredentialBinding, refresh_secret: str) -> RefreshSecretRecord:
        if not isinstance(refresh_secret, str) or not refresh_secret.strip():
            raise ValueError("refresh_secret_required")
        record = RefreshSecretRecord(binding=binding, version=0, state="ready", refresh_secret=refresh_secret)
        key = self._key(binding)
        with self._lock:
            if key in self._records:
                raise SecretStoreConflict("secret_store_record_already_exists")
            self._records[key] = record
        return record

    def read(self, binding: CredentialBinding) -> RefreshSecretRecord:
        key = self._key(binding)
        with self._lock:
            record = self._records.get(key)
        if record is None:
            raise CredentialAuthBlocked("credential_secret_unconfigured")
        return record

    def compare_and_swap(
        self,
        binding: CredentialBinding,
        *,
        expected_version: int,
        replacement: RefreshSecretRecord,
    ) -> RefreshSecretRecord:
        _seconds(expected_version, "secret_store_expected_version_invalid")
        if type(replacement) is not RefreshSecretRecord or replacement.binding != binding:
            raise ValueError("secret_store_replacement_binding_mismatch")
        if replacement.version != expected_version + 1:
            raise ValueError("secret_store_replacement_version_invalid")
        key = self._key(binding)
        with self._lock:
            current = self._records.get(key)
            if current is None or current.version != expected_version:
                raise SecretStoreConflict("secret_store_version_conflict")
            self._records[key] = replacement
        return replacement


@dataclass(frozen=True, slots=True, repr=False)
class RefreshExchangeResult:
    grant: AccessCredentialGrant
    rotated_refresh_secret: str

    def __repr__(self) -> str:
        return "RefreshExchangeResult(<redacted>)"


class RefreshExchange(Protocol):
    """Provider-specific refresh exchange owned by the host only."""

    def exchange(
        self,
        binding: CredentialBinding,
        *,
        refresh_secret: str,
        attempt_id: str,
        minimum_ttl_seconds: int,
    ) -> RefreshExchangeResult:
        ...


class VersionedHostCredentialSource:
    """Versioned HostCredentialSource with durable refresh ownership and recovery.

    The source claims one refresh attempt in the secret store *before* contacting the
    provider. A successful rotated refresh secret is durably committed before access is
    returned. Ambiguous provider/store outcomes transition to ``blocked_ambiguous`` and
    never retry automatically.
    """

    def __init__(
        self,
        binding: CredentialBinding,
        store: VersionedSecretStore,
        exchange: RefreshExchange,
        *,
        attempt_id_factory: Callable[[], str] | None = None,
    ) -> None:
        if type(binding) is not CredentialBinding:
            raise ValueError("credential_binding_required")
        self._binding = binding
        self._store = store
        self._exchange = exchange
        self._attempt_id_factory = attempt_id_factory or (lambda: uuid4().hex)

    def _read(self) -> RefreshSecretRecord:
        record = self._store.read(self._binding)
        if type(record) is not RefreshSecretRecord or record.binding != self._binding:
            raise CredentialAuthBlocked("credential_secret_store_integrity_error")
        return record

    @staticmethod
    def _fixed_attempt(value: str) -> str:
        if not isinstance(value, str) or not value or len(value) > 128:
            raise CredentialAuthBlocked("credential_refresh_attempt_invalid")
        return value

    def assert_available(self) -> None:
        record = self._read()
        if record.state == "ready":
            return None
        if record.state == "revoked":
            raise CredentialRevokedError("credential_source_revoked")
        if record.state == "refreshing":
            raise CredentialRefreshInProgress("credential_refresh_owned_elsewhere")
        if record.state == "blocked_ambiguous":
            raise CredentialAuthBlocked("credential_refresh_outcome_ambiguous")
        raise CredentialAuthBlocked("credential_auth_unavailable")

    def _cas(
        self,
        current: RefreshSecretRecord,
        replacement: RefreshSecretRecord,
    ) -> RefreshSecretRecord:
        return self._store.compare_and_swap(
            self._binding,
            expected_version=current.version,
            replacement=replacement,
        )

    def _claim(self, current: RefreshSecretRecord, attempt_id: str) -> RefreshSecretRecord:
        claimed = replace(
            current,
            version=current.version + 1,
            state="refreshing",
            active_attempt_id=attempt_id,
            failure=None,
        )
        try:
            return self._cas(current, claimed)
        except SecretStoreAmbiguousWrite:
            observed = self._read()
            if (
                observed.state == "refreshing"
                and observed.active_attempt_id == attempt_id
                and observed.version == claimed.version
            ):
                return observed
            raise CredentialAuthBlocked("credential_refresh_claim_ambiguous") from None
        except SecretStoreConflict:
            raise CredentialRefreshInProgress("credential_refresh_owned_elsewhere") from None

    def _block(
        self,
        current: RefreshSecretRecord,
        *,
        attempt_id: str,
        state: str,
        failure: str,
    ) -> RefreshSecretRecord:
        blocked = replace(
            current,
            version=current.version + 1,
            state=state,
            active_attempt_id=None,
            last_attempt_id=attempt_id,
            failure=failure,
        )
        try:
            return self._cas(current, blocked)
        except (SecretStoreConflict, SecretStoreAmbiguousWrite):
            observed = self._read()
            if (
                observed.state == state
                and observed.last_attempt_id == attempt_id
                and observed.failure == failure
            ):
                return observed
            raise CredentialAuthBlocked("credential_refresh_recovery_state_uncertain") from None

    def _validate_exchange_result(
        self,
        result: RefreshExchangeResult,
        *,
        minimum_ttl_seconds: int,
    ) -> None:
        if type(result) is not RefreshExchangeResult:
            raise ValueError("invalid_refresh_exchange_result")
        grant = result.grant
        if type(grant) is not AccessCredentialGrant:
            raise ValueError("invalid_access_grant")
        if grant.provider_id != self._binding.provider_id or grant.account_id != self._binding.account_id:
            raise ValueError("credential_identity_mismatch")
        if _capabilities(grant.capabilities) != self._binding.capabilities:
            raise ValueError("credential_scope_changed")
        if not isinstance(grant.access_token, str) or not grant.access_token.strip():
            raise ValueError("invalid_access_token")
        _seconds(grant.issued_at, "invalid_issue_time")
        _seconds(grant.expires_at, "invalid_expiry")
        _validate_times(grant.issued_at, grant.expires_at)
        if grant.expires_at - grant.issued_at < minimum_ttl_seconds:
            raise ValueError("invalid_access_lifetime")
        if not isinstance(result.rotated_refresh_secret, str) or not result.rotated_refresh_secret.strip():
            raise ValueError("rotated_refresh_secret_required")

    def _commit_success(
        self,
        current: RefreshSecretRecord,
        *,
        attempt_id: str,
        result: RefreshExchangeResult,
    ) -> RefreshSecretRecord:
        committed = replace(
            current,
            version=current.version + 1,
            state="ready",
            refresh_secret=result.rotated_refresh_secret,
            refresh_generation=current.refresh_generation + 1,
            active_attempt_id=None,
            last_attempt_id=attempt_id,
            failure=None,
        )
        try:
            return self._cas(current, committed)
        except SecretStoreAmbiguousWrite:
            observed = self._read()
            if (
                observed.state == "ready"
                and observed.version == committed.version
                and observed.refresh_generation == committed.refresh_generation
                and observed.last_attempt_id == attempt_id
                and observed.refresh_secret == result.rotated_refresh_secret
            ):
                return observed
            if observed.state == "refreshing" and observed.active_attempt_id == attempt_id:
                self._block(
                    observed,
                    attempt_id=attempt_id,
                    state="blocked_ambiguous",
                    failure="secret_store_commit_ambiguous",
                )
            raise CredentialAuthBlocked("credential_refresh_persistence_ambiguous") from None
        except SecretStoreConflict:
            observed = self._read()
            if observed.state == "revoked":
                raise CredentialRevokedError("credential_source_revoked") from None
            raise CredentialAuthBlocked("credential_refresh_persistence_conflict") from None

    def refresh_access(
        self,
        binding: CredentialBinding,
        *,
        minimum_ttl_seconds: int,
    ) -> AccessCredentialGrant:
        if binding != self._binding:
            raise CredentialAuthBlocked("credential_binding_mismatch")
        _seconds(minimum_ttl_seconds, "invalid_minimum_ttl")

        current = self._read()
        if current.state == "revoked":
            raise CredentialRevokedError("credential_source_revoked")
        if current.state == "refreshing":
            raise CredentialRefreshInProgress("credential_refresh_owned_elsewhere")
        if current.state == "blocked_ambiguous":
            raise CredentialAuthBlocked("credential_refresh_outcome_ambiguous")
        if current.state != "ready":
            raise CredentialAuthBlocked("credential_auth_unavailable")

        attempt_id = self._fixed_attempt(self._attempt_id_factory())
        claimed = self._claim(current, attempt_id)
        assert claimed.refresh_secret is not None

        result = None
        exchange_failure: str | None = None
        interrupted: type[BaseException] | None = None
        try:
            result = self._exchange.exchange(
                self._binding,
                refresh_secret=claimed.refresh_secret,
                attempt_id=attempt_id,
                minimum_ttl_seconds=minimum_ttl_seconds,
            )
        except RefreshExchangeRejected:
            exchange_failure = "rejected"
        except BaseException as error:
            exchange_failure = "ambiguous"
            if isinstance(error, KeyboardInterrupt):
                interrupted = KeyboardInterrupt
            elif isinstance(error, SystemExit):
                interrupted = SystemExit

        # Handle provider failure outside the exception handler so secret-bearing
        # provider exceptions are not retained as __context__ on outward errors.
        if exchange_failure == "rejected":
            self._block(
                claimed,
                attempt_id=attempt_id,
                state="blocked_auth",
                failure="refresh_rejected",
            )
            raise CredentialAuthBlocked("credential_refresh_rejected")
        if exchange_failure == "ambiguous":
            self._block(
                claimed,
                attempt_id=attempt_id,
                state="blocked_ambiguous",
                failure="refresh_outcome_ambiguous",
            )
            if interrupted is KeyboardInterrupt:
                raise KeyboardInterrupt("credential_refresh_interrupted")
            if interrupted is SystemExit:
                raise SystemExit("credential_refresh_interrupted")
            raise CredentialAuthBlocked("credential_refresh_outcome_ambiguous")

        validation_failed = False
        try:
            self._validate_exchange_result(result, minimum_ttl_seconds=minimum_ttl_seconds)
        except BaseException:
            validation_failed = True
        if validation_failed:
            self._block(
                claimed,
                attempt_id=attempt_id,
                state="blocked_ambiguous",
                failure="refresh_response_invalid_or_incomplete",
            )
            raise CredentialAuthBlocked("credential_refresh_outcome_ambiguous")

        assert type(result) is RefreshExchangeResult
        self._commit_success(claimed, attempt_id=attempt_id, result=result)
        return result.grant

    def recover_ambiguous_not_applied(
        self,
        *,
        expected_version: int,
        attempt_id: str,
    ) -> RefreshSecretRecord:
        """Operator recovery after external proof that the refresh did not apply."""
        _seconds(expected_version, "secret_store_expected_version_invalid")
        attempt_id = self._fixed_attempt(attempt_id)
        current = self._read()
        if current.version != expected_version:
            raise SecretStoreConflict("secret_store_version_conflict")
        if current.state != "blocked_ambiguous" or current.last_attempt_id != attempt_id:
            raise CredentialAuthBlocked("ambiguous_recovery_precondition_failed")
        replacement = replace(
            current,
            version=current.version + 1,
            state="ready",
            active_attempt_id=None,
            failure=None,
        )
        return self._cas(current, replacement)

    def recover_ambiguous_with_rotated_secret(
        self,
        *,
        expected_version: int,
        attempt_id: str,
        rotated_refresh_secret: str,
    ) -> RefreshSecretRecord:
        """Operator recovery after external proof of the applied rotated secret."""
        _seconds(expected_version, "secret_store_expected_version_invalid")
        attempt_id = self._fixed_attempt(attempt_id)
        if not isinstance(rotated_refresh_secret, str) or not rotated_refresh_secret.strip():
            raise ValueError("rotated_refresh_secret_required")
        current = self._read()
        if current.version != expected_version:
            raise SecretStoreConflict("secret_store_version_conflict")
        if current.state != "blocked_ambiguous" or current.last_attempt_id != attempt_id:
            raise CredentialAuthBlocked("ambiguous_recovery_precondition_failed")
        replacement = replace(
            current,
            version=current.version + 1,
            state="ready",
            refresh_secret=rotated_refresh_secret,
            refresh_generation=current.refresh_generation + 1,
            active_attempt_id=None,
            failure=None,
        )
        return self._cas(current, replacement)

    def revoke(self) -> RefreshSecretRecord:
        current = self._read()
        if current.state == "revoked":
            return current
        replacement = replace(
            current,
            version=current.version + 1,
            state="revoked",
            refresh_secret=None,
            active_attempt_id=None,
            failure="credential_source_revoked",
        )
        return self._cas(current, replacement)
