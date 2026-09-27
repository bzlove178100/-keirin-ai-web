"""Disposable Docker PostgreSQL TLS contract. All keys/passwords are synthetic."""
from contextlib import contextmanager
from dataclasses import replace
from hashlib import sha256
from datetime import datetime, timedelta, timezone
import os
import multiprocessing
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent_core.durable_secret_store import DurableVersionedSecretStore
from agent_core.postgres_host_profile import PostgresHostProfile
from agent_core.postgres_host_factory import StrictPostgresConnectionFactory
from agent_core.bootstrap_lease import BootstrapPasswordLease
from agent_core.postgres_secret_process import ProcessDeadlinePostgresSecretBackend
from agent_core.refresh_credentials import CredentialBinding
from agent_core.versioned_secret_store import SecretStoreError, SecretStoreAmbiguousWrite, SecretStoreConflict

HOST = "db.synthetic.invalid"
PASSWORD = "SYNTHETIC:tls-ci-only"
BINDING = CredentialBinding("provider-a", "account-a", ("read:one", "write:one"))


def _command(args, timeout=60):
    completed = subprocess.run(args, capture_output=True, timeout=timeout)
    if completed.returncode:
        raise RuntimeError("synthetic_tls_command_failed")
    return completed.stdout.decode().strip()


def _certificates(directory):
    now = datetime.now(timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic CI CA")])
    ca = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
          .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
          .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=2))
          .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
          .sign(ca_key, hashes.SHA256()))
    (directory / "ca.crt").write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    (directory / "server.key").write_bytes(server_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    (directory / "server.key").chmod(0o600)
    for filename, start, end in (
        ("valid.crt", now - timedelta(hours=1), now + timedelta(days=1)),
        ("expired.crt", now - timedelta(days=3), now - timedelta(days=2)),
    ):
        cert = (x509.CertificateBuilder()
                .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, HOST)]))
                .issuer_name(name).public_key(server_key.public_key())
                .serial_number(x509.random_serial_number()).not_valid_before(start).not_valid_after(end)
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                .add_extension(x509.SubjectAlternativeName([x509.DNSName(HOST)]), critical=False)
                .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
                .sign(ca_key, hashes.SHA256()))
        (directory / filename).write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    # Distinct trust anchor for the wrong-CA test; no private CA keys are saved.
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Wrong Synthetic CA")])
    other_ca = (x509.CertificateBuilder().subject_name(other_name).issuer_name(other_name)
                .public_key(other_key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=1))
                .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
                .sign(other_key, hashes.SHA256()))
    (directory / "wrong-ca.crt").write_bytes(other_ca.public_bytes(serialization.Encoding.PEM))


@contextmanager
def _server(directory, certificate, *, include_name=False):
    name = "synthetic-secret-tls-" + uuid4().hex[:12]
    try:
        args = ["docker", "run", "--detach", "--rm", "--name", name,
                "--publish", "127.0.0.1::5432", "--mount", f"type=bind,src={directory},dst=/tls,readonly",
                "--env", "POSTGRES_DB=agent_checkpoint_ci", "--env", "POSTGRES_USER=postgres",
                "--env", f"POSTGRES_PASSWORD={PASSWORD}", "postgres:17"]
        if certificate:
            args += ["-c", "ssl=on", "-c", f"ssl_cert_file=/tls/{certificate}",
                     "-c", "ssl_key_file=/tls/server.key"]
        _command(args)
        port = int(_command(["docker", "port", name, "5432/tcp"]).rsplit(":", 1)[1])
        ready = False
        for _ in range(80):
            check = subprocess.run(["docker", "exec", name, "pg_isready", "-h", "127.0.0.1", "-U", "postgres",
                                    "-d", "agent_checkpoint_ci"], capture_output=True, timeout=5)
            if check.returncode == 0:
                ready = True
                break
            time.sleep(0.25)
        if not ready:
            raise RuntimeError("synthetic_tls_server_not_ready")
        yield (port, name) if include_name else port
    finally:
        # Only this uniquely named disposable container is removed, even on failure.
        subprocess.run(["docker", "rm", "--force", "--volumes", name], capture_output=True, timeout=30)


def _profile(port, ca):
    return PostgresHostProfile(HOST, "127.0.0.1", port, "agent_checkpoint_ci", "secret_test_host_a", str(ca))


