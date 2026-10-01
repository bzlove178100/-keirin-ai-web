"""Offline H2a transactions: real temporary files, synthetic accounts/systemd.

Run as root ONLY so ownership/mode checks use real stat data. All account,
process and systemd mutations are replaced by FakeHost; no host user is made.
"""
from contextlib import redirect_stdout
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("h2", ROOT / "review/secret_custody_h2.py")
h2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(h2)


class FakeHost(h2.Host):
    def __init__(self, root):
        self.root = root
        self.account = None
        self.account_group = None
        self.actions = []
        self.failure = None
        self.active_process = False
        self.unit_state = {"LoadState": "not-found", "ActiveState": "inactive",
                           "UnitFileState": "", "FragmentPath": "", "DropInPaths": ""}
        for path in h2.PARENTS:
            self.path(path).mkdir(parents=True, exist_ok=True)
            self.path(path).chmod(0o755)

    def path(self, path):
        return self.root / path.lstrip("/")

    def run(self, *args):
        raise AssertionError("real host command attempted")

    def platform(self):
        if self.failure == "platform":
            raise h2.Stop("UNREVIEWED_OS")

    def user(self):
        return copy.deepcopy(self.account)

    def group(self):
        return copy.deepcopy(self.account_group)

    def no_processes(self, uid):
        h2.need(not self.active_process, "IDENTITY_HAS_PROCESSES")

    def unit(self):
        return self.unit_state.copy()

    def create_user(self, tag):
        self.actions.append("create_user")
        if self.failure == "before_user":
            raise h2.Stop("HOST_COMMAND_FAILED")
        self.account = {"uid": 987, "gid": 987, "tag": tag, "home": "/nonexistent",
                        "shell": "/usr/sbin/nologin", "locked": True, "groups": [987]}
        self.account_group = {"gid": 987, "members": [], "other_primary": []}
        if self.failure == "after_user":
            raise h2.Stop("HOST_COMMAND_FAILED")

    def remove_user(self):
        self.actions.append("remove_user")
        self.account = None

    def remove_group(self):
        self.actions.append("remove_group")
        if self.failure == "remove_group":
            raise h2.Stop("HOST_COMMAND_FAILED")
        self.account_group = None

    def syntax(self):
        if self.failure == "syntax":
            raise h2.Stop("HOST_COMMAND_FAILED")

    def reload(self):
        self.actions.append("reload")
        if self.failure == "reload":
            raise h2.Stop("HOST_COMMAND_FAILED")
        if self.path(h2.UNIT_PATH).exists():
            self.unit_state.update(LoadState="loaded", UnitFileState="static",
                                   FragmentPath=h2.UNIT_PATH, RefuseManualStart="yes")
        else:
            self.unit_state.update(LoadState="not-found", UnitFileState="", FragmentPath="")


