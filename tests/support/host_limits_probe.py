"""Synthetic cgroup-v2 probes; run only inside the gated disposable fixture."""
import errno
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

CGROUP = Path("/sys/fs/cgroup")
MEMORY_BYTES = 128 * 1024 * 1024
PIDS = 24


def require(condition, code):
    if not condition:
        raise RuntimeError(code)


def counters(name):
    return {key: int(value) for key, value in
            (line.split() for line in (CGROUP / name).read_text().splitlines())}


def verify_limits():
    require(os.environ.get("AGENT_EPHEMERAL_HOST_TEST") == "1", "fixture_gate_required")
    require(Path("/proc/self/cgroup").read_text().strip() == "0::/", "private_cgroup_required")
    require((CGROUP / "memory.max").read_text().strip() == str(MEMORY_BYTES), "memory_limit_mismatch")
    require((CGROUP / "memory.swap.max").read_text().strip() == "0", "swap_limit_mismatch")
    require((CGROUP / "pids.max").read_text().strip() == str(PIDS), "pids_limit_mismatch")
    require((CGROUP / "cpu.max").read_text().split() == ["50000", "100000"], "cpu_limit_mismatch")
    require(os.getuid() == 65534 and os.getgid() == 65534, "unprivileged_user_required")
    status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines())
    require(int(status["NoNewPrivs"]) == 1 and int(status["CapEff"], 16) == 0, "privilege_mismatch")


def cpu_probe():
    before = counters("cpu.stat")
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        pass
    after = counters("cpu.stat")
    require(after["nr_throttled"] > before["nr_throttled"], "cpu_not_throttled")
    require(after["throttled_usec"] > before["throttled_usec"], "cpu_throttle_time_missing")


def memory_probe():
    before = counters("memory.events")
    result = subprocess.run([sys.executable, __file__, "memory-hog"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
    require(result.returncode == -signal.SIGKILL, "memory_hog_not_killed")
    require(counters("memory.events")["oom_kill"] > before["oom_kill"], "memory_oom_evidence_missing")


def pids_probe():
    before = counters("pids.events")
    children = []
    denied = False
    try:
        # Hard bound even if a controller is defective; never an unbounded fork loop.
        for _ in range(PIDS + 2):
            try:
                child = os.fork()
            except OSError as error:
                require(error.errno == errno.EAGAIN, "unexpected_fork_failure")
                denied = True
                break
            if child == 0:
                time.sleep(15)
                os._exit(0)
            children.append(child)
        require(denied and children, "pids_not_enforced")
        require(counters("pids.events")["max"] > before["max"], "pids_evidence_missing")
    finally:
        for child in children:
            try:
                os.kill(child, signal.SIGKILL)
            except ProcessLookupError:
                pass
        for child in children:
            os.waitpid(child, 0)


def compatibility_probe():
    for filename in ("test_host_process_safety.py", "test_secret_parent_death.py"):
        result = subprocess.run([sys.executable, "/src/tests/" + filename],
                                capture_output=True, timeout=30)
        require(result.returncode == 0, "existing_os_guard_contract_failed")


def main(mode):
    verify_limits()  # No resource stress unless actual kernel limits are verified.
    if mode == "memory-hog":
        # Bias OOM selection toward this synthetic hog, away from the observer.
        Path("/proc/self/oom_score_adj").write_text("500")
        blocks = []
        for _ in range(256):
            block = bytearray(1024 * 1024)
            # Commit physical pages rather than merely reserving virtual memory.
            for offset in range(0, len(block), 4096):
                block[offset] = 1
            blocks.append(block)
        require(len(blocks) == 0, "memory_limit_not_enforced")
    probes = {"cpu": cpu_probe, "memory": memory_probe,
              "pids": pids_probe, "compatibility": compatibility_probe}
    require(mode in probes, "unknown_probe")
    probes[mode]()
    print("synthetic_host_limits_ok:" + mode, flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
