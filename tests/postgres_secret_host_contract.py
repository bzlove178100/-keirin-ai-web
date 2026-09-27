"""Called only with the committed synthetic fixture in a disposable CI database."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier
import time

import psycopg

from agent_core.durable_secret_store import DurableVersionedSecretStore
from agent_core.postgres_secret_backend import PostgresSecretBackend
from agent_core.refresh_credentials import CredentialBinding
from agent_core.versioned_secret_store import SecretStoreConflict, SecretStoreAmbiguousWrite


def run_host_contract():
    binding = CredentialBinding("provider-a", "account-a", ("read:one", "write:one"))
    key = DurableVersionedSecretStore.key_for(binding)
    # Operator-only fixture preparation. No live DB, Vault or host credentials.
    with psycopg.connect() as admin:
        admin.execute("DELETE FROM agent_credential_private.host_bindings WHERE binding_key='binding-a'")
        admin.execute("UPDATE agent_credential_private.bindings SET binding_key=%s WHERE binding_key='binding-a'", (key,))
        admin.execute("INSERT INTO agent_credential_private.host_bindings VALUES ('secret_test_host_a', %s)", (key,))
        admin.execute("DELETE FROM synthetic_vault.test_faults")

    connections = []

    def factory(**kwargs):
        # CI authentication uses its disposable admin solely to establish session_user;
        # production must use the dedicated login directly, never this switching path.
        connection = psycopg.connect(**kwargs)
        connection.execute("SET SESSION AUTHORIZATION secret_test_host_a")
        connection.commit()
        connections.append(connection)
        return connection

    backend = PostgresSecretBackend(factory, binding, statement_timeout_ms=300, lock_timeout_ms=200)
    store = DurableVersionedSecretStore(backend)
    current = store.read(binding)
    replacement = replace(current, version=current.version + 1, state="ready", active_attempt_id=None)
    assert store.compare_and_swap(binding, expected_version=current.version, replacement=replacement) == replacement
    assert store.read(binding) == replacement
    try:
        store.compare_and_swap(binding, expected_version=current.version, replacement=replacement)
    except SecretStoreConflict:
        pass
    else:
        raise AssertionError("host_conflict_missing")

    # A real row-lock timeout must stop this operation without replaying the CAS.
    with psycopg.connect() as locker:
        locker.execute("SELECT 1 FROM agent_credential_private.bindings WHERE binding_key=%s FOR UPDATE", (key,))
        started = time.monotonic()
        try:
            store.compare_and_swap(binding, expected_version=replacement.version,
                                   replacement=replace(replacement, version=replacement.version + 1))
        except SecretStoreAmbiguousWrite:
            pass
        else:
            raise AssertionError("host_lock_timeout_missing")
        assert time.monotonic() - started < 5
    assert store.read(binding) == replacement

    # The existing synthetic hold sleeps in the SQL function; statement_timeout
    # cancels it before mutation. Client classification intentionally stays ambiguous.
    with psycopg.connect() as admin:
        admin.execute("INSERT INTO synthetic_vault.test_faults VALUES ('hold_initial_cas_lock')")
    started = time.monotonic()
    try:
        store.compare_and_swap(binding, expected_version=replacement.version,
                               replacement=replace(replacement, version=replacement.version + 1))
    except SecretStoreAmbiguousWrite:
        pass
    else:
        raise AssertionError("host_statement_timeout_missing")
    assert time.monotonic() - started < 5
    with psycopg.connect() as admin:
        admin.execute("DELETE FROM synthetic_vault.test_faults")
    assert store.read(binding) == replacement

    barrier = Barrier(2)

    def race(attempt):
        candidate = replace(replacement, version=replacement.version + 1,
                            state="refreshing", active_attempt_id=attempt)
        barrier.wait(timeout=5)
        try:
            store.compare_and_swap(binding, expected_version=replacement.version, replacement=candidate)
            return "committed"
        except SecretStoreConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(race, name) for name in ("host-a", "host-b")]
        assert sorted(f.result(timeout=10) for f in futures) == ["committed", "conflict"]
    assert store.read(binding).version == replacement.version + 1
    assert all(connection.closed for connection in connections)
    print("Synthetic PostgreSQL host adapter: read/CAS, timeouts, independent CAS and cleanup PASS")
