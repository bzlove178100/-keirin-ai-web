"""Synthetic destination egress qualification using an exclusive internal network."""
import json
import re
import time
from uuid import uuid4

from run_host_limits_contract import ROOT, LAUNCHER, command

SERVER = "/src/tests/support/approved_endpoint_server.py"
CLIENT = "/src/tests/support/egress_allowlist_probe.py"
NETWORK_OPTION = "com.docker.network.bridge.enable_ip_masquerade"


def verify_network(data):
    if (type(data) is not dict or data.get("Driver") != "bridge" or data.get("Internal") is not True
            or data.get("Attachable") is not False
            or data.get("Ingress") is not False
            or data.get("Options", {}).get(NETWORK_OPTION) != "false"):
        raise RuntimeError("synthetic_egress_network_invalid")
    ipam = data.get("IPAM", {}).get("Config", [])
    if len(ipam) != 1 or not ipam[0].get("Subnet") or ipam[0].get("Gateway") is None:
        raise RuntimeError("synthetic_egress_ipam_invalid")


def verify_members(data, expected):
    members = data.get("Containers") or {}
    if set(members) != set(expected):
        raise RuntimeError("synthetic_egress_members_invalid")
    for identity, name in expected.items():
        row = members.get(identity, {})
        if row.get("Name") != name or not row.get("IPv4Address"):
            raise RuntimeError("synthetic_egress_member_identity_invalid")


def hardened_args(name, network, image_id, script, extra_env=()):
    args = ["docker", "create", "--name", name, "--network", network,
            "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges=true",
            "--user", "65534:65534", "--log-driver", "none", "--restart", "no",
            "--ulimit", "core=0:0", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=8m,mode=1777",
            "--mount", f"type=bind,src={ROOT / 'tests'},dst=/src/tests,readonly",
            "--env", "PYTHONDONTWRITEBYTECODE=1"]
    for item in extra_env:
        args += ["--env", item]
    return args + ["--entrypoint", LAUNCHER, image_id, script]


def inspect_container(identity, image_id, network, script):
    data = json.loads(command(["docker", "inspect", identity]))[0]
    config, host = data.get("Config", {}), data.get("HostConfig", {})
    networks = data.get("NetworkSettings", {}).get("Networks", {})
    if (data.get("Id") != identity or data.get("Image") != image_id
            or config.get("User") != "65534:65534"
            or config.get("Entrypoint") != [LAUNCHER] or config.get("Cmd") != [script]
            or host.get("NetworkMode") != network or set(networks) != {network}
            or host.get("ReadonlyRootfs") is not True or host.get("Privileged") is not False
            or host.get("CapDrop") != ["ALL"]
            or "no-new-privileges=true" not in host.get("SecurityOpt", [])
            or host.get("LogConfig", {}).get("Type") != "none"
            or host.get("RestartPolicy", {}).get("Name") != "no"):
        raise RuntimeError("synthetic_egress_container_invalid")
    return data


def network_data(network):
    return json.loads(command(["docker", "network", "inspect", network]))[0]


def ipv4_for(data, network):
    value = data["NetworkSettings"]["Networks"][network]["IPAddress"]
    if not re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", value):
        raise RuntimeError("synthetic_egress_ip_invalid")
    return value


def require_running(identity, label):
    if json.loads(command(["docker", "inspect", identity]))[0]["State"]["Running"] is not True:
        raise RuntimeError("synthetic_egress_" + label + "_not_running")


def run_egress_probe(image_id):
    network = "synthetic-egress-" + uuid4().hex[:12]
    server_name = "synthetic-approved-" + uuid4().hex[:12]
    client_name = "synthetic-client-" + uuid4().hex[:12]
    sentinel_name = "synthetic-unapproved-" + uuid4().hex[:12]
    created = []
    try:
        command(["docker", "network", "create", "--driver", "bridge", "--internal",
                 "--opt", NETWORK_OPTION + "=false", network])
        verify_network(network_data(network))

        server_id = command(hardened_args(server_name, network, image_id, SERVER))
        created.append(server_id)
        if not re.fullmatch(r"[0-9a-f]{64}", server_id):
            raise RuntimeError("synthetic_egress_container_identity_invalid")
        inspect_container(server_id, image_id, network, SERVER)
        command(["docker", "start", server_id])
        time.sleep(0.1)
        require_running(server_id, "server")
        server_data = inspect_container(server_id, image_id, network, SERVER)
        server_ip = ipv4_for(server_data, network)

        client_id = command(hardened_args(
            client_name, network, image_id, CLIENT,
            ("SYNTHETIC_ALLOWED_IP=" + server_ip, "SYNTHETIC_EGRESS_GATE=1")))
        created.append(client_id)
        if not re.fullmatch(r"[0-9a-f]{64}", client_id):
            raise RuntimeError("synthetic_egress_container_identity_invalid")
        inspect_container(client_id, image_id, network, CLIENT)
        command(["docker", "start", client_id])
        time.sleep(0.1)
        require_running(client_id, "client")
        exact = {server_id: server_name, client_id: client_name}
        verify_members(network_data(network), exact)

        # Prove live preflight fails closed if any unapproved peer is attached.
        sentinel_id = command(hardened_args(sentinel_name, network, image_id, SERVER))
        created.append(sentinel_id)
        inspect_container(sentinel_id, image_id, network, SERVER)
        command(["docker", "start", sentinel_id])
        time.sleep(0.1)
        require_running(sentinel_id, "sentinel")
        try:
            verify_members(network_data(network), exact)
        except RuntimeError as error:
            if str(error) != "synthetic_egress_members_invalid":
                raise
        else:
            raise RuntimeError("synthetic_egress_extra_peer_not_rejected")
        command(["docker", "rm", "--force", sentinel_id])
        created.remove(sentinel_id)
        verify_members(network_data(network), exact)

        # Release the client only after exact live membership is proven.
        command(["docker", "exec", client_id, LAUNCHER, "-c",
                 "from pathlib import Path; Path('/tmp/egress-go').write_text('go')"])
        if command(["docker", "wait", client_id], timeout=15) != "0":
            raise RuntimeError("synthetic_egress_client_exit_invalid")
        client_state = json.loads(command(["docker", "inspect", client_id]))[0]["State"]
        if client_state["Running"] or client_state["ExitCode"] != 0:
            raise RuntimeError("synthetic_egress_client_exit_invalid")
    finally:
        for identity in reversed(created):
            try:
                command(["docker", "rm", "--force", identity])
            except RuntimeError:
                pass
        try:
            command(["docker", "network", "rm", network])
        except RuntimeError:
            pass
        if command(["docker", "network", "ls", "--quiet", "--filter", "name=^" + network + "$"]):
            raise RuntimeError("synthetic_egress_network_cleanup_failed")
    print("synthetic_egress_allowlist_ok", flush=True)
