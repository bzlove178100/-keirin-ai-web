"""Synthetic-only process termination and loopback network blackhole tests."""
from contextlib import contextmanager
import json
import multiprocessing
import os
from pathlib import Path
import signal
import socket
import sys
import tempfile
import threading
import time
import traceback
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_core.durable_secret_store import (
    DurableSecretBackendAmbiguousWrite as Ambiguous,
    DurableSecretBackendConflict as Conflict,
    DurableSecretBackendUnavailable as Unavailable,
    DurableVersionedSecretStore, _encode_record,
)
from agent_core.postgres_secret_process import ProcessDeadlinePostgresSecretBackend
from agent_core.refresh_credentials import CredentialBinding
from agent_core.versioned_secret_store import RefreshSecretRecord

BINDING = CredentialBinding("synthetic-provider", "synthetic-account", ("read:one",))
KEY = DurableVersionedSecretStore.key_for(BINDING)
MARKER = "SYNTHETIC:driver-password-postgres://private"


def record(version=0):
    return _encode_record(RefreshSecretRecord(BINDING, version, "ready", "SYNTHETIC:refresh"))


def hang():
    # Force the deadline wrapper to escalate TERM -> KILL.
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    while True:
        time.sleep(1)


class DriverFailure(Exception):
    sqlstate = "P0002"

    @property
    def diag(self):
        return self

    message_primary = "credential_version_conflict"


class SyntheticConnection:
    autocommit = False

    def __init__(self):
        self.stage = os.environ.get("SECRET_PROCESS_TEST_STAGE", "success")
        self.raw = record()
        self.fetches = 0

    def cursor(self):
        return self

    def execute(self, sql, params):
        with open(os.environ["SECRET_PROCESS_TEST_JOURNAL"], "a") as journal:
            journal.write("execute\n")
        if self.stage == "execute":
            hang()
        if self.stage == "exit":
            os._exit(23)
        if self.stage in {"conflict", "rollback"}:
            raise DriverFailure(MARKER)
        if self.stage == "noisy":
            print(MARKER, flush=True)
            print(MARKER, file=sys.stderr, flush=True)
            os.write(2, MARKER.encode())
            raise RuntimeError(MARKER)
        self.raw = json.loads(params[2]) if len(params) == 3 else record()
        if self.stage == "oversized":
            self.raw["refresh_secret"] = "SYNTHETIC:" + "x" * 70000

    def fetchone(self):
        self.fetches += 1
        return (self.raw,) if self.fetches == 1 else None

    def commit(self):
        with open(os.environ["SECRET_PROCESS_TEST_JOURNAL"], "a") as journal:
            journal.write("commit\n")
        if self.stage == "commit":
            # Synthetic durable commit succeeds but its acknowledgement is lost.
            Path(os.environ["SECRET_PROCESS_TEST_JOURNAL"]).with_suffix(".json").write_text(json.dumps(self.raw))
            hang()

    def rollback(self):
        if self.stage == "rollback":
            hang()

    def close(self):
        if self.stage == "close":
            hang()


def synthetic_factory(**kwargs):
    if os.environ.get("SECRET_PROCESS_TEST_STAGE") == "connect":
        hang()
    return SyntheticConnection()


def network_blackhole_factory(**kwargs):
    import psycopg
    # Local disposable endpoint accepts TCP but sends no PostgreSQL startup response.
    # Driver connect_timeout is longer than the outer process deadline deliberately.
    return psycopg.connect(host="127.0.0.1", port=os.environ["SECRET_PROCESS_TEST_PORT"],
                           dbname="synthetic", user="synthetic", password="SYNTHETIC:only",
                           sslmode="disable", **kwargs)


@contextmanager
def blackhole():
    accepted = threading.Event()
    stopped = threading.Event()
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    server.settimeout(0.1)

    def serve():
        peer = None
        try:
            while not stopped.is_set():
                try:
                    peer, _ = server.accept()
                    accepted.set()
                    stopped.wait(5)
                    break
                except socket.timeout:
                    continue
        finally:
            if peer is not None:
                peer.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        with patch.dict(os.environ, {"SECRET_PROCESS_TEST_PORT": str(server.getsockname()[1])}):
            yield accepted
    finally:
        stopped.set()
        thread.join(1)
        server.close()


class ProcessDeadlineTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.journal = Path(self.directory.name) / "synthetic-counts.txt"
        self.env = patch.dict(os.environ, {"SECRET_PROCESS_TEST_JOURNAL": str(self.journal),
                                          "SECRET_PROCESS_TEST_STAGE": "success"})
        self.env.start()
        self.children = {p.pid for p in multiprocessing.active_children()}

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()
        self.assertEqual({p.pid for p in multiprocessing.active_children()}, self.children)

    def backend(self, factory=synthetic_factory, timeout=800):
        return ProcessDeadlinePostgresSecretBackend(factory, BINDING, operation_timeout_ms=timeout)

    def assert_safe(self, cls, call):
        started = time.monotonic()
        try:
            call()
        except BaseException as error:
            self.assertIs(type(error), cls)
            self.assertIsNone(error.__context__)
            self.assertIsNone(error.__cause__)
            self.assertNotIn(MARKER, "".join(traceback.format_exception(error)))
        else:
            self.fail("expected fixed failure")
        self.assertLess(time.monotonic() - started, 3.5)

    def test_successful_read_and_commit(self):
        backend = self.backend(timeout=2000)
        self.assertEqual(backend.read(KEY), record())
        self.assertEqual(backend.compare_and_swap(KEY, expected_version=0, replacement=record(1)), record(1))
        self.assertEqual(self.journal.read_text().splitlines(), ["execute", "commit"] * 2)
        self.assertEqual(repr(backend), "ProcessDeadlinePostgresSecretBackend(<redacted>)")

    def test_uncooperative_driver_phases_terminate_without_replay(self):
        for stage in ("connect", "execute", "commit", "rollback", "close", "exit"):
            with self.subTest(stage=stage), patch.dict(os.environ, {"SECRET_PROCESS_TEST_STAGE": stage}):
                self.journal.unlink(missing_ok=True)
                backend = self.backend()
                self.assert_safe(Ambiguous, lambda: backend.compare_and_swap(KEY, expected_version=0, replacement=record(1)))
                lines = self.journal.read_text().splitlines() if self.journal.exists() else []
                self.assertEqual(lines.count("execute"), 0 if stage == "connect" else 1)
                if stage == "commit":
                    self.assertEqual(json.loads(self.journal.with_suffix(".json").read_text()), record(1))
                self.assertEqual({p.pid for p in multiprocessing.active_children()}, self.children)

    def test_read_hang_is_unavailable(self):
        with patch.dict(os.environ, {"SECRET_PROCESS_TEST_STAGE": "execute"}):
            self.assert_safe(Unavailable, lambda: self.backend().read(KEY))

    def test_exact_conflict_survives_process_boundary(self):
        with patch.dict(os.environ, {"SECRET_PROCESS_TEST_STAGE": "conflict"}):
            self.assert_safe(Conflict, lambda: self.backend().compare_and_swap(KEY, expected_version=0, replacement=record(1)))

    def test_real_libpq_startup_blackhole_is_killed_before_connect_timeout(self):
        with blackhole() as accepted:
            self.assert_safe(Unavailable, lambda: self.backend(network_blackhole_factory, 1200).read(KEY))
            self.assertTrue(accepted.is_set(), "child must reach the actual TCP blackhole")

    def test_blackholed_write_is_conservatively_ambiguous(self):
        with blackhole() as accepted:
            self.assert_safe(Ambiguous, lambda: self.backend(network_blackhole_factory, 1200).compare_and_swap(
                KEY, expected_version=0, replacement=record(1)))
            self.assertTrue(accepted.is_set())

    def test_driver_output_and_exception_are_not_forwarded(self):
        # OS-level FD capture also covers raw writes from the spawned child.
        with tempfile.TemporaryFile() as capture, patch.dict(os.environ, {"SECRET_PROCESS_TEST_STAGE": "noisy"}):
            saved = [os.dup(1), os.dup(2)]
            try:
                os.dup2(capture.fileno(), 1)
                os.dup2(capture.fileno(), 2)
                self.assert_safe(Unavailable, lambda: self.backend().read(KEY))
            finally:
                os.dup2(saved[0], 1)
                os.dup2(saved[1], 2)
                for fd in saved:
                    os.close(fd)
            capture.seek(0)
            self.assertNotIn(MARKER.encode(), capture.read())

    def test_bounded_input_and_output(self):
        large = record(1)
        large["refresh_secret"] = "SYNTHETIC:" + "x" * 70000
        self.assert_safe(Unavailable, lambda: self.backend().compare_and_swap(KEY, expected_version=0, replacement=large))
        self.assertFalse(self.journal.exists())
        with patch.dict(os.environ, {"SECRET_PROCESS_TEST_STAGE": "oversized"}):
            self.assert_safe(Unavailable, lambda: self.backend().read(KEY))

    def test_invalid_request_fails_before_spawn(self):
        backend = self.backend()
        for key in ("wrong", None):
            self.assert_safe(Unavailable, lambda: backend.read(key))
        for expected in (True, -1, 2**63 - 1):
            self.assert_safe(Unavailable, lambda: backend.compare_and_swap(KEY, expected_version=expected, replacement=record(1)))
        self.assertFalse(self.journal.exists())

    def test_configuration_is_unbound_and_rejects_closures(self):
        backend = self.backend()
        self.assertFalse(self.journal.exists())
        for timeout in (True, 0, 60001):
            with self.assertRaises(ValueError):
                self.backend(timeout=timeout)
        with self.assertRaises(ValueError):
            self.backend(lambda **kwargs: None)
        self.assertIsNotNone(backend)

    def fake_context(self, response=b"", *, alive=False, interrupt=None):
        class Process:
            pid = 123
            exitcode = 0
            starts = 0

            def start(self):
                self.starts += 1

            def join(self, timeout):
                if interrupt:
                    raise interrupt(MARKER)

            def is_alive(self):
                return alive

            def terminate(self):
                pass

            def kill(self):
                pass

            def close(self):
                pass

        process = Process()
        def create_process(**kwargs):
            buffer, length = kwargs["args"][-2:]
            buffer[:len(response)] = response
            length.value = len(response)
            return process
        return SimpleNamespace(RawArray=lambda *args: bytearray(65536),
                               RawValue=lambda *args: SimpleNamespace(value=0),
                               Process=create_process), process

    def test_corrupt_or_partial_ipc_never_proves_commit(self):
        for response in (b"", b'{"status":', b'{"status":"ok"}',
                         b'{"status":"conflict","extra":"SYNTHETIC:private"}',
                         json.dumps({"status": "ok", "record": record(2)}).encode()):
            context, _ = self.fake_context(response)
            with patch("agent_core.postgres_secret_process.multiprocessing.get_context", return_value=context):
                self.assert_safe(Ambiguous, lambda: self.backend().compare_and_swap(KEY, expected_version=0, replacement=record(1)))

    def test_parent_interruption_is_redacted_and_write_stays_ambiguous(self):
        for cls in (KeyboardInterrupt, SystemExit):
            context, _ = self.fake_context(interrupt=cls)
            with patch("agent_core.postgres_secret_process.multiprocessing.get_context", return_value=context):
                self.assert_safe(cls, lambda: self.backend().read(KEY))
                self.assert_safe(Ambiguous, lambda: self.backend().compare_and_swap(KEY, expected_version=0, replacement=record(1)))

    def test_unreaped_child_quarantines_adapter(self):
        context, process = self.fake_context(alive=True)
        backend = self.backend()
        with patch("agent_core.postgres_secret_process.multiprocessing.get_context", return_value=context):
            self.assert_safe(Ambiguous, lambda: backend.compare_and_swap(KEY, expected_version=0, replacement=record(1)))
            self.assert_safe(Unavailable, lambda: backend.read(KEY))
            self.assertEqual(process.starts, 1)


if __name__ == "__main__":
    unittest.main()
