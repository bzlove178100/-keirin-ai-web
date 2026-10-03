"""Pinned patched DHCPv6 lifecycle through PID 1 restricted recovery, CI only."""
from contextlib import ExitStack
import importlib.util
import os
import socket
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("recovery", Path(__file__).with_name("test_secret_custody_dynamic_recovery.py"))
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)
h = r.module("dhcp6", "test_secret_custody_dhcpv6.py")
t, v, d = h.t, h.v, h.d
KEY = "dhcp6"


def guard():
    h.guard()
    r.guard()


class Recovery:
    def prepare(self):
        guard()
        maintenance = r.shape(KEY)
        t.nft(r.replacement(KEY, "qualification"))
        candidate = r.shape(KEY)
        t.nft(r.replacement(KEY, "maintenance"))
        assert maintenance != candidate and r.shape(KEY) == maintenance
        # This compilation is before networkd/listeners, inside a private netns.
        return maintenance, candidate

    def exercise(self, stack, proc, check, prepared):
        guard()
        maintenance, candidate = prepared
        assert t.rpc(proc, "qualification_listener")
        assert not t.reaches(v.REMOTE, 443)
        assert t.rpc(proc, "clear_events")
        with r.armed(KEY, maintenance, candidate, "lifecycle") as (path, _):
            r.invoke_controller(path, KEY, "after")
            assert r.shape(KEY) == candidate
            old = stack.enter_context(t.connect(v.REMOTE, 443))
            assert t.exchange(old)
            before = h.counts()
            d.wait_for(lambda: any(e["kind"] == "renew" and e["requested_server"] == "primary" and e["answered"] for e in t.rpc(proc, "events")), 18, check)
            d.wait_for(lambda: h.remaining() > h.LEASE - 4 and h.increased(before), 3, check)
            assert r.shape(KEY) == candidate and not (path / "result").exists()
            assert t.exchange(old)
            print("PASS DHCP6_RENEW_REFRESHES_LIFETIME_AFTER_CONTROLLER_SIGKILL", flush=True)
            d.wait_for(lambda: (path / "result").exists(), 25, check)
            assert (path / "result").read_text() == "RESTORE_MAINTENANCE"
        assert r.shape(KEY) == maintenance
        assert not t.exchange(old) and not t.reaches(v.REMOTE, 443)
        check()
        assert t.rpc(proc, "denied")
        print("PASS DHCP6_PID1_TWO_TABLE_RESTORE_REVOKES_OLD_NEW_QUALIFICATION", flush=True)
        # Wrong-source frame is seen before the netdev hook but not by the
        # protocol-specific packet socket. No blanket UDP reopening on restore.
        with ExitStack() as packets:
            sockets = {"ip": h.raw.packet_socket(packets, "host0", v.ETH_IPV6),
                       "all": h.raw.packet_socket(packets, "host0", h.raw.ETH_ALL, socket.SOCK_RAW)}
            before = v.counters()["in_deny"]
            token = "kc-dhcp6-recovered-wrong-source"
            assert t.rpc(proc, "send", "source", token)
            assert h.raw.collect(sockets, token) == {"ip": False, "all": True}
            assert v.counters()["in_deny"] == before + 1
        assert r.shape(KEY) == maintenance
        print("PASS DHCP6_POST_RESTORE_WRONG_SOURCE_FRAME_REJECTED", flush=True)
        # The original mandatory lifecycle now measures a NEW Renew, Rebind,
        # alternate-DUID adoption, and lease expiry after the actual restore.
        assert t.rpc(proc, "clear_events")

    def verify_expired(self, prepared):
        assert r.shape(KEY) == prepared[0]
        assert not t.reaches(v.REMOTE, 443)
        print("PASS DHCP6_POST_RESTORE_FULL_LIFECYCLE_AND_DENIAL_PRESERVED", flush=True)


def kernel():
    guard()
    # No installed/original fallback. Existing build.client_path validates the
    # root-owned manifest, hashes and read-only mount before networkd starts.
    h.lifecycle(client="patched", recovery=Recovery())
    print("RESULT SYNTHETIC_DHCP6_INDEPENDENT_RECOVERY_OK_NO_LIVE_APPLY", flush=True)


class Tests(unittest.TestCase):
    def test_host_namespace_refused_before_mutation(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), patch.object(os, "geteuid", return_value=0), patch.object(os, "readlink", return_value="same"), patch.object(t, "run") as mutate:
            with self.assertRaises(RuntimeError):
                kernel()
            mutate.assert_not_called()

    def test_recovery_opt_in_required_before_lifecycle(self):
        with patch.object(h, "guard"), patch.object(r.d, "guard"), patch.dict(os.environ, {"KC_DYNAMIC_RECOVERY_CI": "0"}), patch.object(h, "lifecycle") as execute:
            with self.assertRaisesRegex(RuntimeError, "OPT_IN_REQUIRED"):
                kernel()
            execute.assert_not_called()


if __name__ == "__main__":
    if sys.argv[1:] == ["--systemd"]:
        kernel()
    else:
        unittest.main(verbosity=2)
