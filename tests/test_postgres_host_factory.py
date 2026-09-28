from pathlib import Path
import os
import sys
import traceback
import unittest
import tempfile
from dataclasses import replace
from hashlib import sha256
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_core.durable_secret_store import DurableSecretBackendUnavailable
from agent_core.postgres_host_factory import StrictPostgresConnectionFactory
from agent_core.postgres_host_profile import PostgresHostProfile
from agent_core.bootstrap_lease import BootstrapPasswordLease

MARKER = "SYNTHETIC:postgres://private-password"
LIMITS = dict(connect_timeout=5, options="-c statement_timeout=5000 -c lock_timeout=1000 "
              "-c idle_in_transaction_session_timeout=5000", autocommit=False, prepare_threshold=None)
BASE_EXPECTED = ("secret_test_host_a", "secret_test_host_a", "agent_checkpoint_ci",
                 False, "off", True, False, False, 5000, 1000, 5000,
                 "none", 0, "off", -1, -1)
EXPECTED = BASE_EXPECTED + (None, None, None)


class Connection:
    autocommit = False

    def __init__(self, row=EXPECTED, failure=None):
        self.row = row
        self.failure = failure
        self.calls = []
        self.fetches = 0

    def call(self, method):
        self.calls.append(method)
        if self.failure == method:
            raise RuntimeError(MARKER)

    def cursor(self):
        self.call("cursor")
        return self

    def execute(self, sql):
        self.call("execute")
        assert MARKER not in sql

    def fetchone(self):
        self.call("fetch")
        self.fetches += 1
        return self.row if self.fetches == 1 else None

    def commit(self):
        self.call("commit")

    def rollback(self):
        self.call("rollback")

    def close(self):
        self.call("close")


class FactoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.ca = Path(self.directory.name) / "ca.crt"
        self.ca.write_bytes(b"SYNTHETIC:CA")
        self.pin = sha256(self.ca.read_bytes()).hexdigest()
        self.profile = PostgresHostProfile("db.synthetic.invalid", "127.0.0.1", 5432,
                                           "agent_checkpoint_ci", "secret_test_host_a", str(self.ca))
        self.lease = BootstrapPasswordLease(self.profile.login, self.profile.database, 1, 200, MARKER)
        self.current_version = 1
        self.events = []
        self.connection = Connection()
        self.env = patch.dict(os.environ, {}, clear=True)
        self.files = patch("agent_core.postgres_host_factory.os.path.lexists", return_value=False)
        self.env.start()
        self.files.start()

    def tearDown(self):
        self.files.stop()
        self.env.stop()
        self.directory.cleanup()

    def source(self):
        self.events.append("source")
        return self.lease

    def connect(self, **kwargs):
        self.events.append("connect")
        self.kwargs = kwargs
        return self.connection

    def factory(self, source=None, connect=None, clock=lambda: 100):
        return StrictPostgresConnectionFactory(self.profile, driver_connect=connect or self.connect,
                                               password_source=source or self.source,
                                               lease_is_current=lambda version: version == self.current_version,
                                               trusted_ca_sha256=self.pin, clock=clock)

    def assert_safe(self, operation, expected=DurableSecretBackendUnavailable):
        try:
            operation()
        except BaseException as error:
            self.assertIs(type(error), expected)
            self.assertIsNone(error.__context__)
            self.assertIsNone(error.__cause__)
            self.assertNotIn(MARKER, "".join(traceback.format_exception(error)))
        else:
            self.fail("expected safe rejection")

    def test_inert_construction_and_verified_handoff(self):
        factory = self.factory()
        self.assertEqual(self.events, [])
        self.assertEqual(repr(factory), "StrictPostgresConnectionFactory(<redacted>)")
        self.assertIs(factory(**LIMITS), self.connection)
        self.assertEqual(self.events, ["source", "connect"])
        self.assertEqual(self.kwargs["sslmode"], "verify-full")
        self.assertEqual(self.kwargs["sslcertmode"], "disable")
        self.assertEqual(self.kwargs["require_auth"], "scram-sha-256")
        self.assertEqual(self.kwargs["passfile"], os.devnull)
        self.assertEqual(self.connection.calls, ["cursor", "execute", "fetch", "fetch", "close", "commit"])

    def test_ambient_configuration_rejected_before_secret_access(self):
        for key in ("PGHOST", "PGPASSWORD", "PGSERVICEFILE", "PGOPTIONS", "PGSSLMODE", "PGUNKNOWN",
                    "OPENSSL_CONF", "OPENSSL_MODULES", "SSL_CERT_FILE", "SSL_CERT_DIR"):
            with self.subTest(key=key), patch.dict(os.environ, {key: MARKER}):
                self.assert_safe(lambda: self.factory()(**LIMITS))
                self.assertEqual(self.events, [])
                self.assertEqual(os.environ[key], MARKER)

    def test_default_files_and_broken_symlinks_rejected(self):
        for name in (".pgpass", ".pg_service.conf", ".postgresql"):
            with patch("agent_core.postgres_host_factory.os.path.lexists", side_effect=lambda path: Path(path).name == name):
                self.assert_safe(lambda: self.factory()(**LIMITS))
                self.assertEqual(self.events, [])

    def test_limits_and_extra_options_cannot_override_profile(self):
        invalid = [dict(LIMITS, sslmode="disable"), dict(LIMITS, password=MARKER),
                   dict(LIMITS, connect_timeout=True), dict(LIMITS, connect_timeout=0),
                   dict(LIMITS, autocommit=True), dict(LIMITS, prepare_threshold=5),
                   dict(LIMITS, options=LIMITS["options"] + " -c role=postgres"),
                   dict(LIMITS, options="-c statement_timeout=0 -c lock_timeout=1 -c idle_in_transaction_session_timeout=0")]
        for limits in invalid:
            self.assert_safe(lambda: self.factory()(**limits))
            self.assertEqual(self.events, [])

    def test_each_identity_privilege_limit_and_core_logging_field_fails_closed(self):
        wrong = ("other", "other", "other", True, "on", False, True, True, 0, 0, 0,
                 "all", -1, "on", 0, 0)
        for index, value in enumerate(wrong):
            with self.subTest(index=index):
                row = list(EXPECTED)
                row[index] = value
                self.connection = Connection(tuple(row))
                self.assert_safe(lambda: self.factory()(**LIMITS))
                self.assertIn("rollback", self.connection.calls)
                self.assertIn("close", self.connection.calls)
                self.assertNotIn("commit", self.connection.calls)

    def test_extension_logging_policy_accepts_only_parameter_safe_states(self):
        safe = [
            (None, None, None),
            ("-1", "-1", None),
            ("-1", "-1", "off"),
            ("-1", "0", "off"),
            ("-1", "256", "off"),
        ]
        for extension_fields in safe:
            with self.subTest(extension_fields=extension_fields):
                self.connection = Connection(BASE_EXPECTED + extension_fields)
                self.assertIs(self.factory()(**LIMITS), self.connection)
        unsafe = [
            ("0", "0", "off"),
            ("10000", "0", "off"),
            ("-2", "0", "off"),
            ("-1", "-2", "off"),
            ("-1", "2147483648", "off"),
            ("10000", "-1", "off"),
            ("0", "256", "off"),
            ("bad", "0", "off"),
            (None, "0", "off"),
            ("-1", None, "off"),
            (None, None, "on"),
            ("-1", "-1", "on"),
        ]
        for extension_fields in unsafe:
            with self.subTest(extension_fields=extension_fields):
                self.connection = Connection(BASE_EXPECTED + extension_fields)
                self.assert_safe(lambda: self.factory()(**LIMITS))
                self.assertIn("rollback", self.connection.calls)
                self.assertIn("close", self.connection.calls)
                self.assertNotIn("commit", self.connection.calls)

    def test_malformed_rows_and_boolean_lookalikes(self):
        for row in (None, list(EXPECTED), EXPECTED[:-1], EXPECTED[:5] + (1,) + EXPECTED[6:]):
            self.connection = Connection(row)
            self.assert_safe(lambda: self.factory()(**LIMITS))
            self.assertNotIn("commit", self.connection.calls)

    def test_driver_faults_never_escape_or_retry(self):
        for stage in ("cursor", "execute", "fetch", "close", "commit"):
            self.events.clear()
            self.connection = Connection(failure=stage)
            self.assert_safe(lambda: self.factory()(**LIMITS))
            self.assertEqual(self.events, ["source", "connect"])
            self.assertIn("rollback", self.connection.calls)

    def test_password_failure_and_connection_failure_are_redacted(self):
        for password in (None, "", "x\x00x", "x" * 16385, 123):
            self.assert_safe(lambda: self.factory(source=lambda: password)(**LIMITS))
            self.assertNotIn("connect", self.events)
        def broken(**kwargs):
            raise RuntimeError(MARKER)
        self.assert_safe(lambda: self.factory(source=broken)(**LIMITS))
        self.assert_safe(lambda: self.factory(connect=broken)(**LIMITS))

    def test_interruptions_are_normalized(self):
        for cls in (KeyboardInterrupt, SystemExit):
            def broken():
                raise cls(MARKER)
            self.assert_safe(lambda: self.factory(source=broken)(**LIMITS), cls)

    def test_trust_replacement_rejected_before_source(self):
        self.ca.write_bytes(b"SYNTHETIC:changed")
        self.assert_safe(lambda: self.factory()(**LIMITS))
        self.assertEqual(self.events, [])

    def test_driver_reads_immutable_snapshot_not_replaced_path(self):
        seen = []
        def connect(**kwargs):
            self.ca.write_bytes(b"SYNTHETIC:changed")
            seen.append(Path(kwargs["sslrootcert"]).read_bytes())
            return self.connect(**kwargs)
        self.factory(connect=connect)(**LIMITS)
        self.assertEqual(seen, [b"SYNTHETIC:CA"])
        self.assertFalse(Path(self.kwargs["sslrootcert"]).exists())

    def test_invalid_expired_or_revoked_lease_never_connects(self):
        for field, value in (("version", True), ("version", -1), ("login", "other"),
                             ("database", "other"), ("expires_at", 100), ("password", "")):
            self.events.clear()
            self.assert_safe(lambda: self.factory(source=lambda: replace(self.lease, **{field: value}))(**LIMITS))
            self.assertNotIn("connect", self.events)
        self.current_version = 2
        self.assert_safe(lambda: self.factory()(**LIMITS))
        self.assertNotIn("connect", self.events)

    def test_rotation_during_connect_closes_without_retry(self):
        def connect(**kwargs):
            self.current_version = 2
            return self.connect(**kwargs)
        self.assert_safe(lambda: self.factory(connect=connect)(**LIMITS))
        self.assertEqual(self.events, ["source", "connect"])
        self.assertIn("rollback", self.connection.calls)

    def test_expiry_and_clock_rollback_during_connect(self):
        for times in ((100, 200), (100, 99)):
            clock = iter(times)
            self.connection = Connection()
            self.assert_safe(lambda: self.factory(clock=lambda: next(clock))(**LIMITS))
            self.assertIn("rollback", self.connection.calls)

    def test_new_connection_acquires_new_version_without_replay(self):
        factory = self.factory()
        factory(**LIMITS)
        self.connection = Connection()
        self.lease = replace(self.lease, version=2, password="SYNTHETIC:rotated")
        self.current_version = 2
        factory(**LIMITS)
        self.assertEqual(self.kwargs["password"], "SYNTHETIC:rotated")
        self.assertEqual(self.events, ["source", "connect"] * 2)
        self.assertNotIn(MARKER, repr(self.lease))


if __name__ == "__main__":
    unittest.main()
