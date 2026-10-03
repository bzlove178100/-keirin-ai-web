"""Routed IPv4/IPv6 PMTU after PID 1 restricted recovery, isolated CI only."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("recovery", Path(__file__).with_name("test_secret_custody_dynamic_recovery.py"))
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)
p = r.module("pmtu", "test_secret_custody_pmtu.py")
t = p.t


def guard():
    p.guard()
    r.guard()


class Recovery:
    def prepare(self, version):
        guard()
        key = "pmtu" + str(version)
        maintenance = r.shape(key)
        t.nft(r.replacement(key, "qualification"))
        candidate = r.shape(key)
        t.nft(r.replacement(key, "maintenance"))
        assert maintenance != candidate and r.shape(key) == maintenance
        # Compile both shapes before opening the management/bulk connections.
        return maintenance, candidate

    def exercise(self, version, stack, admin, bulk, prepared):
        guard()
        key, peer = "pmtu" + str(version), p.ADDRESSES[version][3]
        maintenance, candidate = prepared
        original_socket = bulk.getsockname()

        def check():
            assert t.exchange(admin) and t.exchange(bulk)

        with r.armed(key, maintenance, candidate) as (path, _):
            r.invoke_controller(path, key, "after")
            assert r.shape(key) == candidate
            self.old = stack.enter_context(t.connect(peer, 443))
            assert t.exchange(self.old)
            check()
            assert not (path / "result").exists()
            print(f"PASS IPv{version}_PMTU_CONTROLLER_SIGKILL_QUALIFICATION_ACTIVE", flush=True)
            r.d.wait_for(lambda: (path / "result").exists(), 10, check)
            assert (path / "result").read_text() == "RESTORE_MAINTENANCE"
        assert r.shape(key) == maintenance
        assert not t.exchange(self.old) and not t.reaches(peer, 443)
        check()
        assert t.reaches(peer, 22)
        current = p.state(bulk, version)
        assert current["socket_mtu"] == current["tcp_pmtu"] == 1500
        assert bulk.getsockname() == original_socket
        print(f"PASS IPv{version}_PMTU_PID1_TWO_TABLE_RESTORE_SAME_SOCKET_1500", flush=True)

    def verify(self, version, prepared):
        assert r.shape("pmtu" + str(version)) == prepared[0]
        assert not t.exchange(self.old) and not t.reaches(p.ADDRESSES[version][3], 443)
        print(f"PASS IPv{version}_POST_RESTORE_PMTU_RESTRICTED_SHAPE_AND_OLD_NEW_DENIAL", flush=True)


def kernel():
    guard()
    print("KERNEL", os.uname().release, flush=True)
    for version in (4, 6):
        p.run_case(version, recovery=Recovery())
    print("RESULT SYNTHETIC_PMTU_INDEPENDENT_RECOVERY_OK_NO_LIVE_APPLY", flush=True)


class Tests(unittest.TestCase):
    def test_host_namespace_refused_before_mutation(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), patch.object(os, "geteuid", return_value=0), patch.object(os, "readlink", return_value="same"), patch.object(p, "run_case") as execute:
            with self.assertRaises(RuntimeError):
                kernel()
            execute.assert_not_called()

    def test_recovery_opt_in_required_before_fixture(self):
        with patch.object(p, "guard"), patch.object(r.d, "guard"), patch.dict(os.environ, {"KC_DYNAMIC_RECOVERY_CI": "0"}), patch.object(p, "run_case") as execute:
            with self.assertRaisesRegex(RuntimeError, "OPT_IN_REQUIRED"):
                kernel()
            execute.assert_not_called()


if __name__ == "__main__":
    if sys.argv[1:] == ["--systemd"]:
        kernel()
    else:
        unittest.main(verbosity=2)
