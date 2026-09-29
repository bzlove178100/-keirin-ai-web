"""Qualify a blocked secret CAS under the co-resident hardened application stack."""
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from uuid import uuid4

from run_application_stack_hardened_composition import (
    IMAGE, LAUNCHER, NETWORK_OPTION, PASSWORD, POSTGRES_IMAGE, ROOT,
    _certificates, _prepare_contract, _server_ip, command, network_data,
    verify_image_provenance, verify_members, verify_network,
)
from run_application_stack_hardened_rejections import (
    _client_args, _verify_client, _wait_running, _write_bootstrap,
)

SCENARIO = "lock_deadline"
LOCK_READY = "/tmp/app-stack-lock-ready"
LOCK_GO = "/tmp/app-stack-lock-go"
LOCK_APP = "synthetic-app-stack-lock-holder"


def _marker_exists(identity, path):
    result = subprocess.run(
        [
            "docker", "exec", identity, LAUNCHER, "-c",
            "from pathlib import Path; raise SystemExit(0 if Path(" + repr(path) + ").is_file() else 1)",
        ],
        capture_output=True,
        timeout=5,
    )
    return result.returncode == 0


def _wait_marker(identity, path):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if _marker_exists(identity, path):
            return
        state = json.loads(command(["docker", "inspect", identity]))[0]["State"]
        if state.get("Running") is not True:
            raise RuntimeError("synthetic_lock_deadline_client_exited_before_marker")
        time.sleep(0.05)
    raise RuntimeError("synthetic_lock_deadline_marker_timeout")


def _touch_marker(identity, path):
    command([
        "docker", "exec", identity, LAUNCHER, "-c",
        "from pathlib import Path; Path(" + repr(path) + ").write_text('go')",
    ])


