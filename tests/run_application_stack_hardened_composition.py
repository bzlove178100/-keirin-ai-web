"""Run the actual secret-store/factory/process stack inside the hardened synthetic client."""
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_core.durable_secret_store import DurableVersionedSecretStore
from agent_core.refresh_credentials import CredentialBinding
from host_egress_contract import NETWORK_OPTION, network_data, verify_members, verify_network
from run_host_limits_contract import IMAGE, LAUNCHER, command, verify_image_provenance
from run_host_tls_composition import POSTGRES_IMAGE, _server_ip
from run_secret_tls_contract import HOST, PASSWORD, _certificates

PROBE = "/src/tests/support/postgres_application_stack_probe.py"
BINDING = CredentialBinding("provider-a", "account-a", ("read:one", "write:one"))


def _client_args(name, network, image_id, ca_path, server_ip, ca_sha):
    return [
        "docker", "create", "--name", name, "--network", network, "--cgroupns", "private",
        "--memory", "128m", "--memory-swap", "128m", "--pids-limit", "24",
        "--cpu-period", "100000", "--cpu-quota", "50000", "--read-only",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges=true",
        "--user", "65534:65534", "--log-driver", "none", "--restart", "no",
        "--ulimit", "core=0:0", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777",
        "--mount", f"type=bind,src={ROOT / 'tests'},dst=/src/tests,readonly",
        "--mount", f"type=bind,src={ROOT / 'agent_core'},dst=/src/agent_core,readonly",
        "--mount", f"type=bind,src={ca_path},dst=/tls/ca.crt,readonly",
        "--env", "PYTHONDONTWRITEBYTECODE=1",
        "--env", "SYNTHETIC_POSTGRES_APP_STACK_PROBE=1",
        "--env", "SYNTHETIC_DB_IP=" + server_ip,
        "--env", "SYNTHETIC_DB_PORT=5432",
        "--env", "SYNTHETIC_DB_HOST=" + HOST,
        "--env", "SYNTHETIC_DB_CA=/tls/ca.crt",
        "--env", "SYNTHETIC_DB_CA_SHA256=" + ca_sha,
        "--env", "SYNTHETIC_DB_USER=secret_test_host_a",
        "--env", "SYNTHETIC_DB_NAME=agent_checkpoint_ci",
        "--entrypoint", LAUNCHER,
        image_id, PROBE,
    ]


def _verify_client(identity, image_id, network, ca_path, server_ip, ca_sha):
    data = json.loads(command(["docker", "inspect", identity]))[0]
    config, host = data.get("Config", {}), data.get("HostConfig", {})
    networks = data.get("NetworkSettings", {}).get("Networks", {})
    expected_env = {
        "PYTHONDONTWRITEBYTECODE=1",
        "SYNTHETIC_POSTGRES_APP_STACK_PROBE=1",
        "SYNTHETIC_DB_IP=" + server_ip,
        "SYNTHETIC_DB_PORT=5432",
        "SYNTHETIC_DB_HOST=" + HOST,
        "SYNTHETIC_DB_CA=/tls/ca.crt",
        "SYNTHETIC_DB_CA_SHA256=" + ca_sha,
        "SYNTHETIC_DB_USER=secret_test_host_a",
        "SYNTHETIC_DB_NAME=agent_checkpoint_ci",
    }
    actual_env = set(config.get("Env") or [])
    if not expected_env.issubset(actual_env):
        raise RuntimeError("synthetic_app_stack_client_env_invalid")
    if any(item.startswith(("PGPASSWORD=", "DATABASE_URL=", "SUPABASE_", "SYNTHETIC_DB_PASSWORD="))
           for item in actual_env):
        raise RuntimeError("synthetic_app_stack_client_secret_env_present")
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
        raise RuntimeError("synthetic_app_stack_client_config_invalid")
    mounts = {(row.get("Destination"), row.get("RW")) for row in data.get("Mounts", [])}
    required_mounts = {("/src/tests", False), ("/src/agent_core", False), ("/tls/ca.crt", False)}
    if not required_mounts.issubset(mounts):
        raise RuntimeError("synthetic_app_stack_client_mount_invalid")
    ca_mount = [row for row in data.get("Mounts", []) if row.get("Destination") == "/tls/ca.crt"]
    if len(ca_mount) != 1 or Path(ca_mount[0].get("Source", "")) != ca_path:
        raise RuntimeError("synthetic_app_stack_ca_mount_invalid")


