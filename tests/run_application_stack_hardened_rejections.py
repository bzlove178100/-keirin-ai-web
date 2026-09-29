"""Fail-closed lease/trust/hostname cases for the co-resident application secret stack."""
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
    HOST, IMAGE, LAUNCHER, NETWORK_OPTION, PASSWORD, POSTGRES_IMAGE, PROBE, ROOT,
    _certificates, _prepare_contract, _run_client, _server_ip, _verify_readback,
    command, network_data, verify_image_provenance, verify_members, verify_network,
)

_SCENARIOS = (
    "bad_ca_pin", "stale_lease", "revoked_lease", "expired_lease", "wrong_hostname",
)


def _client_args(name, network, image_id, ca_path, server_ip, ca_sha, scenario):
    hostname = "wrong.invalid" if scenario == "wrong_hostname" else HOST
    trusted_sha = "0" * 64 if scenario == "bad_ca_pin" else ca_sha
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
        "--env", "SYNTHETIC_APP_STACK_SCENARIO=" + scenario,
        "--env", "SYNTHETIC_DB_IP=" + server_ip,
        "--env", "SYNTHETIC_DB_PORT=5432",
        "--env", "SYNTHETIC_DB_HOST=" + hostname,
        "--env", "SYNTHETIC_DB_CA=/tls/ca.crt",
        "--env", "SYNTHETIC_DB_CA_SHA256=" + trusted_sha,
        "--env", "SYNTHETIC_DB_USER=secret_test_host_a",
        "--env", "SYNTHETIC_DB_NAME=agent_checkpoint_ci",
        "--entrypoint", LAUNCHER,
        image_id, PROBE,
    ]


def _verify_client(identity, image_id, network, ca_path, server_ip, ca_sha, scenario):
    data = json.loads(command(["docker", "inspect", identity]))[0]
    config, host = data.get("Config", {}), data.get("HostConfig", {})
    hostname = "wrong.invalid" if scenario == "wrong_hostname" else HOST
    trusted_sha = "0" * 64 if scenario == "bad_ca_pin" else ca_sha
    expected_env = {
        "PYTHONDONTWRITEBYTECODE=1",
        "SYNTHETIC_POSTGRES_APP_STACK_PROBE=1",
        "SYNTHETIC_APP_STACK_SCENARIO=" + scenario,
        "SYNTHETIC_DB_IP=" + server_ip,
        "SYNTHETIC_DB_PORT=5432",
        "SYNTHETIC_DB_HOST=" + hostname,
        "SYNTHETIC_DB_CA=/tls/ca.crt",
        "SYNTHETIC_DB_CA_SHA256=" + trusted_sha,
        "SYNTHETIC_DB_USER=secret_test_host_a",
        "SYNTHETIC_DB_NAME=agent_checkpoint_ci",
    }
    actual_env = set(config.get("Env") or [])
    if not expected_env.issubset(actual_env):
        raise RuntimeError("synthetic_app_stack_rejection_env_invalid")
    if any(item.startswith(("PGPASSWORD=", "DATABASE_URL=", "SUPABASE_", "SYNTHETIC_DB_PASSWORD="))
           for item in actual_env):
        raise RuntimeError("synthetic_app_stack_rejection_secret_env_present")
    if (data.get("Id") != identity or data.get("Image") != image_id
            or config.get("User") != "65534:65534"
            or config.get("Entrypoint") != [LAUNCHER] or config.get("Cmd") != [PROBE]
            or host.get("Memory") != 134217728 or host.get("MemorySwap") != 134217728
            or host.get("PidsLimit") != 24 or host.get("CpuPeriod") != 100000
            or host.get("CpuQuota") != 50000 or host.get("ReadonlyRootfs") is not True
            or host.get("NetworkMode") != network or host.get("CgroupnsMode") != "private"
            or host.get("Privileged") is not False or host.get("CapDrop") != ["ALL"]
            or "no-new-privileges=true" not in host.get("SecurityOpt", [])
            or host.get("LogConfig", {}).get("Type") != "none"
            or host.get("RestartPolicy", {}).get("Name") != "no"):
        raise RuntimeError("synthetic_app_stack_rejection_config_invalid")
    networks = data.get("NetworkSettings", {}).get("Networks", {})
    if set(networks) != {network}:
        raise RuntimeError("synthetic_app_stack_rejection_network_invalid")
    mounts = {(row.get("Destination"), row.get("RW")) for row in data.get("Mounts", [])}
    if not {("/src/tests", False), ("/src/agent_core", False), ("/tls/ca.crt", False)}.issubset(mounts):
        raise RuntimeError("synthetic_app_stack_rejection_mount_invalid")
    ca_mount = [row for row in data.get("Mounts", []) if row.get("Destination") == "/tls/ca.crt"]
    if len(ca_mount) != 1 or Path(ca_mount[0].get("Source", "")) != ca_path:
        raise RuntimeError("synthetic_app_stack_rejection_ca_mount_invalid")


