"""Restricted rescue under wrong shared allowances, isolated CI only.

The second static veth is independent of the tested primary DHCP/DNS/allowance
failure, not out-of-band from this kernel, namespace, or owned firewall tables.
"""
from contextlib import ExitStack
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("dhcp_dns", Path(__file__).with_name("test_secret_custody_dhcp_dns.py"))
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
z, r, d, t = h.z, h.r, h.d, h.t
HOST, PEER, OTHER = "198.51.100.1", "198.51.100.2", "198.51.100.3"
HOST_MAC, PEER_MAC = "02:00:00:00:02:01", "02:00:00:00:02:02"
UNRELATED = "kc_rescue_unrelated"


def guard():
    h.guard()
    r.guard()
    if os.environ.get("KC_RESTRICTED_RESCUE_CI") != "1":
        raise RuntimeError("RESTRICTED_RESCUE_CI_OPT_IN_REQUIRED")


def policy(mode):
    if mode not in ("maintenance", "qualification", "wrong-maintenance"):
        raise ValueError("FIXED_RESCUE_PROFILE_REQUIRED")
    # Rescue material is fixed independently of the deliberately corrupted
    # candidate and its ordinary fallback, never generated from observed peers.
    base = h.policy()
    if mode != "maintenance":
        base = "\n".join(line if "arp " in line else line.replace("192.0.2.2", "192.0.2.99").replace("192.0.2.3", "192.0.2.98") for line in base.splitlines()) + "\n"
        base += f'insert rule netdev {d.LINK_TABLE} egress meta protocol ip udp sport 68 udp dport 67 counter drop comment "rescue_blocked_dhcp"\n'
    # Static addresses/neighbors on this distinct link require no DHCP/DNS/ARP.
    for chain, direction, source, dest in (("input", "iifname", PEER, HOST), ("output", "oifname", HOST, PEER)):
        for port, state in (("dport", "{ new, established }"), ("sport", "established")):
            base += f'insert rule inet {d.TABLE} {chain} {direction} "rescue0" ip saddr {source} ip daddr {dest} tcp {port} 22 ct state {state} accept\n'
    for name, hook, source, dest, mac in (("rescue_in", "ingress", PEER, HOST, PEER_MAC), ("rescue_out", "egress", HOST, PEER, HOST_MAC)):
        base += f'add chain netdev {d.LINK_TABLE} {name} {{ type filter hook {hook} device "rescue0" priority 0; policy drop; }}\n'
        base += f'add rule netdev {d.LINK_TABLE} {name} meta protocol ip ip frag-off & 0x3fff != 0 counter drop\n'
        for port in ("dport", "sport"):
            base += f'add rule netdev {d.LINK_TABLE} {name} ether saddr {mac} meta protocol ip ip saddr {source} ip daddr {dest} tcp {port} 22 accept\n'
        base += f'add rule netdev {d.LINK_TABLE} {name} counter drop comment "{name}_deny"\n'
    if mode == "qualification":
        base += f'''insert rule inet {d.TABLE} input iifname "host0" ip saddr {d.PRIMARY} ip daddr {d.CLIENT} tcp sport 443 ct state established accept
insert rule inet {d.TABLE} output oifname "host0" ip saddr {d.CLIENT} ip daddr {d.PRIMARY} tcp dport 443 ct state {{ new, established }} accept
insert rule netdev {d.LINK_TABLE} ingress meta protocol ip ip saddr {d.PRIMARY} ip daddr {d.CLIENT} tcp sport 443 accept
insert rule netdev {d.LINK_TABLE} egress meta protocol ip ip saddr {d.CLIENT} ip daddr {d.PRIMARY} tcp dport 443 accept
'''
    return base


def replace(mode):
    return "".join(f"delete table {family} {name}\n" for family, name in r.tables("rescue")) + policy(mode)


def verdict(worker_result, shape, path, dependencies, revoked):
    checks = ((worker_result == "RESTORE_MAINTENANCE", "RESTORE_UNVERIFIED"),
              (shape, "SHAPE_UNVERIFIED"), (path, "RESCUE_PATH_UNAVAILABLE"),
              (dependencies, "DEPENDENCIES_UNVERIFIED"), (revoked, "QUALIFICATION_NOT_REVOKED"))
    failed = next((reason for value, reason in checks if value is not True), None)
    return {"decision": "BLOCKED" if failed else "CI_RESCUE_VERIFIED_REVIEW_ONLY",
            "reason": failed or "RESTRICTED_RESCUE_CHECKS_PASSED",
            "qualification": False, "mutation": False, "apply_allowed": False, "freshness_verified": False}


