#!/usr/bin/env python3
"""H2d: two bounded synthetic process failures, never the installed service.

stdin: pinned H2a, --H2D-VALIDATOR--, H2b, --H2D-VALIDATOR--, H2c.
Default inspect is read-only. No secrets, persistent installation or restart.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import select
import signal
import subprocess
import sys
import time
import types
import uuid

HASHES = (
    "8e4ff9838829ce466b9913ea2dd39e2b5adf1854eacec96925fe9ac5e594a0f1",
    "b3c6513d382623f732fc9634ffe414b34c0da93048ce351df17cd2429a70d0bf",
    "d9564bc9ea308ad5584e866c3443c09a04829feda8e5bc5d7ca5bf90134cd166",
)
SEPARATOR = b"\n--H2D-VALIDATOR--\n"
APPROVE = "H2_SYNTHETIC_PROCESS_FAILURE_V1"
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "LC_ALL": "C"}
STATE_KEYS = ("LoadState,ActiveState,SubState,Transient,Description,ControlGroup,MainPID,"
              "Result,ExecMainCode,ExecMainStatus,KillMode,ExitType,Restart,NRestarts,"
              "RuntimeMaxUSec,TimeoutStopUSec,SendSIGKILL,KillSignal,FinalKillSignal")
CHECKS = ("PARENT_FAILURE_TREE_READY", "PARENT_FAILURE_MANAGER_STOP",
          "PARENT_FAILURE_PROCESSES_REAPED", "PARENT_FAILURE_CLEANUP",
          "LAUNCHER_FAILURE_TREE_READY", "LAUNCHER_FAILURE_SERVICE_SURVIVES",
          "LAUNCHER_FAILURE_MANAGER_DEADLINE", "LAUNCHER_FAILURE_PROCESSES_REAPED",
          "LAUNCHER_FAILURE_CLEANUP", "H2A_AND_HOST_RUN_UNCHANGED")

# The child deliberately has no parent-death signal: this measures the external
# manager, not the separately tested application PR_SET_PDEATHSIG safeguard.
CHILD = r'''
import ctypes, fcntl, hashlib, os, resource, signal, stat, sys, time
try:
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    if libc.prctl(4, 0, 0, 0, 0) or libc.prctl(3, 0, 0, 0, 0):
        raise ValueError()
    if libc.prctl(39, 0, 0, 0, 0) != 1 or resource.getrlimit(resource.RLIMIT_CORE) != (0, 0):
        raise ValueError()
    fd, ready, parent = map(int, sys.argv[1:])
    st = os.fstat(fd)
    seals = fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL
    record = os.pread(fd, 65, 0)
    if (os.getppid() != parent or not stat.S_ISREG(st.st_mode) or st.st_nlink != 0
            or st.st_size != 64 or stat.S_IMODE(st.st_mode) != 0o600
            or st.st_uid != os.getuid() or len(record) != 64
            or hashlib.sha256(record[:32]).digest() != record[32:]
            or fcntl.fcntl(fd, fcntl.F_GET_SEALS) & seals != seals):
        raise ValueError()
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    os.write(ready, b"R")
    os.close(ready)
    # Retain the sealed descriptor and record throughout the injected failure.
    time.sleep(60)
except BaseException:
    sys.exit(1)
'''

PARENT = r'''
import ctypes, fcntl, hashlib, os, resource, select, subprocess, sys, time
try:
    uid, gid = int(sys.argv[1]), int(sys.argv[2])
    if os.getresuid() != (uid, uid, uid) or os.getresgid() != (gid, gid, gid) or uid == 0:
        raise ValueError()
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    if libc.prctl(4, 0, 0, 0, 0) or libc.prctl(3, 0, 0, 0, 0):
        raise ValueError()
    if libc.prctl(39, 0, 0, 0, 0) != 1 or resource.getrlimit(resource.RLIMIT_CORE) != (0, 0):
        raise ValueError()
    fd = os.memfd_create("h2d-synthetic", os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
    os.fchmod(fd, 0o600)
    payload = os.urandom(32)
    record = payload + hashlib.sha256(payload).digest()
    if os.write(fd, record) != 64:
        raise ValueError()
    seals = fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL
    fcntl.fcntl(fd, fcntl.F_ADD_SEALS, seals)
    read_fd, write_fd = os.pipe2(os.O_CLOEXEC)
    child = subprocess.Popen(["/usr/bin/python3", "-I", "-B", "-c", CHILD,
                              str(fd), str(write_fd), str(os.getpid())],
                             pass_fds=(fd, write_fd), close_fds=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL,
                             env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "LC_ALL": "C"})
    os.close(write_fd)
    if not select.select([read_fd], [], [], 3)[0] or os.read(read_fd, 2) != b"R":
        raise ValueError()
    os.close(read_fd)
    print("READY " + str(os.getpid()) + " " + str(child.pid), flush=True)
    time.sleep(60)
except BaseException:
    sys.exit(1)
'''
PROBE = "CHILD = " + repr(CHILD) + "\n" + PARENT


class Stop(Exception):
    pass


def need(ok, code):
    if not ok:
        raise Stop(code)


def load_validators(source):
    parts = source.split(SEPARATOR)
    need(len(source) < 196608 and len(parts) == 3, "H2D_VALIDATOR_BUNDLE_INVALID")
    parts = [part + b"\n" for part in parts[:-1]] + [parts[-1]]
    need(all(hashlib.sha256(part).hexdigest() == digest for part, digest in zip(parts, HASHES)),
         "H2D_VALIDATOR_HASH_MISMATCH")
    memory = types.ModuleType("h2c_pinned_failure_profile")
    exec(compile(parts[2], "<pinned-h2c>", "exec"), memory.__dict__)
    h2, controller = memory.load_validators(parts[0][:-1] + memory.SEPARATOR + parts[1])
    return h2, controller, memory


def ready(stream):
    """Bounded nonblocking read; a partial/malicious line cannot block readline."""
    fd = stream.fileno()
    os.set_blocking(fd, False)
    data = b""
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and len(data) < 80:
        if select.select([fd], [], [], min(0.1, max(0, deadline - time.monotonic())))[0]:
            chunk = os.read(fd, 80 - len(data))
            need(bool(chunk), "PROCESS_TREE_NOT_READY")
            data += chunk
            if b"\n" in data:
                match = re.fullmatch(rb"READY ([1-9][0-9]{0,9}) ([1-9][0-9]{0,9})\n", data)
                need(match is not None, "PROCESS_EVIDENCE_INVALID")
                pids = tuple(map(int, match.groups()))
                need(pids[0] != pids[1], "PROCESS_EVIDENCE_INVALID")
                return pids
    raise Stop("PROCESS_TREE_NOT_READY")


def proc_stat(pid):
    try:
        fields = Path("/proc", str(pid), "stat").read_text().rsplit(") ", 1)[1].split()
        return fields[0], int(fields[1]), int(fields[19])  # state, parent, starttime
    except FileNotFoundError:
        return None


def observe_processes(pids, unit, user):
    observed = []
    try:
        for pid in pids:
            fd = os.pidfd_open(pid)
            observed.append((pid, None, fd))
            entry = proc_stat(pid)
            need(entry is not None and entry[0] != "Z", "PROCESS_IDENTITY_UNPROVEN")
            status = dict(line.split(":", 1) for line in
                          Path("/proc", str(pid), "status").read_text().splitlines())
            need(list(map(int, status["Uid"].split())) == [user["uid"]] * 4
                 and list(map(int, status["Gid"].split())) == [user["gid"]] * 4
                 and Path("/proc", str(pid), "cgroup").read_text().strip() == "0::/system.slice/" + unit,
                 "PROCESS_IDENTITY_UNPROVEN")
            if pid == pids[1]:
                need(entry[1] == pids[0] and int(status["SigIgn"], 16) & (1 << (signal.SIGTERM - 1)),
                     "RESISTANT_CHILD_UNPROVEN")
            need(not select.select([fd], [], [], 0)[0], "PROCESS_EXITED_BEFORE_FAULT")
            observed[-1] = (pid, entry[2], fd)
        return observed
    except BaseException:
        for _, _, fd in observed:
            os.close(fd)
        raise


def reaped(observed):
    for pid, start, fd in observed:
        if not select.select([fd], [], [], 0)[0]:
            return False
        entry = proc_stat(pid)
        if entry is not None and entry[2] == start:
            return False  # A zombie is not successful cleanup.
    return True


def make_runner(h2, controller, memory):
    profile = memory.make_runner(h2, controller)
    controller.PROBE = PROBE

    class FailureRunner(type(profile)):
        def __init__(self):
            super().__init__()
            self.unit = "keirin-custody-h2d-" + uuid.uuid4().hex + ".service"
            self.description = "Keirin H2d synthetic process failure " + self.unit

        def args(self):
            args = super().args()
            # Retain the failed unit briefly for reliable Result read-back.
            # Owned cleanup resets only this exact unit after process verification.
            args.remove("--collect")
            return ["--property=RuntimeMaxSec=6s" if a == "--property=RuntimeMaxSec=10s"
                    else "--property=TimeoutStopSec=1s" if a == "--property=TimeoutStopSec=10s"
                    else a for a in args]

        def state(self):
            result = self.command(["/usr/bin/systemctl", "show", self.unit,
                                   "--property=" + STATE_KEYS], timeout=3)
            need(result.returncode == 0 and len(result.stdout) < 4096, "PROCESS_STATE_UNREADABLE")
            return dict(line.split("=", 1) for line in result.stdout.decode().splitlines() if "=" in line)

        def active(self, main):
            state = self.state()
            self.own(state)
            expected = dict(ActiveState="active", SubState="running", MainPID=str(main),
                            ControlGroup="/system.slice/" + self.unit, KillMode="control-group",
                            ExitType="main", Restart="no", NRestarts="0", RuntimeMaxUSec="6s",
                            TimeoutStopUSec="1s", SendSIGKILL="yes", KillSignal="15", FinalKillSignal="9")
            need(all(state.get(k) == v for k, v in expected.items()), "PROCESS_PROFILE_UNPROVEN")

        def wait_failure(self, expected_result, observed):
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                state = self.state()
                self.own(state)
                if state.get("ActiveState") == "failed":
                    need(state.get("Result") == expected_result and state.get("NRestarts") == "0",
                         "MANAGER_FAILURE_REASON_UNPROVEN")
                    if reaped(observed):
                        return
                time.sleep(0.1)
            raise Stop("MANAGER_PROCESS_CLEANUP_UNCONFIRMED")

        def cleanup(self):
            state = self.state()
            if state.get("LoadState") != "not-found":
                self.own(state)
                result = self.command(["/usr/bin/systemctl", "stop", self.unit], timeout=15)
                need(result.returncode == 0, "PROCESS_STOP_FAILED")
                state = self.state()
                if state.get("LoadState") != "not-found":
                    self.own(state)
                    result = self.command(["/usr/bin/systemctl", "reset-failed", self.unit], timeout=3)
                    # An inactive transient unit can be collected between show
                    # and reset-failed. Only verified absence permits cleanup
                    # to continue; existing directory/cgroup checks still apply.
                    if result.returncode != 0:
                        need(self.state().get("LoadState") == "not-found", "PROCESS_RESET_FAILED")
            super().cleanup()
            need(not Path("/sys/fs/cgroup/system.slice", self.unit).exists(), "PROCESS_CGROUP_REMAINS")

        def case(self, kind):
            need(kind in ("parent", "launcher"), "PROCESS_CASE_INVALID")
            need(self.state().get("LoadState") == "not-found", "PROBE_NAME_COLLISION")
            launcher = None
            observed = []
            try:
                launcher = subprocess.Popen(self.args(), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                            stderr=subprocess.DEVNULL, env=ENV, close_fds=True)
                pids = ready(launcher.stdout)
                self.active(pids[0])
                observed = observe_processes(pids, self.unit, self.host.user())
                prefix = kind.upper() + "_FAILURE_"
                lines = ["PASS " + prefix + "TREE_READY"]
                if kind == "parent":
                    # The unique unit's main PID only. Never signal a raw PID,
                    # account-wide process list or the installed H2a service.
                    self.active(pids[0])
                    result = self.command(["/usr/bin/systemctl", "kill", "--kill-whom=main",
                                           "--signal=SIGKILL", self.unit], timeout=3)
                    need(result.returncode == 0, "PARENT_FAULT_NOT_INJECTED")
                    self.wait_failure("signal", observed)
                    need(launcher.wait(timeout=3) != 0, "PARENT_FAILURE_NOT_REPORTED")
                    lines.append("PASS PARENT_FAILURE_MANAGER_STOP")
                else:
                    # Popen's unreaped direct child identity cannot be recycled.
                    launcher.kill()
                    need(launcher.wait(timeout=3) == -signal.SIGKILL, "LAUNCHER_FAULT_NOT_INJECTED")
                    self.active(pids[0])  # Must really survive the launcher first.
                    lines.append("PASS LAUNCHER_FAILURE_SERVICE_SURVIVES")
                    self.wait_failure("timeout", observed)
                    lines.append("PASS LAUNCHER_FAILURE_MANAGER_DEADLINE")
                lines.append("PASS " + prefix + "PROCESSES_REAPED")
            finally:
                try:
                    self.cleanup()  # Fallback cleanup never turns a failed assertion into PASS.
                finally:
                    if launcher is not None:
                        if launcher.poll() is None:
                            launcher.kill()
                            launcher.wait(timeout=3)
                        launcher.stdout.close()
                    for _, _, fd in observed:
                        os.close(fd)
            return lines + ["PASS " + prefix + "CLEANUP"]

    return FailureRunner()


def run(h2, controller, memory, approve):
    need(approve == APPROVE, "H2D_ACKNOWLEDGEMENT_REQUIRED")
    before = memory.run_identity()
    runner = make_runner(h2, controller, memory)
    runner.inspect()
    with runner.package.lock():
        runner.package.verify()
        try:
            lines = runner.case("parent")
            runner.package.verify()
            # New exact name, same verified profile; neither failed unit is restarted.
            runner.unit = "keirin-custody-h2d-" + uuid.uuid4().hex + ".service"
            runner.description = "Keirin H2d synthetic process failure " + runner.unit
            lines += runner.case("launcher")
        finally:
            runner.package.verify()
            need(memory.run_identity() == before, "HOST_RUN_MOUNT_CHANGED")
    lines.append("PASS H2A_AND_HOST_RUN_UNCHANGED")
    need(lines == ["PASS " + key for key in CHECKS], "PROCESS_RESULT_INVALID")
    return lines


def interrupted(signum, frame):
    raise Stop("H2D_INTERRUPTED")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", default="inspect", choices=("inspect", "run"))
    parser.add_argument("--approve", default="")
    args = parser.parse_args(argv)
    h2 = controller = memory = None
    previous = {}
    try:
        h2, controller, memory = load_validators(sys.stdin.buffer.read(196608))
        if args.action == "inspect":
            make_runner(h2, controller, memory).inspect()
            print("RESULT H2D_PROCESS_PROBE_READY_NO_MUTATION")
        else:
            for sig in (signal.SIGINT, signal.SIGTERM):
                previous[sig] = signal.signal(sig, interrupted)
            print("\n".join(run(h2, controller, memory, args.approve)))
            print("RESULT H2D_SYNTHETIC_PROCESS_FAILURE_OK_NO_RUNTIME")
        return 0
    except Exception as error:
        known = [Stop] + [m.Stop for m in (h2, controller, memory) if m is not None]
        print("STOP " + (str(error) if isinstance(error, tuple(known)) else "H2D_STATE_UNREADABLE"))
        print("RESULT NO_RUNTIME_AUTHORIZED_DO_NOT_RETRY_PROBE")
        return 1
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    sys.exit(main())
