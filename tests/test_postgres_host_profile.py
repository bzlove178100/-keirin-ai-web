from dataclasses import replace
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_core.postgres_host_profile import PostgresHostProfile


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.profile = PostgresHostProfile("db.synthetic.invalid", "127.0.0.1", 5432,
                                           "agent_checkpoint_ci", "secret_test_host_a", "/tmp/synthetic-ca.crt")

    def test_fixed_tls_policy_and_no_secret(self):
        options = self.profile.connection_parameters()
        self.assertEqual(options["sslmode"], "verify-full")
        self.assertEqual(options["gssencmode"], "disable")
        self.assertEqual(options["target_session_attrs"], "read-write")
        self.assertNotIn("password", options)
        self.assertNotIn("service", options)
        self.assertEqual(repr(self.profile), "PostgresHostProfile(<redacted>)")
        options["sslmode"] = "disable"
        self.assertEqual(self.profile.connection_parameters()["sslmode"], "verify-full")

    def test_reject_destinations_and_identity_injection(self):
        for field, values in {
            "hostname": ["localhost", "/tmp", "a.invalid,b.invalid", "db.invalid sslmode=disable", "DB.invalid", "a..invalid", "-a.invalid"],
            "host_address": ["127.0.0.1,127.0.0.2", "localhost", "/tmp", "127.0.0.1 sslmode=disable"],
            "port": [True, 0, 65536, "5432"],
            "database": ["postgres://SYNTHETIC:private", "db user=postgres", ""],
            "login": ["postgres", "service_role", "supabase_admin", "authenticator", "anon", "authenticated", "x password=SYNTHETIC:private"],
            "root_certificate": ["system", "relative.crt", "/tmp/../ca.crt", "/tmp//ca.crt", "/tmp/ca\x00.crt", "/"],
        }.items():
            for value in values:
                with self.subTest(field=field), self.assertRaisesRegex(ValueError, "^postgres_host_profile_invalid$") as caught:
                    replace(self.profile, **{field: value})
                self.assertIsNone(caught.exception.__context__)

    def test_canonical_ipv6_and_explicit_ca_path(self):
        self.assertEqual(replace(self.profile, host_address="::1").connection_parameters()["hostaddr"], "::1")


if __name__ == "__main__":
    unittest.main()
