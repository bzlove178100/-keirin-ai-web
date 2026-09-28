"""Synthetic-only controller crash/restart fixture; no deployed reconciliation."""
import json
import os
from pathlib import Path
import re
import select
import signal
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

from run_host_limits_contract import command, create_args, verify_config
from host_supervisor_contract import (
    cgroup_path, process_start, require_empty_cgroup, tree_pids, wait_reaped,
)

LABEL = "synthetic.keirin.host-recovery"


def validate_intent(data):
    if (type(data) is not dict or set(data) != {"version", "run_id", "image_id", "container_id"}
            or type(data["version"]) is not int or data["version"] != 1
            or type(data["run_id"]) is not str or not re.fullmatch(r"[0-9a-f]{32}", data["run_id"])
            or type(data["image_id"]) is not str or not re.fullmatch(r"sha256:[0-9a-f]{64}", data["image_id"])
            or (data["container_id"] is not None and (type(data["container_id"]) is not str
                or not re.fullmatch(r"[0-9a-f]{64}", data["container_id"])) )):
        raise RuntimeError("synthetic_recovery_intent_invalid")
    return data


def name_for(intent):
    return "synthetic-recovery-" + intent["run_id"]


def save_intent(path, intent):
    validate_intent(intent)
    temporary = path.with_suffix(".new")
    with open(temporary, "x") as stream:
        os.chmod(temporary, 0o600)
        json.dump(intent, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    # This fixture tests controller-process death, not host/power-loss durability.


def read_intent(path):
    if path.stat().st_size > 1024:
        raise RuntimeError("synthetic_recovery_intent_invalid")
    return validate_intent(json.loads(path.read_text()))


def candidate(intent):
    validate_intent(intent)
    ids = command(["docker", "ps", "--all", "--quiet", "--no-trunc", "--filter",
                   "label=" + LABEL + "=" + intent["run_id"]]).splitlines()
    if not ids:
        return None
    if len(ids) != 1 or not re.fullmatch(r"[0-9a-f]{64}", ids[0]):
        raise RuntimeError("synthetic_recovery_ambiguous_identity")
    data = json.loads(command(["docker", "inspect", ids[0]]))[0]
    if (data["Id"] != ids[0] or data["Name"] != "/" + name_for(intent)
            or data["Config"].get("Labels", {}).get(LABEL) != intent["run_id"]
            or intent["container_id"] not in (None, ids[0])):
        raise RuntimeError("synthetic_recovery_identity_mismatch")
    verify_config(data, intent["image_id"])
    return data


def reconcile(intent):
    data = candidate(intent)
    if data is None:
        return "absent"
    # Use the immutable full ID, never a name that could be reassigned.
    command(["docker", "rm", "--force", data["Id"]])
    if candidate(intent) is not None:
        raise RuntimeError("synthetic_recovery_removal_unverified")
    return "removed"


def create_fixture(intent):
    args = create_args(name_for(intent), intent["image_id"], "supervisor")
    args[-2] = "/src/tests/support/supervisor_tree_probe.py"
    args[2:2] = ["--label", LABEL + "=" + intent["run_id"]]
    identity = command(args)
    if not re.fullmatch(r"[0-9a-f]{64}", identity):
        raise RuntimeError("synthetic_recovery_create_identity_invalid")
    return identity


def launch(path, phase):
    if phase not in {"before-receipt", "running"}:
        raise RuntimeError("synthetic_recovery_phase_invalid")
    intent = read_intent(path)
    if intent["container_id"] is not None:
        raise RuntimeError("synthetic_recovery_launch_replay_rejected")
    identity = create_fixture(intent)
    if phase == "running":
        intent["container_id"] = identity
        save_intent(path, intent)
        if candidate(intent) is None:
            raise RuntimeError("synthetic_recovery_created_fixture_missing")
        command(["docker", "start", identity])
        ready = False
        for _ in range(40):
            output = command(["docker", "exec", identity, "python", "-c",
                              "from pathlib import Path; p=Path('/tmp/tree-ready'); print(p.read_text() if p.exists() else '')"], timeout=5)
            if output == "synthetic_tree_ready":
                ready = True
                break
            time.sleep(0.1)
        if not ready:
            raise RuntimeError("synthetic_recovery_tree_not_ready")
    # No finally-cleanup: the outer observer now kills this controller with SIGKILL.
    print("synthetic_controller_ready", flush=True)
    time.sleep(30)
    raise RuntimeError("synthetic_controller_fault_missing")


def new_intent(image_id):
    return {"version": 1, "run_id": uuid4().hex, "image_id": image_id, "container_id": None}


def restarted_reconcile(path, expected):
    output = command([sys.executable, __file__, "reconcile", str(path)], timeout=20)
    if output != "synthetic_recovery:" + expected:
        raise RuntimeError("synthetic_recovery_restart_result_invalid")


def run_controller_probe(image_id, phase):
    intent = new_intent(image_id)
    sentinel = new_intent(image_id)
    observed = []
    controller = None
    group = None
    with tempfile.TemporaryDirectory(prefix="synthetic-recovery-") as directory:
        path = Path(directory) / "intent.json"
        save_intent(path, intent)
        try:
            sentinel["container_id"] = create_fixture(sentinel)
            controller = subprocess.Popen([sys.executable, __file__, "launch", str(path), phase],
                                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            if not select.select([controller.stdout], [], [], 20)[0] or controller.stdout.readline(100).strip() != "synthetic_controller_ready":
                raise RuntimeError("synthetic_controller_not_ready")
            intent = read_intent(path)
            data = candidate(intent)
            if data is None or data["State"]["Running"] != (phase == "running"):
                raise RuntimeError("synthetic_controller_fixture_state_invalid")
            if phase == "running":
                pids = tree_pids(command(["docker", "top", data["Id"], "-eo", "pid,ppid,pgid,sid"]), data["State"]["Pid"])
                group = cgroup_path(data["State"]["Pid"])
                for pid in pids:
                    if cgroup_path(pid) != group:
                        raise RuntimeError("synthetic_recovery_cgroup_mismatch")
                    fd = os.pidfd_open(pid)
                    observed.append((pid, process_start(pid), fd))
            controller.kill()
            if controller.wait(timeout=3) != -signal.SIGKILL:
                raise RuntimeError("synthetic_controller_not_killed")
            # Controller death must really leave the target orphaned for recovery.
            remaining = candidate(intent)
            if remaining is None or remaining["State"]["Running"] != (phase == "running"):
                raise RuntimeError("synthetic_controller_orphan_missing")
            restarted_reconcile(path, "removed")
            restarted_reconcile(path, "absent")  # New interpreter again; no replay.
            if observed:
                wait_reaped(observed)
                require_empty_cgroup(group)
            if candidate(sentinel) is None:
                raise RuntimeError("synthetic_recovery_touched_unrelated_fixture")
        finally:
            if controller is not None:
                if controller.poll() is None:
                    controller.kill()
                    controller.wait(timeout=3)
                controller.stdout.close()
            try:
                reconcile(read_intent(path))
            finally:
                try:
                    reconcile(sentinel)
                finally:
                    for _, _, fd in observed:
                        os.close(fd)
    print("synthetic_controller_recovery_ok:" + phase, flush=True)


if __name__ == "__main__":
    if os.environ.get("AGENT_EPHEMERAL_HOST_TEST") != "1":
        raise RuntimeError("synthetic_recovery_gate_required")
    if sys.argv[1] == "launch":
        launch(Path(sys.argv[2]), sys.argv[3])
    elif sys.argv[1] == "reconcile":
        print("synthetic_recovery:" + reconcile(read_intent(Path(sys.argv[2]))), flush=True)
    else:
        raise RuntimeError("synthetic_recovery_command_invalid")
