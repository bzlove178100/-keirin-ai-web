"""Ubuntu 24.04 account CLI integration in a disposable chroot database.

Uses the actual installed shadow executables and production argument builders.
Only --root <temporary tree> is injected; the real runner account database is
never a target. The systemd/process adapter remains synthetic. Run as root on
the required CI VM; no containers, packages, network or live AWS access needed.
"""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("h2_tests", ROOT / "tests/test_secret_custody_h2.py")
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)
h2 = base.h2


class AccountCLIHost(base.FakeHost):
    def __init__(self, root, old_argument=False):
        super().__init__(root)
        self.old_argument = old_argument
        fixtures = {
            "/etc/passwd": "root:x:0:0:root:/root:/bin/sh\n",
            "/etc/group": "root:x:0:\n",
            "/etc/shadow": "root:!:20000:0:99999:7:::\n",
            "/etc/gshadow": "root:!::\n",
            "/etc/nsswitch.conf": "passwd: files\ngroup: files\nshadow: files\n",
            "/etc/login.defs": "SYS_UID_MIN 100\nSYS_UID_MAX 999\nSYS_GID_MIN 100\n"
                               "SYS_GID_MAX 999\nUID_MIN 1000\nGID_MIN 1000\n"
                               "USERGROUPS_ENAB yes\nMAIL_DIR /var/mail\n",
            # Deliberately enabled: --system must still skip mail creation.
            "/etc/default/useradd": "GROUP=100\nHOME=/home\nSHELL=/bin/sh\n"
                                    "SKEL=/etc/skel\nCREATE_MAIL_SPOOL=yes\n",
        }
        for path, data in fixtures.items():
            self.path(path).parent.mkdir(parents=True, exist_ok=True)
            self.path(path).write_text(data)
        for path in ("/etc/skel", "/var/mail", "/usr/sbin"):
            self.path(path).mkdir(parents=True, exist_ok=True)
        # useradd validates the shell path; it is never executed in this test.
        self.path("/usr/sbin/nologin").write_bytes(Path("/usr/sbin/nologin").read_bytes())
        self.path("/usr/sbin/nologin").chmod(0o755)

    def run(self, *args, stage="HOST_COMMAND"):
        if args[0] not in ("/usr/sbin/useradd", "/usr/sbin/userdel",
                           "/usr/sbin/groupdel", "/usr/bin/passwd"):
            raise AssertionError("only account commands may enter the isolated CLI adapter")
        options = args[1:]
        if self.old_argument and args[0] == "/usr/sbin/useradd":
            options = (*options[:-1], "--key", "CREATE_MAIL_SPOOL=no", options[-1])
        return h2.Host.run(self, args[0], "--root", str(self.root), *options, stage=stage)

    def record(self, path):
        for line in self.path(path).read_text().splitlines():
            fields = line.split(":")
            if fields[0] == h2.NAME:
                return fields
        return None

    def user(self):
        row = self.record("/etc/passwd")
        if row is None:
            return None
        status = self.run("/usr/bin/passwd", "-S", h2.NAME, stage="USER_STATUS").split()
        gid = int(row[3])
        return {"uid": int(row[2]), "gid": gid, "tag": row[4], "home": row[5],
                "shell": row[6], "locked": status[:2] == [h2.NAME, "L"], "groups": [gid]}

    def group(self):
        row = self.record("/etc/group")
        if row is None:
            return None
        return {"gid": int(row[2]), "members": row[3].split(",") if row[3] else [],
                "other_primary": []}

    def create_user(self, tag):
        h2.Host.create_user(self, tag)

    def remove_user(self):
        h2.Host.remove_user(self)

    def remove_group(self):
        h2.Host.remove_group(self)


class AccountCLITests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(os.geteuid(), 0, "root is required for the isolated chroot")
        self.assertIn('VERSION_ID="24.04"', Path("/etc/os-release").read_text())
        self.tmp = tempfile.TemporaryDirectory(prefix="h2-account-cli-")
        self.addCleanup(self.tmp.cleanup)
        self.host = AccountCLIHost(Path(self.tmp.name))
        self.package = h2.Package(self.host)

    def assert_no_home_or_mail(self):
        self.assertFalse(self.host.path("/nonexistent").exists())
        self.assertFalse(self.host.path("/home").exists())
        self.assertEqual(list(self.host.path("/var/mail").iterdir()), [])

    def test_real_useradd_verify_and_bounded_removal(self):
        self.assertEqual(self.package.apply(h2.APPROVE), "INSTALLED_DISABLED_NOT_QUALIFIED")
        account = self.host.user()
        self.assertTrue(account["locked"])
        self.assertTrue(0 < account["uid"] < 1000 and 0 < account["gid"] < 1000)
        self.assertEqual(account["home"], "/nonexistent")
        self.assertEqual(account["shell"], "/usr/sbin/nologin")
        self.assert_no_home_or_mail()
        self.assertEqual(self.package.verify(), "INSTALLED_DISABLED_NOT_QUALIFIED")
        self.assertEqual(self.package.rollback(h2.UNDO), "ROLLED_BACK_NO_RUNTIME")
        self.assertIsNone(self.host.user())
        self.assertIsNone(self.host.group())
        self.assertFalse(self.host.path(h2.STATE).exists())

    def test_reproduce_old_failure_then_recover_with_corrected_command(self):
        # This is the actual invalid argument from the first live attempt.
        self.host.old_argument = True
        with self.assertRaisesRegex(h2.Stop, "^USER_CREATE_FAILED$"):
            self.package.apply(h2.APPROVE)
        receipt = self.package.receipt()
        self.assertIsNone(receipt["uid"])
        self.assertIsNone(receipt["gid"])
        self.assertIsNone(self.host.user())
        self.assertIsNone(self.host.group())
        for path in (*h2.DIRS, h2.UNIT_PATH):
            self.assertFalse(self.host.path(path).exists())
        self.assert_no_home_or_mail()
        # Same schema and ownership checks as the receipt on the live host.
        self.host.old_argument = False
        self.assertEqual(self.package.rollback(h2.UNDO), "ROLLED_BACK_NO_RUNTIME")
        self.assertEqual(self.package.apply(h2.APPROVE), "INSTALLED_DISABLED_NOT_QUALIFIED")
        self.assertEqual(self.package.verify(), "INSTALLED_DISABLED_NOT_QUALIFIED")
        self.assert_no_home_or_mail()


if __name__ == "__main__":
    unittest.main(verbosity=2)