def _start_lock_holder(server_id, key):
    sql = (
        "BEGIN; SELECT 1 FROM agent_credential_private.bindings WHERE binding_key='"
        + key + "' FOR UPDATE; SELECT pg_sleep(6); COMMIT;"
    )
    return subprocess.Popen(
        [
            "docker", "exec", "--env", "PGAPPNAME=" + LOCK_APP,
            server_id, "psql", "--username", "postgres", "--dbname", "agent_checkpoint_ci",
            "--set", "ON_ERROR_STOP=1", "--command", sql,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _wait_lock_acquired(server_id, process):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("synthetic_lock_deadline_holder_exited_early")
        count = command([
            "docker", "exec", server_id, "psql", "--username", "postgres",
            "--dbname", "agent_checkpoint_ci", "--tuples-only", "--no-align",
            "--command",
            "SELECT count(*) FROM pg_stat_activity WHERE application_name='"
            + LOCK_APP + "' AND state='active' AND wait_event='PgSleep';",
        ])
        if count == "1":
            return
        time.sleep(0.05)
    raise RuntimeError("synthetic_lock_deadline_holder_not_ready")


def _stop_lock_holder(server_id, process):
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        subprocess.run([
            "docker", "exec", server_id, "psql", "--username", "postgres",
            "--dbname", "agent_checkpoint_ci", "--tuples-only", "--no-align",
            "--command",
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name='"
            + LOCK_APP + "';",
        ], capture_output=True, timeout=10)
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
    if process.returncode not in {0, -9, -15}:
        raise RuntimeError("synthetic_lock_deadline_holder_failed")


def _session_count(server_id, application_name):
    if application_name not in {"agent-secret-host", LOCK_APP}:
        raise RuntimeError("synthetic_lock_deadline_session_name_invalid")
    return command([
        "docker", "exec", server_id, "psql", "--username", "postgres",
        "--dbname", "agent_checkpoint_ci", "--tuples-only", "--no-align",
        "--command", "SELECT count(*) FROM pg_stat_activity WHERE application_name='"
        + application_name + "'",
    ])


def _wait_sessions_gone(server_id):
    # A killed client socket and a finished docker-exec process can disappear from
    # pg_stat_activity a few scheduler ticks after their local processes have exited.
    # Treat that as cleanup convergence, not a data-integrity failure, but keep it
    # strictly bounded and require both fixture and application sessions to reach zero.
    deadline = time.monotonic() + 6
    while time.monotonic() < deadline:
        if (_session_count(server_id, "agent-secret-host") == "0"
                and _session_count(server_id, LOCK_APP) == "0"):
            return
        time.sleep(0.05)
    raise RuntimeError("synthetic_lock_deadline_session_cleanup_timeout")


def _verify_unchanged(server_id, key):
    record = command([
        "docker", "exec", server_id, "psql", "--username", "postgres",
        "--dbname", "agent_checkpoint_ci", "--tuples-only", "--no-align",
        "--command", "SELECT version::text || ':' || state FROM agent_credential_private.bindings WHERE binding_key='" + key + "'",
    ])
    secret_ok = command([
        "docker", "exec", server_id, "psql", "--username", "postgres",
        "--dbname", "agent_checkpoint_ci", "--tuples-only", "--no-align",
        "--command", "SELECT CASE WHEN s.value='SYNTHETIC:a0' THEN 'ok' ELSE 'bad' END FROM agent_credential_private.bindings b JOIN synthetic_vault.secrets s ON s.id=b.secret_id WHERE b.binding_key='" + key + "'",
    ])
    unrelated_ok = command([
        "docker", "exec", server_id, "psql", "--username", "postgres",
        "--dbname", "agent_checkpoint_ci", "--tuples-only", "--no-align",
        "--command", "SELECT CASE WHEN b.version=0 AND s.value='SYNTHETIC:b0' THEN 'ok' ELSE 'bad' END FROM agent_credential_private.bindings b JOIN synthetic_vault.secrets s ON s.id=b.secret_id WHERE b.binding_key='binding-b'",
    ])
    if record != "0:ready" or secret_ok != "ok" or unrelated_ok != "ok":
        # Keep outward evidence secret-free: the query returns only fixed markers.
        raise RuntimeError("synthetic_lock_deadline_record_mutated")
    _wait_sessions_gone(server_id)


def _run_client(network, image_id, ca_path, ca_sha, server_id, server_name, server_ip, key):
    name = "synthetic-app-stack-lock-" + uuid4().hex[:10]
    identity = None
    holder = None
    try:
        identity = command(_client_args(
            name, network, image_id, ca_path, server_ip, ca_sha, SCENARIO
        ))
        if re.fullmatch(r"[0-9a-f]{64}", identity) is None:
            raise RuntimeError("synthetic_lock_deadline_client_identity_invalid")
        _verify_client(identity, image_id, network, ca_path, server_ip, ca_sha, SCENARIO)
        command(["docker", "start", identity])
        _wait_running(identity)
        verify_members(network_data(network), {server_id: server_name, identity: name})
        _write_bootstrap(identity, SCENARIO)
        _touch_marker(identity, "/tmp/app-stack-go")
        _wait_marker(identity, LOCK_READY)

        holder = _start_lock_holder(server_id, key)
        _wait_lock_acquired(server_id, holder)
        _touch_marker(identity, LOCK_GO)

        exit_code = command(["docker", "wait", identity], timeout=35)
        state = json.loads(command(["docker", "inspect", identity]))[0]["State"]
        if exit_code != "0" or state.get("Running") or state.get("ExitCode") != 0:
            raise RuntimeError("synthetic_lock_deadline_client_result_invalid")

        _stop_lock_holder(server_id, holder)
        holder = None
        _verify_unchanged(server_id, key)
    finally:
        if holder is not None:
            try:
                _stop_lock_holder(server_id, holder)
            except BaseException:
                pass
        if identity:
            subprocess.run(["docker", "rm", "--force", identity], capture_output=True, timeout=30)
    verify_members(network_data(network), {server_id: server_name})


def main():
    if os.environ.get("AGENT_EPHEMERAL_TLS_TEST") != "1":
        raise SystemExit("refusing_non_ephemeral_application_stack_lock_deadline")

    network = "synthetic-app-stack-lock-" + uuid4().hex[:10]
    server_name = "synthetic-app-stack-lock-db-" + uuid4().hex[:8]
    server_id = None
    with tempfile.TemporaryDirectory(prefix="synthetic-app-stack-lock-") as temporary:
        directory = Path(temporary)
        directory.chmod(0o755)
        _certificates(directory)
        client_ca = directory / "client-ca.crt"
        client_ca.write_bytes((directory / "ca.crt").read_bytes())
        client_ca.chmod(0o644)
        ca_sha = sha256(client_ca.read_bytes()).hexdigest()
        try:
            command(["docker", "pull", IMAGE], timeout=120)
            image_data = json.loads(command(["docker", "image", "inspect", IMAGE]))[0]
            image_id = verify_image_provenance(image_data)
            command([
                "docker", "run", "--rm", "--user", "root", "--entrypoint", LAUNCHER,
                "--mount", f"type=bind,src={client_ca},dst=/ca.crt", IMAGE,
                "-c", "import os; os.chown('/ca.crt',65534,65534); os.chmod('/ca.crt',0o644)",
            ])
            command([
                "docker", "run", "--rm", "--user", "root", "--mount",
                f"type=bind,src={directory},dst=/tls", POSTGRES_IMAGE,
                "chown", "postgres:postgres", "/tls/server.key",
            ])
            command([
                "docker", "network", "create", "--driver", "bridge", "--internal",
                "--opt", NETWORK_OPTION + "=false", network,
            ])
            verify_network(network_data(network))
            server_id = command([
                "docker", "run", "--detach", "--name", server_name, "--network", network,
                "--mount", f"type=bind,src={directory},dst=/tls,readonly",
                "--mount", f"type=bind,src={ROOT / 'tests'},dst=/src/tests,readonly",
                "--env", "POSTGRES_DB=agent_checkpoint_ci", "--env", "POSTGRES_USER=postgres",
                "--env", f"POSTGRES_PASSWORD={PASSWORD}", POSTGRES_IMAGE,
                "-c", "ssl=on", "-c", "ssl_cert_file=/tls/valid.crt",
                "-c", "ssl_key_file=/tls/server.key", "-c", "password_encryption=scram-sha-256",
            ])
            if re.fullmatch(r"[0-9a-f]{64}", server_id) is None:
                raise RuntimeError("synthetic_lock_deadline_server_identity_invalid")

            ready = False
            for _ in range(80):
                check = subprocess.run([
                    "docker", "exec", server_id, "pg_isready", "-h", "127.0.0.1",
                    "-U", "postgres", "-d", "agent_checkpoint_ci",
                ], capture_output=True, timeout=5)
                if check.returncode == 0:
                    ready = True
                    break
                time.sleep(0.25)
            if not ready:
                raise RuntimeError("synthetic_lock_deadline_server_not_ready")

            key = _prepare_contract(server_id)
            server_ip = _server_ip(server_id, network)
            verify_members(network_data(network), {server_id: server_name})
            _run_client(network, image_id, client_ca, ca_sha, server_id, server_name, server_ip, key)
        finally:
            if server_id:
                subprocess.run(["docker", "rm", "--force", "--volumes", server_id],
                               capture_output=True, timeout=30)
            subprocess.run(["docker", "network", "rm", network], capture_output=True, timeout=30)
            if command(["docker", "network", "ls", "--quiet", "--filter", "name=^" + network + "$"]):
                raise RuntimeError("synthetic_lock_deadline_network_cleanup_failed")

    print("Synthetic hardened application stack lock deadline: ambiguous/no-replay/unchanged PASS")


if __name__ == "__main__":
    main()