def _wait_running(identity):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        state = json.loads(command(["docker", "inspect", identity]))[0]["State"]
        if state.get("Running") is True:
            return
        if state.get("Status") in {"exited", "dead"}:
            raise RuntimeError("synthetic_app_stack_client_exited_before_release")
        time.sleep(0.02)
    raise RuntimeError("synthetic_app_stack_client_not_running")


def _write_bootstrap(identity):
    script = (
        "import sys; from pathlib import Path; "
        "data=sys.stdin.buffer.read(); "
        "p=Path('/tmp/bootstrap-password'); p.write_bytes(data); p.chmod(0o600); "
        "v=Path('/tmp/bootstrap-version'); v.write_text('1'); v.chmod(0o600)"
    )
    result = subprocess.run(
        ["docker", "exec", "--interactive", identity, LAUNCHER, "-c", script],
        input=PASSWORD.encode(), capture_output=True, timeout=10,
    )
    if result.returncode != 0 or result.stdout or result.stderr:
        raise RuntimeError("synthetic_app_stack_bootstrap_handoff_failed")


def _prepare_contract(server_id):
    command([
        "docker", "exec", server_id, "psql", "--username", "postgres",
        "--dbname", "agent_checkpoint_ci", "--set", "ON_ERROR_STOP=1",
        "--file", "/src/tests/support/vault_postgres_contract.sql",
    ], timeout=45)
    command([
        "docker", "exec", server_id, "psql", "--username", "postgres",
        "--dbname", "agent_checkpoint_ci", "--set", "ON_ERROR_STOP=1",
        "--command", "ALTER ROLE secret_test_host_a PASSWORD 'SYNTHETIC:tls-ci-only'",
    ])
    key = DurableVersionedSecretStore.key_for(BINDING)
    if re.fullmatch(r"refresh-secret-v1:[0-9a-f]{64}", key) is None:
        raise RuntimeError("synthetic_app_stack_binding_key_invalid")
    command([
        "docker", "exec", server_id, "psql", "--username", "postgres",
        "--dbname", "agent_checkpoint_ci", "--set", "ON_ERROR_STOP=1",
        "--command",
        "DELETE FROM agent_credential_private.host_bindings WHERE binding_key='binding-a'; "
        + "UPDATE agent_credential_private.bindings SET binding_key='" + key + "' WHERE binding_key='binding-a'; "
        + "INSERT INTO agent_credential_private.host_bindings VALUES ('secret_test_host_a','" + key + "');",
    ])
    return key


def _verify_readback(server_id, key):
    record = command([
        "docker", "exec", server_id, "psql", "--username", "postgres",
        "--dbname", "agent_checkpoint_ci", "--tuples-only", "--no-align",
        "--command", "SELECT version::text || ':' || state FROM agent_credential_private.bindings WHERE binding_key='" + key + "'",
    ])
    secret = command([
        "docker", "exec", server_id, "psql", "--username", "postgres",
        "--dbname", "agent_checkpoint_ci", "--tuples-only", "--no-align",
        "--command", "SELECT s.value FROM agent_credential_private.bindings b JOIN synthetic_vault.secrets s ON s.id=b.secret_id WHERE b.binding_key='" + key + "'",
    ])
    untouched = command([
        "docker", "exec", server_id, "psql", "--username", "postgres",
        "--dbname", "agent_checkpoint_ci", "--tuples-only", "--no-align",
        "--command", "SELECT b.version::text || ':' || s.value FROM agent_credential_private.bindings b JOIN synthetic_vault.secrets s ON s.id=b.secret_id WHERE b.binding_key='binding-b'",
    ])
    sessions = command([
        "docker", "exec", server_id, "psql", "--username", "postgres",
        "--dbname", "agent_checkpoint_ci", "--tuples-only", "--no-align",
        "--command", "SELECT count(*) FROM pg_stat_activity WHERE application_name='agent-secret-host'",
    ])
    if record != "1:ready" or secret != "SYNTHETIC:app-stack-a1" or untouched != "0:SYNTHETIC:b0" or sessions != "0":
        raise RuntimeError("synthetic_app_stack_server_readback_invalid")


