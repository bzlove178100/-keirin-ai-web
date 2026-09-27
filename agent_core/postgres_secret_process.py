"""Opt-in, unbound process deadline for host-only PostgreSQL secret operations."""
from __future__ import annotations

import json
import multiprocessing
import os
import time
from types import FunctionType

from .durable_secret_store import (
    DurableSecretBackendAmbiguousWrite, DurableSecretBackendConflict,
    DurableSecretBackendUnavailable, _binding_key,
)
from .postgres_secret_backend import PostgresSecretBackend, _MAX_BIGINT, _strict_record
from .refresh_credentials import CredentialBinding
from .host_process_safety import assert_safe_spawn_environment, harden_secret_child

_MAX_MESSAGE = 65536
_STOP_GRACE_SECONDS = 0.25


def _child(factory, binding, limits, request, buffer, length):
    # Never pickle an exception or use a Queue/Pipe result that can leave the parent
    # blocked on a partial frame. Only bounded JSON in anonymous shared memory.
    # The parent reads it only after a clean process exit.
    try:
        with open(os.devnull, "wb", buffering=0) as sink:
            os.dup2(sink.fileno(), 1)
            os.dup2(sink.fileno(), 2)
        harden_secret_child()
        message = {"status": "unavailable"}
        write = False
        try:
            data = json.loads(request)
            write = data["write"]
            backend = PostgresSecretBackend(factory, binding, **limits)
            if write:
                result = backend.compare_and_swap(
                    data["key"], expected_version=data["expected"], replacement=data["replacement"],
                )
            else:
                result = backend.read(data["key"])
            message = {"status": "ok", "record": result}
        except DurableSecretBackendConflict:
            message = {"status": "conflict"}
        except DurableSecretBackendAmbiguousWrite:
            message = {"status": "ambiguous"}
        except DurableSecretBackendUnavailable:
            message = {"status": "unavailable"}
        except BaseException:
            message = {"status": "ambiguous" if write else "unavailable"}
        encoded = json.dumps(message, ensure_ascii=True, allow_nan=False).encode("ascii")
        if len(encoded) > _MAX_MESSAGE:
            encoded = b'{"status":"ambiguous"}' if write else b'{"status":"unavailable"}'
        buffer[:len(encoded)] = encoded
        length.value = len(encoded)
    except BaseException:
        os._exit(1)
    # Skip untrusted atexit handlers/stdio flushing after publishing the response.
    os._exit(0)


