"""Unbound host-only PostgreSQL adapter; no credentials or driver are configured here."""
from __future__ import annotations

import json
from typing import Any, Callable

from .durable_secret_store import (
    DurableSecretBackendAmbiguousWrite, DurableSecretBackendConflict,
    DurableSecretBackendUnavailable, _binding_key, _decode_record, _encode_record,
)
from .refresh_credentials import CredentialBinding

_MAX_BIGINT = 2**63 - 1
_FIELDS = frozenset({
    "schema_version", "provider_id", "account_id", "capabilities", "version",
    "state", "refresh_secret", "refresh_generation", "active_attempt_id",
    "last_attempt_id", "failure",
})
_READ = "SELECT agent_credential_private.read_binding(%s)"
_CAS = "SELECT agent_credential_private.cas_binding(%s, %s, %s::jsonb)"


def _strict_record(raw: Any, binding: CredentialBinding) -> dict[str, Any]:
    if type(raw) is not dict or raw.keys() != _FIELDS:
        raise ValueError("record_invalid")
    for field in ("version", "refresh_generation"):
        if type(raw[field]) is not int or not 0 <= raw[field] <= _MAX_BIGINT:
            raise ValueError("record_invalid")
    for field in _FIELDS - {"version", "refresh_generation", "capabilities"}:
        if raw[field] is not None and type(raw[field]) is not str:
            raise ValueError("record_invalid")
    if type(raw["capabilities"]) is not list or any(
        type(value) is not str for value in raw["capabilities"]
    ):
        raise ValueError("record_invalid")
    canonical = _encode_record(_decode_record(raw, binding))
    if canonical != raw:
        raise ValueError("record_invalid")
    return canonical


class PostgresSecretBackend:
    """One fresh, non-pooled connection and at most one CAS per operation.

    The trusted factory accepts psycopg 3 connect keyword arguments, must honor them,
    return an idle dedicated connection with tuple rows / JSONB dict decoding, and
    must never retry, log, or retain parameters/results. It owns primary endpoint,
    TLS verification and bootstrap-secret custody. No DSN is accepted by this class.

    Startup limits bound connection establishment and server statements (including
    commit/rollback). They are not a hard wall-clock bound against an uncooperative
    factory, DNS, network blackholes or blocked driver cleanup. A separately reviewed
    host process deadline is required before live activation. No worker is spawned.
    """

    def __init__(self, connection_factory: Callable[..., Any], binding: CredentialBinding,
                 *, connect_timeout_seconds: int = 5, statement_timeout_ms: int = 5000,
                 lock_timeout_ms: int = 1000) -> None:
        if not callable(connection_factory) or type(binding) is not CredentialBinding:
            raise ValueError("postgres_secret_configuration_invalid")
        for value, maximum in ((connect_timeout_seconds, 30),
                               (statement_timeout_ms, 30000), (lock_timeout_ms, 30000)):
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError("postgres_secret_timeout_invalid")
        if connect_timeout_seconds < 2 or lock_timeout_ms > statement_timeout_ms:
            raise ValueError("postgres_secret_timeout_invalid")
        self._factory = connection_factory
        self._binding = binding
        self._key = _binding_key(binding)
        self._connect_timeout = connect_timeout_seconds
        self._options = (
            f"-c statement_timeout={statement_timeout_ms} "
            f"-c lock_timeout={lock_timeout_ms} "
            f"-c idle_in_transaction_session_timeout={statement_timeout_ms}"
        )

    def __repr__(self) -> str:
        return "PostgresSecretBackend(<redacted>)"

    def read(self, key: str) -> dict[str, Any]:
        return self._operate(key, None, None)

    def compare_and_swap(self, key: str, *, expected_version: int,
                         replacement: dict[str, Any]) -> dict[str, Any]:
        return self._operate(key, expected_version, replacement, write=True)

    def _operate(self, key: str, expected: int | None, replacement: Any,
                 *, write: bool = False) -> dict[str, Any]:
        connection = None
        cursor = None
        submitted = False
        committed = False
        conflict = False
        rolled_back = False
        failed = False
        interrupted = None
        result = None
        phase = "validate"
        try:
            if type(key) is not str or key != self._key:
                raise ValueError("binding_invalid")
            payload = None
            if write:
                if type(expected) is not int or not 0 <= expected < _MAX_BIGINT:
                    raise ValueError("version_invalid")
                payload = _strict_record(replacement, self._binding)
                if payload["version"] != expected + 1:
                    raise ValueError("version_invalid")
            connection = self._factory(
                connect_timeout=self._connect_timeout, options=self._options,
                autocommit=False, prepare_threshold=None,
            )
            if connection.autocommit is not False:
                raise ValueError("transaction_required")
            cursor = connection.cursor()
            parameters = (key, expected, json.dumps(payload)) if write else (key,)
            phase = "execute"
            submitted = write
            cursor.execute(_CAS if write else _READ, parameters)
            phase = "readback"
            row = cursor.fetchone()
            if type(row) is not tuple or len(row) != 1 or cursor.fetchone() is not None:
                raise ValueError("row_invalid")
            result = _strict_record(row[0], self._binding)
            if write and result != payload:
                raise ValueError("readback_mismatch")
            phase = "commit"
            connection.commit()
            committed = True
        except BaseException as error:
            failed = True
            if isinstance(error, KeyboardInterrupt):
                interrupted = KeyboardInterrupt
            elif isinstance(error, SystemExit):
                interrupted = SystemExit
            # Only this exact private-function rejection can prove a CAS conflict.
            # SQLSTATE P0002 alone also describes missing secret/read records.
            try:
                conflict = (write and phase == "execute"
                            and error.sqlstate == "P0002"
                            and error.diag.message_primary == "credential_version_conflict")
            except BaseException:
                conflict = False
        finally:
            if connection is not None:
                if not committed:
                    try:
                        connection.rollback()
                        rolled_back = True
                    except BaseException:
                        pass
                for resource in (cursor, connection):
                    if resource is not None:
                        try:
                            resource.close()
                        except BaseException:
                            # A known commit stays committed even if cleanup fails.
                            pass

        # Outside all handlers: raw driver error/context/DSN cannot escape in errors.
        if failed:
            if submitted:
                if conflict and rolled_back:
                    raise DurableSecretBackendConflict("postgres_secret_version_conflict")
                raise DurableSecretBackendAmbiguousWrite("postgres_secret_write_ambiguous")
            if interrupted is not None:
                raise interrupted("postgres_secret_interrupted")
            raise DurableSecretBackendUnavailable("postgres_secret_unavailable")
        return result