def tls_factory(**kwargs):
    if os.environ.get("AGENT_EPHEMERAL_TLS_TEST") != "1":
        raise RuntimeError("refusing_non_ephemeral_tls")
    profile = replace(_profile(int(os.environ["SYNTHETIC_TLS_PORT"]), Path(os.environ["SYNTHETIC_TLS_CA"])),
                      hostname=os.environ.get("SYNTHETIC_TLS_HOST", HOST))
    # Resolve this synthetic source only inside the deadline child. No live secret
    # facility, environment password or configured production factory is introduced.
    return StrictPostgresConnectionFactory(
        profile, driver_connect=psycopg.connect,
        trusted_ca_sha256=os.environ["SYNTHETIC_TLS_CA_SHA256"],
        password_source=lambda: BootstrapPasswordLease(
            profile.login, profile.database, int(os.environ.get("SYNTHETIC_BOOTSTRAP_VERSION", "1")),
            int(time.time()) + int(os.environ.get("SYNTHETIC_BOOTSTRAP_TTL", "60")),
            PASSWORD if os.environ.get("SYNTHETIC_BOOTSTRAP_VERSION", "1") == "1" else "SYNTHETIC:rotated-ci-only",
        ),
        lease_is_current=lambda version: (
            os.environ.get("SYNTHETIC_BOOTSTRAP_REVOKED") != "1"
            and version == int(os.environ.get("SYNTHETIC_CURRENT_VERSION",
                                               os.environ.get("SYNTHETIC_BOOTSTRAP_VERSION", "1")))
        ),
    )(**kwargs)


class _CrashAfterCommit:
    """Crash only after the adapter's real commit, after strict factory preflight."""
    autocommit = False

    def __init__(self, connection):
        self.connection = connection

    def cursor(self):
        return self.connection.cursor()

    def commit(self):
        self.connection.commit()
        os._exit(73)

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()


def crash_after_commit_factory(**kwargs):
    return _CrashAfterCommit(tls_factory(**kwargs))


def _store(factory=tls_factory, *, deadline_ms=10000):
    return DurableVersionedSecretStore(ProcessDeadlinePostgresSecretBackend(
        factory, BINDING, operation_timeout_ms=deadline_ms,
        statement_timeout_ms=4000, lock_timeout_ms=3000))


def _expect_fixed(error_type, message, operation):
    try:
        operation()
    except error_type as error:
        assert type(error) is error_type
        assert str(error) == message
        assert error.__context__ is None and error.__cause__ is None
        return
    raise AssertionError("synthetic_recovery_expected_failure_missing")


def _restart_reader(expected):
    # A fresh parent interpreter constructs its own backend and spawns a new child.
    assert _store().read(BINDING) == expected


