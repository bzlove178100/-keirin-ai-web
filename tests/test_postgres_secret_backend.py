"""Synthetic-only host transport, integrity, ambiguity and redaction checks."""
import copy
from pathlib import Path
import sys
import traceback
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_core.durable_secret_store import (
    DurableSecretBackendAmbiguousWrite as Ambiguous,
    DurableSecretBackendConflict as Conflict,
    DurableSecretBackendUnavailable as Unavailable,
    DurableVersionedSecretStore, _encode_record,
)
from agent_core.postgres_secret_backend import PostgresSecretBackend
from agent_core.refresh_credentials import CredentialBinding
from agent_core.versioned_secret_store import RefreshSecretRecord

BINDING = CredentialBinding("provider-a", "account-a", ("read:one", "write:one"))
KEY = DurableVersionedSecretStore.key_for(BINDING)
MARKER = "SYNTHETIC:password=driver-secret postgres://private-host"


def record(version=0):
    return _encode_record(RefreshSecretRecord(BINDING, version, "ready", "SYNTHETIC:a0"))


class DriverError(Exception):
    def __init__(self, code=None, primary=None):
        super().__init__(MARKER)
        self.sqlstate = code
        self.diag = SimpleNamespace(message_primary=primary)


class FakeConnection:
    autocommit = False

    def __init__(self, raw=None, faults=None):
        self.raw = record() if raw is None else raw
        self.faults = faults or {}
        self.calls = []
        self.fetches = 0

    def call(self, name):
        self.calls.append(name)
        if name in self.faults:
            raise self.faults[name]

    def cursor(self):
        self.call("cursor")
        return self

    def execute(self, sql, params):
        self.sql, self.params = sql, params
        self.call("execute")

    def fetchone(self):
        self.call("fetch")
        self.fetches += 1
        return (self.raw,) if self.fetches == 1 else None

    def commit(self):
        self.call("commit")

    def rollback(self):
        self.call("rollback")

    def close(self):
        self.call("close")


