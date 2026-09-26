from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping, Protocol

from .refresh_credentials import CredentialAuthBlocked, CredentialBinding
from .versioned_secret_store import (
    RefreshSecretRecord,
    SecretStoreAmbiguousWrite,
    SecretStoreConflict,
    SecretStoreError,
)

SECRET_RECORD_SCHEMA_VERSION = "credential-refresh-secret-record-v1"


class DurableSecretBackendError(RuntimeError):
    """Base class for host-only durable backend transport/storage failures."""


class DurableSecretBackendConflict(DurableSecretBackendError):
    """The backend definitively rejected a stale expected version."""


class DurableSecretBackendAmbiguousWrite(DurableSecretBackendError):
    """The backend cannot prove whether a CAS write committed."""


class DurableSecretBackendUnavailable(DurableSecretBackendError):
    """The durable backend is unavailable for the requested operation."""


class DurableSecretBackend(Protocol):
    """Minimal durable backend used by ``DurableVersionedSecretStore``.

    Implementations own encryption/secret-manager/database authentication. They must not
    log payloads. ``compare_and_swap`` must atomically compare ``expected_version`` and
    either return the committed record, raise ``DurableSecretBackendConflict`` when the
    stale write is known not to have applied, or raise
    ``DurableSecretBackendAmbiguousWrite`` when commit outcome is unknown.
    """

    def read(self, key: str) -> Mapping[str, Any] | None:
        ...

    def compare_and_swap(
        self,
        key: str,
        *,
        expected_version: int,
        replacement: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        ...


def _nonnegative_int(value: Any, error: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(error)
    return value


def _binding_key(binding: CredentialBinding) -> str:
    if type(binding) is not CredentialBinding:
        raise ValueError("credential_binding_required")
    canonical = json.dumps(
        {
            "provider_id": binding.provider_id,
            "account_id": binding.account_id,
            "capabilities": list(binding.capabilities),
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "refresh-secret-v1:" + sha256(canonical).hexdigest()


def _encode_record(record: RefreshSecretRecord) -> dict[str, Any]:
    """Encode host-only durable state. Returned mapping contains the refresh secret."""
    if type(record) is not RefreshSecretRecord:
        raise ValueError("refresh_secret_record_required")
    return {
        "schema_version": SECRET_RECORD_SCHEMA_VERSION,
        "provider_id": record.binding.provider_id,
        "account_id": record.binding.account_id,
        "capabilities": list(record.binding.capabilities),
        "version": record.version,
        "state": record.state,
        "refresh_secret": record.refresh_secret,
        "refresh_generation": record.refresh_generation,
        "active_attempt_id": record.active_attempt_id,
        "last_attempt_id": record.last_attempt_id,
        "failure": record.failure,
    }


def _decode_record(raw: Mapping[str, Any], expected_binding: CredentialBinding) -> RefreshSecretRecord:
    if not isinstance(raw, Mapping):
        raise ValueError("secret_store_record_object_required")
    if raw.get("schema_version") != SECRET_RECORD_SCHEMA_VERSION:
        raise ValueError("secret_store_record_schema_mismatch")
    provider_id = raw.get("provider_id")
    account_id = raw.get("account_id")
    capabilities = raw.get("capabilities")
    if not isinstance(provider_id, str) or not isinstance(account_id, str):
        raise ValueError("secret_store_record_identity_invalid")
    if not isinstance(capabilities, list) or any(not isinstance(value, str) for value in capabilities):
        raise ValueError("secret_store_record_capabilities_invalid")
    binding = CredentialBinding(provider_id, account_id, tuple(capabilities))
    if binding != expected_binding:
        raise ValueError("secret_store_record_binding_mismatch")

    version = _nonnegative_int(raw.get("version"), "secret_store_record_version_invalid")
    generation = _nonnegative_int(
        raw.get("refresh_generation"),
        "secret_store_record_generation_invalid",
    )
    state = raw.get("state")
    if not isinstance(state, str):
        raise ValueError("secret_store_record_state_invalid")
    refresh_secret = raw.get("refresh_secret")
    if refresh_secret is not None and not isinstance(refresh_secret, str):
        raise ValueError("secret_store_record_secret_invalid")
    active_attempt_id = raw.get("active_attempt_id")
    last_attempt_id = raw.get("last_attempt_id")
    failure = raw.get("failure")
    if active_attempt_id is not None and not isinstance(active_attempt_id, str):
        raise ValueError("secret_store_record_active_attempt_invalid")
    if last_attempt_id is not None and not isinstance(last_attempt_id, str):
        raise ValueError("secret_store_record_last_attempt_invalid")
    if failure is not None and not isinstance(failure, str):
        raise ValueError("secret_store_record_failure_invalid")

    return RefreshSecretRecord(
        binding=binding,
        version=version,
        state=state,
        refresh_secret=refresh_secret,
        refresh_generation=generation,
        active_attempt_id=active_attempt_id,
        last_attempt_id=last_attempt_id,
        failure=failure,
    )


class DurableVersionedSecretStore:
    """Strict adapter from a durable atomic-CAS backend to VersionedSecretStore.

    The adapter deliberately exposes no secret-bearing safe/report method. Backend
    exceptions are converted to fixed classifications outside exception handlers so a
    provider-specific message cannot remain attached to outward exception context.
    """

    def __init__(self, backend: DurableSecretBackend) -> None:
        if backend is None:
            raise ValueError("durable_secret_backend_required")
        self._backend = backend

    def __repr__(self) -> str:
        return f"DurableVersionedSecretStore(backend={type(self._backend).__name__!r}, secrets='<redacted>')"

    @staticmethod
    def key_for(binding: CredentialBinding) -> str:
        return _binding_key(binding)

    def read(self, binding: CredentialBinding) -> RefreshSecretRecord:
        key = _binding_key(binding)
        raw: Mapping[str, Any] | None = None
        failure: str | None = None
        interrupted: type[BaseException] | None = None
        try:
            raw = self._backend.read(key)
        except DurableSecretBackendUnavailable:
            failure = "unavailable"
        except BaseException as error:
            failure = "unexpected"
            if isinstance(error, KeyboardInterrupt):
                interrupted = KeyboardInterrupt
            elif isinstance(error, SystemExit):
                interrupted = SystemExit

        if failure is not None:
            if interrupted is KeyboardInterrupt:
                raise KeyboardInterrupt("secret_store_backend_interrupted")
            if interrupted is SystemExit:
                raise SystemExit("secret_store_backend_interrupted")
            raise SecretStoreError("secret_store_backend_unavailable")
        if raw is None:
            raise CredentialAuthBlocked("credential_secret_unconfigured")

        invalid = False
        record: RefreshSecretRecord | None = None
        try:
            record = _decode_record(raw, binding)
        except (TypeError, ValueError):
            invalid = True
        if invalid or type(record) is not RefreshSecretRecord:
            raise SecretStoreError("secret_store_record_invalid")
        return record

    def compare_and_swap(
        self,
        binding: CredentialBinding,
        *,
        expected_version: int,
        replacement: RefreshSecretRecord,
    ) -> RefreshSecretRecord:
        expected = _nonnegative_int(expected_version, "secret_store_expected_version_invalid")
        if type(replacement) is not RefreshSecretRecord or replacement.binding != binding:
            raise ValueError("secret_store_replacement_binding_mismatch")
        if replacement.version != expected + 1:
            raise ValueError("secret_store_replacement_version_invalid")

        key = _binding_key(binding)
        payload = _encode_record(replacement)
        raw: Mapping[str, Any] | None = None
        failure: str | None = None
        interrupted: type[BaseException] | None = None
        try:
            raw = self._backend.compare_and_swap(
                key,
                expected_version=expected,
                replacement=payload,
            )
        except DurableSecretBackendConflict:
            failure = "conflict"
        except DurableSecretBackendAmbiguousWrite:
            failure = "ambiguous"
        except DurableSecretBackendUnavailable:
            failure = "unavailable"
        except BaseException as error:
            failure = "unexpected"
            if isinstance(error, KeyboardInterrupt):
                interrupted = KeyboardInterrupt
            elif isinstance(error, SystemExit):
                interrupted = SystemExit

        if failure == "conflict":
            raise SecretStoreConflict("secret_store_version_conflict")
        if failure == "ambiguous":
            raise SecretStoreAmbiguousWrite("secret_store_write_ambiguous")
        if failure is not None:
            if interrupted is KeyboardInterrupt:
                raise KeyboardInterrupt("secret_store_backend_interrupted")
            if interrupted is SystemExit:
                raise SystemExit("secret_store_backend_interrupted")
            raise SecretStoreError("secret_store_backend_unavailable")
        if raw is None:
            raise SecretStoreError("secret_store_cas_readback_missing")

        invalid = False
        stored: RefreshSecretRecord | None = None
        try:
            stored = _decode_record(raw, binding)
        except (TypeError, ValueError):
            invalid = True
        if invalid or type(stored) is not RefreshSecretRecord:
            raise SecretStoreError("secret_store_cas_readback_invalid")
        if stored != replacement:
            raise SecretStoreError("secret_store_cas_readback_mismatch")
        return stored
