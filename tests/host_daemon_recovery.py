"""Synthetic Docker-daemon restart/reconciliation qualification; CI only."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from run_host_limits_contract import command
from host_controller_recovery import (
    candidate,
    create_fixture,
    new_intent,
    read_intent,
    reconcile,
    restarted_reconcile,
    save_intent,
)
from host_supervisor_contract import (
    cgroup_path,
    process_start,
    require_empty_cgroup,
    tree_pids,
    wait_reaped,
)


def _require_supported_daemon():
    # The qualification below is intentionally for a non-live-restore daemon: a
    # daemon restart must terminate the synthetic container, after which a fresh
    # reconciler removes the exact immutable identity. Do not silently reinterpret
    # a different daemon policy as equivalent evidence.
    if command(["docker", "info", "--format", "{{.LiveRestoreEnabled}}"] ).lower() != "false":
        raise RuntimeError("synthetic_daemon_live_restore_unqualified")
    status = subprocess.run(
        ["systemctl", "is-active", "docker"], capture_output=True, text=True, timeout=5)
    if status.returncode != 0 or status.stdout.strip() != "active":
        raise RuntimeError("synthetic_daemon_service_unqualified")


def _restart_daemon():
    result = subprocess.run(
        ["sudo", "-n", "systemctl", "restart", "docker"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError("synthetic_daemon_restart_failed")
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        check = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if check.returncode == 0 and check.stdout.strip():
            return
        time.sleep(0.2)
    raise RuntimeError("synthetic_daemon_restart_not_ready")


def _wait_tree_ready(identity):
    for _ in range(60):
        result = subprocess.run(
            ["docker", "exec", identity, "python", "-c",
             "from pathlib import Path; p=Path('/tmp/tree-ready'); print(p.read_text() if p.exists() else '')"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip() == "synthetic_tree_ready":
            return
        time.sleep(0.1)
    raise RuntimeError("synthetic_daemon_tree_not_ready")


def run_daemon_recovery_probe(image_id):
    if os.environ.get("AGENT_EPHEMERAL_HOST_TEST") != "1":
        raise RuntimeError("synthetic_daemon_gate_required")
    _require_supported_daemon()

    intent = new_intent(image_id)
    sentinel = new_intent(image_id)
    observed = []
    group = None
    with tempfile.TemporaryDirectory(prefix="synthetic-daemon-recovery-") as directory:
        path = Path(directory) / "intent.json"
        save_intent(path, intent)
        try:
            # An unrelated stopped fixture must survive exact reconciliation.
            sentinel["container_id"] = create_fixture(sentinel)

            intent["container_id"] = create_fixture(intent)
            save_intent(path, intent)
            data = candidate(intent)
            if data is None or data["Id"] != intent["container_id"]:
                raise RuntimeError("synthetic_daemon_fixture_missing")
            command(["docker", "start", data["Id"]])
            _wait_tree_ready(data["Id"])

            data = candidate(read_intent(path))
            if data is None or not data["State"].get("Running"):
                raise RuntimeError("synthetic_daemon_fixture_not_running")
            pids = tree_pids(
                command(["docker", "top", data["Id"], "-eo", "pid,ppid,pgid,sid"]),
                data["State"]["Pid"],
            )
            group = cgroup_path(data["State"]["Pid"])
            for pid in pids:
                if cgroup_path(pid) != group:
                    raise RuntimeError("synthetic_daemon_cgroup_mismatch")
                observed.append((pid, process_start(pid), os.pidfd_open(pid)))

            _restart_daemon()

            # restart=no + live-restore=false must not resurrect the secret-host
            # process tree. The exact labeled container may remain as stopped state
            # until the fresh reconciler removes it.
            after = candidate(read_intent(path))
            if after is None or after["Id"] != intent["container_id"]:
                raise RuntimeError("synthetic_daemon_identity_lost")
            if after["State"].get("Running") or int(after["State"].get("Pid") or 0) != 0:
                raise RuntimeError("synthetic_daemon_fixture_resurrected")

            restarted_reconcile(path, "removed")
            restarted_reconcile(path, "absent")
            wait_reaped(observed)
            require_empty_cgroup(group)
            if candidate(sentinel) is None:
                raise RuntimeError("synthetic_daemon_recovery_touched_unrelated_fixture")
        finally:
            try:
                reconcile(read_intent(path))
            finally:
                try:
                    reconcile(sentinel)
                finally:
                    for _, _, fd in observed:
                        os.close(fd)

    print("synthetic_daemon_recovery_ok", flush=True)
