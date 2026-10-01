#!/usr/bin/env python3
"""H2b: bounded synthetic sandbox probe; never starts the installed H2a unit.

Read the hash-pinned H2a validator source from stdin. Default inspect is read-only.
run requires the explicit CLI accident guard; operator authorization is separate.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import types
import uuid

H2A_HASH = "8e4ff9838829ce466b9913ea2dd39e2b5adf1854eacec96925fe9ac5e594a0f1"
APPROVE = "H2_SYNTHETIC_PROBE_V1"
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "LC_ALL": "C"}
CHECKS = ("IDENTITY", "PRIVILEGES", "CORE_UMASK", "READONLY_CONFIG_CODE",
          "PRIVATE_TMP", "PRIVATE_NETWORK", "IPV4_BLOCKED", "IPV6_BLOCKED",
          "CGROUP_IDENTITY", "MEMORY_LIMIT", "SWAP_LIMIT", "TASK_LIMIT", "CPU_LIMIT")
PROBE = r'''
import errno, os, resource, socket, sys, tempfile
from pathlib import Path

class Failed(Exception):
    pass

def check(ok, code):
    if not ok:
        raise Failed(code)
    print("PASS " + code, flush=True)

def blocked(family, code):
    try:
        s = socket.socket(family, socket.SOCK_STREAM)
    except OSError as e:
        check(e.errno in (errno.EAFNOSUPPORT, errno.EPERM, errno.EACCES), code)
    else:
        s.close()
        check(False, code)

try:
    uid, gid = int(sys.argv[1]), int(sys.argv[2])
    unit, network = sys.argv[3:5]
    temporary = [tuple(map(int, v.split(":"))) for v in sys.argv[5:7]]
    check(os.getresuid() == (uid, uid, uid) and os.getresgid() == (gid, gid, gid)
          and uid != 0 and gid != 0 and set(os.getgroups()) <= {gid}, "IDENTITY")
    status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines())
    check(int(status["NoNewPrivs"]) == 1 and all(int(status[k], 16) == 0
          for k in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb")), "PRIVILEGES")
    mask = os.umask(0o077)
    check(mask == 0o077 and resource.getrlimit(resource.RLIMIT_CORE) == (0, 0), "CORE_UMASK")
    check(all(os.statvfs(p).f_flag & os.ST_RDONLY for p in
          ("/etc/keirin-custody/gates.json", "/opt/keirin-custody")), "READONLY_CONFIG_CODE")
    private = True
    for directory, previous in zip(("/tmp", "/var/tmp"), temporary):
        s = os.stat(directory)
        private = private and (s.st_dev, s.st_ino) != previous
        # Anonymous one-byte temporary file; no named data survives the process.
        with tempfile.TemporaryFile(dir=directory) as f:
            f.write(b"x")
            f.flush()
    check(private, "PRIVATE_TMP")
    check(os.readlink("/proc/self/ns/net") != network, "PRIVATE_NETWORK")
    # Test socket creation only. No connect, DNS request, listener or packet.
    blocked(socket.AF_INET, "IPV4_BLOCKED")
    blocked(socket.AF_INET6, "IPV6_BLOCKED")
    expected = "/system.slice/" + unit
    check(Path("/proc/self/cgroup").read_text().strip() == "0::" + expected, "CGROUP_IDENTITY")
    cg = Path("/sys/fs/cgroup") / expected.lstrip("/")
    check((cg / "memory.max").read_text().strip() == "134217728", "MEMORY_LIMIT")
    check((cg / "memory.swap.max").read_text().strip() == "0", "SWAP_LIMIT")
    check((cg / "pids.max").read_text().strip() == "24", "TASK_LIMIT")
    quota, period = (cg / "cpu.max").read_text().split()
    check(quota != "max" and int(quota) > 0 and int(period) == 2 * int(quota), "CPU_LIMIT")
except Failed as e:
    print("FAIL " + str(e), flush=True)
    sys.exit(1)
except Exception:
    print("FAIL UNREADABLE", flush=True)
    sys.exit(1)
'''


class Stop(Exception):
    """Only fixed non-sensitive codes are printed."""


def need(ok, code):
    if not ok:
        raise Stop(code)


def load_h2(source):
    need(len(source) < 65536 and hashlib.sha256(source).hexdigest() == H2A_HASH,
         "H2A_VALIDATOR_HASH_MISMATCH")
    module = types.ModuleType("h2a_pinned_validator")
    exec(compile(source, "<pinned-h2a>", "exec"), module.__dict__)
    return module


def properties(h2):
    # Reuse every H2a service setting except the placeholder command/type and
    # null output. Only this transient synthetic service receives these changes.
    section = ""
    result = []
    for line in h2.UNIT.splitlines():
        if line.startswith("["):
            section = line
        elif section == "[Service]" and "=" in line:
            key = line.split("=", 1)[0]
            if key not in ("Type", "ExecStart", "StandardOutput", "StandardError"):
                result.append(line)
    return result + ["Type=exec", "RuntimeMaxSec=10s"]


def validate_output(output, returncode):
    need(len(output) < 4096, "PROBE_OUTPUT_INVALID")
    lines = output.decode("ascii", errors="strict").splitlines()
    expected = ["PASS " + key for key in CHECKS]
    if returncode == 0:
        need(lines == expected, "PROBE_OUTPUT_INVALID")
        return lines
    if lines and lines[-1].startswith("FAIL "):
        key = lines[-1][5:]
        if key in (*CHECKS, "UNREADABLE") and lines[:-1] == expected[:len(lines)-1]:
            raise Stop("PROBE_" + key + "_FAILED")
    raise Stop("PROBE_EXECUTION_FAILED")


class Runner:
    def __init__(self, h2):
        self.h2 = h2
        self.host = h2.Host()
        self.package = h2.Package(self.host)
        self.unit = "keirin-custody-h2b-" + uuid.uuid4().hex + ".service"
        self.description = "Keirin H2b synthetic probe " + self.unit

    def command(self, args, timeout=20):
        try:
            return subprocess.run(args, env=ENV, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired):
            raise Stop("PROBE_COMMAND_UNAVAILABLE") from None

    def state(self):
        r = self.command(["/usr/bin/systemctl", "show", self.unit,
                          "--property=LoadState,ActiveState,Transient,Description"], timeout=3)
        need(r.returncode == 0 and len(r.stdout) < 4096, "PROBE_STATE_UNREADABLE")
        return dict(line.split("=", 1) for line in r.stdout.decode().splitlines() if "=" in line)

    def own(self, state):
        need(state.get("Transient") == "yes" and state.get("Description") == self.description,
             "PROBE_OWNERSHIP_UNPROVEN")

    def no_temporary_dirs(self):
        return not any(p.name.startswith("systemd-private-") and ("-" + self.unit + "-") in p.name
                       for directory in ("/tmp", "/var/tmp") for p in Path(directory).iterdir())

    def cleanup(self):
        state = self.state()
        if state.get("LoadState") != "not-found":
            self.own(state)
            r = self.command(["/usr/bin/systemctl", "stop", self.unit], timeout=15)
            need(r.returncode == 0, "PROBE_STOP_FAILED")
        deadline = time.monotonic() + 3
        for _ in range(20):
            state = self.state()
            if state.get("LoadState") == "not-found" and self.no_temporary_dirs():
                return
            if state.get("LoadState") != "not-found":
                self.own(state)
            if time.monotonic() >= deadline:
                break
            time.sleep(0.1)
        raise Stop("PROBE_CLEANUP_UNCONFIRMED")

    def args(self):
        user = self.host.user()
        temporary = []
        for directory in ("/tmp", "/var/tmp"):
            s = os.stat(directory)
            temporary.append(str(s.st_dev) + ":" + str(s.st_ino))
        args = ["/usr/bin/systemd-run", "--quiet", "--wait", "--pipe", "--collect",
                "--unit=" + self.unit, "--description=" + self.description, "--slice=system.slice"]
        args.extend("--property=" + p for p in properties(self.h2))
        # Clear manager-supplied environment too, before starting the interpreter.
        return args + ["--", "/usr/bin/env", "-i", "PATH=" + ENV["PATH"], "LANG=C", "LC_ALL=C",
                       "/usr/bin/python3", "-I", "-B", "-c", PROBE,
                       str(user["uid"]), str(user["gid"]), self.unit,
                       os.readlink("/proc/self/ns/net"), *temporary]

    def inspect(self):
        self.package.verify()
        need(os.path.isfile("/usr/bin/systemd-run") and os.access("/usr/bin/systemd-run", os.X_OK),
             "SYSTEMD_RUN_MISSING")

    def run(self, approve):
        need(approve == APPROVE, "H2B_ACKNOWLEDGEMENT_REQUIRED")
        self.inspect()
        with self.package.lock():
            self.package.verify()
            need(self.state().get("LoadState") == "not-found", "PROBE_NAME_COLLISION")
            # Only enter cleanup after the absent-name check; a foreign unit
            # must never be stopped even if a creation attempt fails.
            try:
                r = self.command(self.args(), timeout=35)
                lines = validate_output(r.stdout, r.returncode)
            finally:
                self.cleanup()
                self.package.verify()
        return lines


def interrupted(signum, frame):
    raise Stop("PROBE_INTERRUPTED")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", default="inspect", choices=("inspect", "run"))
    parser.add_argument("--approve", default="")
    args = parser.parse_args(argv)
    h2 = None
    previous = {}
    try:
        h2 = load_h2(sys.stdin.buffer.read(65536))
        runner = Runner(h2)
        if args.action == "inspect":
            runner.inspect()
            print("RESULT H2B_PROBE_READY_NO_MUTATION")
        else:
            for sig in (signal.SIGINT, signal.SIGTERM):
                previous[sig] = signal.signal(sig, interrupted)
            lines = runner.run(args.approve)
            print("\n".join(lines))
            print("PASS PROBE_CLEANUP_AND_H2A_UNCHANGED")
            print("RESULT H2B_BASIC_SANDBOX_OK_NO_RUNTIME")
        return 0
    except Exception as exc:
        if isinstance(exc, Stop) or (h2 is not None and isinstance(exc, h2.Stop)):
            print("STOP " + str(exc))
        else:
            print("STOP H2B_STATE_UNREADABLE")
        print("RESULT NO_RUNTIME_AUTHORIZED_DO_NOT_RETRY_PROBE")
        return 1
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    sys.exit(main())
