"""Offline H2b failure, output and cleanup contracts; no real service actions."""
from contextlib import nullcontext, redirect_stdout
import importlib.util
import io
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("h2b", ROOT / "review/secret_custody_h2b.py")
h2b = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(h2b)
SOURCE = (ROOT / "review/secret_custody_h2.py").read_bytes()
h2 = h2b.load_h2(SOURCE)


class ProbeTests(unittest.TestCase):
    def runner(self):
        r = h2b.Runner(h2)
        r.package = Mock()
        r.package.lock.side_effect = nullcontext
        r.command = Mock()
        return r

    def test_validator_tampering_rejected_before_exec(self):
        with self.assertRaisesRegex(h2b.Stop, "H2A_VALIDATOR_HASH_MISMATCH"):
            h2b.load_h2(SOURCE + b"\nraise RuntimeError('must not execute')")

    def test_profile_keeps_all_security_settings_and_bounds_runtime(self):
        values = dict(p.split("=", 1) for p in h2b.properties(h2))
        self.assertEqual(values["User"], "keirin-custody")
        self.assertEqual(values["Group"], "keirin-custody")
        self.assertEqual(values["PrivateNetwork"], "yes")
        self.assertEqual(values["RestrictAddressFamilies"], "AF_UNIX")
        self.assertEqual(values["CapabilityBoundingSet"], "")
        self.assertEqual(values["MemoryMax"], "128M")
        self.assertEqual(values["Type"], "exec")
        self.assertEqual(values["RuntimeMaxSec"], "10s")
        self.assertEqual(values["KillMode"], "control-group")
        self.assertNotIn("ExecStart", values)
        self.assertNotIn("RefuseManualStart", values)

    def test_missing_duplicate_reordered_and_unknown_proofs_rejected(self):
        valid = ["PASS " + k for k in h2b.CHECKS]
        self.assertEqual(h2b.validate_output(("\n".join(valid) + "\n").encode(), 0), valid)
        for lines in (valid[:-1], valid + [valid[-1]], list(reversed(valid)), valid + ["secret"]):
            with self.subTest(lines=len(lines)), self.assertRaises(h2b.Stop):
                h2b.validate_output("\n".join(lines).encode(), 0)

    def test_only_fixed_failure_codes_are_returned(self):
        with self.assertRaisesRegex(h2b.Stop, "^PROBE_IDENTITY_FAILED$"):
            h2b.validate_output(b"FAIL IDENTITY\n", 1)
        with self.assertRaisesRegex(h2b.Stop, "^PROBE_EXECUTION_FAILED$"):
            h2b.validate_output(b"FAIL private-secret-value\n", 1)

    def test_acknowledgement_precedes_host_operations(self):
        r = self.runner()
        with self.assertRaisesRegex(h2b.Stop, "ACKNOWLEDGEMENT_REQUIRED"):
            r.run("")
        r.package.verify.assert_not_called()
        r.command.assert_not_called()

    def test_name_collision_never_stops_existing_unit(self):
        r = self.runner()
        r.inspect = Mock()
        r.state = Mock(return_value={"LoadState": "loaded"})
        r.cleanup = Mock()
        with self.assertRaisesRegex(h2b.Stop, "PROBE_NAME_COLLISION"):
            r.run(h2b.APPROVE)
        r.cleanup.assert_not_called()
        r.command.assert_not_called()

    def test_failure_and_timeout_clean_up_and_reverify(self):
        for failure in (h2b.Stop("PROBE_COMMAND_UNAVAILABLE"), h2b.Stop("PROBE_INTERRUPTED")):
            r = self.runner()
            r.inspect = Mock()
            r.state = Mock(return_value={"LoadState": "not-found"})
            r.args = Mock(return_value=["fixed-test-command"])
            r.command.side_effect = failure
            r.cleanup = Mock()
            with self.assertRaises(h2b.Stop):
                r.run(h2b.APPROVE)
            r.cleanup.assert_called_once()
            self.assertEqual(r.package.verify.call_count, 2)

    def test_cleanup_refuses_foreign_unit(self):
        r = self.runner()
        r.state = Mock(return_value={"LoadState": "loaded", "Transient": "yes", "Description": "other"})
        with self.assertRaisesRegex(h2b.Stop, "PROBE_OWNERSHIP_UNPROVEN"):
            r.cleanup()
        r.command.assert_not_called()

    def test_cleanup_stops_only_own_transient_unit(self):
        r = self.runner()
        r.state = Mock(side_effect=[{"LoadState": "loaded", "Transient": "yes", "Description": r.description},
                                   {"LoadState": "not-found"}])
        r.command.return_value = subprocess.CompletedProcess([], 0, b"")
        r.no_temporary_dirs = Mock(return_value=True)
        r.cleanup()
        r.command.assert_called_once_with(["/usr/bin/systemctl", "stop", r.unit], timeout=15)

    def test_cleanup_residue_is_not_success(self):
        r = self.runner()
        r.state = Mock(return_value={"LoadState": "not-found"})
        r.no_temporary_dirs = Mock(return_value=False)
        with patch.object(h2b.time, "sleep"), self.assertRaisesRegex(h2b.Stop, "PROBE_CLEANUP_UNCONFIRMED"):
            r.cleanup()

    def test_main_redacts_unexpected_errors(self):
        out = io.StringIO()
        with patch.object(h2b.sys, "stdin", Mock(buffer=io.BytesIO(SOURCE))), \
                patch.object(h2b.Runner, "inspect", side_effect=OSError("private-error")), redirect_stdout(out):
            self.assertEqual(h2b.main([]), 1)
        self.assertEqual(out.getvalue(), "STOP H2B_STATE_UNREADABLE\n"
                         "RESULT NO_RUNTIME_AUTHORIZED_DO_NOT_RETRY_PROBE\n")


if __name__ == "__main__":
    unittest.main()
