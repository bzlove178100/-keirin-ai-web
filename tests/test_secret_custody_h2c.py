"""Offline H2c trust, evidence and unchanged-host contracts."""
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("h2c", ROOT / "review/secret_custody_h2c.py")
h2c = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(h2c)
A = (ROOT / "review/secret_custody_h2.py").read_bytes()
B = (ROOT / "review/secret_custody_h2b.py").read_bytes()
BUNDLE = A.rstrip(b"\n") + h2c.SEPARATOR + B


def runner():
    h2, controller = h2c.load_validators(BUNDLE)
    return h2c.make_runner(h2, controller), controller


class MemoryContractTests(unittest.TestCase):
    def test_both_sources_verified_before_any_exec(self):
        for data in (BUNDLE.replace(b"import argparse", b"import builtins", 1),
                     BUNDLE + b"\nraise RuntimeError()", BUNDLE[:80],
                     BUNDLE + h2c.SEPARATOR, b"x" * 131072):
            with self.subTest(size=len(data)), patch("builtins.exec") as execute:
                with self.assertRaises(h2c.Stop):
                    h2c.load_validators(data)
                execute.assert_not_called()

    def test_exact_sources_load_and_fixed_module_is_private(self):
        r1, c1 = runner()
        r2, c2 = runner()
        self.assertIsNot(c1, c2)
        self.assertEqual(len(c1.CHECKS), 20)
        self.assertEqual(c1.CHECKS, c2.CHECKS)
        self.assertNotEqual(r1.unit, r2.unit)
        self.assertTrue(r1.unit.startswith("keirin-custody-h2c-"))

    def test_tmpfs_added_without_relaxing_existing_profile(self):
        r, c = runner()
        r.host = Mock()
        r.host.user.return_value = {"uid": 987, "gid": 987}
        args = r.args()
        props = [a[len("--property="):] for a in args if a.startswith("--property=")]
        self.assertEqual(props[:-1], c.properties(r.h2))
        self.assertEqual(props[-1], "TemporaryFileSystem=/run:rw,size=1048576,nr_inodes=128,mode=0700,"
                         "nosuid,nodev,noexec,noswap,uid=987,gid=987")
        self.assertIn("RuntimeMaxSec=10s", props)
        self.assertIn("MemorySwapMax=0", props)
        self.assertIn("KillMode=control-group", props)
        self.assertIn("--collect", args)
        self.assertIn("--pipe", args)
        self.assertIn(c.PROBE, args)

    def test_acknowledgement_precedes_host_operations(self):
        r, c = runner()
        with patch.object(c.Runner, "run") as execute, patch.object(h2c, "run_identity") as observe:
            with self.assertRaisesRegex(h2c.Stop, "H2C_ACKNOWLEDGEMENT_REQUIRED"):
                r.run("")
            execute.assert_not_called()
            observe.assert_not_called()

    def test_host_run_drift_rejected_even_after_service_success(self):
        r, c = runner()
        with patch.object(h2c, "run_identity", side_effect=[("before",), ("after",)]), \
                patch.object(c.Runner, "run", return_value=["PASS"]):
            with self.assertRaisesRegex(h2c.Stop, "HOST_RUN_MOUNT_CHANGED"):
                r.run(h2c.APPROVE)

    def test_inner_failure_preserved_when_host_is_unchanged(self):
        r, c = runner()
        with patch.object(h2c, "run_identity", return_value=("same",)) as observe, \
                patch.object(c.Runner, "run", side_effect=c.Stop("PROBE_MEMFD_HANDOFF_FAILED")):
            with self.assertRaisesRegex(c.Stop, "^PROBE_MEMFD_HANDOFF_FAILED$"):
                r.run(h2c.APPROVE)
            self.assertEqual(observe.call_count, 2)

    def test_new_evidence_is_required_in_exact_order(self):
        _, c = runner()
        lines = ["PASS " + k for k in c.CHECKS]
        self.assertEqual(c.validate_output("\n".join(lines).encode(), 0), lines)
        for data in (lines[:13], lines[:-1], lines + [lines[-1]], list(reversed(lines))):
            with self.assertRaises(c.Stop):
                c.validate_output("\n".join(data).encode(), 0)
        prefix = lines[:c.CHECKS.index("MEMFD_HANDOFF")]
        with self.assertRaisesRegex(c.Stop, "^PROBE_MEMFD_HANDOFF_FAILED$"):
            c.validate_output("\n".join(prefix + ["FAIL MEMFD_HANDOFF"]).encode(), 1)

    def test_unexpected_child_text_is_redacted(self):
        _, c = runner()
        with self.assertRaisesRegex(c.Stop, "^PROBE_EXECUTION_FAILED$"):
            c.validate_output(b"private-test-material\n", 1)

    def test_default_is_readonly_inspection(self):
        r = Mock()
        out = io.StringIO()
        with patch.object(h2c.sys, "stdin", Mock(buffer=io.BytesIO(BUNDLE))), \
                patch.object(h2c, "make_runner", return_value=r), redirect_stdout(out):
            self.assertEqual(h2c.main([]), 0)
        r.inspect.assert_called_once_with()
        r.run.assert_not_called()
        self.assertEqual(out.getvalue(), "RESULT H2C_MEMORY_PROBE_READY_NO_MUTATION\n")

    def test_main_redacts_unknown_errors(self):
        out = io.StringIO()
        with patch.object(h2c.sys, "stdin", Mock(buffer=io.BytesIO(BUNDLE))), \
                patch.object(h2c, "make_runner", side_effect=OSError("private-test-material")), redirect_stdout(out):
            self.assertEqual(h2c.main([]), 1)
        self.assertEqual(out.getvalue(), "STOP H2C_STATE_UNREADABLE\n"
                         "RESULT NO_RUNTIME_AUTHORIZED_DO_NOT_RETRY_PROBE\n")


if __name__ == "__main__":
    unittest.main()
