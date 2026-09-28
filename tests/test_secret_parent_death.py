"""Synthetic parent crashes under a disposable Linux subreaper, no credentials."""
import ctypes
import json
import multiprocessing
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_core import host_process_safety as safety
from agent_core import postgres_secret_process as process
from test_postgres_secret_process import BINDING, KEY, record


def hanging_factory(**kwargs):
    # The PID is the only persisted fixture data; no request/secret is logged.
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    Path(os.environ["SYNTHETIC_CHILD_PID"]).write_text(str(os.getpid()))
    while True:
        time.sleep(0.05)


def blocked_parent():
    process.ProcessDeadlinePostgresSecretBackend(
        hanging_factory, BINDING, operation_timeout_ms=60000,
    ).read(KEY)


def crash_probe(directory, termination):
    # Keep subreaper changes out of the unit-test host. Reap the actual child and
    # prove SIGKILL, rather than accepting disappearance or zombie state as success.
    assert safety._prctl(36, 1) == 0  # PR_SET_CHILD_SUBREAPER
    pid_file = Path(directory) / "child.pid"
    os.environ["SYNTHETIC_CHILD_PID"] = str(pid_file)
    parent = multiprocessing.get_context("spawn").Process(target=blocked_parent)
    child_pid = None
    parent.start()
    try:
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if pid_file.exists() and pid_file.read_text():
                child_pid = int(pid_file.read_text())
                break
            time.sleep(0.02)
        assert child_pid is not None, "factory_not_reached"
        os.kill(parent.pid, termination)
        parent.join(3)
        assert parent.exitcode == -termination, "parent_not_terminated"
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            pid, status = os.waitpid(child_pid, os.WNOHANG)
            if pid:
                child_pid = None
                assert os.WIFSIGNALED(status) and os.WTERMSIG(status) == signal.SIGKILL
                print("parent_death_child_reaped", flush=True)
                return
            time.sleep(0.02)
        raise AssertionError("child_survived_parent")
    finally:
        if parent.is_alive():
            parent.kill()
            parent.join(3)
        if child_pid is not None:
            try:
                os.kill(child_pid, signal.SIGKILL)
                os.waitpid(child_pid, 0)
            except ProcessLookupError:
                pass
        parent.close()


def rejected_child(*args):
    with patch.object(process, "guard_secret_parent", side_effect=RuntimeError("SYNTHETIC:private")):
        process._child(*args)


class SecretParentDeathTests(unittest.TestCase):
    def test_parent_termination_kills_and_reaps_blocked_child(self):
        for termination in (signal.SIGTERM, signal.SIGKILL):
            with self.subTest(signal=termination), tempfile.TemporaryDirectory() as directory:
                result = subprocess.run(
                    [sys.executable, __file__, "--crash-probe", directory, str(int(termination))],
                    capture_output=True, text=True, timeout=20,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), "parent_death_child_reaped")

    def test_invalid_or_already_changed_parent_rejected_before_registration(self):
        for parent_pid in (None, True, 0, -1, "123", 123):
            with self.subTest(pid=parent_pid), patch.object(safety.os, "getppid", return_value=456), \
                    patch.object(safety, "_prctl") as call:
                with self.assertRaisesRegex(RuntimeError, "^secret_host_parent_guard_failed$") as caught:
                    safety.guard_secret_parent(parent_pid)
                self.assertIsNone(caught.exception.__context__)
                call.assert_not_called()

    def test_registration_failure_readback_failure_and_parent_race(self):
        def registered(option, value=0):
            if option == 2:
                ctypes.c_int.from_address(value).value = signal.SIGKILL
            return 0

        for behavior, parents in (([-1], [123]), ([0, -1], [123]), ([0, 0], [123]),
                                  (registered, [123, 456])):
            with patch.object(safety.os, "getppid", side_effect=parents), \
                    patch.object(safety, "_prctl", side_effect=behavior):
                with self.assertRaisesRegex(RuntimeError, "^secret_host_parent_guard_failed$") as caught:
                    safety.guard_secret_parent(123)
                self.assertIsNone(caught.exception.__context__)
        with patch.object(safety.sys, "platform", "unsupported"), patch.object(safety, "_prctl") as call:
            with self.assertRaisesRegex(RuntimeError, "^secret_host_parent_guard_failed$"):
                safety.guard_secret_parent(123)
            call.assert_not_called()

    def test_guard_failure_has_no_factory_or_reply(self):
        context = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
                "SYNTHETIC_CHILD_PID": str(Path(directory) / "child.pid")}):
            for write in (False, True):
                buffer = context.RawArray("B", 65536)
                length = context.RawValue("I", 0)
                request = json.dumps(dict(key=KEY, expected=0, replacement=record(1), write=write)).encode()
                child = context.Process(target=rejected_child, args=(
                    hanging_factory, BINDING, {}, request, buffer, length, os.getpid(),
                ))
                child.start()
                try:
                    child.join(5)
                    self.assertEqual(child.exitcode, 1)
                    self.assertEqual(length.value, 0)
                    self.assertFalse(Path(os.environ["SYNTHETIC_CHILD_PID"]).exists())
                finally:
                    if child.is_alive():
                        child.kill()
                        child.join(2)
                    child.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--crash-probe":
        crash_probe(sys.argv[2], int(sys.argv[3]))
    else:
        unittest.main()
