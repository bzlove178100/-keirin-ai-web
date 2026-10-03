"""Offline boundaries for the fixed H2d fault probe; no host mutations."""
from contextlib import redirect_stdout
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("h2d", ROOT / "review/secret_custody_h2d.py")
h2d = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(h2d)
SOURCES = [(ROOT / ("review/secret_custody_" + name + ".py")).read_bytes()
           for name in ("h2", "h2b", "h2c")]
BUNDLE = h2d.SEPARATOR.join(part[:-1] for part in SOURCES) + b"\n"


def runner():
    h2, controller, memory = h2d.load_validators(BUNDLE)
    return h2d.make_runner(h2, controller, memory), h2, controller, memory


class FailureTests(unittest.TestCase):
    def test_all_three_sources_are_checked_before_execution(self):
        for i in range(3):
            parts = SOURCES.copy()
            parts[i] += b"# tamper\n"
            data = h2d.SEPARATOR.join(part[:-1] for part in parts) + b"\n"
            with patch("builtins.exec") as execute:
                with self.assertRaisesRegex(h2d.Stop, "H2D_VALIDATOR_HASH_MISMATCH"):
                    h2d.load_validators(data)
                execute.assert_not_called()
        for data in (b"", BUNDLE + h2d.SEPARATOR, b"x" * 196608):
            with self.assertRaisesRegex(h2d.Stop, "H2D_VALIDATOR_BUNDLE_INVALID"):
                h2d.load_validators(data)

    def test_profile_is_preserved_with_only_tighter_stop_and_runtime(self):
        r, h2, control, memory = runner()
        with patch.object(r.host, "user", return_value={"uid": 991, "gid": 992}):
            args = r.args()
        self.assertNotIn("--collect", args)
        for prop in control.properties(h2):
            expected = {"RuntimeMaxSec=10s": "RuntimeMaxSec=6s",
                        "TimeoutStopSec=10s": "TimeoutStopSec=1s"}.get(prop, prop)
            self.assertIn("--property=" + expected, args)
        self.assertIn("--property=TemporaryFileSystem=/run:rw,size=1048576,nr_inodes=128,mode=0700,"
                      "nosuid,nodev,noexec,noswap,uid=991,gid=992", args)
        self.assertEqual(args[args.index("-c") + 1], h2d.PROBE)
        self.assertIn("RefuseManualStart=yes", h2.UNIT)
        self.assertEqual(control.PROBE, h2d.PROBE)

    def test_acknowledgement_precedes_host_actions(self):
        with patch.object(h2d, "make_runner") as make:
            with self.assertRaisesRegex(h2d.Stop, "H2D_ACKNOWLEDGEMENT_REQUIRED"):
                h2d.run(None, None, None, "")
            make.assert_not_called()

    def test_ready_accepts_only_exact_bounded_record(self):
        for data, valid in ((b"READY 11 12\n", True), (b"private\n", False),
                            (b"READY 11 11\n", False), (b"READY 0 12\n", False),
                            (b"READY 11 12\nextra", False), (b"x" * 80, False),
                            (b"READY 11", False)):
            read, write = os.pipe()
            os.write(write, data)
            os.close(write)
            with os.fdopen(read, "rb") as stream:
                if valid:
                    self.assertEqual(h2d.ready(stream), (11, 12))
                else:
                    with self.assertRaises(h2d.Stop):
                        h2d.ready(stream)

    def test_partial_live_pipe_times_out_without_blocking_readline(self):
        read, write = os.pipe()
        os.write(write, b"READY")
        try:
            with os.fdopen(read, "rb") as stream, patch.object(h2d.time, "monotonic", side_effect=[0, 6]):
                with self.assertRaisesRegex(h2d.Stop, "PROCESS_TREE_NOT_READY"):
                    h2d.ready(stream)
        finally:
            os.close(write)

    def test_zombies_and_live_processes_are_not_cleaned_up(self):
        cases = (([], None, False), ([31], ("Z", 1, 100), False),
                 ([31], ("S", 1, 100), False), ([31], None, True), ([31], ("S", 1, 101), True))
        for ready, entry, expected in cases:
            with patch.object(h2d.select, "select", return_value=(ready, [], [])), \
                    patch.object(h2d, "proc_stat", return_value=entry):
                self.assertEqual(h2d.reaped([(20, 100, 31)]), expected)

    def test_identity_failure_closes_opened_pidfd(self):
        with patch.object(h2d.os, "pidfd_open", return_value=41), \
                patch.object(h2d.os, "close") as close, \
                patch.object(h2d, "proc_stat", return_value=None):
            with self.assertRaisesRegex(h2d.Stop, "PROCESS_IDENTITY_UNPROVEN"):
                h2d.observe_processes((11, 12), "unit", {"uid": 991, "gid": 992})
            close.assert_called_once_with(41)

    def test_foreign_name_is_never_started_or_stopped(self):
        r, _, _, _ = runner()
        with patch.object(r, "state", return_value={"LoadState": "loaded"}), \
                patch.object(r, "cleanup") as cleanup, patch.object(h2d.subprocess, "Popen") as spawn:
            with self.assertRaisesRegex(h2d.Stop, "PROBE_NAME_COLLISION"):
                r.case("parent")
            cleanup.assert_not_called()
            spawn.assert_not_called()

    def test_cleanup_never_resets_an_unowned_unit(self):
        r, _, control, _ = runner()
        with patch.object(r, "state", return_value={"LoadState": "loaded", "Transient": "yes",
                                                    "Description": "unrelated"}), \
                patch.object(r, "command") as command:
            with self.assertRaisesRegex(control.Stop, "PROBE_OWNERSHIP_UNPROVEN"):
                r.cleanup()
            command.assert_not_called()

    def test_wrong_manager_result_is_not_success(self):
        r, _, _, _ = runner()
        state = dict(LoadState="loaded", ActiveState="failed", Transient="yes",
                     Description=r.description, Result="exit-code", NRestarts="0")
        with patch.object(r, "state", return_value=state):
            with self.assertRaisesRegex(h2d.Stop, "MANAGER_FAILURE_REASON_UNPROVEN"):
                r.wait_failure("timeout", [])

    def test_reset_error_requires_verified_absence_and_complete_cleanup(self):
        for disappeared in (False, True):
            r, _, _, _ = runner()
            owned = dict(LoadState="loaded", Transient="yes", Description=r.description)
            absent = {"LoadState": "not-found"}
            states = [owned, owned, absent if disappeared else owned]
            if disappeared:
                states += [absent, absent]
            with patch.object(r, "state", side_effect=states), \
                    patch.object(r, "command", side_effect=[subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 1)]) as command, \
                    patch.object(r, "no_temporary_dirs", return_value=True) as directories, \
                    patch.object(h2d.Path, "exists", return_value=False) as cgroup:
                if disappeared:
                    r.cleanup()
                    directories.assert_called_once()
                    cgroup.assert_called_once()
                else:
                    with self.assertRaisesRegex(h2d.Stop, "^PROCESS_RESET_FAILED$"):
                        r.cleanup()
                    directories.assert_not_called()
                self.assertEqual([call.args[0][1] for call in command.call_args_list], ["stop", "reset-failed"])

    def test_disappeared_unit_with_remaining_cgroup_still_fails(self):
        r, _, _, _ = runner()
        owned = dict(LoadState="loaded", Transient="yes", Description=r.description)
        absent = {"LoadState": "not-found"}
        with patch.object(r, "state", side_effect=[owned, owned, absent, absent, absent]), \
                patch.object(r, "command", side_effect=[subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 1)]), \
                patch.object(r, "no_temporary_dirs", return_value=True), \
                patch.object(h2d.Path, "exists", return_value=True):
            with self.assertRaisesRegex(h2d.Stop, "^PROCESS_CGROUP_REMAINS$"):
                r.cleanup()

    def test_fallback_cleanup_does_not_hide_failure(self):
        r, _, _, _ = runner()
        fake = MagicMock()
        fake.poll.return_value = 1
        with patch.object(r, "state", return_value={"LoadState": "not-found"}), \
                patch.object(r, "args", return_value=[]), \
                patch.object(h2d.subprocess, "Popen", return_value=fake), \
                patch.object(h2d, "ready", side_effect=h2d.Stop("PROCESS_TREE_NOT_READY")), \
                patch.object(r, "cleanup") as cleanup:
            with self.assertRaisesRegex(h2d.Stop, "PROCESS_TREE_NOT_READY"):
                r.case("parent")
            cleanup.assert_called_once()
            fake.stdout.close.assert_called_once()

    def test_inspect_and_unknown_error_output(self):
        r = MagicMock()
        source = MagicMock(buffer=io.BytesIO(BUNDLE))
        output = io.StringIO()
        with patch.object(h2d.sys, "stdin", source), patch.object(h2d, "make_runner", return_value=r), \
                redirect_stdout(output):
            self.assertEqual(h2d.main([]), 0)
        r.inspect.assert_called_once()
        r.case.assert_not_called()
        self.assertEqual(output.getvalue(), "RESULT H2D_PROCESS_PROBE_READY_NO_MUTATION\n")
        output = io.StringIO()
        with patch.object(h2d.sys, "stdin", MagicMock(buffer=io.BytesIO(BUNDLE))), \
                patch.object(h2d, "run", side_effect=RuntimeError("private-material")), redirect_stdout(output):
            self.assertEqual(h2d.main(["run", "--approve", h2d.APPROVE]), 1)
        self.assertEqual(output.getvalue(), "STOP H2D_STATE_UNREADABLE\n"
                         "RESULT NO_RUNTIME_AUTHORIZED_DO_NOT_RETRY_PROBE\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
