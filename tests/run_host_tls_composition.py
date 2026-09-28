"""Compose a hardened synthetic host with PostgreSQL TLS on an exclusive network."""
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
from run_secret_tls_contract import HOST, PASSWORD, _certificates

PROBE = "/src/tests/support/postgres_tls_probe.py"
POSTGRES_IMAGE = "postgres:17"


def _server_ip(identity, network):
    data = json.loads(command(["docker", "inspect", identity]))[0]
    networks = data.get("NetworkSettings", {}).get("Networks", {})
    if set(networks) != {network}:
        raise RuntimeError("synthetic_tls_server_network_invalid")
    address = networks[network].get("IPAddress", "")
    if not re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", address):
        raise RuntimeError("synthetic_tls_server_ip_invalid")
    return address


def _client_args(name, network, image_id, directory, server_ip, hostname, ca_name):
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
        "--env", "SYNTHETIC_POSTGRES_TLS_PROBE=1",
        "--env", "SYNTHETIC_DB_IP=" + server_ip,
        "--env", "SYNTHETIC_DB_PORT=5432",
        "--env", "SYNTHETIC_DB_HOST=" + hostname,
        "--env", "SYNTHETIC_DB_CA=/tls/" + ca_name,
        "--entrypoint", LAUNCHER,
        image_id, PROBE,
    ]


def _verify_client(identity, image_id, network, directory, server_ip, hostname, ca_name):
    data = json.loads(command(["docker", "inspect", identity]))[0]
    config, host = data.get("Config", {}), data.get("HostConfig", {})
    networks = data.get("NetworkSettings", {}).get("Networks", {})
    expected_env = {
        "PYTHONDONTWRITEBYTECODE=1",
        "SYNTHETIC_POSTGRES_TLS_PROBE=1",
        "SYNTHETIC_DB_IP=" + server_ip,
        "SYNTHETIC_DB_PORT=5432",
        "SYNTHETIC_DB_HOST=" + hostname,
        "SYNTHETIC_DB_CA=/tls/" + ca_name,
    }
    actual_env = set(config.get("Env") or [])
    if not expected_env.issubset(actual_env):
        raise RuntimeError("synthetic_tls_client_env_invalid")
    if any(item.startswith(("PGPASSWORD=", "DATABASE_URL=", "SUPABASE_")) for item in actual_env):
        raise RuntimeError("synthetic_tls_client_secret_env_present")
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
        raise RuntimeError("synthetic_tls_client_config_invalid")
    mounts = {(row.get("Destination"), row.get("RW")) for row in data.get("Mounts", [])}
    if ("/src/tests", False) not in mounts or ("/tls", False) not in mounts:
        raise RuntimeError("synthetic_tls_client_mount_invalid")
    if Path(directory).name not in str(data.get("Mounts", [])):
        raise RuntimeError("synthetic_tls_client_ca_mount_invalid")


def _run_client_case(network, image_id, directory, server_id, server_name,
                     server_ip, hostname, ca_name, expected_exit):
    client_name = "synthetic-tls-client-" + uuid4().hex[:12]
    client_id = None
    try:
        client_id = command(_client_args(
            client_name, network, image_id, directory, server_ip, hostname, ca_name))
        if not re.fullmatch(r"[0-9a-f]{64}", client_id):
            raise RuntimeError("synthetic_tls_client_identity_invalid")
        _verify_client(client_id, image_id, network, directory, server_ip, hostname, ca_name)
        verify_members(network_data(network), {server_id: server_name, client_id: client_name})
        command(["docker", "start", client_id])
        exit_code = command(["docker", "wait", client_id], timeout=15)
        state = json.loads(command(["docker", "inspect", client_id]))[0]["State"]
        if exit_code != str(expected_exit) or state.get("Running") or state.get("ExitCode") != expected_exit:
            raise RuntimeError("synthetic_tls_client_result_invalid")
    finally:
        if client_id:
            try:
                command(["docker", "rm", "--force", client_id])
            except RuntimeError:
                pass


def main():
    if os.environ.get("AGENT_EPHEMERAL_TLS_TEST") != "1":
        raise SystemExit("refusing_non_ephemeral_tls")

    network = "synthetic-host-tls-" + uuid4().hex[:12]
    server_name = "synthetic-host-tls-db-" + uuid4().hex[:12]
    server_id = None
    with tempfile.TemporaryDirectory(prefix="synthetic-host-tls-") as temporary:
        directory = Path(temporary)
        directory.chmod(0o755)
        _certificates(directory)
        try:
            command(["docker", "pull", IMAGE], timeout=120)
            image_data = json.loads(command(["docker", "image", "inspect", IMAGE]))[0]
            image_id = verify_image_provenance(image_data)

            # Match the PostgreSQL fixture's key ownership without exposing a live secret.
            command(["docker", "run", "--rm", "--user", "root", "--mount",
                     f"type=bind,src={directory},dst=/tls", POSTGRES_IMAGE,
                     "chown", "postgres:postgres", "/tls/server.key"])

            command(["docker", "network", "create", "--driver", "bridge", "--internal",
                     "--opt", NETWORK_OPTION + "=false", network])
            verify_network(network_data(network))

            server_id = command([
                "docker", "run", "--detach", "--name", server_name, "--network", network,
                "--mount", f"type=bind,src={directory},dst=/tls,readonly",
                "--env", "POSTGRES_DB=agent_checkpoint_ci", "--env", "POSTGRES_USER=postgres",
                "--env", f"POSTGRES_PASSWORD={PASSWORD}", POSTGRES_IMAGE,
                "-c", "ssl=on", "-c", "ssl_cert_file=/tls/valid.crt",
                "-c", "ssl_key_file=/tls/server.key",
            ])
            if not re.fullmatch(r"[0-9a-f]{64}", server_id):
                raise RuntimeError("synthetic_tls_server_identity_invalid")
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
                raise RuntimeError("synthetic_tls_server_not_ready")

            server_ip = _server_ip(server_id, network)
            verify_members(network_data(network), {server_id: server_name})

            # Positive control: hardened client, reviewed CA and expected DNS identity.
            _run_client_case(network, image_id, directory, server_id, server_name,
                             server_ip, HOST, "ca.crt", 0)
            # Negative controls prove hostname and trust-anchor validation stay active.
            _run_client_case(network, image_id, directory, server_id, server_name,
                             server_ip, "wrong.synthetic.invalid", "ca.crt", 23)
            _run_client_case(network, image_id, directory, server_id, server_name,
                             server_ip, HOST, "wrong-ca.crt", 23)
        finally:
            if server_id:
                subprocess.run(["docker", "rm", "--force", "--volumes", server_id],
                               capture_output=True, timeout=30)
            subprocess.run(["docker", "network", "rm", network], capture_output=True, timeout=30)
            if command(["docker", "network", "ls", "--quiet", "--filter", "name=^" + network + "$"]):
                raise RuntimeError("synthetic_tls_network_cleanup_failed")

    print("Synthetic hardened-host PostgreSQL TLS composition: exact internal network, resource limits, verified CA/name and negative controls PASS")


if __name__ == "__main__":
    main()