def _wait_running(identity):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        state = json.loads(command(["docker", "inspect", identity]))[0]["State"]
        if state.get("Running") is True:
            return
        if state.get("Status") in {"exited", "dead"}:
            raise RuntimeError("synthetic_app_stack_rejection_exited_early")
        time.sleep(0.02)
    raise RuntimeError("synthetic_app_stack_rejection_not_running")


def _write_bootstrap(identity, scenario):
    current = "2" if scenario == "stale_lease" else "1"
    script = (
        "import sys; from pathlib import Path; "
        "data=sys.stdin.buffer.read(); "
        "p=Path('/tmp/bootstrap-password'); p.write_bytes(data); p.chmod(0o600); "
        "v=Path('/tmp/bootstrap-version'); v.write_text('1'); v.chmod(0o600); "
        "c=Path('/tmp/bootstrap-current-version'); c.write_text(sys.argv[1]); c.chmod(0o600)"
    )
    result = subprocess.run(
        ["docker", "exec", "--interactive", identity, LAUNCHER, "-c", script, current],
        input=PASSWORD.encode(), capture_output=True, timeout=10,
    )
    if result.returncode != 0 or result.stdout or result.stderr:
        raise RuntimeError("synthetic_app_stack_rejection_bootstrap_handoff_failed")


def _run_case(network, image_id, ca_path, ca_sha, server_id, server_name, server_ip, key, scenario):
    name = "synthetic-app-stack-" + scenario.replace("_", "-") + "-" + uuid4().hex[:8]
    identity = None
    try:
        identity = command(_client_args(name, network, image_id, ca_path, server_ip, ca_sha, scenario))
        if re.fullmatch(r"[0-9a-f]{64}", identity) is None:
            raise RuntimeError("synthetic_app_stack_rejection_identity_invalid")
        _verify_client(identity, image_id, network, ca_path, server_ip, ca_sha, scenario)
        command(["docker", "start", identity])
        _wait_running(identity)
        verify_members(network_data(network), {server_id: server_name, identity: name})
        _write_bootstrap(identity, scenario)
        command([
            "docker", "exec", identity, LAUNCHER, "-c",
            "from pathlib import Path; Path('/tmp/app-stack-go').write_text('go')",
        ])
        exit_code = command(["docker", "wait", identity], timeout=35)
        state = json.loads(command(["docker", "inspect", identity]))[0]["State"]
        if exit_code != "0" or state.get("Running") or state.get("ExitCode") != 0:
            raise RuntimeError("synthetic_app_stack_rejection_result_invalid")
        _verify_readback(server_id, key)
    finally:
        if identity:
            subprocess.run(["docker", "rm", "--force", identity], capture_output=True, timeout=30)
    verify_members(network_data(network), {server_id: server_name})


def main():
    if os.environ.get("AGENT_EPHEMERAL_TLS_TEST") != "1":
        raise SystemExit("refusing_non_ephemeral_application_stack_rejections")

    network = "synthetic-app-stack-reject-" + uuid4().hex[:10]
    server_name = "synthetic-app-stack-reject-db-" + uuid4().hex[:8]
    server_id = None
    with tempfile.TemporaryDirectory(prefix="synthetic-app-stack-reject-") as temporary:
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
                raise RuntimeError("synthetic_app_stack_rejection_server_identity_invalid")
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
                raise RuntimeError("synthetic_app_stack_rejection_server_not_ready")

            key = _prepare_contract(server_id)
            server_ip = _server_ip(server_id, network)
            verify_members(network_data(network), {server_id: server_name})
            _run_client(network, image_id, client_ca, ca_sha, server_id, server_name, server_ip, key)
            for scenario in _SCENARIOS:
                _run_case(network, image_id, client_ca, ca_sha, server_id, server_name, server_ip, key, scenario)
        finally:
            if server_id:
                subprocess.run(["docker", "rm", "--force", "--volumes", server_id],
                               capture_output=True, timeout=30)
            subprocess.run(["docker", "network", "rm", network], capture_output=True, timeout=30)
            if command(["docker", "network", "ls", "--quiet", "--filter", "name=^" + network + "$"]):
                raise RuntimeError("synthetic_app_stack_rejection_network_cleanup_failed")

    print("Synthetic hardened application stack rejection cases: trust, hostname, stale/revoked/expired lease PASS")


if __name__ == "__main__":
    main()
