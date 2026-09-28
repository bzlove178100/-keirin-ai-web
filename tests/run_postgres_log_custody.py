"""Synthetic PostgreSQL server-log custody proof; no real endpoint or credential."""
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import sys

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent_core.durable_secret_store import DurableSecretBackendUnavailable
from run_secret_tls_contract import _admin, _certificates, _server, PASSWORD, tls_factory

LOG_SECRET = "SYNTHETIC:postgres-log-secret-marker-7d7b17"
LIMITS = dict(
    connect_timeout=5,
    options="-c statement_timeout=5000 -c lock_timeout=1000 -c idle_in_transaction_session_timeout=5000",
    autocommit=False,
    prepare_threshold=None,
)


def expect_factory_blocked():
    try:
        connection = tls_factory(**LIMITS)
    except DurableSecretBackendUnavailable as error:
        if str(error) != "postgres_host_factory_unavailable":
            raise AssertionError("synthetic_log_gate_error_mismatch") from None
        return
    else:
        connection.close()
    raise AssertionError("synthetic_log_gate_expected_rejection_missing")


def require_factory_open():
    connection = tls_factory(**LIMITS)
    connection.close()


def prove_bind_redaction(server_name):
    connection = tls_factory(**LIMITS)
    try:
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT 1 / 0 WHERE %s::text IS NOT NULL", (LOG_SECRET,))
        except psycopg.errors.DivisionByZero:
            pass
        else:
            raise AssertionError("synthetic_log_error_missing")
        finally:
            cursor.close()
        connection.rollback()
    finally:
        connection.close()

    # Observe the real disposable PostgreSQL stderr channel without printing it.
    result = subprocess.run(["docker", "logs", server_name], capture_output=True, timeout=10)
    if result.returncode != 0:
        raise AssertionError("synthetic_postgres_log_read_failed")
    payload = result.stdout + result.stderr
    if b"division by zero" not in payload:
        raise AssertionError("synthetic_postgres_log_positive_control_missing")
    if LOG_SECRET.encode() in payload:
        raise AssertionError("synthetic_postgres_bind_secret_logged")


def main():
    if os.environ.get("AGENT_EPHEMERAL_TLS_TEST") != "1":
        raise SystemExit("refusing_non_ephemeral_log_custody")
    for key in list(os.environ):
        if key.startswith("PG"):
            del os.environ[key]

    import tempfile
    with tempfile.TemporaryDirectory(prefix="synthetic-postgres-log-") as temporary:
        directory = Path(temporary)
        directory.chmod(0o755)
        _certificates(directory)
        subprocess.run([
            "docker", "run", "--rm", "--user", "root", "--mount",
            f"type=bind,src={directory},dst=/tls", "postgres:17",
            "chown", "postgres:postgres", "/tls/server.key",
        ], check=True, capture_output=True, timeout=60)
        ca = directory / "ca.crt"
        with _server(directory, "valid.crt", include_name=True) as (port, server_name):
            with _admin(port, ca) as admin:
                admin.execute((ROOT / "tests/support/vault_postgres_contract.sql").read_text(), prepare=False)
                admin.execute("ALTER ROLE secret_test_host_a PASSWORD 'SYNTHETIC:tls-ci-only'")
            os.environ["SYNTHETIC_TLS_PORT"] = str(port)
            os.environ["SYNTHETIC_TLS_CA"] = str(ca)
            os.environ["SYNTHETIC_TLS_CA_SHA256"] = sha256(ca.read_bytes()).hexdigest()

            # PostgreSQL 17 defaults satisfy the log-safe handoff policy. Prove each
            # secret-bearing log path is fail-closed if an operator weakens it.
            require_factory_open()
            for enable, disable in (
                ("ALTER ROLE secret_test_host_a SET log_statement='all'",
                 "ALTER ROLE secret_test_host_a RESET log_statement"),
                ("ALTER ROLE secret_test_host_a SET log_parameter_max_length_on_error=-1",
                 "ALTER ROLE secret_test_host_a RESET log_parameter_max_length_on_error"),
                ("ALTER ROLE secret_test_host_a SET log_duration=on",
                 "ALTER ROLE secret_test_host_a RESET log_duration"),
                ("ALTER ROLE secret_test_host_a SET log_min_duration_statement=0",
                 "ALTER ROLE secret_test_host_a RESET log_min_duration_statement"),
                ("ALTER ROLE secret_test_host_a SET log_min_duration_sample=0",
                 "ALTER ROLE secret_test_host_a RESET log_min_duration_sample"),
            ):
                with _admin(port, ca) as admin:
                    admin.execute(enable)
                try:
                    expect_factory_blocked()
                finally:
                    with _admin(port, ca) as admin:
                        admin.execute(disable)
                require_factory_open()

            prove_bind_redaction(server_name)

    print("Synthetic PostgreSQL log custody: unsafe session policy rejected and error Bind marker absent from observed server logs PASS")


if __name__ == "__main__":
    main()
