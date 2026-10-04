"""Real kernel expiry despite final-check worker loss and delayed stale apply."""
from contextlib import ExitStack
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest
from unittest.mock import patch


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


HERE = Path(__file__).resolve().parent
c = module("context", HERE / "test_secret_custody_recovery_context.py")
r, t, d = c.r, c.t, c.d
lease = module("lease", HERE.parent / "review/secret_custody_qualification_lease.py")
CASES = ("normal", "worker-loss", "delayed-apply", "identity-drift")
PREFIXES = ("192.0.2.", "2001:db8:1::")
UNRELATED = "kc_lease_unrelated"


def guard():
    r.guard()
    if os.environ.get("KC_QUALIFICATION_LEASE_CI") != "1":
        raise RuntimeError("QUALIFICATION_LEASE_CI_OPT_IN_REQUIRED")


def peer():
    guard()
    assert os.readlink("/proc/self/ns/net") != os.environ.get("FIXTURE_PARENT_NETNS")
    with ExitStack() as stack:
        print("READY", flush=True)
        for line in sys.stdin:
            assert len(line) < 1024
            op = json.loads(line)
            if op == ["setup"]:
                t.run(t.IP, "link", "set", "peer0", "addrgenmode", "none")
                t.setup("peer0", t.MAC_PEER, ("2", "9"))
                for prefix in PREFIXES:
                    for suffix in ("2", "9"):
                        for port in (22, 443):
                            t.listen(stack, prefix + suffix, port)
            elif op == ["changed_mac"]:
                for flag, prefix in (("-4", PREFIXES[0]), ("-6", PREFIXES[1])):
                    t.run(t.IP, flag, "neigh", "replace", prefix + "1", "lladdr", c.CHANGED_MAC,
                          "nud", "permanent", "dev", "peer0")
            else:
                raise ValueError("FIXED_LEASE_PEER_OPERATION_REQUIRED")
            print("true", flush=True)


def held_controller(value):
    guard()
    path = r.w.directory(value)
    original = r.readiness
    calls = 0
    def check(*args):
        nonlocal calls
        original(*args)
        calls += 1
        if calls == 2:
            (path / "checkpoint").write_text("final")
            assert r.w.await_file(path / "release", 12) == "final"
    with patch.object(r, "readiness", side_effect=check):
        r.controller(value, "time", "after")


def guard_handles():
    result = {}
    for family, table in lease.TABLES:
        rows = json.loads(t.run(t.NFT, "-j", "list", "table", family, table).stdout)["nftables"]
        result[family] = [(kind, item["handle"]) for row in rows for kind, item in row.items()
                          if kind in ("table", "chain", "rule", "set")]
        sets = [row["set"] for row in rows if "set" in row]
        assert len(sets) == 1 and sets[0]["name"] == lease.SET and "timeout" in sets[0]["flags"]
    return result


