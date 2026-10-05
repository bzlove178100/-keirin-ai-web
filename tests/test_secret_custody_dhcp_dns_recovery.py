"""Real DHCP DNS changes across controller death and PID 1 recovery, CI only."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import Mock, patch

SPEC = importlib.util.spec_from_file_location("dhcp_dns", Path(__file__).with_name("test_secret_custody_dhcp_dns.py"))
h = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(h)
z, r, d, t = h.z, h.r, h.d, h.t
KEY = "dhcp-dns"
LEASE_KEY = "dhcp-dns-lease"
lease = r.lease_module()


def guard(guarded=False):
    h.guard()
    r.guard()
    if type(guarded) is not bool:
        raise ValueError("FIXED_DHCP_DNS_GUARD_MODE_REQUIRED")
    if guarded and os.environ.get("KC_DHCP_DNS_LEASE_CI") != "1":
        raise RuntimeError("DHCP_DNS_LEASE_CI_OPT_IN_REQUIRED")


def guard_handles():
    return [[(kind, item["handle"]) for row in report["nftables"] for kind, item in row.items()
             if kind in ("table", "chain", "rule", "set")] for report in r.lease_reports()]


def denied(proc, res, expected, kind, active):
    # A UDP client's timeout does not cancel the resolver's retrying query.
    # Use A before restoration and a distinct AAAA after it. Require one NEW
    # transaction, not a coalesced old query or a cached failure.
    assert (kind, active) in ((1, 0), (28, 1))
    assert res.active_transactions() == active
    res.call("FlushCaches")
    before = t.rpc(proc, "dns_events", d.ALTERNATE)
    drops = d.raw.counters("inet", d.TABLE)["dns_output_deny"]
    z.query(kind=kind, success=False)
    after = res.active_transactions()
    assert after == active + 1, "NEW_DENIED_TRANSACTION_REQUIRED"
    assert d.raw.counters("inet", d.TABLE)["dns_output_deny"] > drops
    assert t.rpc(proc, "dns_events", d.ALTERNATE) == before
    assert r.shape(KEY) == expected and t.rpc(proc, "check")
    print("DENIED_TRANSACTION", "A" if kind == 1 else "AAAA", active, after, flush=True)


class Recovery:
    def __init__(self, guarded=False):
        if type(guarded) is not bool:
            raise ValueError("FIXED_DHCP_DNS_GUARD_MODE_REQUIRED")
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
        return maintenance, candidate

    def exercise(self, stack, proc, res, initial, prepared):
        guard(self.guarded)
        maintenance, candidate = prepared
        original = h.stamp(res)["processes"]
        assert t.rpc(proc, "qualification_listener")
        assert not t.reaches(d.PRIMARY, 443)

        def check():
            res.check()
            assert t.rpc(proc, "check"), "ADMIN_TRANSPORT_LOST"
            assert d.address_present() and d.default_route_present()

        with r.armed(self.key, maintenance, candidate, "lifecycle") as (path, _):
            seen = time.monotonic()
            ready = json.loads((path / "ready").read_text())
            if self.guarded:
                self.handles = guard_handles()
            r.invoke_controller(path, self.key, "after")
            assert r.shape(KEY) == candidate
            old = stack.enter_context(t.connect(d.PRIMARY, 443))
            assert t.exchange(old) and t.reaches(d.PRIMARY, 443)
            res.call("FlushCaches")
            before = len(t.rpc(proc, "dns_events", d.PRIMARY))
            z.query()
            z.query(kind=28, tcp=True)
            assert len(t.rpc(proc, "dns_events", d.PRIMARY)) >= before + 2
            assert not (path / "result").exists()
            print("PASS DHCP_DNS_FRESH_STUB_QUERIES_AFTER_CONTROLLER_SIGKILL", flush=True)

            if self.guarded:
                # Wait from observed readiness, later than the original guard
                # creation. No worker restoration or rule edits cause denial.
                d.wait_for(lambda: time.monotonic() > seen + lease.SECONDS + .2, 12, check)
                assert r.shape(KEY) == candidate and not (path / "result").exists()
                assert r.process_start(ready["pid"]) == ready["start"]
                assert not t.exchange(old) and not t.reaches(d.PRIMARY, 443)
                assert guard_handles() == self.handles
                res.call("FlushCaches")
                before = len(t.rpc(proc, "dns_events", d.PRIMARY))
                z.query()
                z.query(kind=28, tcp=True)
                assert len(t.rpc(proc, "dns_events", d.PRIMARY)) >= before + 2
                check()
                print("PASS DHCP_DNS_KERNEL_EXPIRY_WITH_CANDIDATE_AND_LIVE_WORKER_PRESERVES_FRESH_DNS_ADMIN", flush=True)

            epoch = t.rpc(proc, "change", d.ALTERNATE)
            d.wait_for(lambda: h.accepted(proc, epoch, d.ALTERNATE) and h.lease_dns(res) == d.ALTERNATE
                       and h.dns_values(res) == h.expected_dns(res, d.ALTERNATE), 18, check)
            observed = h.observation(res)
            decision = h.compare.compare(initial["report"], observed["report"])
            assert decision["decision"] == "CHANGE_REVIEW_REQUIRED", decision
            assert not any(decision[k] for k in ("qualification", "mutation", "apply_allowed", "freshness_verified"))
            denied(proc, res, candidate, 1, 0)
            assert not (path / "result").exists()
            if self.guarded:
                assert not t.exchange(old) and not t.reaches(d.PRIMARY, 443)
                assert guard_handles() == self.handles
            else:
                assert t.exchange(old)
            print("PASS DHCP_DNS_RENEWED_UNAPPROVED_SOURCE_DENIED_WHILE_CONTROLLER_DEAD", flush=True)

            d.wait_for(lambda: (path / "result").exists(), 25, check)
            assert (path / "result").read_text() == "RESTORE_MAINTENANCE"
            if self.guarded:
                assert guard_handles() == self.handles
                print("PASS DHCP_DNS_PID1_RESTORE_AFTER_KERNEL_EXPIRY_WITHOUT_REARM", flush=True)
        assert not path.exists() and not Path(f'/proc/{ready["pid"]}').exists()
        assert r.shape(KEY) == maintenance
        assert not t.exchange(old) and not t.reaches(d.PRIMARY, 443)
        check()
        assert h.dns_values(res) == h.expected_dns(res, d.ALTERNATE)
        print("PASS DHCP_DNS_PID1_TWO_TABLE_RESTORE_REVOKES_OLD_NEW_QUALIFICATION", flush=True)

        denied(proc, res, maintenance, 28, 1)
        assert not t.exchange(old) and not t.reaches(d.PRIMARY, 443)
        print("PASS DHCP_DNS_UNAPPROVED_SOURCE_STAYS_DENIED_AFTER_RESTORE", flush=True)
        epoch = t.rpc(proc, "change", d.PRIMARY)
        d.wait_for(lambda: h.accepted(proc, epoch, d.PRIMARY) and h.lease_dns(res) == d.PRIMARY
                   and h.dns_values(res) == h.expected_dns(res, d.PRIMARY), 18, check)
        d.wait_for(lambda: res.active_transactions() == 0, 15, check)
        res.call("FlushCaches")
        before = len(t.rpc(proc, "dns_events", d.PRIMARY))
        z.query()
        z.query(kind=28, tcp=True)
        assert len(t.rpc(proc, "dns_events", d.PRIMARY)) >= before + 2
        observed = h.observation(res)
        assert h.compare.compare(initial["report"], observed["report"])["decision"] == "OBSERVATIONS_MATCH_REVIEW_ONLY"
        assert h.stamp(res)["processes"] == original
        assert r.shape(KEY) == maintenance
        check()
        print("PASS DHCP_DNS_POST_RESTORE_RENEWAL_APPROVED_SAME_DAEMONS_AND_ADMIN", flush=True)
        # The original twelve-record suite now continues under the actually
        # restored policy, including killed/mixed collectors and real expiry.

    def verify_expired(self, prepared):
        assert r.shape(KEY) == prepared[0] and not t.reaches(d.PRIMARY, 443)
        if self.guarded:
            assert guard_handles() == self.handles
            print("PASS DHCP_DNS_GUARD_UNCHANGED_THROUGH_REAL_DHCP_EXPIRY", flush=True)
        print("PASS DHCP_DNS_POST_RESTORE_FULL_OBSERVATION_AND_EXPIRY_LIFECYCLE", flush=True)


def kernel(guarded=False):
    guard(guarded)
    h.kernel(recovery=Recovery(guarded))
    result = "GUARDED" if guarded else "INDEPENDENT"
    print(f"RESULT SYNTHETIC_DHCP_DNS_{result}_RECOVERY_OK_NO_LIVE_APPLY", flush=True)


class Tests(unittest.TestCase):
    def test_host_namespace_refused_before_mutation(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), patch.object(os, "geteuid", return_value=0), patch.object(os, "readlink", return_value="same"), patch.object(t, "run") as run:
            with self.assertRaises(RuntimeError):
                kernel()
            run.assert_not_called()

    def test_recovery_opt_in_required_before_fixture(self):
        with patch.object(h, "guard"), patch.object(d, "guard"), patch.dict(os.environ, {"KC_DYNAMIC_RECOVERY_CI": "0"}), patch.object(h, "kernel") as launch:
            with self.assertRaisesRegex(RuntimeError, "DYNAMIC_RECOVERY_CI_OPT_IN_REQUIRED"):
                kernel()
            launch.assert_not_called()

    def test_restoration_uses_exact_dns_profile_and_owned_tables(self):
        self.assertEqual(r.tables(KEY), r.tables(4))
        self.assertEqual(r.profile(KEY, "maintenance"), h.policy())
        self.assertNotEqual(r.profile(KEY, "maintenance"), r.profile(4, "maintenance"))
        for mode in ("maintenance", "qualification"):
            self.assertTrue(r.replacement(KEY, mode).startswith(
                f"delete table inet {d.TABLE}\ndelete table netdev {d.LINK_TABLE}\n"))
        with self.assertRaises(ValueError):
            r.profile(KEY, "open")

    def test_guarded_alias_keeps_dns_policy_and_requires_receipt(self):
        self.assertEqual(r.GUARDED[LEASE_KEY], (KEY, "dhcp4"))
        self.assertEqual(r.tables(LEASE_KEY), r.tables(KEY))
        for mode in ("maintenance", "qualification"):
            self.assertEqual(r.profile(LEASE_KEY, mode), r.profile(KEY, mode))
            self.assertNotIn("kc_lease_guard", r.replacement(LEASE_KEY, mode))
        with patch.object(r, "lease_reports", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "QUALIFICATION_GUARD_REQUIRED"):
                r.require_lease({"version": LEASE_KEY})
        self.assertEqual(Recovery().cleanup_tables(), ())
        self.assertEqual(Recovery(True).cleanup_tables(), lease.TABLES)
        for value in (1, None, "true"):
            with self.assertRaisesRegex(ValueError, "FIXED_DHCP_DNS_GUARD_MODE_REQUIRED"):
                Recovery(value)

    def test_guarded_opt_in_before_fixture(self):
        with patch.object(h, "guard"), patch.object(r, "guard"), patch.dict(os.environ, {"KC_DHCP_DNS_LEASE_CI": "0"}), patch.object(h, "kernel") as launch:
            with self.assertRaisesRegex(RuntimeError, "DHCP_DNS_LEASE_CI_OPT_IN_REQUIRED"):
                kernel(guarded=True)
            launch.assert_not_called()

    def test_post_restore_denial_requires_distinct_new_transaction(self):
        for after in (1, 2):
            res = Mock()
            res.active_transactions.side_effect = [1, after]
            with patch.object(z, "query") as query, patch.object(t, "rpc", side_effect=[[], [], True]), patch.object(d.raw, "counters", side_effect=[{"dns_output_deny": 3}, {"dns_output_deny": 4}]), patch.object(r, "shape", return_value="maintenance"):
                if after == 1:
                    with self.assertRaisesRegex(AssertionError, "NEW_DENIED_TRANSACTION_REQUIRED"):
                        denied(None, res, "maintenance", 28, 1)
                else:
                    denied(None, res, "maintenance", 28, 1)
                query.assert_called_once_with(kind=28, success=False)


if __name__ == "__main__":
    if sys.argv[1:] == ["--systemd"]:
        kernel()
    elif sys.argv[1:] == ["--lease-systemd"]:
        kernel(guarded=True)
    else:
        unittest.main(verbosity=2)