def _run_recovery(port, ca, server_name, current):
    children = {child.pid for child in multiprocessing.active_children()}
    store = _store()
    candidate = replace(current, version=current.version + 1)
    for key, value in (("SYNTHETIC_BOOTSTRAP_TTL", "0"),
                       ("SYNTHETIC_CURRENT_VERSION", "2"),
                       ("SYNTHETIC_BOOTSTRAP_REVOKED", "1"),
                       ("SYNTHETIC_TLS_HOST", "wrong.synthetic.invalid")):
        os.environ[key] = value
        try:
            _expect_fixed(SecretStoreError, "secret_store_backend_unavailable", lambda: store.read(BINDING))
            _expect_fixed(SecretStoreError, "secret_store_backend_unavailable", lambda: store.compare_and_swap(
                BINDING, expected_version=current.version, replacement=candidate))
        finally:
            del os.environ[key]
        assert _store().read(BINDING) == current

    # A real COMMIT survives a child crash. Never replay an unknown write outcome.
    _expect_fixed(SecretStoreAmbiguousWrite, "secret_store_write_ambiguous",
                  lambda: _store(crash_after_commit_factory).compare_and_swap(
                      BINDING, expected_version=current.version, replacement=candidate))
    assert _store().read(BINDING) == candidate
    _expect_fixed(SecretStoreConflict, "secret_store_version_conflict", lambda: store.compare_and_swap(
        BINDING, expected_version=current.version, replacement=candidate))
    current = candidate

    # Deadline kills a TLS client blocked on a real row lock before it can commit.
    with _admin(port, ca) as locker:
        locker.execute("SELECT 1 FROM agent_credential_private.bindings WHERE binding_key=%s FOR UPDATE",
                       (DurableVersionedSecretStore.key_for(BINDING),))
        _expect_fixed(SecretStoreAmbiguousWrite, "secret_store_write_ambiguous",
                      lambda: _store(deadline_ms=1500).compare_and_swap(
                          BINDING, expected_version=current.version,
                          replacement=replace(current, version=current.version + 1)))
    assert _store().read(BINDING) == current

    reader = multiprocessing.get_context("spawn").Process(target=_restart_reader, args=(current,))
    reader.start()
    try:
        reader.join(15)
        assert reader.exitcode == 0
    finally:
        if reader.is_alive():
            reader.kill()
            reader.join(2)
        reader.close()

    # Pause only our uniquely named disposable container. No live DB is contacted.
    _command(["docker", "pause", server_name])
    try:
        _expect_fixed(SecretStoreError, "secret_store_backend_unavailable",
                      lambda: _store(deadline_ms=1500).read(BINDING))
        _expect_fixed(SecretStoreAmbiguousWrite, "secret_store_write_ambiguous",
                      lambda: _store(deadline_ms=1500).compare_and_swap(
                          BINDING, expected_version=current.version,
                          replacement=replace(current, version=current.version + 1)))
    finally:
        _command(["docker", "unpause", server_name])
    assert _store().read(BINDING) == current
    _command(["docker", "restart", "--time", "0", server_name])
    # Readiness polling belongs to the fixture, never to the production adapter.
    for attempt in range(80):
        result = subprocess.run(["docker", "exec", server_name, "pg_isready", "-h", "127.0.0.1",
                                 "-U", "postgres", "-d", "agent_checkpoint_ci"],
                                capture_output=True, timeout=5)
        if result.returncode == 0:
            break
        time.sleep(0.25)
    else:
        raise AssertionError("synthetic_restart_not_ready")
    assert _store().read(BINDING) == current

    revoked = replace(current, version=current.version + 1, state="revoked",
                      refresh_secret=None, failure="credential_source_revoked")
    assert store.compare_and_swap(BINDING, expected_version=current.version, replacement=revoked) == revoked
    _expect_fixed(SecretStoreAmbiguousWrite, "secret_store_write_ambiguous", lambda: _store().compare_and_swap(
        BINDING, expected_version=revoked.version, replacement=replace(current, version=revoked.version + 1)))
    assert _store().read(BINDING) == revoked
    assert {child.pid for child in multiprocessing.active_children()} == children
    deadline = time.monotonic() + 6
    while True:
        with _admin(port, ca) as admin:
            count = admin.execute("SELECT count(*) FROM pg_stat_activity WHERE application_name='agent-secret-host'").fetchone()[0]
        if count == 0:
            break
        assert time.monotonic() < deadline, "synthetic_tls_sessions_not_reaped"
        time.sleep(0.05)
    print("Synthetic full host recovery: lease/TLS rejection, commit crash, lock deadline, parent/server restart, DB outage and terminal revocation PASS")


def _must_block_store(store):
    try:
        store.read(BINDING)
    except SecretStoreError:
        return
    raise AssertionError("synthetic_factory_expected_rejection_missing")


def _must_reject(profile):
    rejected = False
    try:
        with psycopg.connect(**profile.connection_parameters(), password=PASSWORD, connect_timeout=2):
            pass
    except psycopg.OperationalError:
        rejected = True
    if not rejected:
        raise AssertionError("synthetic_tls_expected_rejection_missing")


def _admin(port, ca, *, encrypted=True):
    return psycopg.connect(host=HOST, hostaddr="127.0.0.1", port=port, user="postgres",
                           password=PASSWORD, dbname="agent_checkpoint_ci", connect_timeout=2,
                           sslmode="verify-full" if encrypted else "disable", sslrootcert=str(ca),
                           gssencmode="disable")


