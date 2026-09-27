"""Synthetic direct-login/process integration; never a live host factory."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import multiprocessing
import os
from threading import Barrier
import time

import psycopg

from agent_core.durable_secret_store import DurableVersionedSecretStore
from agent_core.postgres_secret_process import ProcessDeadlinePostgresSecretBackend
from agent_core.refresh_credentials import CredentialBinding
from agent_core.versioned_secret_store import SecretStoreAmbiguousWrite, SecretStoreConflict, SecretStoreError

BINDING = CredentialBinding("provider-a", "account-a", ("read:one", "write:one"))
KEY = DurableVersionedSecretStore.key_for(BINDING)


def _assert_fixture():
    if (os.environ.get("AGENT_EPHEMERAL_DB_TEST") != "1"
            or os.environ.get("PGHOST") != "127.0.0.1"
            or os.environ.get("PGDATABASE") != "agent_checkpoint_ci"
            or os.environ.get("PGPORT") != "5432"):
        raise RuntimeError("refusing_non_ephemeral_database")


def _connect_synthetic(login, **kwargs):
    _assert_fixture()
    connection = psycopg.connect(
        host="127.0.0.1", hostaddr="127.0.0.1", port=5432,
        dbname="agent_checkpoint_ci", user=login, password="SYNTHETIC:host-ci-only",
        # This disposable service is plaintext; never reuse this profile outside CI.
        sslmode="disable", gssencmode="disable", target_session_attrs="read-write",
        application_name="synthetic-secret-process", **kwargs,
    )
    try:
        identity = connection.execute(
            "SELECT session_user, current_user, current_database(), pg_is_in_recovery(), "
            "current_setting('transaction_read_only')"
        ).fetchone()
        if identity != (login, login, "agent_checkpoint_ci", False, "off"):
            raise RuntimeError("synthetic_session_identity_invalid")
        connection.commit()
        return connection
    except BaseException:
        connection.close()
        raise


def synthetic_login_factory(**kwargs):
    return _connect_synthetic("secret_test_host_a", **kwargs)


def other_login_factory(**kwargs):
    return _connect_synthetic("secret_test_host_b", **kwargs)


class _LostAcknowledgement:
    """Actual database commit completes; the child never returns acknowledgement."""
    autocommit = False

    def __init__(self, connection):
        self.connection = connection

    def cursor(self):
        return self.connection.cursor()

    def commit(self):
        self.connection.commit()
        # Deliberately blocked after PostgreSQL acknowledged COMMIT to the child.
        while True:
            time.sleep(1)

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()


def lost_ack_factory(**kwargs):
    return _LostAcknowledgement(synthetic_login_factory(**kwargs))


def _store(factory=synthetic_login_factory, *, deadline_ms=5000):
    return DurableVersionedSecretStore(ProcessDeadlinePostgresSecretBackend(
        factory, BINDING, operation_timeout_ms=deadline_ms,
        statement_timeout_ms=4000, lock_timeout_ms=3000,
    ))


def _expect(error_class, operation):
    try:
        operation()
    except error_class:
        return
    raise AssertionError("synthetic_expected_fixed_failure_missing")


def run_process_contract():
    # The outer runner already checked the loopback/disposable-database boundary.
    # These passwords belong only to the temporary CI roles; never project identities.
    _assert_fixture()
    with psycopg.connect() as admin:
        admin.execute("ALTER ROLE secret_test_host_a PASSWORD 'SYNTHETIC:host-ci-only'")
        admin.execute("ALTER ROLE secret_test_host_b PASSWORD 'SYNTHETIC:host-ci-only'")
    before_children = {process.pid for process in multiprocessing.active_children()}
    store = _store()
    current = store.read(BINDING)
    replacement = replace(current, version=current.version + 1, state="ready", active_attempt_id=None)
    assert store.compare_and_swap(BINDING, expected_version=current.version, replacement=replacement) == replacement
    # Fresh parent/child/store observes the committed record.
    assert _store().read(BINDING) == replacement
    _expect(SecretStoreConflict, lambda: store.compare_and_swap(
        BINDING, expected_version=current.version, replacement=replacement))
    _expect(SecretStoreError, lambda: _store(other_login_factory).read(BINDING))
    _expect(SecretStoreAmbiguousWrite, lambda: _store(other_login_factory).compare_and_swap(
        BINDING, expected_version=replacement.version,
        replacement=replace(replacement, version=replacement.version + 1)))
    assert store.read(BINDING) == replacement

    # Two outer callers create two child processes and two real direct-login sessions.
    barrier = Barrier(2)
    def race(attempt):
        candidate = replace(replacement, version=replacement.version + 1,
                            state="refreshing", active_attempt_id=attempt)
        barrier.wait(timeout=5)
        try:
            _store().compare_and_swap(BINDING, expected_version=replacement.version, replacement=candidate)
            return "committed"
        except SecretStoreConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(race, attempt) for attempt in ("process-a", "process-b")]
        assert sorted(future.result(timeout=10) for future in futures) == ["committed", "conflict"]
    current = store.read(BINDING)
    assert current.version == replacement.version + 1
    assert current.active_attempt_id in {"process-a", "process-b"}

    # Actual database commit persists even when the process deadline kills the child
    # before the parent receives a reply. Recovery reads, never replays the CAS.
    replacement = replace(current, version=current.version + 1, state="ready", active_attempt_id=None)
    started = time.monotonic()
    _expect(SecretStoreAmbiguousWrite, lambda: _store(lost_ack_factory, deadline_ms=2000).compare_and_swap(
        BINDING, expected_version=current.version, replacement=replacement))
    assert time.monotonic() - started < 4
    assert _store().read(BINDING) == replacement

    # Killing the caller while a row lock is held cannot authorize replay or success.
    with psycopg.connect() as locker:
        locker.execute("SELECT 1 FROM agent_credential_private.bindings WHERE binding_key=%s FOR UPDATE", (KEY,))
        _expect(SecretStoreAmbiguousWrite, lambda: _store(deadline_ms=1000).compare_and_swap(
            BINDING, expected_version=replacement.version,
            replacement=replace(replacement, version=replacement.version + 1)))
    assert _store().read(BINDING) == replacement

    # Revoke through the same process path; stale and fresh attempts cannot resurrect.
    revoked = replace(replacement, version=replacement.version + 1, state="revoked",
                      refresh_secret=None, failure="credential_source_revoked")
    assert store.compare_and_swap(BINDING, expected_version=replacement.version, replacement=revoked) == revoked
    _expect(SecretStoreConflict, lambda: store.compare_and_swap(
        BINDING, expected_version=replacement.version, replacement=revoked))
    _expect(SecretStoreAmbiguousWrite, lambda: store.compare_and_swap(
        BINDING, expected_version=revoked.version,
        replacement=replace(replacement, version=revoked.version + 1)))
    assert _store().read(BINDING) == revoked
    assert {process.pid for process in multiprocessing.active_children()} == before_children
    # Server sessions can outlive killed clients briefly; bounded observation checks
    # that no active/idle-in-transaction session survives the 4s SQL deadline.
    deadline = time.monotonic() + 6
    while True:
        with psycopg.connect() as admin:
            count = admin.execute(
                "SELECT count(*) FROM pg_stat_activity WHERE application_name='synthetic-secret-process'"
            ).fetchone()[0]
        if count == 0:
            break
        if time.monotonic() >= deadline:
            raise AssertionError("synthetic_secret_sessions_not_reaped")
        time.sleep(0.05)
    print("Synthetic process/PostgreSQL: direct login, restart readback, CAS race, lost COMMIT ack, lock kill, revocation and cleanup PASS")
