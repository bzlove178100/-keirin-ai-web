"""Pinned patched DHCPv6 lifecycle through PID 1 restricted recovery, CI only."""
from contextlib import ExitStack
import importlib.util
import json
import os
import socket
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("recovery", Path(__file__).with_name("test_secret_custody_dynamic_recovery.py"))
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)
h = r.module("dhcp6", "test_secret_custody_dhcpv6.py")
t, v, d = h.t, h.v, h.d
KEY = "dhcp6"
LEASE_KEY = "dhcp6-lease"
lease = r.lease_module()


def guard(guarded=False):
    h.guard()
    r.guard()
    if type(guarded) is not bool:
        raise ValueError("FIXED_DHCP6_GUARD_MODE_REQUIRED")
    if guarded and os.environ.get("KC_DHCP6_LEASE_CI") != "1":
        raise RuntimeError("DHCP6_LEASE_CI_OPT_IN_REQUIRED")


def guard_handles():
    return [[(kind, item["handle"]) for row in report["nftables"] for kind, item in row.items()
             if kind in ("table", "chain", "rule", "set")] for report in r.lease_reports()]


class Recovery:
    def __init__(self, guarded=False):
        if type(guarded) is not bool:
            raise ValueError("FIXED_DHCP6_GUARD_MODE_REQUIRED")
        self.guarded = guarded
        self.key = LEASE_KEY if guarded else KEY
        self.handles = None

    def cleanup_tables(self):
        return lease.TABLES if self.guarded else ()

    def prepare(self):
        guard(self.guarded)
        maintenance = r.shape(KEY)
        t.nft(r.replacement(KEY, "qualification"))
        candidate = r.shape(KEY)
        t.nft(r.replacement(KEY, "maintenance"))
        assert maintenance != candidate and r.shape(KEY) == maintenance
        # This compilation is before networkd/listeners, inside a private netns.
        return maintenance, candidate

    def exercise(self, stack, proc, check, prepared):
        guard(self.guarded)
        maintenance, candidate = prepared
        assert t.rpc(proc, "qualification_listener")
        assert not t.reaches(v.REMOTE, 443)
        assert t.rpc(proc, "clear_events")
        with r.armed(self.key, maintenance, candidate, "lifecycle") as (path, _):
            seen = time.monotonic()
            ready = json.loads((path / "ready").read_text())
            if self.guarded:
                self.handles = guard_handles()
            r.invoke_controller(path, self.key, "after")
            assert r.shape(KEY) == candidate
            old = stack.enter_context(t.connect(v.REMOTE, 443))
            assert t.exchange(old) and t.reaches(v.REMOTE, 443)
            before = h.counts()
            d.wait_for(lambda: any(e["kind"] == "renew" and e["requested_server"] == "primary" and e["answered"] for e in t.rpc(proc, "events")), 18, check)
            d.wait_for(lambda: h.remaining() > h.LEASE - 4 and h.increased(before), 3, check)
            assert r.shape(KEY) == candidate and not (path / "result").exists()
            if not self.guarded:
                assert t.exchange(old)
            print("PASS DHCP6_RENEW_REFRESHES_LIFETIME_AFTER_CONTROLLER_SIGKILL", flush=True)
            if self.guarded:
                # The guard was created before readiness. This later bound
                # proves expiry with candidate tables and the same live worker.
                d.wait_for(lambda: time.monotonic() > seen + lease.SECONDS + .2, 12, check)
                assert r.shape(KEY) == candidate and not (path / "result").exists()
                assert r.process_start(ready["pid"]) == ready["start"]
                assert not t.exchange(old) and not t.reaches(v.REMOTE, 443)
                assert guard_handles() == self.handles
                check()
                print("PASS DHCP6_KERNEL_EXPIRY_WITH_CANDIDATE_AND_LIVE_WORKER_PRESERVES_ADMIN", flush=True)
                # A fresh Renew must succeed AFTER expiry, not merely the
                # exchange which preceded it. No event can be counted twice.
                before = h.counts()
                assert t.rpc(proc, "clear_events")
                d.wait_for(lambda: any(e["kind"] == "renew" and e["requested_server"] == "primary" and e["answered"]
                           for e in t.rpc(proc, "events")), 12, check)
                d.wait_for(lambda: h.remaining() > h.LEASE - 4 and h.increased(before), 3, check)
                assert r.shape(KEY) == candidate and not (path / "result").exists()
                assert r.process_start(ready["pid"]) == ready["start"]
                assert not t.exchange(old) and not t.reaches(v.REMOTE, 443)
                assert guard_handles() == self.handles
                print("PASS DHCP6_FRESH_RENEW_AFTER_GUARD_EXPIRY_BEFORE_RESTORE", flush=True)
            d.wait_for(lambda: (path / "result").exists(), 25, check)
            assert (path / "result").read_text() == "RESTORE_MAINTENANCE"
            if self.guarded:
                assert guard_handles() == self.handles
                print("PASS DHCP6_PID1_RESTORES_AFTER_KERNEL_EXPIRY_WITHOUT_REARM", flush=True)
        assert not path.exists() and not Path(f'/proc/{ready["pid"]}').exists()
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
        if self.guarded:
            assert guard_handles() == self.handles
            print("PASS DHCP6_GUARD_UNCHANGED_THROUGH_REBIND_AND_REAL_ADDRESS_EXPIRY", flush=True)
        print("PASS DHCP6_POST_RESTORE_FULL_LIFECYCLE_AND_DENIAL_PRESERVED", flush=True)


