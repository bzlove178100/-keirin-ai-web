"""Synthetic OS checks in disposable children; never harden the test parent."""
import json
import multiprocessing
import os
from pathlib import Path
import resource
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_core import host_process_safety as safety
from agent_core import postgres_secret_process as process
from agent_core.durable_secret_store import DurableSecretBackendUnavailable
from test_postgres_secret_process import BINDING, KEY, record, SyntheticConnection


def guarded_factory(**kwargs):
    assert resource.getrlimit(resource.RLIMIT_CORE) == (0, 0)
    assert safety._prctl(3) == 0
    assert safety._prctl(39) == 1
    assert os.umask(0o077) == 0o077
    return SyntheticConnection()


def failed_guard_child(*args):
    with patch.object(process, "harden_secret_child", side_effect=RuntimeError("SYNTHETIC:private")):
        process._child(*args)


class HostProcessSafetyTests(unittest.TestCase):
    def test_kernel_controls_before_factory_and_parent_unchanged(self):
        before = (resource.getrlimit(resource.RLIMIT_CORE), safety._prctl(3), safety._prctl(39))
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            "SECRET_PROCESS_TEST_JOURNAL": str(Path(directory) / "calls"),
            "SECRET_PROCESS_TEST_STAGE": "success",
        }):
            backend = process.ProcessDeadlinePostgresSecretBackend(guarded_factory, BINDING)
            self.assertEqual(backend.read(KEY), record())
            self.assertEqual(backend.compare_and_swap(KEY, expected_version=0, replacement=record(1)), record(1))
        self.assertEqual((resource.getrlimit(resource.RLIMIT_CORE), safety._prctl(3), safety._prctl(39)), before)

    def test_unsafe_environment_blocks_read_and_write_before_spawn(self):
        backend = process.ProcessDeadlinePostgresSecretBackend(guarded_factory, BINDING)
        for key in ("LD_PRELOAD", "LD_LIBRARY_PATH", "LD_AUDIT", "DYLD_INSERT_LIBRARIES",
                    *safety._PYTHON_OVERRIDES):
            with self.subTest(key=key), patch.dict(os.environ, {key: "SYNTHETIC:private"}), \
                    patch.object(process.multiprocessing, "get_context") as spawn:
                for operation in (lambda: backend.read(KEY), lambda: backend.compare_and_swap(
                        KEY, expected_version=0, replacement=record(1))):
                    with self.assertRaisesRegex(DurableSecretBackendUnavailable, "^secret_process_unavailable$") as caught:
                        operation()
                    self.assertIsNone(caught.exception.__context__)
                spawn.assert_not_called()
                self.assertEqual(os.environ[key], "SYNTHETIC:private")

    def test_failed_set_or_readback_is_fixed_and_context_free(self):
        # Mock every irreversible operation; no changes to this parent process.
        for results in ((-1,), (0, -1), (0, 0, 1), (0, 0, 0, 0)):
            with patch.object(safety.resource, "setrlimit"), \
                    patch.object(safety.resource, "getrlimit", return_value=(0, 0)), \
                    patch.object(safety, "_prctl", side_effect=results), patch.object(safety.os, "umask") as mask:
                with self.assertRaisesRegex(RuntimeError, "^secret_host_child_unsafe$") as caught:
                    safety.harden_secret_child()
                self.assertIsNone(caught.exception.__context__)
                mask.assert_not_called()
        with patch.object(safety.resource, "setrlimit", side_effect=OSError("SYNTHETIC:private")):
            with self.assertRaisesRegex(RuntimeError, "^secret_host_child_unsafe$"):
                safety.harden_secret_child()
        with patch.object(safety.sys, "platform", "unsupported"):
            with self.assertRaisesRegex(RuntimeError, "^secret_host_child_unsafe$"):
                safety.harden_secret_child()

    def test_hardening_failure_exits_without_factory_or_success_reply(self):
        context = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
                "SECRET_PROCESS_TEST_JOURNAL": str(Path(directory) / "calls")}):
            for write in (False, True):
                buffer = context.RawArray("B", 65536)
                length = context.RawValue("I", 0)
                request = json.dumps(dict(key=KEY, expected=0, replacement=record(1), write=write)).encode()
                child = context.Process(target=failed_guard_child, args=(guarded_factory, BINDING, {}, request, buffer, length))
                child.start()
                try:
                    child.join(5)
                    self.assertEqual(child.exitcode, 1)
                    self.assertEqual(length.value, 0)
                    self.assertFalse((Path(directory) / "calls").exists())
                finally:
                    if child.is_alive():
                        child.kill()
                        child.join(2)
                    child.close()


if __name__ == "__main__":
    unittest.main()
