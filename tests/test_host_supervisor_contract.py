"""Observer false-positive guards; Docker tree faults run in dedicated CI."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import host_supervisor_contract as supervisor


class SupervisorContractTests(unittest.TestCase):
    def test_requires_complete_tree_with_detached_grandchild(self):
        valid = "PID PPID PGID SID\n100 9 100 100\n101 100 100 100\n102 101 102 102\n"
        self.assertEqual(supervisor.tree_pids(valid, 100), [100, 101, 102])
        for wrong in (valid.replace("102 101 102 102", "102 101 100 100"),
                      valid.replace("101 100", "101 9"),
                      valid + "103 100 100 100\n", valid.replace("102 101 102 102\n", "")):
            with self.subTest(tree=wrong), self.assertRaises(RuntimeError):
                supervisor.tree_pids(wrong, 100)

    def test_real_pidfd_and_separate_reaping_evidence_are_both_required(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
        fd = os.pidfd_open(child.pid)
        observed = [(child.pid, "synthetic-start", fd)]
        try:
            # Some local runtimes virtualize process IDs without a matching /proc.
            # Exercise actual pidfds with controlled proc evidence here; Docker CI
            # must use real host /proc identities without mocks or a fallback.
            with patch.object(supervisor, "process_start", return_value="synthetic-start"):
                with self.assertRaisesRegex(RuntimeError, "synthetic_tree_not_reaped"):
                    supervisor.wait_reaped(observed, timeout=0.1)
                child.kill()
                with self.assertRaisesRegex(RuntimeError, "synthetic_tree_not_reaped"):
                    supervisor.wait_reaped(observed, timeout=0.2)
            child.wait(timeout=2)
            with patch.object(supervisor, "process_start", return_value=None):
                supervisor.wait_reaped(observed, timeout=1)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=2)
            os.close(fd)

    def test_empty_or_incomplete_cgroup_evidence_is_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            group = Path(directory)
            with self.assertRaisesRegex(RuntimeError, "synthetic_tree_cgroup_evidence_missing"):
                supervisor.require_empty_cgroup(group)
            (group / "cgroup.events").write_text("populated 1\n")
            (group / "cgroup.procs").write_text("123\n")
            with self.assertRaisesRegex(RuntimeError, "synthetic_tree_cgroup_populated"):
                supervisor.require_empty_cgroup(group)
            (group / "cgroup.events").write_text("populated 0\n")
            with self.assertRaisesRegex(RuntimeError, "synthetic_tree_cgroup_populated"):
                supervisor.require_empty_cgroup(group)
            (group / "cgroup.procs").write_text("")
            supervisor.require_empty_cgroup(group)
        supervisor.require_empty_cgroup(group)
        with self.assertRaisesRegex(RuntimeError, "synthetic_tree_identity_missing"):
            supervisor.wait_reaped([])

    def test_prestart_failure_still_removes_only_fixture_container(self):
        # A failed pre-start inspect must still clean up only its own fixture.
        calls = []

        def command(args, timeout=45):
            calls.append(args)
            if args[1] == "inspect":
                raise RuntimeError("synthetic_inspect_failure")
            return ""

        with patch.object(supervisor, "command", side_effect=command):
            with self.assertRaisesRegex(RuntimeError, "synthetic_inspect_failure"):
                supervisor.run_supervisor_probe("sha256:" + "a" * 64, "crash")
        name = calls[0][3]
        self.assertTrue(name.startswith("synthetic-supervisor-"))
        self.assertEqual(calls[-2], ["docker", "rm", "--force", name])
        self.assertEqual(calls[-1][-1], "name=^/" + name + "$")


if __name__ == "__main__":
    unittest.main()
