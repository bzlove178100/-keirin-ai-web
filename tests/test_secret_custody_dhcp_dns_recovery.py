"""Real DHCP DNS changes across controller death and PID 1 recovery, CI only."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("dhcp_dns", Path(__file__).with_name("test_secret_custody_dhcp_dns.py"))
h = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(h)
z, r, d, t = h.z, h.r, h.d, h.t
KEY = "dhcp-dns"


def guard():
    h.guard()
    r.guard()


def denied(proc, res, expected):
    # A completed earlier timeout may have left an upstream transaction alive.
    # Require actual drain and a new output drop, never cached failure evidence.
    d.wait_for(lambda: res.active_transactions() == 0, 15, res.check)
    res.call("FlushCaches")
    before = t.rpc(proc, "dns_events", d.ALTERNATE)
    drops = d.raw.counters("inet", d.TABLE)["dns_output_deny"]
    z.query(success=False)
    assert d.raw.counters("inet", d.TABLE)["dns_output_deny"] > drops
    assert t.rpc(proc, "dns_events", d.ALTERNATE) == before
    assert r.shape(KEY) == expected and t.rpc(proc, "check")


class Recovery:
    def prepare(self):
        guard()
        maintenance = r.shape(KEY)
        t.nft(r.replacement(KEY, "qualification"))
        candidate = r.shape(KEY)
        t.nft(r.replacement(KEY, "maintenance"))
        assert maintenance != candidate and r.shape(KEY) == maintenance
        return maintenance, candidate

    def exercise(self, stack, proc, res, initial, prepared):
        guard()
        maintenance, candidate = prepared
        original = h.stamp(res)["processes"]
        assert t.rpc(proc, "qualification_listener")
        assert not t.reaches(d.PRIMARY, 443)

        def check():
            res.check()
            assert t.rpc(proc, "check"), "ADMIN_TRANSPORT_LOST"
            assert d.address_present() and d.default_route_present()

        with r.armed(KEY, maintenance, candidate, "lifecycle") as (path, _):
            r.invoke_controller(path, KEY, "after")
            assert r.shape(KEY) == candidate
            old = stack.enter_context(t.connect(d.PRIMARY, 443))
            assert t.exchange(old)
            res.call("FlushCaches")
            before = len(t.rpc(proc, "dns_events", d.PRIMARY))
            z.query()
            z.query(kind=28, tcp=True)
            assert len(t.rpc(proc, "dns_events", d.PRIMARY)) >= before + 2
            assert not (path / "result").exists()
            print("PASS DHCP_DNS_FRESH_STUB_QUERIES_AFTER_CONTROLLER_SIGKILL", flush=True)

            epoch = t.rpc(proc, "change", d.ALTERNATE)
            d.wait_for(lambda: h.accepted(proc, epoch, d.ALTERNATE) and h.lease_dns(res) == d.ALTERNATE
                       and h.dns_values(res) == h.expected_dns(res, d.ALTERNATE), 18, check)
            observed = h.observation(res)
            decision = h.compare.compare(initial["report"], observed["report"])
            assert decision["decision"] == "CHANGE_REVIEW_REQUIRED", decision
            assert not any(decision[k] for k in ("qualification", "mutation", "apply_allowed", "freshness_verified"))
            denied(proc, res, candidate)
            assert t.exchange(old) and not (path / "result").exists()
            print("PASS DHCP_DNS_RENEWED_UNAPPROVED_SOURCE_DENIED_WHILE_CONTROLLER_DEAD", flush=True)

            d.wait_for(lambda: (path / "result").exists(), 25, check)
            assert (path / "result").read_text() == "RESTORE_MAINTENANCE"
        assert r.shape(KEY) == maintenance
        assert not t.exchange(old) and not t.reaches(d.PRIMARY, 443)
        check()
        assert h.dns_values(res) == h.expected_dns(res, d.ALTERNATE)
        print("PASS DHCP_DNS_PID1_TWO_TABLE_RESTORE_REVOKES_OLD_NEW_QUALIFICATION", flush=True)

        denied(proc, res, maintenance)
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
        print("PASS DHCP_DNS_POST_RESTORE_FULL_OBSERVATION_AND_EXPIRY_LIFECYCLE", flush=True)


def kernel():
    guard()
    h.kernel(recovery=Recovery())
    print("RESULT SYNTHETIC_DHCP_DNS_INDEPENDENT_RECOVERY_OK_NO_LIVE_APPLY", flush=True)


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


if __name__ == "__main__":
    if sys.argv[1:] == ["--systemd"]:
        kernel()
    else:
        unittest.main(verbosity=2)