def case(name):
    guard()
    parent = os.environ.get("LEASE_CASE_PARENT_NETNS")
    if name not in CASES or not parent or parent == os.readlink("/proc/self/ns/net"):
        raise RuntimeError("DISTINCT_LEASE_CASE_NAMESPACE_REQUIRED")
    r.empty()
    try:
        with ExitStack() as stack:
            proc = subprocess.Popen(["unshare", "--net", sys.executable, "-I", "-B", __file__, "--peer"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                env=dict(os.environ, FIXTURE_PARENT_NETNS=os.readlink("/proc/self/ns/net")))
            stack.callback(c.close, proc)
            assert t.read_line(proc).strip() == "READY"
            t.run(t.IP, "link", "add", "host0", "type", "veth", "peer", "name", "peer0")
            t.run(t.IP, "link", "set", "peer0", "netns", str(proc.pid))
            t.run(t.IP, "link", "set", "host0", "addrgenmode", "none")
            t.setup("host0", t.MAC_HOST, ("1",))
            assert t.rpc(proc, "setup")
            for prefix in PREFIXES:
                assert t.reaches(prefix + "2", 443) and t.reaches(prefix + "9", 443)
            t.nft(r.profile("time", "maintenance"))
            maintenance = r.shape("time")
            t.nft(r.replacement("time", "qualification"))
            candidate = r.shape("time")
            t.nft(r.replacement("time", "maintenance"))
            t.nft(f"table inet {UNRELATED} {{ chain sentinel {{ counter drop; }}; }}\n")
            unrelated = r.table_shape("inet", UNRELATED)
            admins = [stack.enter_context(t.connect(p + "2", 22)) for p in PREFIXES]
            def administration():
                assert all(t.exchange(s) for s in admins)
                assert all(t.reaches(p + "2", 22) for p in PREFIXES)
            administration()
            assert all(not t.reaches(p + "2", 443) for p in PREFIXES)
            ifindex = r.recovery_context("time")["interfaces"]["host0"]["ifindex"]
            # The lease is born before readiness, never in candidate/restore.
            t.nft(lease.install(ifindex))
            armed_at = time.monotonic()
            handles = guard_handles()
            print("PASS LEASE_RESTRICTED_ANCHOR_ADMIN_AND_KERNEL_GUARD", name, flush=True)
            with r.armed("time", maintenance, candidate, window="lifecycle" if name in ("worker-loss", "delayed-apply") else "short") as (path, unit):
                ready = json.loads((path / "ready").read_text())
                old = []
                if name in ("worker-loss", "delayed-apply"):
                    controller = subprocess.Popen([sys.executable, "-I", "-B", __file__, "--held-controller", str(path)],
                                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    stack.callback(c.close, controller)
                    assert r.w.await_file(path / "checkpoint", 2) == "final"
                    t.run("/usr/bin/systemctl", "kill", "--signal=SIGKILL", unit)
                    d.wait_for(lambda: t.run("/usr/bin/systemctl", "show", unit, "--property=MainPID", "--value").stdout == b"0\n", 2)
                    assert not Path(f'/proc/{ready["pid"]}').exists() and not (path / "result").exists()
                    if name == "delayed-apply":
                        d.wait_for(lambda: time.monotonic() > armed_at + lease.SECONDS + 0.2, 10, administration)
                    (path / "release").write_text("final")
                    _, error = controller.communicate(timeout=4)
                    assert controller.returncode == -signal.SIGKILL, error[-1500:]
                    assert (path / "applied").read_text() == "after"
                else:
                    r.invoke_controller(path, "time", "after")
                assert r.shape("time") == candidate
                if name != "delayed-apply":
                    old = [stack.enter_context(t.connect(p + "2", 443)) for p in PREFIXES]
                    assert all(t.exchange(s) for s in old)
                    assert all(t.reaches(p + "2", 443) for p in PREFIXES)
                else:
                    assert all(not t.reaches(p + "2", 443) for p in PREFIXES)
                assert all(not t.reaches(p + "9", 443) for p in PREFIXES)
                if name == "identity-drift":
                    t.run(t.IP, "link", "set", "host0", "address", c.CHANGED_MAC)
                    # NETDEV_CHANGEADDR flushes even permanent ARP/ND entries.
                    # Re-establish the static fixture transport deliberately;
                    # the changed MAC still causes the worker's context stop.
                    neighbours = json.loads(t.run(t.IP, "-j", "neigh", "show", "dev", "host0").stdout)
                    assert not any(n["dst"] in (p + "2" for p in PREFIXES) for n in neighbours)
                    print("LEASE_MAC_CHANGE_FLUSHED_STATIC_NEIGHBOURS", json.dumps(neighbours), flush=True)
                    for flag, prefix in (("-4", PREFIXES[0]), ("-6", PREFIXES[1])):
                        t.run(t.IP, flag, "neigh", "replace", prefix + "2", "lladdr", t.MAC_PEER,
                              "nud", "permanent", "dev", "host0")
                    assert t.rpc(proc, "changed_mac")
                print("PASS LEASE_CONTROLLER_DEAD_FAULT_APPLIED", name, flush=True)
                # Keep attempting traffic while time passes: established traffic
                # must NOT refresh the lease. The observer does no nft mutation.
                while time.monotonic() <= armed_at + lease.SECONDS + 0.2:
                    for sock in old:
                        t.exchange(sock)
                    administration()
                    time.sleep(0.05)
                if name in ("normal", "identity-drift"):
                    result = r.w.await_file(path / "result", 2)
                    assert result == ("RESTORE_MAINTENANCE" if name == "normal" else "STOP_RECOVERY_CONTEXT_CHANGED")
                else:
                    assert not (path / "result").exists() and not Path(f'/proc/{ready["pid"]}').exists()
                assert r.shape("time") == (maintenance if name == "normal" else candidate)
                assert all(not t.exchange(s) for s in old)
                assert all(not t.reaches(p + "2", 443) for p in PREFIXES)
                administration()
                assert guard_handles() == handles
                print("PASS LEASE_OLD_NEW_IPV4_IPV6_REVOKED_ADMIN_PRESERVED", name, flush=True)
                # Explicit stale/replay controls AFTER expiry, not recovery.
                assert t.nft(lease.install(ifindex), success=False).returncode != 0
                for _ in range(2):
                    t.nft(r.replacement("time", "qualification"))
                    assert r.shape("time") == candidate and guard_handles() == handles
                    assert all(not t.reaches(p + "2", 443) for p in PREFIXES)
                administration()
                print("PASS LEASE_REARM_REJECTED_CANDIDATE_REPLAY_CANNOT_REOPEN", name, flush=True)
            assert not path.exists() and not Path(f'/proc/{ready["pid"]}').exists()
            assert r.table_shape("inet", UNRELATED) == unrelated
    finally:
        t.run(t.IP, "link", "del", "host0", success=False)
        for family, table in (*r.tables("time"), *lease.TABLES, ("inet", UNRELATED)):
            t.nft(f"delete table {family} {table}\n", success=False)
    r.empty()
    print("PASS LEASE_CASE_PROCESSES_LINKS_TABLES_PRIVATE_FILES_CLEANED", name, flush=True)


def kernel():
    guard()
    r.empty()
    print("KERNEL", os.uname().release, flush=True)
    for name in CASES:
        subprocess.run(["unshare", "--net", sys.executable, "-I", "-B", __file__, "--case", name],
            env=dict(os.environ, LEASE_CASE_PARENT_NETNS=os.readlink("/proc/self/ns/net")), timeout=40, check=True)
        r.empty()
    print("RESULT SYNTHETIC_KERNEL_LEASE_REVOKED_NO_LIVE_APPLY", flush=True)


class Tests(unittest.TestCase):
    def test_scope_index_and_no_refresh_or_broad_established_bypass(self):
        for bad in (True, 0, -1, "3", 2**31):
            with self.assertRaises(ValueError):
                lease.install(bad)
        text = lease.install(3)
        self.assertEqual(text.count("create table"), 2)
        self.assertEqual(text.count("timeout 8s"), 2)
        self.assertEqual(text.count("gc-interval 1m"), 2)
        self.assertEqual(text.count("counter drop"), 4)
        self.assertEqual(text.count("@qualification return"), 8)
        self.assertIn("meta oif 3", text)
        self.assertIn("meta iif 3", text)
        for bad in ("update", "flush", "delete", "ct state", "flowtable", "add @"):
            self.assertNotIn(bad, text)

    def test_candidate_and_restore_do_not_own_or_reset_guard(self):
        for mode in ("maintenance", "qualification"):
            text = r.replacement("time", mode)
            for _, table in lease.TABLES:
                self.assertNotIn(table, text)

    def test_host_namespace_and_opt_in_guard_precede_commands(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), patch.object(os, "geteuid", return_value=0), patch.object(os, "readlink", return_value="same"), patch.object(t, "run") as run:
            with self.assertRaises(RuntimeError):
                kernel()
            run.assert_not_called()
        with patch.object(r, "guard"), patch.dict(os.environ, {"KC_QUALIFICATION_LEASE_CI": "0"}), patch.object(t, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "OPT_IN_REQUIRED"):
                kernel()
            run.assert_not_called()

    def test_distinct_case_namespace_required(self):
        with patch(__name__ + ".guard"), patch.object(os, "readlink", return_value="same"), patch.dict(os.environ, {"LEASE_CASE_PARENT_NETNS": "same"}), patch.object(t, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "DISTINCT_LEASE_CASE_NAMESPACE_REQUIRED"):
                case("normal")
            run.assert_not_called()


if __name__ == "__main__":
    if sys.argv[1:] == ["--systemd"]:
        kernel()
    elif sys.argv[1:] == ["--peer"]:
        peer()
    elif len(sys.argv) == 3 and sys.argv[1] == "--case":
        case(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "--held-controller":
        held_controller(sys.argv[2])
    else:
        unittest.main(verbosity=2)
