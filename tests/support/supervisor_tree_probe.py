"""Deliberately uncooperative synthetic tree, confined by the Docker fixture."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from host_limits_probe import require, verify_limits


def main(role):
    verify_limits()
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    deadline = time.monotonic() + 45
    if role == "supervisor":
        require(os.getpid() == 1, "supervisor_not_namespace_init")
        # Inject abrupt application exit, without finally/atexit/child cleanup.
        signal.signal(signal.SIGUSR1, lambda *_: os._exit(23))
        subprocess.Popen([sys.executable, __file__, "child"])
    elif role == "child":
        subprocess.Popen([sys.executable, __file__, "leaf"], start_new_session=True)
        Path("/tmp/child-ready").write_text("ready")
    elif role == "leaf":
        require(os.getsid(0) == os.getpid() and os.getpgrp() == os.getpid(), "leaf_not_detached")
        Path("/tmp/leaf-ready").write_text("ready")
    else:
        raise RuntimeError("invalid_supervisor_role")
    while time.monotonic() < deadline:
        if role == "supervisor":
            if Path("/tmp/child-ready").exists() and Path("/tmp/leaf-ready").exists():
                Path("/tmp/tree-ready").write_text("synthetic_tree_ready")
        time.sleep(0.05)
    os._exit(24)  # Fail boundedly if the outer controller never delivers its fault.


if __name__ == "__main__":
    main(sys.argv[1])
