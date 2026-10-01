"""Real process deaths on the explicitly opted-in disposable systemd CI VM."""
import importlib.util
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load("h2d_tests", "tests/test_secret_custody_h2d.py")
fixture = load("h2d_fixture", "tests/test_secret_custody_h2b_systemd.py")
h2d = base.h2d


class RealFailureTests(unittest.TestCase):
    # Reuse fixture setup, not its unrelated H2b test methods.
    cleanup_fixture = classmethod(fixture.RealSystemdTests.cleanup_fixture.__func__)
    restore_parents = classmethod(fixture.RealSystemdTests.restore_parents.__func__)
    assert_clean = fixture.RealSystemdTests.assert_clean

    @classmethod
    def setUpClass(cls):
        if os.environ.get("H2D_CI_FIXTURE") != "1":
            raise RuntimeError("H2d fixture opt-in required")
        fixture.RealSystemdTests.setUpClass.__func__(cls)

    def runner(self):
        r, h2, control, memory = base.runner()
        r.host, r.package = self.host, self.package
        return r, h2, control, memory

    def test_both_real_failures_reap_tree_then_collect_without_restarting(self):
        r, h2, control, memory = self.runner()
        before = memory.run_identity()
        started = time.monotonic()
        with patch.object(h2d, "make_runner", return_value=r):
            self.assertEqual(h2d.run(h2, control, memory, h2d.APPROVE),
                             ["PASS " + key for key in h2d.CHECKS])
        self.assertLess(time.monotonic() - started, 25)
        self.assertEqual(memory.run_identity(), before)
        self.assert_clean(r)

    def test_unexpected_output_is_redacted_and_owned_service_cleaned_up(self):
        r, _, control, _ = self.runner()
        with patch.object(control, "PROBE", "import time; print('private-error', flush=True); time.sleep(60)"):
            with self.assertRaisesRegex(h2d.Stop, "^PROCESS_EVIDENCE_INVALID$"):
                r.case("parent")
        self.assert_clean(r)

    def test_child_rejects_corrupted_record_before_readiness(self):
        r, _, control, _ = self.runner()
        bad = h2d.PROBE.replace("record = payload + hashlib.sha256(payload).digest()",
                               "record = payload + bytes(32)")
        self.assertNotEqual(bad, h2d.PROBE)
        with patch.object(control, "PROBE", bad):
            with self.assertRaisesRegex(h2d.Stop, "^PROCESS_TREE_NOT_READY$"):
                r.case("parent")
        self.assert_clean(r)

    def test_failed_manager_assertion_cannot_be_rescued_by_fallback_cleanup(self):
        r, _, _, _ = self.runner()
        real_wait = r.wait_failure
        with patch.object(r, "wait_failure", side_effect=lambda expected, observed: real_wait("timeout", observed)):
            with self.assertRaisesRegex(h2d.Stop, "^MANAGER_FAILURE_REASON_UNPROVEN$"):
                r.case("parent")
        self.assert_clean(r)


if __name__ == "__main__":
    if os.environ.get("H2D_CI_FIXTURE") != "1":
        raise RuntimeError("H2d fixture opt-in required before host setup")
    unittest.main(verbosity=2)
