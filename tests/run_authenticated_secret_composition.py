"""Authenticate and execute synthetic secret-store read/CAS inside the hardened host composition."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from uuid import uuid4

from host_egress_contract import NETWORK_OPTION, network_data, verify_members, verify_network
from run_host_limits_contract import IMAGE, LAUNCHER, ROOT, command, verify_image_provenance
from run_host_tls_composition import POSTGRES_IMAGE, _server_ip
from run_secret_tls_contract import HOST, PASSWORD, _certificates

PROBE = "/src/tests/support/postgres_authenticated_secret_probe.py"
SQL_CONTRACT = "/src/tests/support/vault_postgres_contract.sql"


def _client_args(name, network, image_id, directory, server_ip):
    return [
        "docker", "create", "--name", name, "--network", network, "--cgroupns", "private",
        "--memory", "128m", "--memory-swap", "128m", "--pids-limit", "24",
        "--cpu-period", "100000", "--cpu-quota", "50000", "--read-only",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges=true",
        "--user", "65534:65534", "--log-driver", "none", "--restart", "no",
        "--ulimit", "core=0:0", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=8m,mode=1777",
        "--mount", f"type=bind,src={ROOT / 'tests'},dst=/src/tests,readonly",
        "--mount", f"type=bind,src={directory},dst=/tls,readonly",
        "--env", "PYTHONDONTWRITEBYTECODE=1",
        "--env", "SYNTHETIC_POSTGRES_AUTH_SECRET_PROBE=1",
        "--env", "SYNTHETIC_DB_IP=" + server_ip,
        "--env", "SYNTHETIC_DB_PORT=5432",
        "--env", "SYNTHETIC_DB_HOST=" + HOST,
        "--env", "SYNTHETIC_DB_CA=/tls/ca.crt",
        "--env", "SYNTHETIC_DB_USER=secret_test_host_a",
        "--env", "SYNTHETIC_DB_NAME=agent_checkpoint_ci",
        "--entrypoint", LAUNCHER,
        image_id, PROBE,
    ]


def _verify_client(identity, image_id, network, directory, server_ip):
    data = json.loads(command(["docker", "inspect", identity]))[0]
    config, host = data.get("Config", {}), data.get("HostConfig", {})
    networks = data.get("NetworkSettings", {}).get("Networks", {})
    expected_env = {
        "PYTHONDONTWRITEBYTECODE=1",
        "SYNTHETIC_POSTGRES_AUTH_SECRET_PROBE=1",
        "SYNTHETIC_DB_IP=" + server_ip,
        "SYNTHETIC_DB_PORT=5432",
        "SYNTHETIC_DB_HOST=" + HOST,
        "SYNTHETIC_DB_CA=/tls/ca.crt",
        "SYNTHETIC_DB_USER=secret_test_host_a",
        "SYNTHETIC_DB_NAME=agent_checkpoint_ci",
    }
    actual_env = set(config.get("Env") or [])
    if not expected_env.issubset(actual_env):
        raise RuntimeError("synthetic_auth_client_env_invalid")
    if any(item.startswith(("PGPASSWORD=", "DATABASE_URL=", "SUPABASE_", "SYNTHETIC_DB_PASSWORD="))
           for item in actual_env):
        raise RuntimeError("synthetic_auth_client_secret_env_present")
    expected_limits = {
        "Memory": 134217728,
        "MemorySwap": 134217728,
        "PidsLimit": 24,
        "CpuPeriod": 100000,
        "CpuQuota": 50000,
        "ReadonlyRootfs": True,
        "NetworkMode": network,
        "CgroupnsMode": "private",
        "Privileged": False,
    }
    if (data.get("Id") != identity or data.get("Image") != image_id
            or any(host.get(key) != value for key, value in expected_limits.items())
            or config.get("User") != "65534:65534"
            or config.get("Entrypoint") != [LAUNCHER] or config.get("Cmd") != [PROBE]
            or set(networks) != {network}
            or host.get("CapDrop") != ["ALL"]
            or "no-new-privileges=true" not in host.get("SecurityOpt", [])
            or host.get("LogConfig", {}).get("Type") != "none"
            or host.get("RestartPolicy", {}).get("Name") != "no"):
        raise RuntimeError("synthetic_auth_client_config_invalid")
    mounts = {(row.get("Destination"), row.get("RW")) for row in data.get("Mounts", [])}
    if ("/src/tests", False) not in mounts or ("/tls", False) not in mounts:
        raise RuntimeError("synthetic_auth_client_mount_invalid")
    if Path(directory).name not in str(data.get("Mounts", [])):
        raise RuntimeError("synthetic_auth_client_ca_mount_invalid")


def _require_running(identity):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        state = json.loads(command(["docker", "inspect", identity]))[0]["State"]
        if state.get("Running") is True:
            return
        if state.get("Status") in {"exited", "dead"}:
            raise RuntimeError("synthetic_auth_client_exited_before_release")
        time.sleep(0.02)
    raise RuntimeError("synthetic_auth_client_not_running")


def _write_bootstrap_password(identity):
    script = (
        "import sys; from pathlib import Path; "
        "data=sys.stdin.buffer.read(); "
        "p=Path('/tmp/bootstrap-password'); p.write_bytes(data); p.chmod(0o600)"
    )
    result = subprocess.run(
        ["docker", "exec", "--interactive", identity, LAUNCHER, "-c", script],
        input=PASSWORD.encode(), capture_output=True, timeout=10,
    )
    if result.returncode != 0 or result.stdout or result.stderr:
        raise RuntimeError("synthetic_auth_bootstrap_handoff_failed")


def _prepare_contract(server_id):
    command([
        "docker", "exec", server_id, "psql", "--username", "postgres",
        "--dbname", "agent_checkpoint_ci", "--set", "ON_ERROR_STOP=1",
        "--file", SQL_CONTRACT,
    ], timeout=45)
    command([
        "docker", "exec", server_id, "psql", "--username", "postgres",
        "--dbname", "agent_checkpoint_ci", "--set", "ON_ERROR_STOP=1",
        "--command", "ALTER ROLE secret_test_host_a PASSWORD 'SYNTHETIC:tls-ci-only'",
    ])


def _verify_readback(server_id):
    record = command([
        "docker", "exec", server_id, "psql", "--username", "postgres",
        "--dbname", "agent_checkpoint_ci", "--tuples-only", "--no-align",
        "--command", "SELECT version::text || ':' || state FROM agent_credential_private.bindings WHERE binding_key='binding-a'",
    ])
    secret = command([
        "docker", "exec", server_id, "psql", "--username", "postgres",
        "--dbname", "agent_checkpoint_ci", "--tuples-only", "--no-align",
        "--command", "SELECT value FROM synthetic_vault.secrets WHERE id=1",
    ])
    untouched = command([
        "docker", "exec", server_id, "psql", "--username", "postgres",
        "--dbname", "agent_checkpoint_ci", "--tuples-only", "--no-align",
        "--command", "SELECT b.version::text || ':' || s.value FROM agent_credential_private.bindings b JOIN synthetic_vault.secrets s ON s.id=b.secret_id WHERE b.binding_key='binding-b'",
    ])
    sessions = command([
        "docker", "exec", server_id, "psql", "--username", "postgres",
        "--dbname", "agent_checkpoint_ci", "--tuples-only", "--no-align",
        "--command", "SELECT count(*) FROM pg_stat_activity WHERE application_name='agent-secret-host-composed'",
    ])
    if record != "1:ready" or secret != "SYNTHETIC:composed-a1" or untouched != "0:SYNTHETIC:b0" or sessions != "0":
        raise RuntimeError("synthetic_auth_server_readback_invalid")


def _run_client(network, image_id, directory, server_id, server_name, server_ip):
    client_name = "synthetic-auth-client-" + uuid4().hex[:12]
    client_id = None
    try:
        client_id = command(_client_args(client_name, network, image_id, directory, server_ip))
        if not re.fullmatch(r"[0-9a-f]{64}", client_id):
            raise RuntimeError("synthetic_auth_client_identity_invalid")
        _verify_client(client_id, image_id, network, directory, server_ip)
        command(["docker", "start", client_id])
        _require_running(client_id)
        verify_members(network_data(network), {server_id: server_name, client_id: client_name})
        _write_bootstrap_password(client_id)
        command([
            "docker", "exec", client_id, LAUNCHER, "-c",
            "from pathlib import Path; Path('/tmp/auth-go').write_text('go')",
        ])
        exit_code = command(["docker", "wait", client_id], timeout=20)
        state = json.loads(command(["docker", "inspect", client_id]))[0]["State"]
        if exit_code != "0" or state.get("Running") or state.get("ExitCode") != 0:
            raise RuntimeError("synthetic_auth_client_result_invalid")
        _verify_readback(server_id)
    finally:
        if client_id:
            subprocess.run(["docker", "rm", "--force", client_id], capture_output=True, timeout=30)


def main():
    if os.environ.get("AGENT_EPHEMERAL_TLS_TEST") != "1":
        raise SystemExit("refusing_non_ephemeral_authenticated_secret_composition")

    network = "synthetic-auth-secret-" + uuid4().hex[:12]
    server_name = "synthetic-auth-secret-db-" + uuid4().hex[:12]
    server_id = None
    with tempfile.TemporaryDirectory(prefix="synthetic-auth-secret-") as temporary:
        directory = Path(temporary)
        directory.chmod(0o755)
        _certificates(directory)
        try:
            command(["docker", "pull", IMAGE], timeout=120)
            image_data = json.loads(command(["docker", "image", "inspect", IMAGE]))[0]
            image_id = verify_image_provenance(image_data)

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
            if not re.fullmatch(r"[0-9a-f]{64}", server_id):
                raise RuntimeError("synthetic_auth_server_identity_invalid")
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
                raise RuntimeError("synthetic_auth_server_not_ready")

            _prepare_contract(server_id)
            server_ip = _server_ip(server_id, network)
            verify_members(network_data(network), {server_id: server_name})
            _run_client(network, image_id, directory, server_id, server_name, server_ip)
        finally:
            if server_id:
                subprocess.run(["docker", "rm", "--force", "--volumes", server_id],
                               capture_output=True, timeout=30)
            subprocess.run(["docker", "network", "rm", network], capture_output=True, timeout=30)
            if command(["docker", "network", "ls", "--quiet", "--filter", "name=^" + network + "$"]):
                raise RuntimeError("synthetic_auth_network_cleanup_failed")

    print("Synthetic hardened-host authenticated secret composition: TLS/SCRAM, mapped read/CAS, stale conflict, cross-binding denial and durable readback PASS")


if __name__ == "__main__":
    main()
