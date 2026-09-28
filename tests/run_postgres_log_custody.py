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
PLAN_POSITIVE = "SYNTHETIC:auto-explain-positive-9c3912"
PLAN_PROTECTED = "SYNTHETIC:auto-explain-protected-41e821"
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


def apply_role_settings(port, ca, statements):
    with _admin(port, ca) as admin:
        for statement in statements:
            admin.execute(statement)


def server_logs(server_name):
    result = subprocess.run(["docker", "logs", server_name], capture_output=True, timeout=10)
    if result.returncode != 0:
        raise AssertionError("synthetic_postgres_log_read_failed")
    return result.stdout + result.stderr


def prove_loaded_plan_guard(port, ca, server_name):
    # LOAD the real module: arbitrary dotted GUC placeholders alone do not prove
    # extension behavior. Positive control is confined to a synthetic admin session.
    with _admin(port, ca) as admin:
        admin.execute("LOAD 'auto_explain'")
        admin.execute("SET auto_explain.log_parameter_max_length=0")
        admin.execute("SET auto_explain.log_verbose=on")
        admin.execute("SET auto_explain.sample_rate=1")
        admin.execute("SET plan_cache_mode=force_custom_plan")
        admin.execute("SET auto_explain.log_min_duration=0")
        row = admin.execute("SELECT %s::text", (PLAN_POSITIVE,)).fetchone()
        if row != (PLAN_POSITIVE,):
            raise AssertionError("synthetic_plan_query_control_failed")
    payload = server_logs(server_name)
    if b"plan:" not in payload or PLAN_POSITIVE.encode() not in payload:
        raise AssertionError("synthetic_plan_constant_positive_control_missing")

    # Preload the actual extension in every fresh dedicated-role session. Even
    # with its Bind list suppressed, an enabled plan logger must block handoff.
    apply_role_settings(port, ca, (
        "ALTER ROLE secret_test_host_a SET session_preload_libraries='auto_explain'",
        "ALTER ROLE secret_test_host_a SET auto_explain.log_parameter_max_length=0",
        "ALTER ROLE secret_test_host_a SET auto_explain.log_verbose=on",
        "ALTER ROLE secret_test_host_a SET auto_explain.log_min_duration=0",
    ))
    try:
        expect_factory_blocked()
        apply_role_settings(port, ca, (
            "ALTER ROLE secret_test_host_a SET auto_explain.log_min_duration=-1",
        ))
        connection = tls_factory(**LIMITS)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_setting('auto_explain.log_min_duration'), "
                               "current_setting('auto_explain.sample_rate')")
                # sample_rate was not set as a dotted placeholder for this role;
                # its registered default proves LOAD without privileged GUC access.
                if cursor.fetchone() != ('-1', '1'):
                    raise AssertionError("synthetic_loaded_extension_control_missing")
                cursor.execute("SELECT %s::text", (PLAN_PROTECTED,))
                if cursor.fetchone() != (PLAN_PROTECTED,):
                    raise AssertionError("synthetic_protected_plan_query_failed")
            connection.commit()
        finally:
            connection.close()
        payload = server_logs(server_name)
        if PLAN_POSITIVE.encode() not in payload:
            raise AssertionError("synthetic_plan_log_channel_missing")
        if PLAN_PROTECTED.encode() in payload:
            raise AssertionError("synthetic_protected_plan_constant_logged")
    finally:
        apply_role_settings(port, ca, (
            "ALTER ROLE secret_test_host_a RESET session_preload_libraries",
            "ALTER ROLE secret_test_host_a RESET auto_explain.log_parameter_max_length",
            "ALTER ROLE secret_test_host_a RESET auto_explain.log_verbose",
            "ALTER ROLE secret_test_host_a RESET auto_explain.log_min_duration",
        ))
    require_factory_open()


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
    payload = server_logs(server_name)
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
            # core and extension parameter-log path is fail-closed if weakened.
            require_factory_open()
            cases = (
                (("ALTER ROLE secret_test_host_a SET log_statement='all'",),
                 ("ALTER ROLE secret_test_host_a RESET log_statement",)),
                (("ALTER ROLE secret_test_host_a SET log_parameter_max_length_on_error=-1",),
                 ("ALTER ROLE secret_test_host_a RESET log_parameter_max_length_on_error",)),
                (("ALTER ROLE secret_test_host_a SET log_duration=on",),
                 ("ALTER ROLE secret_test_host_a RESET log_duration",)),
                (("ALTER ROLE secret_test_host_a SET log_min_duration_statement=0",),
                 ("ALTER ROLE secret_test_host_a RESET log_min_duration_statement",)),
                (("ALTER ROLE secret_test_host_a SET log_min_duration_sample=0",),
                 ("ALTER ROLE secret_test_host_a RESET log_min_duration_sample",)),
                (("ALTER ROLE secret_test_host_a SET auto_explain.log_min_duration=10000",
                  "ALTER ROLE secret_test_host_a SET auto_explain.log_parameter_max_length=-1"),
                 ("ALTER ROLE secret_test_host_a RESET auto_explain.log_min_duration",
                  "ALTER ROLE secret_test_host_a RESET auto_explain.log_parameter_max_length")),
                (("ALTER ROLE secret_test_host_a SET pgaudit.log_parameter=on",),
                 ("ALTER ROLE secret_test_host_a RESET pgaudit.log_parameter",)),
            )
            for enable, disable in cases:
                apply_role_settings(port, ca, enable)
                try:
                    expect_factory_blocked()
                finally:
                    apply_role_settings(port, ca, disable)
                require_factory_open()

            # A loaded extension may remain present, but plan logging must be off.
            safe_extension = (
                "ALTER ROLE secret_test_host_a SET auto_explain.log_min_duration=-1",
                "ALTER ROLE secret_test_host_a SET auto_explain.log_parameter_max_length=0",
                "ALTER ROLE secret_test_host_a SET pgaudit.log_parameter=off",
            )
            apply_role_settings(port, ca, safe_extension)
            require_factory_open()
            apply_role_settings(port, ca, (
                "ALTER ROLE secret_test_host_a RESET auto_explain.log_min_duration",
                "ALTER ROLE secret_test_host_a RESET auto_explain.log_parameter_max_length",
                "ALTER ROLE secret_test_host_a RESET pgaudit.log_parameter",
            ))
            require_factory_open()

            prove_loaded_plan_guard(port, ca, server_name)
            prove_bind_redaction(server_name)

    print("Synthetic PostgreSQL log custody: loaded plan logger rejected, protected plan/Bind markers absent from observed server logs PASS")


if __name__ == "__main__":
    main()
