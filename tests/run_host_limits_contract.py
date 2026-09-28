"""Opt-in synthetic Docker qualification; never configures a deployed host."""
import json
import os
from pathlib import Path
import re
import subprocess
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
APPROVED_IMAGE_DIGEST = "sha256:d5ae74acb8026b32a2f6deea45003c5bd4e2880700c19c44bda54670ad3eff90"
IMAGE = "python:3.12.14-slim-bookworm@" + APPROVED_IMAGE_DIGEST
APPROVED_REPO_DIGEST = "python@" + APPROVED_IMAGE_DIGEST
LAUNCHER = "/usr/local/bin/python3"
PROBE = "/src/tests/support/host_limits_probe.py"


def command(args, timeout=45):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError("synthetic_host_command_failed")
    return result.stdout.strip()


def create_args(name, image_id, mode):
    return ["docker", "create", "--name", name, "--network", "none", "--cgroupns", "private",
            "--memory", "128m", "--memory-swap", "128m", "--pids-limit", "24",
            "--cpu-period", "100000", "--cpu-quota", "50000", "--read-only",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges=true",
            "--user", "65534:65534", "--log-driver", "none", "--restart", "no",
            "--ulimit", "core=0:0", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=32m,mode=1777",
            "--mount", f"type=bind,src={ROOT / 'tests'},dst=/src/tests,readonly",
            "--mount", f"type=bind,src={ROOT / 'agent_core'},dst=/src/agent_core,readonly",
            "--env", "AGENT_EPHEMERAL_HOST_TEST=1", "--env", "PYTHONDONTWRITEBYTECODE=1",
            "--entrypoint", LAUNCHER,
            image_id, PROBE, mode]


def verify_image_provenance(data):
    if (type(data) is not dict or data.get("Os") != "linux" or data.get("Architecture") != "amd64"
            or data.get("Id") is None or not re.fullmatch(r"sha256:[0-9a-f]{64}", data["Id"])
            or APPROVED_REPO_DIGEST not in data.get("RepoDigests", [])):
        raise RuntimeError("synthetic_host_image_provenance_invalid")
    return data["Id"]


def verify_launcher(data, expected_command):
    config = data.get("Config", {})
    if (config.get("Entrypoint") != [LAUNCHER]
            or config.get("Cmd") != expected_command):
        raise RuntimeError("synthetic_host_launcher_mismatch")


def verify_config(data, image_id, *, expected_log_driver="none"):
    if expected_log_driver not in {"none", "json-file"}:
        raise RuntimeError("synthetic_host_log_driver_invalid")
    host, config = data["HostConfig"], data["Config"]
    expected = {"Memory": 134217728, "MemorySwap": 134217728, "PidsLimit": 24,
                "CpuPeriod": 100000, "CpuQuota": 50000, "ReadonlyRootfs": True,
                "NetworkMode": "none", "CgroupnsMode": "private", "Privileged": False}
    if (any(host[key] != value for key, value in expected.items())
            or config["User"] != "65534:65534" or data["Image"] != image_id
            or host["LogConfig"]["Type"] != expected_log_driver
            or host["RestartPolicy"]["Name"] != "no"
            or host["CapDrop"] != ["ALL"]
            or "no-new-privileges=true" not in host["SecurityOpt"]):
        raise RuntimeError("synthetic_host_config_mismatch")


def run_probe(image_id, mode):
    name = "synthetic-host-limits-" + uuid4().hex[:12]
    try:
        command(create_args(name, image_id, mode))
        data = json.loads(command(["docker", "inspect", name]))[0]
        verify_config(data, image_id)
        verify_launcher(data, [PROBE, mode])
        output = command(["docker", "start", "--attach", name], timeout=60)
        state = json.loads(command(["docker", "inspect", name]))[0]["State"]
        if state["Running"] or state["ExitCode"] != 0 or output != "synthetic_host_limits_ok:" + mode:
            raise RuntimeError("synthetic_host_probe_failed:" + mode)
    finally:
        # Also removes descendants after a timeout/error. Only our unique fixture.
        command(["docker", "rm", "--force", name])
        if command(["docker", "ps", "--all", "--quiet", "--filter", "name=^/" + name + "$"]):
            raise RuntimeError("synthetic_host_cleanup_failed")
    print("synthetic_host_limits_ok:" + mode, flush=True)


def main():
    if os.environ.get("AGENT_EPHEMERAL_HOST_TEST") != "1":
        raise RuntimeError("synthetic_host_gate_required")
    if command(["docker", "info", "--format", "{{.CgroupVersion}}"]) != "2":
        raise RuntimeError("synthetic_host_cgroup_v2_required")
    # Pull an explicitly approved immutable manifest, never a moving tag.
    command(["docker", "pull", IMAGE], timeout=120)
    image_data = json.loads(command(["docker", "image", "inspect", IMAGE]))[0]
    image_id = verify_image_provenance(image_data)
    print("synthetic_host_image:" + image_id, flush=True)
    print("synthetic_host_manifest:" + APPROVED_IMAGE_DIGEST, flush=True)
    for mode in ("cpu", "memory", "pids", "compatibility", "network"):
        run_probe(image_id, mode)
    from host_supervisor_contract import run_supervisor_probe
    for mode in ("crash", "forced-stop"):
        run_supervisor_probe(image_id, mode)
    from host_controller_recovery import run_controller_probe
    for phase in ("before-receipt", "running"):
        run_controller_probe(image_id, phase)
    from host_logging_contract import run_logging_probe
    for driver in ("json-file", "none"):
        run_logging_probe(image_id, driver)


if __name__ == "__main__":
    main()
