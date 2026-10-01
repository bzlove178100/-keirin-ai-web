#!/usr/bin/env python3
"""H2c: synthetic private tmpfs and sealed-descriptor handoff; no live secrets.

stdin is exact H2a source, a --H2C-VALIDATOR-- line, then exact H2b source.
Default inspect is read-only. No persistent installation or runtime activation.
"""
import argparse
import hashlib
import os
from pathlib import Path
import signal
import sys
import types
import uuid

H2A_HASH = "8e4ff9838829ce466b9913ea2dd39e2b5adf1854eacec96925fe9ac5e594a0f1"
H2B_HASH = "b3c6513d382623f732fc9634ffe414b34c0da93048ce351df17cd2429a70d0bf"
APPROVE = "H2_SYNTHETIC_MEMORY_V1"
SEPARATOR = b"\n--H2C-VALIDATOR--\n"
CHECKS = ("PRIVATE_RUN_TMPFS", "TMPFS_BOUND_AND_FLAGS", "ANONYMOUS_TMPFILE",
          "DUMPABLE_DISABLED", "MEMFD_SEALED", "MEMFD_HANDOFF", "MEMORY_FDS_CLOSED")

# Only a descriptor number is passed to this executable child. Its data and
# checksum are generated inside the sandbox and exist only in anonymous memory.
CHILD = r'''
import ctypes, errno, fcntl, hashlib, os, resource, stat, sys
try:
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    if libc.prctl(4, 0, 0, 0, 0) != 0 or libc.prctl(3, 0, 0, 0, 0) != 0:
        raise ValueError()
    if libc.prctl(39, 0, 0, 0, 0) != 1 or resource.getrlimit(resource.RLIMIT_CORE) != (0, 0):
        raise ValueError()
    fd = int(sys.argv[1])
    st = os.fstat(fd)
    seals = fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL
    if (not stat.S_ISREG(st.st_mode) or st.st_nlink != 0 or st.st_size != 64
            or stat.S_IMODE(st.st_mode) != 0o600 or st.st_uid != os.getuid()
            or fcntl.fcntl(fd, fcntl.F_GET_SEALS) & seals != seals):
        raise ValueError()
    record = os.pread(fd, 65, 0)
    if len(record) != 64 or hashlib.sha256(record[:32]).digest() != record[32:]:
        raise ValueError()
    for action in (lambda: os.pwrite(fd, b"x", 0),
                   lambda: os.ftruncate(fd, 63), lambda: os.ftruncate(fd, 65)):
        try:
            action()
        except OSError as error:
            if error.errno != errno.EPERM:
                raise
        else:
            raise ValueError()
    os.close(fd)
    del record
    print("HANDOFF_OK", flush=True)
except BaseException:
    sys.exit(1)
'''

EXTRA_PROBE = r'''
import ctypes, fcntl, hashlib, stat, subprocess

fd = None
try:
    previous_mount = sys.argv[7]
    previous_run = tuple(map(int, sys.argv[8].split(":")))
    current = os.stat("/run")
    entries = [line.split() for line in Path("/proc/self/mountinfo").read_text().splitlines()]
    mounts = [entry for entry in entries if entry[4] == "/run"]
    check(os.readlink("/proc/self/ns/mnt") != previous_mount
          and (current.st_dev, current.st_ino) != previous_run and len(mounts) == 1
          and mounts[0][mounts[0].index("-") + 1] == "tmpfs"
          and (current.st_uid, current.st_gid) == (uid, gid)
          and stat.S_IMODE(current.st_mode) == 0o700, "PRIVATE_RUN_TMPFS")
    fs = os.statvfs("/run")
    required = os.ST_NOSUID | os.ST_NODEV | os.ST_NOEXEC
    check(fs.f_blocks * fs.f_frsize == 1048576 and fs.f_files == 128
          and fs.f_flag & required == required and not fs.f_flag & os.ST_RDONLY
          and "noswap" in mounts[0][-1].split(","), "TMPFS_BOUND_AND_FLAGS")
    # One-byte anonymous test only; no capacity exhaustion or named host file.
    with tempfile.TemporaryFile(dir="/run") as file:
        file.write(b"x")
        file.flush()
        st = os.fstat(file.fileno())
        check(st.st_nlink == 0 and stat.S_IMODE(st.st_mode) == 0o600
              and st.st_dev == current.st_dev and st.st_uid == uid, "ANONYMOUS_TMPFILE")
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    check(libc.prctl(4, 0, 0, 0, 0) == 0 and libc.prctl(3, 0, 0, 0, 0) == 0,
          "DUMPABLE_DISABLED")
    fd = os.memfd_create("h2c-synthetic", os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
    os.fchmod(fd, 0o600)
    payload = os.urandom(32)
    record = payload + hashlib.sha256(payload).digest()
    if os.write(fd, record) != 64:
        raise Failed("MEMFD_SEALED")
    seals = fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL
    fcntl.fcntl(fd, fcntl.F_ADD_SEALS, seals)
    check(fcntl.fcntl(fd, fcntl.F_GET_SEALS) & seals == seals
          and not os.get_inheritable(fd), "MEMFD_SEALED")
    result = subprocess.run(["/usr/bin/python3", "-I", "-B", "-c", CHILD, str(fd)],
                            pass_fds=(fd,), close_fds=True, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "LC_ALL": "C"},
                            timeout=3, check=False)
    check(result.returncode == 0 and result.stdout == b"HANDOFF_OK\n", "MEMFD_HANDOFF")
    os.close(fd)
    closed = fd
    fd = None
    try:
        os.fstat(closed)
    except OSError as error:
        check(error.errno == errno.EBADF, "MEMORY_FDS_CLOSED")
    else:
        raise Failed("MEMORY_FDS_CLOSED")
    del payload, record
except Failed as error:
    print("FAIL " + str(error), flush=True)
    sys.exit(1)
except Exception:
    print("FAIL UNREADABLE", flush=True)
    sys.exit(1)
finally:
    if fd is not None:
        os.close(fd)
'''


