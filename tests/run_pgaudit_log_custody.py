"""Behavioral pgAudit parameter-redaction proof on disposable PostgreSQL 17."""
from contextlib import contextmanager
from hashlib import sha256
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from run_postgres_log_custody import apply_role_settings, expect_factory_blocked, server_logs
from run_secret_tls_contract import HOST, PASSWORD, _admin, _certificates, tls_factory

BASE_IMAGE = "postgres:17.11-bookworm"
PGAUDIT_PACKAGE = "postgresql-17-pgaudit=17.1-2.pgdg12+1"
PGAUDIT_VERSION = "17.1"
AUDIT_POSITIVE = "SYNTHETIC:pgaudit-positive-4d9b2a"
AUDIT_PROTECTED = "SYNTHETIC:pgaudit-protected-b73c11"
POSITIVE_SQL_TAG = "pgaudit_positive_control_6e391a"
PROTECTED_SQL_TAG = "pgaudit_protected_control_8c42f7"
LIMITS = dict(
    connect_timeout=5,
    options="-c statement_timeout=5000 -c lock_timeout=1000 -c idle_in_transaction_session_timeout=5000",
    autocommit=False,
    prepare_threshold=None,
)


def _command(args, *, timeout=120, input_bytes=None):
    result = subprocess.run(args, input=input_bytes, capture_output=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError("synthetic_pgaudit_command_failed")
    return result.stdout.decode().strip()


def _build_image():
    tag = "synthetic-pgaudit-" + uuid4().hex[:12]
    dockerfile = f"""FROM {BASE_IMAGE}
RUN set -eux; \\
    test \"$(postgres --version | awk '{{print $3}}')\" = \"17.11\"; \\
    . /etc/os-release; test \"$VERSION_CODENAME\" = \"bookworm\"; \\
    apt-get update; \\
    apt-get install -y --no-install-recommends '{PGAUDIT_PACKAGE}'; \\
    test \"$(dpkg-query -W -f='${{Version}}' postgresql-17-pgaudit)\" = \"17.1-2.pgdg12+1\"; \\
    rm -rf /var/lib/apt/lists/*
""".encode()
    _command(["docker", "build", "--pull", "--tag", tag, "-"], timeout=240, input_bytes=dockerfile)
    package = _command([
        "docker", "run", "--rm", "--entrypoint", "dpkg-query", tag,
        "-W", "-f=${Version}", "postgresql-17-pgaudit",
    ])
    if package != "17.1-2.pgdg12+1":
        raise RuntimeError("synthetic_pgaudit_package_version_mismatch")
    return tag


@contextmanager
def _pgaudit_server(directory, image):
    name = "synthetic-pgaudit-db-" + uuid4().hex[:12]
    try:
        _command([
            "docker", "run", "--rm", "--user", "root", "--mount",
            f"type=bind,src={directory},dst=/tls", image,
            "chown", "postgres:postgres", "/tls/server.key",
        ], timeout=60)
        container_id = _command([
            "docker", "run", "--detach", "--rm", "--name", name,
            "--publish", "127.0.0.1::5432",
            "--mount", f"type=bind,src={directory},dst=/tls,readonly",
            "--env", "POSTGRES_DB=agent_checkpoint_ci", "--env", "POSTGRES_USER=postgres",
            "--env", f"POSTGRES_PASSWORD={PASSWORD}", image,
            "-c", "shared_preload_libraries=pgaudit",
            "-c", "ssl=on", "-c", "ssl_cert_file=/tls/valid.crt",
            "-c", "ssl_key_file=/tls/server.key",
        ])
        if not re.fullmatch(r"[0-9a-f]{64}", container_id):
            raise RuntimeError("synthetic_pgaudit_server_identity_invalid")
        port = int(_command(["docker", "port", name, "5432/tcp"]).rsplit(":", 1)[1])
        ready = False
        for _ in range(80):
            check = subprocess.run([
                "docker", "exec", name, "pg_isready", "-h", "127.0.0.1",
                "-U", "postgres", "-d", "agent_checkpoint_ci",
            ], capture_output=True, timeout=5)
            if check.returncode == 0:
                ready = True
                break
            time.sleep(0.25)
        if not ready:
            raise RuntimeError("synthetic_pgaudit_server_not_ready")
        yield port, name
    finally:
        subprocess.run(["docker", "rm", "--force", "--volumes", name], capture_output=True, timeout=30)


def _configure_contract(port, ca):
    with _admin(port, ca) as admin:
        admin.execute("CREATE EXTENSION pgaudit")
        version = admin.execute(
            "SELECT extversion FROM pg_extension WHERE extname='pgaudit'"
        ).fetchone()
        if version != (PGAUDIT_VERSION,):
            raise AssertionError("synthetic_pgaudit_extension_version_mismatch")
        loaded = admin.execute(
            "SELECT current_setting('shared_preload_libraries'), current_setting('pgaudit.log_parameter')"
        ).fetchone()
        if loaded[0] != "pgaudit" or loaded[1] not in ("off", "on"):
            raise AssertionError("synthetic_pgaudit_loaded_control_missing")
        admin.execute((ROOT / "tests/support/vault_postgres_contract.sql").read_text(), prepare=False)
        admin.execute("ALTER ROLE secret_test_host_a PASSWORD 'SYNTHETIC:tls-ci-only'")
        admin.execute("CREATE TABLE pgaudit_parameter_probe(id integer PRIMARY KEY)")
        admin.execute("INSERT INTO pgaudit_parameter_probe VALUES (1)")
        admin.execute("GRANT SELECT ON pgaudit_parameter_probe TO secret_test_host_a")


def _positive_control(port, ca, server_name):
    with _admin(port, ca) as admin:
        admin.execute("SET pgaudit.log='read'")
        admin.execute("SET pgaudit.log_parameter=on")
        row = admin.execute(
            f"SELECT id FROM pgaudit_parameter_probe WHERE id=1 AND %s::text IS NOT NULL /* {POSITIVE_SQL_TAG} */",
            (AUDIT_POSITIVE,),
        ).fetchone()
        if row != (1,):
            raise AssertionError("synthetic_pgaudit_positive_query_failed")
    payload = server_logs(server_name)
    if (b"AUDIT:" not in payload or POSITIVE_SQL_TAG.encode() not in payload
            or AUDIT_POSITIVE.encode() not in payload):
        raise AssertionError("synthetic_pgaudit_parameter_positive_control_missing")


def _protected_control(port, ca, server_name):
    apply_role_settings(port, ca, (
        "ALTER ROLE secret_test_host_a SET pgaudit.log='read'",
        "ALTER ROLE secret_test_host_a SET pgaudit.log_parameter=on",
    ))
    try:
        expect_factory_blocked()
        apply_role_settings(port, ca, (
            "ALTER ROLE secret_test_host_a SET pgaudit.log_parameter=off",
        ))
        connection = tls_factory(**LIMITS)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_setting('pgaudit.log'), current_setting('pgaudit.log_parameter')"
                )
                if cursor.fetchone() != ("read", "off"):
                    raise AssertionError("synthetic_pgaudit_protected_policy_missing")
                cursor.execute(
                    f"SELECT id FROM pgaudit_parameter_probe WHERE id=1 AND %s::text IS NOT NULL /* {PROTECTED_SQL_TAG} */",
                    (AUDIT_PROTECTED,),
                )
                if cursor.fetchone() != (1,):
                    raise AssertionError("synthetic_pgaudit_protected_query_failed")
            connection.commit()
        finally:
            connection.close()
        payload = server_logs(server_name)
        if b"AUDIT:" not in payload or PROTECTED_SQL_TAG.encode() not in payload:
            raise AssertionError("synthetic_pgaudit_protected_log_channel_missing")
        if AUDIT_PROTECTED.encode() in payload:
            raise AssertionError("synthetic_pgaudit_protected_parameter_logged")
    finally:
        apply_role_settings(port, ca, (
            "ALTER ROLE secret_test_host_a RESET pgaudit.log",
            "ALTER ROLE secret_test_host_a RESET pgaudit.log_parameter",
        ))