def peer():
    guard()
    assert os.readlink("/proc/self/ns/net") != os.environ.get("FIXTURE_PARENT_NETNS")
    with ExitStack() as stack:
        print("READY", flush=True)
        old = None
        for line in sys.stdin:
            assert len(line) < 1024
            op = json.loads(line)
            if op == ["setup"]:
                t.run(t.IP, "link", "set", "lo", "up")
                t.run(t.IP, "link", "set", "rescuepeer", "address", PEER_MAC, "addrgenmode", "none")
                for address in (PEER, OTHER):
                    t.run(t.IP, "addr", "add", address + "/29", "dev", "rescuepeer")
                t.run(t.IP, "link", "set", "rescuepeer", "up")
                t.run(t.IP, "neigh", "replace", HOST, "lladdr", HOST_MAC, "nud", "permanent", "dev", "rescuepeer")
                for port in (22, 2222):
                    t.listen(stack, PEER, port)
                result = True
            elif op == ["open"]:
                old = stack.enter_context(t.connect(HOST, 22, PEER))
                result = t.exchange(old)
            elif op == ["check"]:
                result = {"old": t.exchange(old), "new": t.reaches(HOST, 22, PEER)}
            elif op == ["other"]:
                result = {"source": t.reaches(HOST, 22, OTHER), "port": t.reaches(HOST, 2222, PEER)}
            else:
                raise ValueError("FIXED_RESCUE_RPC_REQUIRED")
            print(json.dumps(result), flush=True)


