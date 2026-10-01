"""Real systemd 255 synthetic probe on an explicitly opted-in disposable CI VM.

Creates the H2a fixture via its real account/files/manager adapter and removes
only that owned fixture afterwards. The CI host's global swap precondition is
synthetic; no global swap setting is changed. The probe still checks its real
cgroup memory.swap.max=0. Production retains the full no-swap precondition.
"""
from contextlib import redirect_stdout
import importlib.util
import io
import os
from pathlib import Path
import stat
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("h2b_tests", ROOT / "tests/test_secret_custody_h2b.py")
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)
h2, h2b = base.h2, base.h2b


class NoSwapFixture:
    def read_text(self):
        return "Filename Type Size Used Priority\n"


class CIHost(h2.Host):
    def path(self, path):
        return NoSwapFixture() if path == "/proc/swaps" else super().path(path)


class RealSystemdTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("H2B_CI_FIXTURE") != "1" or os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("Only explicitly opted-in disposable GitHub CI may run this fixture")
        # Hosted build images may make /opt developer-writable. Tighten only
        # these parent directory entries for this disposable fixture, preserving
        # their exact metadata for restoration. Do not bypass H2a's real guard.
        cls.parents = []
        cls.addClassCleanup(cls.restore_parents)
        for name in h2.PARENTS:
            p = Path(name)
            s = p.lstat()
            if not stat.S_ISDIR(s.st_mode):
                raise RuntimeError("CI parent must be a real directory")
            if s.st_uid != 0 or s.st_mode & 0o022:
                cls.parents.append((p, s))
                print("CI fixture tightens parent: " + name, flush=True)
                os.chown(p, 0, 0)
                p.chmod(stat.S_IMODE(s.st_mode) & ~0o022)
        cls.host = CIHost()
        cls.package = h2.Package(cls.host)
        cls.package.fresh()  # Never adopt a pre-existing account/service/receipt.
        cls.addClassCleanup(cls.cleanup_fixture)
        cls.package.apply(h2.APPROVE)

    @classmethod
    def cleanup_fixture(cls):
        if os.path.lexists(h2.STATE):
            cls.package.rollback(h2.UNDO)

    @classmethod
    def restore_parents(cls):
        for p, previous in reversed(cls.parents):
            current = p.lstat()
            if (current.st_dev, current.st_ino) != (previous.st_dev, previous.st_ino):
                raise RuntimeError("CI parent replaced; metadata restoration refused")
            os.chown(p, previous.st_uid, previous.st_gid)
            p.chmod(stat.S_IMODE(previous.st_mode))

    def runner(self):
        runner = h2b.Runner(h2)
        runner.host = self.host
        runner.package = self.package
        return runner

    def assert_clean(self, runner):
        self.assertEqual(runner.state()["LoadState"], "not-found")
        self.assertTrue(runner.no_temporary_dirs())
        self.assertEqual(self.package.verify(), "INSTALLED_DISABLED_NOT_QUALIFIED")

    def test_actual_sandbox_and_controller_readback(self):
        runner = self.runner()
        self.assertEqual(runner.run(h2b.APPROVE), ["PASS " + k for k in h2b.CHECKS])
        self.assert_clean(runner)

    def test_failed_child_is_redacted_and_collected(self):
        runner = self.runner()
        with patch.object(h2b, "PROBE", "import sys; print('private-synthetic-error'); sys.exit(7)"):
            with self.assertRaisesRegex(h2b.Stop, "^PROBE_EXECUTION_FAILED$"):
                runner.run(h2b.APPROVE)
        self.assert_clean(runner)

    def test_manager_deadline_terminates_child_and_collects_unit(self):
        runner = self.runner()
        original = h2b.properties
        def shorter(h2):
            return ["RuntimeMaxSec=1s" if p.startswith("RuntimeMaxSec=") else p for p in original(h2)]
        started = time.monotonic()
        with patch.object(h2b, "PROBE", "import time; time.sleep(60)"), \
                patch.object(h2b, "properties", shorter):
            with self.assertRaisesRegex(h2b.Stop, "^PROBE_EXECUTION_FAILED$"):
                runner.run(h2b.APPROVE)
        self.assertLess(time.monotonic() - started, 15)
        self.assert_clean(runner)


if __name__ == "__main__":
    unittest.main(verbosity=2)