class Stop(Exception):
    pass


def load_validators(source):
    parts = source.split(SEPARATOR)
    if len(source) >= 131072 or len(parts) != 2:
        raise Stop("H2C_VALIDATOR_BUNDLE_INVALID")
    a, b = parts[0] + b"\n", parts[1]
    if hashlib.sha256(a).hexdigest() != H2A_HASH or hashlib.sha256(b).hexdigest() != H2B_HASH:
        raise Stop("H2C_VALIDATOR_HASH_MISMATCH")
    module = types.ModuleType("h2b_pinned_memory_controller")
    exec(compile(b, "<pinned-h2b>", "exec"), module.__dict__)
    return module.load_h2(a), module


def run_identity():
    s = os.stat("/run")
    mounts = tuple(line for line in Path("/proc/self/mountinfo").read_text().splitlines()
                   if line.split()[4] == "/run")
    return s.st_dev, s.st_ino, os.readlink("/proc/self/ns/mnt"), mounts


def make_runner(h2, controller):
    # Private, hash-verified module instance; only these fixed stronger probe
    # settings change. Its lifecycle/ownership/cleanup code is reused verbatim.
    controller.APPROVE = APPROVE
    controller.CHECKS += CHECKS
    controller.PROBE += "\nCHILD = " + repr(CHILD) + "\n" + EXTRA_PROBE

    class MemoryRunner(controller.Runner):
        def __init__(self):
            super().__init__(h2)
            self.unit = "keirin-custody-h2c-" + uuid.uuid4().hex + ".service"
            self.description = "Keirin H2c synthetic memory probe " + self.unit

        def args(self):
            args = super().args()
            user = self.host.user()
            # /run already exists. This mount is private to the transient unit;
            # no host directory creation or persistent mount change is needed.
            options = ("TemporaryFileSystem=/run:rw,size=1048576,nr_inodes=128,mode=0700,"
                       "nosuid,nodev,noexec,noswap,uid=" + str(user["uid"]) + ",gid=" + str(user["gid"]))
            args.insert(args.index("--"), "--property=" + options)
            before = run_identity()
            return args + [before[2], str(before[0]) + ":" + str(before[1])]

        def run(self, approve):
            if approve != APPROVE:
                raise Stop("H2C_ACKNOWLEDGEMENT_REQUIRED")
            before = run_identity()
            try:
                return super().run(approve)
            finally:
                if run_identity() != before:
                    raise Stop("HOST_RUN_MOUNT_CHANGED")

    return MemoryRunner()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", default="inspect", choices=("inspect", "run"))
    parser.add_argument("--approve", default="")
    args = parser.parse_args(argv)
    h2 = controller = None
    previous = {}
    try:
        h2, controller = load_validators(sys.stdin.buffer.read(131072))
        runner = make_runner(h2, controller)
        if args.action == "inspect":
            runner.inspect()
            print("RESULT H2C_MEMORY_PROBE_READY_NO_MUTATION")
        else:
            for sig in (signal.SIGINT, signal.SIGTERM):
                previous[sig] = signal.signal(sig, controller.interrupted)
            lines = runner.run(args.approve)
            print("\n".join(lines))
            print("PASS PROBE_CLEANUP_H2A_AND_HOST_RUN_UNCHANGED")
            print("RESULT H2C_SYNTHETIC_MEMORY_OK_NO_RUNTIME")
        return 0
    except Exception as error:
        expected = (Stop,) + ((h2.Stop, controller.Stop) if h2 is not None else ())
        print("STOP " + (str(error) if isinstance(error, expected) else "H2C_STATE_UNREADABLE"))
        print("RESULT NO_RUNTIME_AUTHORIZED_DO_NOT_RETRY_PROBE")
        return 1
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    sys.exit(main())
