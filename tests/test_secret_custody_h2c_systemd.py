"""Real no-secret memory probe, using the owned disposable H2b CI fixture."""
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


base = load("h2c_tests", "tests/test_secret_custody_h2c.py")
fixture = load("h2c_fixture", "tests/test_secret_custody_h2b_systemd.py")


class RealMemoryTests(fixture.RealSystemdTests):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("H2C_CI_FIXTURE") != "1":
            raise RuntimeError("H2c fixture opt-in required")
        super().setUpClass()

    def runner(self):
        r, self.controller = base.runner()
        r.host = self.host
        r.package = self.package
        return r

    def test_actual_sandbox_and_controller_readback(self):
        r = self.runner()
        before = base.h2c.run_identity()
        self.assertEqual(r.run(base.h2c.APPROVE), ["PASS " + k for k in self.controller.CHECKS])
        self.assertEqual(base.h2c.run_identity(), before)
        self.assert_clean(r)

    def test_failed_child_is_redacted_and_collected(self):
        r = self.runner()
        with patch.object(self.controller, "PROBE", "import sys; print('private-test-material'); sys.exit(7)"):
            with self.assertRaisesRegex(self.controller.Stop, "^PROBE_EXECUTION_FAILED$"):
                r.run(base.h2c.APPROVE)
        self.assert_clean(r)

    def test_manager_deadline_terminates_child_and_collects_unit(self):
        r = self.runner()
        original = self.controller.properties
        def shorter(h2):
            return ["RuntimeMaxSec=1s" if p.startswith("RuntimeMaxSec=") else p for p in original(h2)]
        started = time.monotonic()
        with patch.object(self.controller, "PROBE", "import time; time.sleep(60)"), \
                patch.object(self.controller, "properties", shorter):
            with self.assertRaisesRegex(self.controller.Stop, "^PROBE_EXECUTION_FAILED$"):
                r.run(base.h2c.APPROVE)
        self.assertLess(time.monotonic() - started, 15)
        self.assert_clean(r)

    def test_corrupted_memory_record_is_rejected_without_leak(self):
        r = self.runner()
        original = self.controller.PROBE
        corrupt = original.replace("record = payload + hashlib.sha256(payload).digest()",
                                   "record = payload + bytes(32)")
        self.assertNotEqual(corrupt, original)
        with patch.object(self.controller, "PROBE", corrupt):
            with self.assertRaisesRegex(self.controller.Stop, "^PROBE_MEMFD_HANDOFF_FAILED$"):
                r.run(base.h2c.APPROVE)
        self.assert_clean(r)

    def test_unsealed_descriptor_is_rejected_by_executable_child(self):
        r = self.runner()
        # Reach the real child with the seal-add and parent seal-readback guard
        # fault-injected only in this CI case. The child must independently fail.
        original = self.controller.PROBE
        unsealed = original.replace("fcntl.fcntl(fd, fcntl.F_ADD_SEALS, seals)", "pass")
        unsealed = unsealed.replace("check(fcntl.fcntl(fd, fcntl.F_GET_SEALS) & seals == seals",
                                    "check(True")
        self.assertNotEqual(unsealed, original)
        with patch.object(self.controller, "PROBE", unsealed):
            with self.assertRaisesRegex(self.controller.Stop, "^PROBE_MEMFD_HANDOFF_FAILED$"):
                r.run(base.h2c.APPROVE)
        self.assert_clean(r)


if __name__ == "__main__":
    unittest.main(verbosity=2)
