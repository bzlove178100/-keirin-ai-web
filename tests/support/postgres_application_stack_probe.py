"""Synthetic co-resident application secret-stack probe for the hardened client."""
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
from agent_core.versioned_secret_store import SecretStoreConflict, SecretStoreError
from support.stdlib_pg_driver import connect as stdlib_connect

BINDING = CredentialBinding("provider-a", "account-a", ("read:one", "write:one"))
PASSWORD_FILE = Path("/tmp/bootstrap-password")
VERSION_FILE = Path("/tmp/bootstrap-version")
CURRENT_VERSION_FILE = Path("/tmp/bootstrap-current-version")
SOURCE_USED_FILE = Path("/tmp/bootstrap-source-used")
GATE = Path("/tmp/app-stack-go")
_SCENARIOS = frozenset({
    "success", "bad_ca_pin", "stale_lease", "revoked_lease", "expired_lease",
    "wrong_hostname",
})


def _required(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError("synthetic_app_stack_config_missing")
    return value


def _scenario():
    scenario = os.environ.get("SYNTHETIC_APP_STACK_SCENARIO", "success")
    if scenario not in _SCENARIOS:
        raise RuntimeError("synthetic_app_stack_scenario_invalid")
    return scenario


def _profile():
    return PostgresHostProfile(
        _required("SYNTHETIC_DB_HOST"),
        _required("SYNTHETIC_DB_IP"),
        int(_required("SYNTHETIC_DB_PORT")),
        _required("SYNTHETIC_DB_NAME"),
        _required("SYNTHETIC_DB_USER"),
        _required("SYNTHETIC_DB_CA"),
    )


def _password_source():
    SOURCE_USED_FILE.write_text("used")
    SOURCE_USED_FILE.chmod(0o600)
    profile = _profile()
    password = PASSWORD_FILE.read_text()
    version = int(VERSION_FILE.read_text())
    if password != "SYNTHETIC:tls-ci-only" or version != 1:
        raise RuntimeError("synthetic_app_stack_bootstrap_invalid")
    expires_at = int(time.time()) - 1 if _scenario() == "expired_lease" else int(time.time()) + 60
    return BootstrapPasswordLease(
        profile.login, profile.database, version, expires_at, password
    )


def _lease_is_current(version):
    if _scenario() == "revoked_lease":
        return False
    try:
        return version == int(CURRENT_VERSION_FILE.read_text()) == 1
    except (OSError, ValueError):
        return False


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


def _store():
    return DurableVersionedSecretStore(
        ProcessDeadlinePostgresSecretBackend(
            strict_connection_factory,
            BINDING,
            operation_timeout_ms=8000,
            connect_timeout_seconds=3,
            statement_timeout_ms=4000,
            lock_timeout_ms=1000,
        )
    )


def _wait_for_release():
    deadline = time.monotonic() + 10
    while not GATE.exists():
        if time.monotonic() >= deadline:
            raise RuntimeError("synthetic_app_stack_release_timeout")
        time.sleep(0.02)
    if (not PASSWORD_FILE.is_file() or not VERSION_FILE.is_file()
            or not CURRENT_VERSION_FILE.is_file()):
        raise RuntimeError("synthetic_app_stack_bootstrap_missing")


def _expect_unavailable(scenario):
    try:
        _store().read(BINDING)
    except SecretStoreError as error:
        if (type(error) is not SecretStoreError
                or str(error) != "secret_store_backend_unavailable"
                or error.__context__ is not None or error.__cause__ is not None):
            raise RuntimeError("synthetic_app_stack_rejection_contract_invalid") from None
    else:
        raise RuntimeError("synthetic_app_stack_rejection_missing")

    source_used = SOURCE_USED_FILE.exists()
    if scenario == "bad_ca_pin":
        if source_used:
            raise RuntimeError("synthetic_app_stack_bad_pin_touched_bootstrap")
    elif not source_used:
        raise RuntimeError("synthetic_app_stack_expected_bootstrap_not_used")


def main():
    if os.environ.get("SYNTHETIC_POSTGRES_APP_STACK_PROBE") != "1":
        raise RuntimeError("synthetic_app_stack_gate_required")
    if _required("SYNTHETIC_DB_USER") != "secret_test_host_a" or _required("SYNTHETIC_DB_NAME") != "agent_checkpoint_ci":
        raise RuntimeError("synthetic_app_stack_identity_invalid")
    _wait_for_release()
    scenario = _scenario()
    before_children = {child.pid for child in multiprocessing.active_children()}
    try:
        if scenario != "success":
            _expect_unavailable(scenario)
        else:
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

            try:
                _store().compare_and_swap(BINDING, expected_version=0, replacement=candidate)
            except SecretStoreConflict as error:
                if (type(error) is not SecretStoreConflict
                        or str(error) != "secret_store_version_conflict"
                        or error.__context__ is not None or error.__cause__ is not None):
                    raise RuntimeError("synthetic_app_stack_conflict_contract_invalid") from None
            else:
                raise RuntimeError("synthetic_app_stack_stale_cas_accepted")

            if _store().read(BINDING) != candidate:
                raise RuntimeError("synthetic_app_stack_stale_cas_mutated")

        if {child.pid for child in multiprocessing.active_children()} != before_children:
            raise RuntimeError("synthetic_app_stack_child_not_reaped")
    finally:
        for path in (
            PASSWORD_FILE, VERSION_FILE, CURRENT_VERSION_FILE, SOURCE_USED_FILE, GATE,
        ):
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    print("synthetic_postgres_application_stack_" + scenario + "_ok", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(25) from None
