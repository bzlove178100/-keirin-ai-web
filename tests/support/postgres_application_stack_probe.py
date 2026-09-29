"""Synthetic co-resident application secret-stack probe for the hardened client."""
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import multiprocessing
import os
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / "tests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from agent_core.bootstrap_lease import BootstrapPasswordLease
from agent_core.durable_secret_store import DurableVersionedSecretStore
from agent_core.postgres_host_factory import StrictPostgresConnectionFactory
from agent_core.postgres_host_profile import PostgresHostProfile
from agent_core.postgres_secret_process import ProcessDeadlinePostgresSecretBackend
from agent_core.refresh_credentials import CredentialBinding
from agent_core.versioned_secret_store import (
    SecretStoreAmbiguousWrite,
    SecretStoreConflict,
    SecretStoreError,
)
from support.stdlib_pg_driver import connect as stdlib_connect

BINDING = CredentialBinding("provider-a", "account-a", ("read:one", "write:one"))
PASSWORD_FILE = Path("/tmp/bootstrap-password")
VERSION_FILE = Path("/tmp/bootstrap-version")
GATE = Path("/tmp/app-stack-go")
LOCK_READY = Path("/tmp/app-stack-lock-ready")
LOCK_GO = Path("/tmp/app-stack-lock-go")