def spawn(stack, filename):
    proc = subprocess.Popen(["unshare", "--net", sys.executable, "-I", "-B", filename, "--peer"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
        env=dict(os.environ, FIXTURE_PARENT_NETNS=os.readlink("/proc/self/ns/net")))
    def close():
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
        proc.stdin.close()
        proc.stdout.close()
        assert not Path(f"/proc/{proc.pid}").exists()
    stack.callback(close)
    assert t.read_line(proc).strip() == "READY"
    return proc


def ready(res):
    d.wait_for(lambda: d.address_present() and d.default_route_present()
               and h.lease_dns(res) == d.PRIMARY and h.dns_values(res) == h.expected_dns(res, d.PRIMARY), 20, res.check)


def fresh(main, res):
    d.wait_for(lambda: res.active_transactions() == 0, 15, res.check)
    res.call("FlushCaches")
    before = len(t.rpc(main, "dns_events", d.PRIMARY))
    z.query()
    z.query(kind=28, tcp=True)
    assert len(t.rpc(main, "dns_events", d.PRIMARY)) >= before + 2


def denied(main, res, kind):
    assert t.rpc(main, "admin_state") == {"old": False, "new": False}
    res.call("FlushCaches")
    before = t.rpc(main, "dns_events", d.PRIMARY)
    active = res.active_transactions()
    drops = d.raw.counters("inet", d.TABLE)["dns_output_deny"]
    z.query(kind=kind, success=False)
    assert res.active_transactions() == active + 1
    assert d.raw.counters("inet", d.TABLE)["dns_output_deny"] > drops
    assert t.rpc(main, "dns_events", d.PRIMARY) == before


def case(broken):
    guard()
    z.y.empty()
    label = "BROKEN" if broken else "AVAILABLE"
    try:
        with ExitStack() as stack:
            main, rescue = spawn(stack, h.__file__), spawn(stack, __file__)
            for host, remote, proc, mac in (("host0", "peer0", main, t.MAC_HOST), ("rescue0", "rescuepeer", rescue, HOST_MAC)):
                t.run(t.IP, "link", "add", host, "type", "veth", "peer", "name", remote)
                t.run(t.IP, "link", "set", remote, "netns", str(proc.pid))
                t.run(t.IP, "link", "set", host, "address", mac, "addrgenmode", "none")
                t.run(t.IP, "link", "set", host, "up")
            t.run(t.IP, "link", "set", "lo", "up")
            t.run(t.IP, "addr", "add", HOST + "/29", "dev", "rescue0")
            t.run(t.IP, "neigh", "replace", PEER, "lladdr", PEER_MAC, "nud", "permanent", "dev", "rescue0")
            assert t.rpc(main, "setup") and t.rpc(rescue, "setup")
            for port in (22, 2222):
                t.listen(stack, "0.0.0.0", port)
            assert t.rpc(rescue, "open") and t.reaches(PEER, 22, HOST) and t.reaches(PEER, 2222, HOST)
            assert t.rpc(rescue, "other") == {"source": True, "port": True}
            assert t.rpc(main, "qualification_listener")
            t.nft(policy("maintenance"))
            maintenance = r.shape("rescue")
            t.nft(replace("qualification"))
            candidate = r.shape("rescue")
            t.nft(replace("maintenance"))
            t.nft(f"table inet {UNRELATED} {{ chain sentinel {{ counter drop; }} }}\n")
            unrelated = r.table_shape("inet", UNRELATED)
            with z.resolver(dhcp=True) as res:
                ready(res)
                original = h.stamp(res)["processes"]
                assert t.rpc(main, "open") and t.rpc(rescue, "open")
                fresh(main, res)
                assert t.rpc(rescue, "other") == {"source": False, "port": False}
                assert not t.reaches(PEER, 2222, HOST) and not t.reaches(d.PRIMARY, 443)
                print("PASS RESCUE_BASELINE_EXACT_STATIC_PATH_AND_REAL_DHCP_DNS", label, flush=True)
                if not broken:
                    t.nft(replace("qualification"))
                    denied(main, res, 1)
                    t.nft(replace("wrong-maintenance"))
                    denied(main, res, 28)
                    assert t.rpc(rescue, "check") == {"old": True, "new": True}
                    print("PASS SHARED_WRONG_CANDIDATE_AND_FALLBACK_BOTH_FAIL_PRIMARY", flush=True)
                    # Explicit setup reset, not an automatic unfiltered fallback.
                    t.nft(replace("maintenance"))
                    fresh(main, res)
                    assert t.rpc(main, "open")

                with r.armed("rescue", maintenance, candidate, "lifecycle") as (path, _):
                    worker_pid = json.loads((path / "ready").read_text())["pid"]
                    assert t.reaches(PEER, 22, HOST) and t.rpc(rescue, "check") == {"old": True, "new": True}
                    r.invoke_controller(path, "rescue", "after")
                    assert r.shape("rescue") == candidate
                    old = stack.enter_context(t.connect(d.PRIMARY, 443))
                    assert t.exchange(old)
                    epoch = t.rpc(main, "change", d.PRIMARY)
                    count = d.raw.counters("netdev", d.LINK_TABLE)["rescue_blocked_dhcp"]
                    denied(main, res, 1)
                    d.wait_for(lambda: d.raw.counters("netdev", d.LINK_TABLE)["rescue_blocked_dhcp"] > count, 12, res.check)
                    assert not any(e["epoch"] == epoch for e in t.rpc(main, "events"))
                    assert d.address_present() and not (path / "result").exists()
                    assert t.rpc(rescue, "check") == {"old": True, "new": True}
                    print("PASS CONTROLLER_DEAD_PRIMARY_ADMIN_DNS_AND_REAL_DHCP_DENIED", label, flush=True)
                    if broken:
                        t.run(t.IP, "link", "set", "rescue0", "down")
                        assert not t.reaches(PEER, 22, HOST)
                    d.wait_for(lambda: (path / "result").exists(), 25, res.check)
                    result = (path / "result").read_text()
                    assert result == "RESTORE_MAINTENANCE" and r.shape("rescue") == maintenance
                assert not path.exists() and not Path(f"/proc/{worker_pid}").exists()
                revoked = not t.exchange(old) and not t.reaches(d.PRIMARY, 443)
                assert revoked
                print("PASS PID1_RESTRICTED_RESCUE_SHAPE_AND_QUALIFICATION_REVOCATION", label, flush=True)
                d.wait_for(lambda: any(e["epoch"] == epoch and e["answered"] and e["kind"] in ("select", "renew", "rebind") for e in t.rpc(main, "events")), 20, res.check)
                ready(res)
                fresh(main, res)
                assert t.rpc(main, "open") and t.rpc(main, "check")
                assert h.stamp(res)["processes"] == original
                assert r.table_shape("inet", UNRELATED) == unrelated
                print("PASS RESCUE_REAL_DHCP_ACK_FRESH_DNS_AND_PRIMARY_ADMIN_RETURN", label, flush=True)
                transport = t.rpc(rescue, "check")
                available = t.reaches(PEER, 22, HOST) and transport == {"old": True, "new": True}
                assert available == (not broken)
                decision = verdict(result, r.shape("rescue") == maintenance, available, True, revoked)
                assert decision["decision"] == ("BLOCKED" if broken else "CI_RESCUE_VERIFIED_REVIEW_ONLY")
                if broken:
                    assert decision["reason"] == "RESCUE_PATH_UNAVAILABLE"
                assert not any(decision[k] for k in ("qualification", "mutation", "apply_allowed", "freshness_verified"))
                assert t.rpc(rescue, "other") == {"source": False, "port": False}
                assert not t.reaches(PEER, 2222, HOST)
                print("PASS RESCUE_VERDICT", label, json.dumps(decision, sort_keys=True), flush=True)
            print("PASS RESCUE_PRIVATE_DAEMONS_RUNTIME_AND_CGROUP_CLEANED", label, flush=True)
    finally:
        for interface in ("host0", "rescue0"):
            t.run(t.IP, "link", "del", interface, success=False)
        for family, name in (*r.tables("rescue"), ("inet", UNRELATED)):
            t.nft(f"delete table {family} {name}\n", success=False)
    z.y.empty()
    print("PASS RESCUE_PEERS_LINKS_AND_OWNED_RULES_CLEANED", label, flush=True)


def kernel():
    guard()
    print("KERNEL", os.uname().release, flush=True)
    for binary in (z.NETWORKD, z.DAEMON, z.BUS_DAEMON):
        print("CLIENT", binary, hashlib.sha256(Path(binary).read_bytes()).hexdigest(), flush=True)
    for broken in (False, True):
        case(broken)
    print("RESULT SYNTHETIC_RESTRICTED_RESCUE_OK_NO_LIVE_APPLY", flush=True)


class Tests(unittest.TestCase):
    def test_host_namespace_refused_before_commands(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), patch.object(os, "geteuid", return_value=0), patch.object(os, "readlink", return_value="same"), patch.object(t, "run") as run:
            with self.assertRaises(RuntimeError):
                kernel()
            run.assert_not_called()

    def test_explicit_rescue_opt_in_required(self):
        with patch.object(h, "guard"), patch.object(r, "guard"), patch.dict(os.environ, {"KC_RESTRICTED_RESCUE_CI": "0"}), patch.object(t, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "RESTRICTED_RESCUE_CI_OPT_IN_REQUIRED"):
                kernel()
            run.assert_not_called()

    def test_each_missing_proof_blocks_despite_shape_restoration(self):
        values = ["RESTORE_MAINTENANCE", True, True, True, True]
        for index in range(5):
            changed = values.copy()
            changed[index] = False
            result = verdict(*changed)
            self.assertEqual(result["decision"], "BLOCKED")
            self.assertFalse(any(result[k] for k in ("qualification", "mutation", "apply_allowed", "freshness_verified")))
        self.assertEqual(verdict(*values)["decision"], "CI_RESCUE_VERIFIED_REVIEW_ONLY")
        self.assertEqual(verdict(values[0], True, False, True, True)["reason"], "RESCUE_PATH_UNAVAILABLE")

    def test_fixed_profile_separates_rescue_from_shared_corruption(self):
        good, bad, fallback = policy("maintenance"), policy("qualification"), policy("wrong-maintenance")
        self.assertIn('ip saddr 192.0.2.2 tcp dport 22', good)
        for value in (bad, fallback):
            self.assertIn('ip saddr 192.0.2.99 tcp dport 22', value)
            self.assertIn('rescue_blocked_dhcp', value)
        self.assertNotIn('rescue_blocked_dhcp', good)
        self.assertNotIn('tcp dport 443', fallback)
        for value in (good, bad, fallback):
            self.assertIn('ip saddr 198.51.100.2 ip daddr 198.51.100.1 tcp dport 22', value)
            self.assertIn('device "rescue0" priority 0; policy drop;', value)
            self.assertNotIn('flush ruleset', value)
        self.assertEqual(r.profile("rescue", "maintenance"), good)
        self.assertEqual(r.profile("rescue", "qualification"), bad)
        self.assertEqual(r.tables("rescue"), r.tables(4))
        with self.assertRaises(ValueError):
            policy("unfiltered")


if __name__ == "__main__":
    if sys.argv[1:] == ["--systemd"]:
        kernel()
    elif sys.argv[1:] == ["--peer"]:
        peer()
    else:
        unittest.main(verbosity=2)