def main():
    if os.environ.get("AGENT_EPHEMERAL_TLS_TEST") != "1":
        raise SystemExit("refusing_non_ephemeral_tls")
    # Test child inheritance has no ambient libpq configuration. This is a fixture
    # control, not a production environment sanitizer or a bootstrap integration.
    for key in list(os.environ):
        if key.startswith("PG"):
            del os.environ[key]
    with tempfile.TemporaryDirectory(prefix="synthetic-secret-tls-") as temporary:
        directory = Path(temporary)
        directory.chmod(0o755)
        _certificates(directory)
        # Resolve ownership using the image's postgres account, not a guessed UID.
        _command(["docker", "run", "--rm", "--user", "root", "--mount",
                  f"type=bind,src={directory},dst=/tls", "postgres:17", "chown", "postgres:postgres", "/tls/server.key"])
        ca = directory / "ca.crt"
        with _server(directory, "valid.crt", include_name=True) as (port, server_name):
            with _admin(port, ca) as admin:
                admin.execute((ROOT / "tests/support/vault_postgres_contract.sql").read_text(), prepare=False)
                admin.execute("ALTER ROLE secret_test_host_a PASSWORD 'SYNTHETIC:tls-ci-only'")
                key = DurableVersionedSecretStore.key_for(BINDING)
                admin.execute("DELETE FROM agent_credential_private.host_bindings WHERE binding_key='binding-a'")
                admin.execute("UPDATE agent_credential_private.bindings SET binding_key=%s WHERE binding_key='binding-a'", (key,))
                admin.execute("INSERT INTO agent_credential_private.host_bindings VALUES ('secret_test_host_a',%s)", (key,))
            os.environ["SYNTHETIC_TLS_PORT"] = str(port)
            os.environ["SYNTHETIC_TLS_CA"] = str(ca)
            # Pin comes from fixture provisioning; never derive it in the factory
            # from an untrusted candidate file on each connection.
            os.environ["SYNTHETIC_TLS_CA_SHA256"] = sha256(ca.read_bytes()).hexdigest()
            store = DurableVersionedSecretStore(ProcessDeadlinePostgresSecretBackend(tls_factory, BINDING))
            current = store.read(BINDING)
            updated = replace(current, version=current.version + 1)
            assert store.compare_and_swap(BINDING, expected_version=current.version, replacement=updated) == updated
            assert store.read(BINDING) == updated
            original_ca = ca.read_bytes()
            ca.write_bytes((directory / "wrong-ca.crt").read_bytes())
            try:
                _must_block_store(store)
            finally:
                ca.write_bytes(original_ca)
            assert store.read(BINDING) == updated
            os.environ["SYNTHETIC_BOOTSTRAP_REVOKED"] = "1"
            try:
                _must_block_store(store)
            finally:
                del os.environ["SYNTHETIC_BOOTSTRAP_REVOKED"]
            with _admin(port, ca) as admin:
                admin.execute("ALTER ROLE secret_test_host_a PASSWORD 'SYNTHETIC:rotated-ci-only'")
            try:
                _must_block_store(store)  # Old lease/password cannot connect.
                os.environ["SYNTHETIC_BOOTSTRAP_VERSION"] = "2"
                assert store.read(BINDING) == updated
            finally:
                with _admin(port, ca) as admin:
                    admin.execute("ALTER ROLE secret_test_host_a PASSWORD 'SYNTHETIC:tls-ci-only'")
                os.environ["SYNTHETIC_BOOTSTRAP_VERSION"] = "1"
            # Even an otherwise valid TLS session must be rejected if ambient
            # configuration or the actual login's privileges changed.
            os.environ["PGSERVICE"] = "SYNTHETIC:unapproved"
            try:
                _must_block_store(store)
            finally:
                del os.environ["PGSERVICE"]
            for enable, disable in (
                ("ALTER ROLE secret_test_host_a CREATEDB", "ALTER ROLE secret_test_host_a NOCREATEDB"),
                ("GRANT secret_test_host_b TO secret_test_host_a", "REVOKE secret_test_host_b FROM secret_test_host_a"),
                ("ALTER ROLE secret_test_host_a SET default_transaction_read_only=on", "ALTER ROLE secret_test_host_a RESET default_transaction_read_only"),
            ):
                with _admin(port, ca) as admin:
                    admin.execute(enable)
                try:
                    _must_block_store(store)
                finally:
                    with _admin(port, ca) as admin:
                        admin.execute(disable)
            assert store.read(BINDING) == updated
            _must_reject(replace(_profile(port, ca), hostname="wrong.synthetic.invalid"))
            _must_reject(replace(_profile(port, ca), root_certificate=str(directory / "wrong-ca.crt")))
            # Positive control after negatives rules out an unavailable server.
            assert store.read(BINDING) == updated
            _run_recovery(port, ca, server_name, updated)
        for certificate in ("expired.crt", None):
            with _server(directory, certificate) as port:
                # Ensure a valid account exists and the server is reachable, so a
                # TLS test cannot pass merely because authentication/availability failed.
                with _admin(port, ca, encrypted=False) as admin:
                    admin.execute("CREATE ROLE secret_test_host_a LOGIN PASSWORD 'SYNTHETIC:tls-ci-only'")
                _must_reject(_profile(port, ca))
                with _admin(port, ca, encrypted=False) as admin:
                    assert admin.execute("SELECT 1").fetchone() == (1,)
    print("Synthetic TLS PostgreSQL: verified TLS process read/CAS, wrong hostname/CA, expired certificate and plaintext rejection PASS")
    print("Synthetic strict factory: ambient rejection, session/privilege/read-write checks and verified handoff PASS")
    print("Synthetic pinned trust/bootstrap: sealed CA TLS, CA replacement rejection, revocation and password rotation PASS")


if __name__ == "__main__":
    main()