def main():
    if os.environ.get("AGENT_EPHEMERAL_TLS_TEST") != "1":
        raise SystemExit("refusing_non_ephemeral_pgaudit_custody")
    for key in list(os.environ):
        if key.startswith("PG"):
            del os.environ[key]

    image = None
    try:
        image = _build_image()
        with tempfile.TemporaryDirectory(prefix="synthetic-pgaudit-log-") as temporary:
            directory = Path(temporary)
            directory.chmod(0o755)
            _certificates(directory)
            ca = directory / "ca.crt"
            with _pgaudit_server(directory, image) as (port, server_name):
                _configure_contract(port, ca)
                os.environ["SYNTHETIC_TLS_PORT"] = str(port)
                os.environ["SYNTHETIC_TLS_CA"] = str(ca)
                os.environ["SYNTHETIC_TLS_CA_SHA256"] = sha256(ca.read_bytes()).hexdigest()
                _positive_control(port, ca, server_name)
                _protected_control(port, ca, server_name)
    finally:
        for name in ("SYNTHETIC_TLS_PORT", "SYNTHETIC_TLS_CA", "SYNTHETIC_TLS_CA_SHA256"):
            os.environ.pop(name, None)
        if image:
            subprocess.run(["docker", "image", "rm", "--force", image], capture_output=True, timeout=60)

    print("Synthetic pgAudit 17.1 behavior: parameter-on positive control observed and protected parameter absent with strict handoff PASS")


if __name__ == "__main__":
    main()
