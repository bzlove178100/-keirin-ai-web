"""Guarded DHCPv4 and IPv6 RA recovery in disposable CI namespaces only."""
from contextlib import ExitStack
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("recovery", Path(__file__).with_name("test_secret_custody_dynamic_recovery.py"))
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)
d, t, v = r.d, r.t, r.v
lease = r.lease_module()
PROFILES = {4: "dhcp4-lease", 6: "ra6-lease"}
UNRELATED = "kc_dynamic_lease_unrelated"


def guard():
    r.guard()
    if os.environ.get("KC_DYNAMIC_LEASE_CI") != "1":
        raise RuntimeError("DYNAMIC_LEASE_CI_OPT_IN_REQUIRED")


def handles():
    return [[(kind, item["handle"]) for row in report["nftables"] for kind, item in row.items()
             if kind in ("table", "chain", "rule", "set")] for report in r.lease_reports()]


def case(version):
    guard()
    if type(version) is not int or version not in PROFILES:
        raise ValueError("FIXED_DYNAMIC_LEASE_FAMILY_REQUIRED")
    profile = PROFILES[version]
    r.empty()
    proc = subprocess.Popen(["unshare", "--net", sys.executable, "-I", "-B", r.__file__, "--peer", str(version)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
        env=dict(os.environ, FIXTURE_PARENT_NETNS=os.readlink("/proc/self/ns/net")))
    try:
        assert t.read_line(proc).strip() == "READY"
        t.run(t.IP, "link", "add", "host0", "type", "veth", "peer", "name", "peer0")
        t.run(t.IP, "link", "set", "peer0", "netns", str(proc.pid))
        t.run(t.IP, "link", "set", "lo", "up")
        t.run(t.IP, "link", "set", "host0", "address", t.MAC_HOST, "addrgenmode", "none")
        t.run("sysctl", "-qw", "net.ipv6.conf.host0.disable_ipv6=" + ("1" if version == 4 else "0"),
              "net.ipv6.conf.host0.accept_ra=0")
        t.run(t.IP, "link", "set", "host0", "up")
        assert t.rpc(proc, "setup")
        t.nft(r.profile(profile, "maintenance"))
        maintenance = r.shape(profile)
        t.nft(r.replacement(profile, "qualification"))
        candidate = r.shape(profile)
        t.nft(r.replacement(profile, "maintenance"))
        t.nft(f"table inet {UNRELATED} {{ chain sentinel {{ counter drop; }}; }}\n")
        unrelated = r.table_shape("inet", UNRELATED)
        peer = d.PRIMARY if version == 4 else v.REMOTE
        with ExitStack() as stack:
            for port in (22, 80):
                t.listen(stack, "0.0.0.0" if version == 4 else "::", port)
            root, _ = stack.enter_context(d.networkd(ipv6=version == 6))
            if version == 4:
                d.wait_for(lambda: d.address_present() and d.default_route_present()
                           and d.lease_server(root) == d.PRIMARY, 20)
            else:
                d.wait_for(lambda: v.usable(v.HOST_LL), 8)
                t.rpc(proc, "ra", True)
                d.wait_for(lambda: v.usable(v.CLIENT) and v.route_present(), 8)
            assert t.rpc(proc, "open")

            def administration():
                assert (d.address_present() and d.default_route_present()) if version == 4 else (v.usable(v.CLIENT) and v.route_present())
                assert t.rpc(proc, "check"), "DYNAMIC_LEASE_ADMIN_LOST"
                assert r.table_shape("inet", UNRELATED) == unrelated

            def restricted():
                assert r.shape(profile) == maintenance
                assert not t.reaches(peer, 443) and t.rpc(proc, "denied")
                administration()

            restricted()
            print(f"PASS IPv{version}_GUARDED_DYNAMIC_MAINTENANCE_ANCHOR", flush=True)
            with r.armed(profile, maintenance, candidate, window="lifecycle") as (path, _):
                guard_seen = time.monotonic()
                original_handles = handles()
                ready = json.loads((path / "ready").read_text())
                r.invoke_controller(path, profile, "after")
                assert r.shape(profile) == candidate
                old = stack.enter_context(t.connect(peer, 443))
                assert t.exchange(old) and t.reaches(peer, 443)
                print(f"PASS IPv{version}_GUARDED_DYNAMIC_APPLIED_CONTROLLER_DEAD", flush=True)
                before = r.counters(version)
                if version == 4:
                    assert t.rpc(proc, "mode", "normal")
                    d.wait_for(lambda: any(e["kind"] == "renew" and e["answered"]
                               for e in t.rpc(proc, "events")), 18, administration)
                    assert r.counters(version)["link_in_dhcp"] > before["link_in_dhcp"]
                else:
                    start = time.monotonic()
                    d.wait_for(lambda: time.monotonic() > start + v.LIFETIME + 1,
                               v.LIFETIME + 3, administration)
                    assert r.counters(version)["in_ra"] > before["in_ra"]
                # Receipt is born before readiness. Waiting from observed ready
                # is conservative; the kernel lease must have expired by here.
                d.wait_for(lambda: time.monotonic() > guard_seen + lease.SECONDS + .2, 12, administration)
                assert r.shape(profile) == candidate and not (path / "result").exists()
                assert Path(f'/proc/{ready["pid"]}').exists()
                assert not t.exchange(old) and not t.reaches(peer, 443)
                assert handles() == original_handles
                r.neighbors(version, proc)
                administration()
                print(f"PASS IPv{version}_KERNEL_EXPIRY_REVOKES_DATA_PRESERVES_REFRESH_ADMIN_AND_NEIGHBORS", flush=True)
                d.wait_for(lambda: (path / "result").exists(), 25, administration)
                assert (path / "result").read_text() == "RESTORE_MAINTENANCE"
                assert r.shape(profile) == maintenance and handles() == original_handles
                assert not t.exchange(old) and not t.reaches(peer, 443)
                administration()
                print(f"PASS IPv{version}_PID1_RESTORES_AFTER_GUARD_EXPIRY_NO_REARM", flush=True)
            assert not path.exists() and not Path(f'/proc/{ready["pid"]}').exists()
            restricted()
            if version == 4:
                assert t.rpc(proc, "mode", "rebind")
                d.wait_for(lambda: d.lease_server(root) == d.ALTERNATE, 28, restricted)
                events = t.rpc(proc, "events")
                assert any(e["kind"] == "renew" and not e["answered"] for e in events)
                assert any(e["kind"] == "rebind" and e["answered"] for e in events)
                restricted()
            else:
                before = r.counters(version)["in_ra"]
                start = time.monotonic()
                d.wait_for(lambda: time.monotonic() > start + v.LIFETIME + 1,
                           v.LIFETIME + 3, restricted)
                assert r.counters(version)["in_ra"] > before
                assert t.rpc(proc, "ra", False) > 0
                d.wait_for(lambda: not v.route_present(), v.LIFETIME + 3)
                assert v.usable(v.CLIENT) and not v.routes() and t.rpc(proc, "expired")
                assert not t.reaches(peer, 443) and r.shape(profile) == maintenance
            assert handles() == original_handles
            print(f"PASS IPv{version}_POST_EXPIRY_REBIND_OR_RA_REFRESH_AND_EXPIRY", flush=True)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
        proc.stdin.close()
        proc.stdout.close()
        t.run(t.IP, "link", "del", "host0", success=False)
        for family, name in (*r.tables(profile), *lease.TABLES, ("inet", UNRELATED)):
            t.nft(f"delete table {family} {name}\n", success=False)
        r.empty()
    print(f"PASS IPv{version}_DYNAMIC_LEASE_UNITS_PROCESSES_LINKS_RULES_FILES_CLEANED", flush=True)


def kernel():
    guard()
    for version in (4, 6):
        case(version)
    print("RESULT SYNTHETIC_DYNAMIC_LEASE_OK_NO_LIVE_APPLY", flush=True)


class Tests(unittest.TestCase):
    def test_fixed_profile_tuples_and_both_layer_lease(self):
        for name, family, host, peer in (("dhcp4", "ip", d.CLIENT, d.PRIMARY), ("ra6", "ip6", v.CLIENT, v.REMOTE)):
            text = lease.install(3, name)
            self.assertEqual(text.count("create table"), 2)
            self.assertEqual(text.count("timeout 8s"), 2)
            self.assertEqual(text.count("@qualification return"), 4)
            self.assertEqual(text.count("counter drop"), 4)
            self.assertIn(f"{family} saddr {host} {family} daddr {peer}", text)
            self.assertNotIn("192.0.2.1 ", text)
            for bad in ("update", "ct state", "flowtable", "flush"):
                self.assertNotIn(bad, text)
        for bad in (None, [], "live", "192.0.2.2"):
            with self.assertRaises(ValueError):
                lease.install(3, bad)

    def test_guarded_aliases_preserve_base_policy_and_require_receipts(self):
        for version, profile in PROFILES.items():
            self.assertEqual(r.tables(profile), r.tables(version))
            for mode in ("maintenance", "qualification"):
                self.assertEqual(r.profile(profile, mode), r.profile(version, mode))
                self.assertNotIn("kc_lease_guard", r.replacement(profile, mode))
            with patch.object(r, "lease_reports", return_value=[]):
                with self.assertRaisesRegex(RuntimeError, "QUALIFICATION_GUARD_REQUIRED"):
                    r.require_lease({"version": profile})

    def test_host_namespace_and_opt_in_refused_before_commands(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), patch.object(os, "geteuid", return_value=0), patch.object(os, "readlink", return_value="same"), patch.object(t, "run") as run:
            with self.assertRaises(RuntimeError):
                kernel()
            run.assert_not_called()
        with patch.object(r, "guard"), patch.dict(os.environ, {"KC_DYNAMIC_LEASE_CI": "0"}), patch.object(t, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "OPT_IN_REQUIRED"):
                kernel()
            run.assert_not_called()


if __name__ == "__main__":
    if sys.argv[1:] == ["--systemd"]:
        kernel()
    else:
        unittest.main(verbosity=2)
