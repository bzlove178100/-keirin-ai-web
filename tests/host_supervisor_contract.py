"""Docker PID-namespace supervisor qualification, synthetic fixtures only."""
import json
import os
from pathlib import Path
import select
import time
from uuid import uuid4

from run_host_limits_contract import command, create_args, verify_config


def process_start(pid):
    try:
        # comm may contain spaces/parentheses; starttime is field 22.
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except FileNotFoundError:
        return None


def tree_pids(top, init_pid):
    rows = [tuple(map(int, line.split())) for line in top.splitlines()[1:]]
    if len(rows) != 3 or any(len(row) != 4 for row in rows):
        raise RuntimeError("synthetic_tree_shape_invalid")
    pids = {row[0] for row in rows}
    children = [row for row in rows if row[1] == init_pid]
    if init_pid not in pids or len(pids) != 3 or len(children) != 1:
        raise RuntimeError("synthetic_tree_parent_invalid")
    leaves = [row for row in rows if row[1] == children[0][0]]
    if len(leaves) != 1 or leaves[0][0] != leaves[0][2] or leaves[0][0] != leaves[0][3]:
        raise RuntimeError("synthetic_tree_detached_leaf_missing")
    return sorted(pids)


def wait_reaped(observed, timeout=5):
    """Require exit via stable pidfds AND disappearance of original /proc identities.

    Readable pidfds alone can mean zombies, so they do not prove reaping.
    """
    if not observed or any(start is None for _, start, _ in observed):
        raise RuntimeError("synthetic_tree_identity_missing")
    poller = select.poll()
    for _, _, fd in observed:
        poller.register(fd, select.POLLIN)
    exited = set()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for fd, event in poller.poll(50):
            if event & select.POLLNVAL:
                raise RuntimeError("synthetic_tree_pidfd_invalid")
            if event & (select.POLLIN | select.POLLHUP):
                exited.add(fd)
        if len(exited) == len(observed) and all(process_start(pid) != start for pid, start, _ in observed):
            return
        time.sleep(0.02)
    raise RuntimeError("synthetic_tree_not_reaped")


def cgroup_path(pid):
    value = Path(f"/proc/{pid}/cgroup").read_text().strip()
    if not value.startswith("0::/") or "\n" in value:
        raise RuntimeError("synthetic_tree_cgroup_invalid")
    relative = Path(value[4:])
    if not relative.parts or ".." in relative.parts or relative.is_absolute():
        raise RuntimeError("synthetic_tree_cgroup_invalid")
    return Path("/sys/fs/cgroup") / relative


def require_empty_cgroup(group):
    try:
        events = dict(line.split() for line in (group / "cgroup.events").read_text().splitlines())
        if events.get("populated") != "0" or (group / "cgroup.procs").read_text().strip():
            raise RuntimeError("synthetic_tree_cgroup_populated")
    except FileNotFoundError:
        if group.exists():
            raise RuntimeError("synthetic_tree_cgroup_evidence_missing")


def run_supervisor_probe(image_id, mode):
    if mode not in {"crash", "forced-stop"}:
        raise RuntimeError("synthetic_supervisor_mode_invalid")
    name = "synthetic-supervisor-" + uuid4().hex[:12]
    observed = []
    try:
        args = create_args(name, image_id, "supervisor")
        args[-2] = "/src/tests/support/supervisor_tree_probe.py"
        command(args)
        verify_config(json.loads(command(["docker", "inspect", name]))[0], image_id)
        command(["docker", "start", name])
        ready = False
        for _ in range(40):
            output = command(["docker", "exec", name, "python", "-c",
                              "from pathlib import Path; p=Path('/tmp/tree-ready'); print(p.read_text() if p.exists() else '')"], timeout=5)
            if output == "synthetic_tree_ready":
                ready = True
                break
            time.sleep(0.1)
        if not ready:
            raise RuntimeError("synthetic_tree_not_ready")
        init_pid = json.loads(command(["docker", "inspect", name]))[0]["State"]["Pid"]
        pids = tree_pids(command(["docker", "top", name, "-eo", "pid,ppid,pgid,sid"]), init_pid)
        group = cgroup_path(init_pid)
        for pid in pids:
            if cgroup_path(pid) != group:
                raise RuntimeError("synthetic_tree_cgroup_mismatch")
            fd = os.pidfd_open(pid)
            start = process_start(pid)
            observed.append((pid, start, fd))
            if start is None:
                raise RuntimeError("synthetic_tree_exited_before_fault")
        if mode == "crash":
            command(["docker", "kill", "--signal", "USR1", name])
        else:
            # Every tree member ignores TERM. Docker must escalate after one second.
            command(["docker", "stop", "--time", "1", name], timeout=10)
        exit_code = command(["docker", "wait", name], timeout=10)
        if exit_code != ("23" if mode == "crash" else "137"):
            raise RuntimeError("synthetic_supervisor_exit_mismatch")
        wait_reaped(observed)
        require_empty_cgroup(group)
    finally:
        try:
            command(["docker", "rm", "--force", name])
            if command(["docker", "ps", "--all", "--quiet", "--filter", "name=^/" + name + "$"]):
                raise RuntimeError("synthetic_supervisor_cleanup_failed")
        finally:
            for _, _, fd in observed:
                os.close(fd)
    print("synthetic_supervisor_ok:" + mode, flush=True)