class ProcessDeadlinePostgresSecretBackend:
    """One spawned, reaped process per operation; no implicit activation or retry.

    Linux host contract: trusted importable top-level factory, no import-time I/O,
    no grandchildren, no logging/telemetry/core dumps, verified primary/TLS and secret
    custody. Factory credentials are resolved in the child, not passed as task inputs.
    Process termination cannot prove server rollback; interrupted CAS stays ambiguous.

    The deadline includes child startup and DB I/O. Reaping permits two additional
    250ms waits (TERM then KILL). OS process creation/scheduling/unkillable kernel work
    cannot be absolutely bounded in Python; an external host supervisor is still needed.
    """

    def __init__(self, connection_factory, binding: CredentialBinding, *,
                 operation_timeout_ms: int = 10000, connect_timeout_seconds: int = 5,
                 statement_timeout_ms: int = 5000, lock_timeout_ms: int = 1000):
        if (type(connection_factory) is not FunctionType
                or connection_factory.__qualname__ != connection_factory.__name__
                or connection_factory.__closure__ is not None):
            raise ValueError("secret_process_factory_invalid")
        if type(operation_timeout_ms) is not int or not 100 <= operation_timeout_ms <= 60000:
            raise ValueError("secret_process_deadline_invalid")
        self._limits = dict(connect_timeout_seconds=connect_timeout_seconds,
                            statement_timeout_ms=statement_timeout_ms,
                            lock_timeout_ms=lock_timeout_ms)
        # Validate configuration without opening a connection.
        PostgresSecretBackend(connection_factory, binding, **self._limits)
        if len(json.dumps([binding.provider_id, binding.account_id, binding.capabilities])) > 4096:
            raise ValueError("secret_process_binding_invalid")
        self._factory = connection_factory
        self._binding = binding
        self._key = _binding_key(binding)
        self._timeout = operation_timeout_ms / 1000
        self._quarantined = False

    def __repr__(self):
        return "ProcessDeadlinePostgresSecretBackend(<redacted>)"

    def read(self, key):
        return self._operate(key, None, None, False)

    def compare_and_swap(self, key, *, expected_version, replacement):
        return self._operate(key, expected_version, replacement, True)

    def _operate(self, key, expected, replacement, write):
        status = "unavailable"
        result = None
        process = None
        started = False
        clean_exit = False
        buffer = None
        length = None
        interrupted = None
        try:
            assert_safe_spawn_environment()
            if self._quarantined or type(key) is not str or key != self._key:
                raise ValueError("secret_process_request_invalid")
            if write:
                if type(expected) is not int or not 0 <= expected < _MAX_BIGINT:
                    raise ValueError("secret_process_request_invalid")
                replacement = _strict_record(replacement, self._binding)
                if replacement["version"] != expected + 1:
                    raise ValueError("secret_process_request_invalid")
            request = json.dumps(dict(key=key, expected=expected, replacement=replacement,
                                      write=write), ensure_ascii=True, allow_nan=False).encode("ascii")
            if len(request) > _MAX_MESSAGE:
                raise ValueError("secret_process_request_invalid")
            context = multiprocessing.get_context("spawn")
            buffer = context.RawArray("B", _MAX_MESSAGE)
            length = context.RawValue("I", 0)
            process = context.Process(target=_child, args=(
                self._factory, self._binding, self._limits, request, buffer, length,
            ), daemon=True)
            deadline = time.monotonic() + self._timeout
            # Conservative before start: a startup failure may occur after spawning.
            started = True
            status = "ambiguous" if write else "unavailable"
            process.start()
            process.join(max(0.0, deadline - time.monotonic()))
            clean_exit = process.exitcode == 0 and time.monotonic() <= deadline
            if clean_exit:
                if not 0 < length.value <= _MAX_MESSAGE:
                    raise ValueError("secret_process_response_invalid")
                message = json.loads(bytes(buffer[:length.value]))
                if type(message) is not dict:
                    raise ValueError("secret_process_response_invalid")
                candidate = message.get("status")
                if candidate == "ok" and set(message) == {"status", "record"}:
                    result = _strict_record(message["record"], self._binding)
                    if write and result != replacement:
                        raise ValueError("secret_process_response_invalid")
                    status = "ok"
                elif set(message) == {"status"} and candidate in {"unavailable", "conflict", "ambiguous"}:
                    status = candidate if write else "unavailable"
                else:
                    raise ValueError("secret_process_response_invalid")
        except BaseException as error:
            status = "ambiguous" if started and write else "unavailable"
            if not (started and write):
                if isinstance(error, KeyboardInterrupt):
                    interrupted = KeyboardInterrupt
                elif isinstance(error, SystemExit):
                    interrupted = SystemExit
        finally:
            # No unbounded join and no parent-side driver rollback/close calls.
            if process is not None and process.pid is not None:
                try:
                    if process.is_alive():
                        process.terminate()
                        process.join(_STOP_GRACE_SECONDS)
                    if process.is_alive():
                        process.kill()
                        process.join(_STOP_GRACE_SECONDS)
                    if process.is_alive():
                        self._quarantined = True
                    else:
                        process.close()
                except BaseException:
                    self._quarantined = True
            if self._quarantined:
                status = "ambiguous" if started and write else "unavailable"
            # Best-effort erase IPC copies only after the child has stopped writing.
            # This is not a guarantee of erasing Python/driver/OS memory copies.
            if buffer is not None and not self._quarantined:
                buffer[:] = b"\x00" * _MAX_MESSAGE
                length.value = 0
        if status == "ok":
            return result
        if status == "conflict":
            raise DurableSecretBackendConflict("secret_process_version_conflict")
        if status == "ambiguous":
            raise DurableSecretBackendAmbiguousWrite("secret_process_write_ambiguous")
        if interrupted is not None:
            raise interrupted("secret_process_interrupted")
        raise DurableSecretBackendUnavailable("secret_process_unavailable")
