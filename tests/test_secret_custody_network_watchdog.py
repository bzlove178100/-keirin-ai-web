"""CI-only real systemd recovery rehearsal. No live installer or apply command.

PID 1 supervises the watchdog in a disposable network namespace; a separate
applying process dies. The observing test parent is NOT the recovery process.
All profiles/traffic are fixed documentation-address fixtures from PR #173.
"""
from contextlib import contextmanager
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("transition", Path(__file__).with_name("test_secret_custody_network_transition.py"))
t = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(t)


def guard():
    t.guard()
    if (os.environ.get("KC_WATCHDOG_CI") != "1"
            or Path("/proc/1/comm").read_text().strip() != "systemd"):
        raise RuntimeError("CI_SYSTEMD_FIXTURE_REQUIRED")


def directory(value):
    if not re.fullmatch(r"/run/kc-watchdog-ci-[a-z0-9_]+", value):
        raise RuntimeError("FIXTURE_PATH_REQUIRED")
    path = Path(value)
    s = path.lstat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid != 0 or stat.S_IMODE(s.st_mode) != 0o700:
        raise RuntimeError("PRIVATE_ROOT_FIXTURE_REQUIRED")
    return path


@contextmanager
def locked(path):
    fd = os.open(path / "lock", os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        deadline = time.monotonic() + 2
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("LOCK_DEADLINE")
                time.sleep(0.02)
        yield
    finally:
        os.close(fd)


def decide(current, maintenance, candidate):
    if current == maintenance:
        return "ALREADY_MAINTENANCE"
    if current == candidate:
        return "RESTORE_MAINTENANCE"
    return "STOP_OWNED_TABLE_DRIFT"


def watchdog(value):
    guard()
    path = directory(value)
    data = json.loads((path / "expected.json").read_text())
    if (data["netns"] != os.readlink("/proc/self/ns/net")
            or os.getppid() != 1):
        raise RuntimeError("INDEPENDENT_SUPERVISOR_AND_NAMESPACE_REQUIRED")
    # Immutable in memory after loading; the applying child never writes it.
    maintenance, candidate = data["maintenance"], data["candidate"]
    with locked(path):
        if t.shape(t.r.TABLE) != maintenance:
            raise RuntimeError("MAINTENANCE_ANCHOR_REQUIRED")
        deadline = time.monotonic() + 5
        (path / "ready").write_text(json.dumps({"pid": os.getpid(), "deadline": deadline}))
    while time.monotonic() < deadline:
        time.sleep(max(0, min(0.05, deadline - time.monotonic())))
    with locked(path):
        result = decide(t.shape(t.r.TABLE), maintenance, candidate)
        if result == "RESTORE_MAINTENANCE":
            t.nft(t.r.replacement("maintenance"))
            if t.shape(t.r.TABLE) != maintenance:
                raise RuntimeError("FALLBACK_READBACK_MISMATCH")
        (path / "result").write_text(result)


def controller(value, mode):
    guard()
    path = directory(value)
    data = json.loads((path / "expected.json").read_text())
    with locked(path):
        ready = json.loads((path / "ready").read_text())
        # No readiness or insufficient remaining recovery window => no apply.
        if ready["deadline"] - time.monotonic() < 2:
            raise RuntimeError("WATCHDOG_NOT_ARMED")
        if os.readlink(f'/proc/{ready["pid"]}/ns/net') != data["netns"]:
            raise RuntimeError("WATCHDOG_NAMESPACE_CHANGED")
        if mode != "before":
            t.owned_transition(data["maintenance"], "qualification")
    (path / "applied").write_text(mode)
    os.kill(os.getpid(), signal.SIGKILL)


def await_file(path, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return path.read_text()
        time.sleep(0.05)
    raise RuntimeError("FIXTURE_READINESS_DEADLINE:" + path.name)


@contextmanager
def armed(maintenance, candidate):
    guard()
    path = Path(tempfile.mkdtemp(prefix="kc-watchdog-ci-", dir="/run"))
    path.chmod(0o700)
    unit = path.name + ".service"
    try:
        (path / "lock").write_text("")
        (path / "expected.json").write_text(json.dumps({
            "netns": os.readlink("/proc/self/ns/net"),
            "maintenance": maintenance, "candidate": candidate}))
        for item in path.iterdir():
            item.chmod(0o600)
        t.run("/usr/bin/systemd-run", "--quiet", "--unit=" + unit,
              "--property=Type=exec", "--property=Restart=no",
              "--property=RuntimeMaxSec=15", "--property=TimeoutStopSec=2",
              "--property=KillMode=control-group", "--property=UMask=0077",
              "--property=StandardOutput=null", "--property=StandardError=journal",
              "--property=NetworkNamespacePath=/proc/" + str(os.getpid()) + "/ns/net",
              "--setenv=GITHUB_ACTIONS=true", "--setenv=KC_WATCHDOG_CI=1",
              "/usr/bin/python3", "-I", "-B", str(Path(__file__).resolve()), "--worker", str(path))
        ready = json.loads(await_file(path / "ready", 4))
        assert ready["pid"] != os.getpid()
        status = t.run("/usr/bin/systemctl", "show", unit,
                       "--property=MainPID,ActiveState,Restart").stdout.decode()
        assert f'MainPID={ready["pid"]}\n' in status
        assert "ActiveState=active\n" in status and "Restart=no\n" in status
        yield path
    finally:
        t.run("/usr/bin/systemctl", "stop", unit, success=False)
        t.run("/usr/bin/systemctl", "reset-failed", unit, success=False)
        status = t.run("/usr/bin/systemctl", "show", unit, "--property=MainPID").stdout
        assert status == b"MainPID=0\n"
        shutil.rmtree(path)


def death(path, mode):
    result = subprocess.run(["/usr/bin/python3", "-I", "-B", __file__,
                             "--controller", str(path), mode], timeout=4)
    assert result.returncode == -signal.SIGKILL
    assert (path / "applied").read_text() == mode


def scenarios(stack, maintenance, candidate, check_packets):
    with armed(maintenance, candidate) as path:
        death(path, "before")
        assert await_file(path / "result", 7) == "ALREADY_MAINTENANCE"
        assert t.shape(t.r.TABLE) == maintenance
    check_packets()
    print("PASS WATCHDOG_PREAPPLY_CONTROLLER_DEATH_NO_MUTATION", flush=True)

    with armed(maintenance, candidate) as path:
        death(path, "after")
        assert t.shape(t.r.TABLE) == candidate
        old = [stack.enter_context(t.connect(prefix + "2", 443)) for _, prefix in t.r.FAMILIES]
        assert all(t.exchange(sock) for sock in old)
        assert await_file(path / "result", 7) == "RESTORE_MAINTENANCE"
        assert t.shape(t.r.TABLE) == maintenance
    assert all(not t.exchange(sock) for sock in old)
    assert all(not t.reaches(prefix + "2", 443) for _, prefix in t.r.FAMILIES)
    check_packets()
    print("PASS PID1_WATCHDOG_RESTORES_AFTER_CONTROLLER_SIGKILL", flush=True)
    print("PASS WATCHDOG_REVOKES_QUALIFICATION_PRESERVES_ADMIN_IPV4_IPV6", flush=True)

    with armed(maintenance, candidate) as path:
        death(path, "after")
        with locked(path):
            t.nft(f"add rule inet {t.r.TABLE} output tcp dport 9443 drop\n")
            changed = t.shape(t.r.TABLE)
        assert await_file(path / "result", 7) == "STOP_OWNED_TABLE_DRIFT"
        assert t.shape(t.r.TABLE) == changed
    # Explicit fixture teardown, not watchdog behavior or a live drift override.
    t.nft(t.r.replacement("maintenance"))
    assert t.shape(t.r.TABLE) == maintenance
    check_packets()
    print("PASS WATCHDOG_UNKNOWN_DRIFT_STOPS_WITHOUT_OVERWRITE", flush=True)
    print("PASS WATCHDOG_UNITS_PROCESSES_AND_PRIVATE_FIXTURES_CLEANED", flush=True)


class Tests(unittest.TestCase):
    def test_unknown_state_never_requests_replacement(self):
        self.assertEqual(decide({"other": 1}, {"safe": 1}, {"candidate": 1}), "STOP_OWNED_TABLE_DRIFT")

    def test_no_readiness_never_applies(self):
        with tempfile.TemporaryDirectory() as value:
            path = Path(value)
            (path / "lock").touch()
            (path / "expected.json").write_text("{}")
            with patch(__name__ + ".guard"), patch(__name__ + ".directory", return_value=path), \
                    patch.object(t, "owned_transition") as mutate:
                with self.assertRaises(FileNotFoundError):
                    controller(value, "after")
                mutate.assert_not_called()

    def test_expired_readiness_never_applies(self):
        with tempfile.TemporaryDirectory() as value:
            path = Path(value)
            (path / "lock").touch()
            (path / "expected.json").write_text("{}")
            (path / "ready").write_text(json.dumps({"deadline": 0}))
            with patch(__name__ + ".guard"), patch(__name__ + ".directory", return_value=path), \
                    patch.object(t, "owned_transition") as mutate:
                with self.assertRaisesRegex(RuntimeError, "WATCHDOG_NOT_ARMED"):
                    controller(value, "after")
                mutate.assert_not_called()

    def test_worker_refuses_host_namespace(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), patch.object(os, "geteuid", return_value=0), \
                patch.object(os, "readlink", return_value="same"), patch(__name__ + ".directory") as read:
            with self.assertRaisesRegex(RuntimeError, "DISPOSABLE_CI_NETWORK_NAMESPACE_REQUIRED"):
                watchdog("/run/kc-watchdog-ci-test")
            read.assert_not_called()


if __name__ == "__main__":
    if sys.argv[1:] == ["--systemd"]:
        guard()
        t.kernel_rehearsal(scenarios)
        print("RESULT SYNTHETIC_INDEPENDENT_RECOVERY_OK_NO_LIVE_APPLY")
    elif len(sys.argv) == 3 and sys.argv[1] == "--worker":
        watchdog(sys.argv[2])
    elif len(sys.argv) == 4 and sys.argv[1] == "--controller" and sys.argv[3] in ("before", "after"):
        controller(sys.argv[2], sys.argv[3])
    else:
        unittest.main(verbosity=2)