def _required(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError("synthetic_app_stack_config_missing")
    return value


def _profile():
    return PostgresHostProfile(
        _required("SYNTHETIC_DB_HOST"),
        _required("SYNTHETIC_DB_IP"),
        int(_required("SYNTHETIC_DB_PORT")),
        _required("SYNTHETIC_DB_NAME"),
        _required("SYNTHETIC_DB_USER"),
        _required("SYNTHETIC_DB_CA"),
    )


def _bootstrap_mode():
    mode = os.environ.get("SYNTHETIC_BOOTSTRAP_MODE", "normal")
    if mode not in {"normal", "expired", "stale", "revoked"}:
        raise RuntimeError("synthetic_app_stack_bootstrap_mode_invalid")
    return mode


def _password_source():
    profile = _profile()
    password = PASSWORD_FILE.read_text()
    version = int(VERSION_FILE.read_text())
    if password != "SYNTHETIC:tls-ci-only" or version != 1:
        raise RuntimeError("synthetic_app_stack_bootstrap_invalid")
    mode = _bootstrap_mode()
    expires_at = int(time.time()) - 1 if mode == "expired" else int(time.time()) + 60
    return BootstrapPasswordLease(
        profile.login, profile.database, version, expires_at, password
    )


def _lease_is_current(version):
    try:
        configured = int(VERSION_FILE.read_text())
    except (OSError, ValueError):
        return False
    mode = _bootstrap_mode()
    if mode == "revoked":
        return False
    if mode == "stale":
        configured += 1
    return version == configured == 1


def strict_connection_factory(**limits):
    if os.environ.get("SYNTHETIC_POSTGRES_APP_STACK_PROBE") != "1":
        raise RuntimeError("synthetic_app_stack_gate_required")
    return StrictPostgresConnectionFactory(
        _profile(),
        driver_connect=stdlib_connect,
        password_source=_password_source,
        lease_is_current=_lease_is_current,
        trusted_ca_sha256=_required("SYNTHETIC_DB_CA_SHA256"),
    )(**limits)


def _store(*, operation_timeout_ms=8000, statement_timeout_ms=4000, lock_timeout_ms=1000):
    return DurableVersionedSecretStore(
        ProcessDeadlinePostgresSecretBackend(
            strict_connection_factory,
            BINDING,
            operation_timeout_ms=operation_timeout_ms,
            connect_timeout_seconds=3,
            statement_timeout_ms=statement_timeout_ms,
            lock_timeout_ms=lock_timeout_ms,
        )
    )


def _expect_fixed(error_type, message, action):
    try:
        action()
    except error_type as error:
        if (type(error) is not error_type or str(error) != message
                or error.__context__ is not None or error.__cause__ is not None):
            raise RuntimeError("synthetic_app_stack_error_contract_invalid") from None
        return
    raise RuntimeError("synthetic_app_stack_expected_failure_missing")


@contextmanager
def _temporary_environment(**updates):
    original = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            os.environ[key] = value
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _wait_for(path, error):
    deadline = time.monotonic() + 12
    while not path.exists():
        if time.monotonic() >= deadline:
            raise RuntimeError(error)
        time.sleep(0.02)


def _wait_for_release():
    _wait_for(GATE, "synthetic_app_stack_release_timeout")
    if not PASSWORD_FILE.is_file() or not VERSION_FILE.is_file():
        raise RuntimeError("synthetic_app_stack_bootstrap_missing")


def _assert_no_child_leak(before_children):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if {child.pid for child in multiprocessing.active_children()} == before_children:
            return
        time.sleep(0.02)
    raise RuntimeError("synthetic_app_stack_child_not_reaped")


def main():
    if os.environ.get("SYNTHETIC_POSTGRES_APP_STACK_PROBE") != "1":
        raise RuntimeError("synthetic_app_stack_gate_required")
    if (_required("SYNTHETIC_DB_USER") != "secret_test_host_a"
            or _required("SYNTHETIC_DB_NAME") != "agent_checkpoint_ci"):
        raise RuntimeError("synthetic_app_stack_identity_invalid")
    _required("SYNTHETIC_WRONG_DB_CA")
    _required("SYNTHETIC_WRONG_DB_CA_SHA256")
    _wait_for_release()
    before_children = {child.pid for child in multiprocessing.active_children()}
    try:
        initial = _store().read(BINDING)
        if (initial.version != 0 or initial.state != "ready"
                or initial.refresh_secret != "SYNTHETIC:a0"
                or initial.refresh_generation != 0):
            raise RuntimeError("synthetic_app_stack_initial_record_invalid")

        candidate = replace(
            initial,
            version=1,
            refresh_secret="SYNTHETIC:app-stack-a1",
        )
        stored = _store().compare_and_swap(
            BINDING, expected_version=0, replacement=candidate
        )
        if stored != candidate or _store().read(BINDING) != candidate:
            raise RuntimeError("synthetic_app_stack_cas_readback_invalid")

        _expect_fixed(
            SecretStoreConflict,
            "secret_store_version_conflict",
            lambda: _store().compare_and_swap(
                BINDING, expected_version=0, replacement=candidate
            ),
        )
        if _store().read(BINDING) != candidate:
            raise RuntimeError("synthetic_app_stack_stale_cas_mutated")

        for mode in ("expired", "stale", "revoked"):
            with _temporary_environment(SYNTHETIC_BOOTSTRAP_MODE=mode):
                _expect_fixed(
                    SecretStoreError,
                    "secret_store_backend_unavailable",
                    lambda: _store().read(BINDING),
                )
            if _store().read(BINDING) != candidate:
                raise RuntimeError("synthetic_app_stack_lease_failure_mutated")

        with _temporary_environment(SYNTHETIC_DB_HOST="wrong.synthetic.invalid"):
            _expect_fixed(
                SecretStoreError,
                "secret_store_backend_unavailable",
                lambda: _store().read(BINDING),
            )
        if _store().read(BINDING) != candidate:
            raise RuntimeError("synthetic_app_stack_wrong_hostname_mutated")

        with _temporary_environment(
            SYNTHETIC_DB_CA=_required("SYNTHETIC_WRONG_DB_CA"),
            SYNTHETIC_DB_CA_SHA256=_required("SYNTHETIC_WRONG_DB_CA_SHA256"),
        ):
            _expect_fixed(
                SecretStoreError,
                "secret_store_backend_unavailable",
                lambda: _store().read(BINDING),
            )
        if _store().read(BINDING) != candidate:
            raise RuntimeError("synthetic_app_stack_wrong_trust_mutated")

        LOCK_READY.write_text("ready")
        _wait_for(LOCK_GO, "synthetic_app_stack_lock_release_timeout")
        blocked_candidate = replace(
            candidate,
            version=2,
            refresh_secret="SYNTHETIC:must-not-commit",
        )
        _expect_fixed(
            SecretStoreAmbiguousWrite,
            "secret_store_write_ambiguous",
            lambda: _store(
                operation_timeout_ms=1500,
                statement_timeout_ms=6000,
                lock_timeout_ms=5000,
            ).compare_and_swap(
                BINDING, expected_version=1, replacement=blocked_candidate
            ),
        )
        if _store().read(BINDING) != candidate:
            raise RuntimeError("synthetic_app_stack_deadline_mutated")
        _assert_no_child_leak(before_children)
    finally:
        for path in (PASSWORD_FILE, VERSION_FILE, GATE, LOCK_READY, LOCK_GO):
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    print(
        "synthetic_postgres_application_stack_ok:read-cas,lease-failclosed,wrong-name,wrong-trust,deadline",
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(25) from None