class TransactionTests(unittest.TestCase):
    def setUp(self):
        # Some local sandboxes map only UID/GID 0. Do not fake successful chown:
        # the required privileged CI runner executes these filesystem tests.
        mappings = [list(map(int, line.split())) for line in Path("/proc/self/gid_map").read_text().splitlines()]
        if not any(start <= 987 < start + count for start, _, count in mappings):
            if os.environ.get("H2_REQUIRE_FULL_FS_TESTS") == "1":
                self.fail("CI must provide real GID mappings; skipping is forbidden")
            self.skipTest("GID 987 is unmapped here; real ownership tests require CI")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.host = FakeHost(Path(self.tmp.name))
        self.p = h2.Package(self.host)

    def snapshot(self):
        return {str(p.relative_to(self.host.root)): (
            p.lstat().st_mode, p.lstat().st_uid, p.lstat().st_gid,
            p.read_bytes() if p.is_file() and not p.is_symlink() else None)
            for p in self.host.root.rglob("*")}

    def install(self):
        self.assertEqual(self.p.apply(h2.APPROVE), "INSTALLED_DISABLED_NOT_QUALIFIED")

    def test_inspect_is_read_only(self):
        before = self.snapshot()
        self.p.fresh()
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.host.actions, [])

    def test_acknowledgements_deny_before_host_access(self):
        self.host.failure = "platform"
        for action in ("apply", "rollback"):
            with self.subTest(action=action), self.assertRaisesRegex(h2.Stop, "APPROVAL_REQUIRED"):
                getattr(self.p, action)("")
        self.assertEqual(self.host.actions, [])

    def test_platform_failure_leaves_no_state(self):
        before = self.snapshot()
        self.host.failure = "platform"
        with self.assertRaises(h2.Stop):
            self.p.apply(h2.APPROVE)
        self.assertEqual(before, self.snapshot())

    def test_existing_identity_not_adopted(self):
        self.host.account_group = {"gid": 555, "members": [], "other_primary": []}
        with self.assertRaisesRegex(h2.Stop, "IDENTITY_ALREADY_EXISTS"):
            self.p.apply(h2.APPROVE)
        self.assertEqual(self.host.actions, [])

    def test_existing_path_not_overwritten(self):
        self.host.path("/opt/keirin-custody").mkdir()
        before = self.snapshot()
        with self.assertRaisesRegex(h2.Stop, "TARGET_ALREADY_EXISTS"):
            self.p.apply(h2.APPROVE)
        self.assertEqual(before, self.snapshot())

    def test_dangling_symlink_is_conflict(self):
        self.host.path(h2.UNIT_PATH).symlink_to("/does-not-exist")
        with self.assertRaisesRegex(h2.Stop, "TARGET_ALREADY_EXISTS"):
            self.p.apply(h2.APPROVE)
        self.assertEqual(self.host.actions, [])

    def test_unsafe_parent_denied(self):
        self.host.path("/etc/systemd/system").chmod(0o777)
        with self.assertRaisesRegex(h2.Stop, "UNTRUSTED_PARENT"):
            self.p.apply(h2.APPROVE)
        self.assertEqual(self.host.actions, [])

    def test_foreign_unit_denied(self):
        self.host.unit_state.update(LoadState="loaded", FragmentPath="/run/foreign.service")
        with self.assertRaisesRegex(h2.Stop, "UNIT_ALREADY_EXISTS"):
            self.p.apply(h2.APPROVE)
        self.assertEqual(self.host.actions, [])

    def test_apply_verify_and_reapply(self):
        self.install()
        self.assertEqual(self.host.actions, ["create_user", "reload"])
        before = self.snapshot()
        self.assertEqual(self.p.verify(), "INSTALLED_DISABLED_NOT_QUALIFIED")
        self.assertEqual(before, self.snapshot())
        with self.assertRaises(h2.Stop):
            self.p.apply(h2.APPROVE)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.host.actions, ["create_user", "reload"])

    def test_rollback_restores_only_package_scope(self):
        unrelated = self.host.path("/opt/keep.txt")
        unrelated.write_text("not owned by H2")
        before = self.snapshot()
        self.install()
        self.assertEqual(self.p.rollback(h2.UNDO), "ROLLED_BACK_NO_RUNTIME")
        self.assertEqual(before, self.snapshot())
        self.assertIsNone(self.host.account)
        self.assertIsNone(self.host.account_group)

    def test_partial_failures_are_inspectable_and_removable(self):
        for failure in ("before_user", "after_user", "syntax", "reload"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                host = FakeHost(Path(directory))
                p = h2.Package(host)
                host.failure = failure
                with self.assertRaises(h2.Stop):
                    p.apply(h2.APPROVE)
                self.assertTrue(host.path(h2.RECEIPT).exists())
                with self.assertRaises(h2.Stop):
                    p.apply(h2.APPROVE)
                host.failure = None
                self.assertEqual(p.rollback(h2.UNDO), "ROLLED_BACK_NO_RUNTIME")

    def assert_rollback_denied_without_deleting(self):
        before = self.snapshot()
        actions = self.host.actions[:]
        with self.assertRaises(h2.Stop):
            self.p.rollback(h2.UNDO)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(actions, self.host.actions)

    def test_rollback_refuses_added_contents(self):
        self.install()
        self.host.path("/opt/keirin-custody/foreign.txt").write_text("keep")
        self.assert_rollback_denied_without_deleting()

    def test_rollback_refuses_modified_config(self):
        self.install()
        self.host.path("/etc/keirin-custody/gates.json").write_text('{"runtime":true}')
        self.assert_rollback_denied_without_deleting()

    def test_rollback_refuses_symlink(self):
        self.install()
        path = self.host.path("/etc/keirin-custody/gates.json")
        path.unlink()
        path.symlink_to(self.host.path(h2.UNIT_PATH))
        self.assert_rollback_denied_without_deleting()

    def test_rollback_refuses_hardlink(self):
        self.install()
        os.link(self.host.path(h2.UNIT_PATH), self.host.path("/opt/linked"))
        self.assert_rollback_denied_without_deleting()

    def test_rollback_refuses_permissions_or_owner_drift(self):
        self.install()
        unit = self.host.path(h2.UNIT_PATH)
        unit.chmod(0o666)
        self.assert_rollback_denied_without_deleting()
        unit.chmod(0o644)
        os.chown(unit, 123, 123)
        self.assert_rollback_denied_without_deleting()

    def test_rollback_refuses_identity_drift(self):
        self.install()
        self.host.account["groups"].append(27)
        self.assert_rollback_denied_without_deleting()

    def test_rollback_refuses_group_shared_by_other_identity(self):
        self.install()
        self.host.account_group["other_primary"].append("other-user")
        self.assert_rollback_denied_without_deleting()

    def test_rollback_refuses_processes(self):
        self.install()
        self.host.active_process = True
        self.assert_rollback_denied_without_deleting()

    def test_rollback_refuses_active_enabled_or_overridden_unit(self):
        self.install()
        original = self.host.unit_state.copy()
        for change in ({"ActiveState": "active"}, {"UnitFileState": "enabled"},
                       {"DropInPaths": "/etc/systemd/system/service.d/foreign.conf"}):
            self.host.unit_state = original | change
            self.assert_rollback_denied_without_deleting()

    def test_uncommitted_receipt_stops_before_cleanup(self):
        self.install()
        self.host.path(h2.RECEIPT + ".next").write_text("interrupted journal write")
        self.assert_rollback_denied_without_deleting()

    def test_group_removal_failure_retains_recovery_receipt(self):
        self.install()
        self.host.failure = "remove_group"
        with self.assertRaises(h2.Stop):
            self.p.rollback(h2.UNDO)
        self.assertTrue(self.host.path(h2.RECEIPT).exists())
        self.assertIsNone(self.host.account)
        self.host.failure = None
        self.assertEqual(self.p.rollback(h2.UNDO), "ROLLED_BACK_NO_RUNTIME")

    def test_concurrent_mutation_denied(self):
        self.install()
        with self.p.lock(), self.assertRaisesRegex(h2.Stop, "ANOTHER_H2_OPERATION_ACTIVE"):
            self.p.rollback(h2.UNDO)
        self.assertEqual(self.p.verify(), "INSTALLED_DISABLED_NOT_QUALIFIED")


class BoundaryTests(unittest.TestCase):
    def test_cli_defaults_readonly_and_redacts_errors(self):
        out = io.StringIO()
        with patch.object(h2.Package, "fresh", side_effect=OSError("private-secret-value")), redirect_stdout(out):
            self.assertEqual(h2.main([]), 1)
        self.assertNotIn("private-secret-value", out.getvalue())
        self.assertIn("HOST_STATE_UNREADABLE_OR_PARTIAL", out.getvalue())

    def test_process_runner_bounds_and_sanitizes(self):
        result = subprocess.CompletedProcess([], 1, b"secret-stdout", b"secret-stderr")
        with patch.object(h2.subprocess, "run", return_value=result) as run:
            with self.assertRaisesRegex(h2.Stop, "^HOST_COMMAND_FAILED$"):
                h2.Host().run("/usr/bin/systemctl", "daemon-reload")
        self.assertEqual(run.call_args.kwargs["timeout"], 20)
        self.assertEqual(run.call_args.kwargs["env"], h2.ENV)
        self.assertFalse(run.call_args.kwargs.get("shell", False))

    def test_user_creation_is_nonlogin_nohome_locked(self):
        with patch.object(h2.Host, "run", return_value="") as run:
            h2.Host().create_user("unique-tag")
        args = run.call_args.args
        for flag in ("--system", "--user-group", "--no-create-home", "--no-log-init"):
            self.assertIn(flag, args)
        self.assertEqual(args[args.index("--password") + 1], "!")
        self.assertEqual(args[args.index("--shell") + 1], "/usr/sbin/nologin")

    def test_unit_is_nonactivating_and_gates_closed(self):
        self.assertIn("ExecStart=/usr/bin/false\n", h2.UNIT)
        self.assertIn("RefuseManualStart=yes\n", h2.UNIT)
        self.assertNotIn("[Install]", h2.UNIT)
        self.assertIn("PrivateNetwork=yes\n", h2.UNIT)
        self.assertIn("MemorySwapMax=0\n", h2.UNIT)
        self.assertIn("LimitCORE=0\n", h2.UNIT)
        gates = json.loads(h2.GATES)
        self.assertTrue(all(value is False for key, value in gates.items() if key != "schema"))

    def test_systemd_255_unit_syntax(self):
        # Parses a temporary unit only: never talks to or modifies the manager.
        with tempfile.TemporaryDirectory() as directory:
            unit = Path(directory) / "keirin-custody.service"
            unit.write_text(h2.UNIT)
            result = subprocess.run(["/usr/bin/systemd-analyze", "verify", str(unit)],
                                    env=h2.ENV, capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertEqual(result.stderr, b"", result.stderr.decode())


if __name__ == "__main__":
    if os.geteuid() != 0:
        raise SystemExit("Run with sudo for temporary-file ownership tests; host commands are faked.")
    unittest.main()