class BackendTests(unittest.TestCase):
    def backend(self, connection=None, factory_error=None, **kwargs):
        self.connection = connection or FakeConnection()
        self.options = []

        def factory(**options):
            self.options.append(options)
            if factory_error:
                raise factory_error
            return self.connection

        return PostgresSecretBackend(factory, BINDING, **kwargs)

    def assert_safe(self, cls, call):
        try:
            call()
        except BaseException as error:
            self.assertIs(type(error), cls)
            self.assertIsNone(error.__context__)
            self.assertIsNone(error.__cause__)
            self.assertNotIn(MARKER, str(error))
            self.assertNotIn(MARKER, repr(error))
            self.assertNotIn(MARKER, "".join(traceback.format_exception(error)))
        else:
            self.fail("expected fixed error")

    def test_read_and_connection_limits(self):
        backend = self.backend()
        self.assertEqual(backend.read(KEY), record())
        self.assertEqual(self.options, [{
            "connect_timeout": 5, "autocommit": False, "prepare_threshold": None,
            "options": "-c statement_timeout=5000 -c lock_timeout=1000 "
                       "-c idle_in_transaction_session_timeout=5000",
        }])
        self.assertEqual(self.connection.calls, ["cursor", "execute", "fetch", "fetch", "commit", "close", "close"])
        self.assertEqual(repr(backend), "PostgresSecretBackend(<redacted>)")

    def test_successful_cas_is_committed_once(self):
        backend = self.backend(FakeConnection(record(1)))
        self.assertEqual(backend.compare_and_swap(KEY, expected_version=0, replacement=record(1)), record(1))
        self.assertEqual(self.connection.calls.count("execute"), 1)
        self.assertNotIn("SYNTHETIC", self.connection.sql)
        self.assertEqual(self.connection.params[:2], (KEY, 0))

    def test_pre_submission_failures_never_write_or_retry(self):
        for stage in ("connect", "cursor"):
            with self.subTest(stage=stage):
                backend = self.backend(FakeConnection(faults={stage: DriverError()}),
                                       factory_error=DriverError() if stage == "connect" else None)
                self.assert_safe(Unavailable, lambda: backend.compare_and_swap(KEY, expected_version=0, replacement=record(1)))
                self.assertEqual(len(self.options), 1)
                self.assertNotIn("execute", self.connection.calls)

    def test_write_failures_are_ambiguous_and_not_retried(self):
        for stage in ("execute", "fetch", "commit"):
            for error in (DriverError(), TimeoutError(MARKER), KeyboardInterrupt(MARKER), SystemExit(MARKER)):
                with self.subTest(stage=stage, error=type(error)):
                    backend = self.backend(FakeConnection(record(1), {stage: error}))
                    self.assert_safe(Ambiguous, lambda: backend.compare_and_swap(KEY, expected_version=0, replacement=record(1)))
                    self.assertEqual(len(self.options), 1)
                    self.assertEqual(self.connection.calls.count("execute"), 1)
                    self.assertIn("rollback", self.connection.calls)

    def test_only_exact_conflict_and_confirmed_rollback(self):
        for primary, rollback_fails, expected in (
            ("credential_version_conflict", False, Conflict),
            ("credential_secret_missing", False, Ambiguous),
            ("credential_version_conflict", True, Ambiguous),
        ):
            faults = {"execute": DriverError("P0002", primary)}
            if rollback_fails:
                faults["rollback"] = DriverError()
            backend = self.backend(FakeConnection(faults=faults))
            self.assert_safe(expected, lambda: backend.compare_and_swap(KEY, expected_version=0, replacement=record(1)))

    def test_commit_conflict_text_is_still_ambiguous(self):
        backend = self.backend(FakeConnection(record(1), {"commit": DriverError("P0002", "credential_version_conflict")}))
        self.assert_safe(Ambiguous, lambda: backend.compare_and_swap(KEY, expected_version=0, replacement=record(1)))

    def test_read_failures_and_cleanup_are_redacted(self):
        for stage in ("execute", "fetch", "commit"):
            backend = self.backend(FakeConnection(faults={stage: DriverError(), "rollback": DriverError(), "close": DriverError()}))
            self.assert_safe(Unavailable, lambda: backend.read(KEY))
            self.assertEqual(self.connection.calls.count("close"), 2)

    def test_cleanup_failure_does_not_hide_known_commit(self):
        backend = self.backend(FakeConnection(record(1), {"close": DriverError()}))
        self.assertEqual(backend.compare_and_swap(KEY, expected_version=0, replacement=record(1)), record(1))

    def test_invalid_records_on_input_read_and_cas(self):
        invalid = []
        for field, value in (("extra", MARKER), ("version", True), ("version", 2**63),
                             ("refresh_generation", -1), ("refresh_generation", 1.0),
                             ("account_id", "other"), ("capabilities", ["write:one", "read:one"]),
                             ("capabilities", ["read:one", "read:one", "write:one"]),
                             ("failure", MARKER), ("active_attempt_id", MARKER),
                             ("refresh_secret", None), ("state", "revoked")):
            raw = record(1)
            raw[field] = value
            invalid.append(raw)
        missing = record(1)
        del missing["failure"]
        invalid.append(missing)
        for raw in invalid:
            with self.subTest(fields=sorted(raw)):
                backend = self.backend()
                self.assert_safe(Unavailable, lambda: backend.compare_and_swap(KEY, expected_version=0, replacement=raw))
                self.assertEqual(self.options, [])
                backend = self.backend(FakeConnection(copy.deepcopy(raw)))
                self.assert_safe(Unavailable, lambda: backend.read(KEY))
                backend = self.backend(FakeConnection(copy.deepcopy(raw)))
                self.assert_safe(Ambiguous, lambda: backend.compare_and_swap(KEY, expected_version=0, replacement=record(1)))
                self.assertNotIn("commit", self.connection.calls)

    def test_valid_but_mismatched_readback_is_ambiguous(self):
        backend = self.backend(FakeConnection(record(2)))
        self.assert_safe(Ambiguous, lambda: backend.compare_and_swap(KEY, expected_version=0, replacement=record(1)))

    def test_invalid_keys_versions_and_autocommit(self):
        backend = self.backend()
        self.assert_safe(Unavailable, lambda: backend.read(MARKER))
        for expected in (True, -1, 2**63 - 1, 0.0):
            self.assert_safe(Unavailable, lambda: backend.compare_and_swap(KEY, expected_version=expected, replacement=record(1)))
        self.assertEqual(self.options, [])
        self.connection.autocommit = True
        self.assert_safe(Unavailable, lambda: backend.read(KEY))
        self.assertNotIn("execute", self.connection.calls)

    def test_interruption_before_write_is_sanitized(self):
        for cls in (KeyboardInterrupt, SystemExit):
            backend = self.backend(factory_error=cls(MARKER))
            self.assert_safe(cls, lambda: backend.read(KEY))

    def test_timeout_configuration_rejected_without_io(self):
        for kwargs in ({"connect_timeout_seconds": 0}, {"connect_timeout_seconds": 1},
                       {"connect_timeout_seconds": True}, {"statement_timeout_ms": 30001},
                       {"lock_timeout_ms": 6000}):
            with self.assertRaises(ValueError):
                self.backend(**kwargs)


if __name__ == "__main__":
    unittest.main()