def kernel(guarded=False):
    guard(guarded)
    # No installed/original fallback. Existing build.client_path validates the
    # root-owned manifest, hashes and read-only mount before networkd starts.
    h.lifecycle(client="patched", recovery=Recovery(guarded))
    result = "GUARDED" if guarded else "INDEPENDENT"
    print(f"RESULT SYNTHETIC_DHCP6_{result}_RECOVERY_OK_NO_LIVE_APPLY", flush=True)


class Tests(unittest.TestCase):
    def test_guarded_alias_preserves_dhcp6_policy_and_requires_receipt(self):
        self.assertEqual(r.GUARDED[LEASE_KEY], (KEY, "ra6"))
        self.assertEqual(lease.tuples("ra6"), (("ip6", v.CLIENT, v.REMOTE),))
        self.assertEqual(r.tables(LEASE_KEY), r.tables(KEY))
        for mode in ("maintenance", "qualification"):
            self.assertEqual(r.profile(LEASE_KEY, mode), r.profile(KEY, mode))
            self.assertNotEqual(r.profile(LEASE_KEY, mode), r.profile(6, mode))
            self.assertNotIn("kc_lease_guard", r.replacement(LEASE_KEY, mode))
        with patch.object(r, "lease_reports", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "QUALIFICATION_GUARD_REQUIRED"):
                r.require_lease({"version": LEASE_KEY})
        self.assertEqual(Recovery().cleanup_tables(), ())
        self.assertEqual(Recovery(True).cleanup_tables(), lease.TABLES)

    def test_guarded_mode_requires_explicit_opt_in_before_lifecycle(self):
        with patch.object(h, "guard"), patch.object(r, "guard"), patch.dict(os.environ, {"KC_DHCP6_LEASE_CI": "0"}), patch.object(h, "lifecycle") as execute:
            with self.assertRaisesRegex(RuntimeError, "DHCP6_LEASE_CI_OPT_IN_REQUIRED"):
                kernel(guarded=True)
            execute.assert_not_called()
        for value in (1, None, "true"):
            with self.assertRaisesRegex(ValueError, "FIXED_DHCP6_GUARD_MODE_REQUIRED"):
                Recovery(value)

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
    elif sys.argv[1:] == ["--lease-systemd"]:
        kernel(guarded=True)
    else:
        unittest.main(verbosity=2)