def _run_client(network, image_id, ca_path, ca_sha, server_id, server_name, server_ip, key):
    name = "synthetic-app-stack-client-" + uuid4().hex[:12]
    identity = None
    try:
        identity = command(_client_args(name, network, image_id, ca_path, server_ip, ca_sha))
        if re.fullmatch(r"[0-9a-f]{64}", identity) is None:
            raise RuntimeError("synthetic_app_stack_client_identity_invalid")
        _verify_client(identity, image_id, network, ca_path, server_ip, ca_sha)
        command(["docker", "start", identity])
        _wait_running(identity)
        verify_members(network_data(network), {server_id: server_name, identity: name})
        _write_bootstrap(identity)
        command([
            "docker", "exec", identity, LAUNCHER, "-c",
            "from pathlib import Path; Path('/tmp/app-stack-go').write_text('go')",
        ])
        exit_code = command(["docker", "wait", identity], timeout=45)
        state = json.loads(command(["docker", "inspect", identity]))[0]["State"]
        if exit_code != "0" or state.get("Running") or state.get("ExitCode") != 0:
            raise RuntimeError("synthetic_app_stack_client_result_invalid")
        _verify_readback(server_id, key)
    finally:
        if identity:
            subprocess.run(["docker", "rm", "--force", identity], capture_output=True, timeout=30)


def _restore_client_ca_owner(path, uid, gid):
    subprocess.run([
        "docker", "run", "--rm", "--user", "root",
        "--mount", f"type=bind,src={path},dst=/ca.crt",
        IMAGE, "-c", "import os; os.chown('/ca.crt'," + str(uid) + "," + str(gid) + ")",
    ], capture_output=True, timeout=30)


def main():
    if os.environ.get("AGENT_EPHEMERAL_TLS_TEST") != "1":
        raise SystemExit("refusing_non_ephemeral_application_stack_composition")

    network = "synthetic-app-stack-" + uuid4().hex[:12]
    server_name = "synthetic-app-stack-db-" + uuid4().hex[:12]
    server_id = None
    client_ca = None
    original_uid, original_gid = os.getuid(), os.getgid()
    with tempfile.TemporaryDirectory(prefix="synthetic-app-stack-") as temporary:
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
                "docker", "run", "--rm", "--user", "root",
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
                raise RuntimeError("synthetic_app_stack_server_identity_invalid")
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
                raise RuntimeError("synthetic_app_stack_server_not_ready")
            key = _prepare_contract(server_id)
            server_ip = _server_ip(server_id, network)
            verify_members(network_data(network), {server_id: server_name})
            _run_client(network, image_id, client_ca, ca_sha, server_id, server_name, server_ip, key)
        finally:
            if server_id:
                subprocess.run(["docker", "rm", "--force", "--volumes", server_id],
                               capture_output=True, timeout=30)
            subprocess.run(["docker", "network", "rm", network], capture_output=True, timeout=30)
            if client_ca and client_ca.exists():
                _restore_client_ca_owner(client_ca, original_uid, original_gid)
            try:
                if command(["docker", "network", "ls", "--quiet", "--filter", "name=^" + network + "$"]):
                    raise RuntimeError("synthetic_app_stack_network_cleanup_failed")
            except RuntimeError:
                raise

    print("Synthetic hardened application stack: StrictFactory + process deadline + durable store + TLS/SCRAM/private CAS PASS")


if __name__ == "__main__":
    main()
