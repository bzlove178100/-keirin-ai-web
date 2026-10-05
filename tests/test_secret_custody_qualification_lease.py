"""Real kernel expiry despite final-check worker loss and delayed stale apply."""
from contextlib import ExitStack
import copy
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
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
CASES = ("normal", "worker-loss", "delayed-apply", "identity-drift",
         "guarded-normal", "guarded-missing", "guarded-changed", "guarded-expired", "guarded-recreated")
RESTART_CASES = ("restart-before", "restart-after", "paused-worker")
CLOCK_CASES = ("clock-lease", "clock-readiness", "clock-namespace")
PREFIXES = ("192.0.2.", "2001:db8:1::")
UNRELATED = "kc_lease_unrelated"


def guard():
    r.guard()
    if os.environ.get("KC_QUALIFICATION_LEASE_CI") != "1":
        raise RuntimeError("QUALIFICATION_LEASE_CI_OPT_IN_REQUIRED")


def restart_guard():
    guard()
    if os.environ.get("KC_RECOVERY_RESTART_CI") != "1":
        raise RuntimeError("RECOVERY_RESTART_CI_OPT_IN_REQUIRED")


def clock_guard():
    guard()
    if os.environ.get("KC_SUSPEND_CLOCK_CI") != "1":
        raise RuntimeError("SUSPEND_CLOCK_CI_OPT_IN_REQUIRED")


def clock_controller(value, name):
    """Fixed CI-only clock fault, never a production environment hook."""
    clock_guard()
    if name not in CLOCK_CASES:
        raise ValueError("FIXED_CLOCK_CASE_REQUIRED")
    path = r.w.directory(value)
    data = json.loads((path / "expected.json").read_text())
    actual = os.readlink("/proc/self/ns/time")
    original = data["context"]["time_ns"]
    assert os.readlink("/proc/self/ns/net") == data["netns"]
    assert (actual != original) == (name == "clock-namespace")
    offset = {"clock-lease": 9, "clock-readiness": 23, "clock-namespace": 0}[name]
    print("CLOCK_FAULT", name, json.dumps({"prepared_time_ns": original, "observed_time_ns": actual,
          "monotonic": time.monotonic(), "boottime": r.boottime(),
          "injected_observer_boottime_offset": offset}), flush=True)
    if name == "clock-namespace":
        r.controller(value, "time-lease", "after")
    else:
        original_clock = r.boottime
        # Model elapsed suspended time in this observer only. The kernel clock,
        # original worker and guard remain real and unchanged in the parent.
        with patch.object(r, "boottime", side_effect=lambda: original_clock() + offset):
            r.controller(value, "time-lease", "after")


def clock_case(name, maintenance, candidate, administration):
    clock_guard()
    with r.armed("time-lease", maintenance, candidate, "lifecycle") as (path, _):
        data = json.loads((path / "expected.json").read_text())
        ready = json.loads((path / "ready").read_text())
        original = {f: (path / f).read_bytes() for f in ("expected.json", "ready", "worker.claim")}
        handles = guard_handles()
        r.readiness(path, data)
        print("PASS CLOCK_BOUND_DUAL_DEADLINES_AND_REAL_LIVE_GUARD", name, flush=True)
        command = [sys.executable, "-I", "-B", __file__, "--clock-controller", str(path), name]
        if name == "clock-namespace":
            command = ["unshare", "--time", "--fork"] + command
        result = subprocess.run(command, capture_output=True, timeout=4)
        expected = {"clock-lease": b"QUALIFICATION_GUARD_REQUIRED", "clock-readiness": b"WATCHDOG_NOT_ARMED",
                    "clock-namespace": b"RECOVERY_CONTEXT_CHANGED_STOP"}[name]
        assert result.returncode != 0 and expected in result.stderr, (result.stdout + result.stderr)[-2500:]
        assert b"CLOCK_FAULT" in result.stdout
        print(result.stdout.decode().strip(), flush=True)
        print("PASS CLOCK_STALE_CONTROLLER_REFUSED_BEFORE_APPLY", name, expected.decode(), flush=True)
        # The same unmodified preparation is STILL admissible in its actual
        # clock domain. Refusal is not explained by genuine eight-second expiry.
        r.readiness(path, data)
        assert r.process_start(ready["pid"]) == ready["start"]
        print("PASS CLOCK_ORIGINAL_DOMAIN_WORKER_AND_GUARD_STILL_LIVE", name, flush=True)
        assert all((path / f).read_bytes() == value for f, value in original.items())
        assert not (path / "applied").exists() and not (path / "result").exists()
        assert r.shape("time") == maintenance and guard_handles() == handles
        assert all(not t.reaches(p + "2", 443) for p in PREFIXES)
        administration()
        print("PASS CLOCK_NO_RULE_RECEIPT_REWRITE_ADMIN_PRESERVED", name, flush=True)
    assert not path.exists() and not Path(f'/proc/{ready["pid"]}').exists()


def restart_case(name, maintenance, candidate, administration, stack):
    restart_guard()
    with r.armed("time-lease", maintenance, candidate, "lifecycle") as (path, unit):
        seen = time.monotonic()
        ready = json.loads((path / "ready").read_text())
        data = json.loads((path / "expected.json").read_text())
        original = {f: (path / f).read_bytes() for f in ("ready", "worker.claim", "expected.json")}
        handles = guard_handles()
        r.readiness(path, data)
        print("PASS RESTART_BOUND_LIVE_GUARD_AND_SINGLE_WORKER_CLAIM", name, flush=True)
        old = []
        if name != "restart-before":
            r.invoke_controller(path, "time-lease", "after")
            old = [stack.enter_context(t.connect(p + "2", 443)) for p in PREFIXES]
            assert all(t.exchange(s) for s in old) and all(t.reaches(p + "2", 443) for p in PREFIXES)
        applied = (path / "applied").read_bytes() if (path / "applied").exists() else None
        if name == "paused-worker":
            t.run("/usr/bin/systemctl", "kill", "--signal=SIGSTOP", unit)
            d.wait_for(lambda: "State:\tT" in Path(f'/proc/{ready["pid"]}/status').read_text(), 2)
            assert r.process_start(ready["pid"]) == ready["start"]
            print("PASS WORKER_PROCESS_STOPPED_NOT_HOST_SUSPEND", name, flush=True)
        else:
            t.run("/usr/bin/systemctl", "kill", "--signal=SIGKILL", unit)
            d.wait_for(lambda: t.run("/usr/bin/systemctl", "show", unit, "--property=MainPID", "--value").stdout == b"0\n", 2)
            assert not Path(f'/proc/{ready["pid"]}').exists()
            # Type=exec may report a successful exec before the worker refuses.
            t.run("/usr/bin/systemctl", "restart", unit, success=False)
            def refused():
                state = t.run("/usr/bin/systemctl", "show", unit, "--property=MainPID,ActiveState,ExecMainStatus").stdout
                return all(v in state.splitlines() for v in (b"MainPID=0", b"ActiveState=failed", b"ExecMainStatus=1"))
            d.wait_for(refused, 3)
            log = t.run("/usr/bin/journalctl", "--no-pager", "-u", unit, "-n", "30").stdout
            assert b"WORKER_ATTEMPT_ALREADY_USED" in log, log[-2000:]
            # Prove replay was refused while the original guard was still live,
            # not merely because it had already expired or rules had changed.
            r.require_lease(data)
            rejected = subprocess.run([sys.executable, "-I", "-B", r.__file__, "--controller", str(path), "time-lease", "after"],
                                      capture_output=True, timeout=4)
            assert rejected.returncode != 0 and b"WATCHDOG_DEAD" in rejected.stderr, rejected.stderr[-1500:]
            assert ((path / "applied").read_bytes() if (path / "applied").exists() else None) == applied
            print("PASS WORKER_RESTART_REFUSED_LIVE_LEASE_OLD_READINESS_CANNOT_APPLY", name, flush=True)
        assert all((path / f).read_bytes() == value for f, value in original.items())
        d.wait_for(lambda: time.monotonic() > seen + lease.SECONDS + .2, 12, administration)
        assert r.shape("time") == (maintenance if name == "restart-before" else candidate)
        assert not (path / "result").exists()
        if name == "paused-worker":
            assert "State:\tT" in Path(f'/proc/{ready["pid"]}/status').read_text()
            assert r.process_start(ready["pid"]) == ready["start"]
        assert all(not t.exchange(s) for s in old) and all(not t.reaches(p + "2", 443) for p in PREFIXES)
        administration()
        assert guard_handles() == handles
        print("PASS RESTART_OLD_NEW_IPV4_IPV6_EXPIRED_ADMIN_PRESERVED", name, flush=True)
        if name == "paused-worker":
            d.wait_for(lambda: time.monotonic() > ready["deadline"] + .2, 16, administration)
            assert "State:\tT" in Path(f'/proc/{ready["pid"]}/status').read_text()
            assert not (path / "result").exists() and r.shape("time") == candidate
            t.run("/usr/bin/systemctl", "kill", "--signal=SIGCONT", unit)
            assert r.w.await_file(path / "result", 4) == "RESTORE_MAINTENANCE"
            assert r.shape("time") == maintenance
            print("PASS SAME_WORKER_RESUME_AFTER_ORIGINAL_DEADLINE_RESTORES_WITHOUT_REARM", name, flush=True)
        else:
            assert not Path(f'/proc/{ready["pid"]}').exists() and not (path / "result").exists()
            print("PASS RESTART_REFUSAL_DOES_NOT_CLAIM_MAINTENANCE_RECOVERY", name, flush=True)
        assert all((path / f).read_bytes() == value for f, value in original.items())
        assert guard_handles() == handles and all(not t.reaches(p + "2", 443) for p in PREFIXES)
        administration()
    assert not path.exists() and not Path(f'/proc/{ready["pid"]}').exists()


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



def guarded_case(name, maintenance, candidate, administration):
    with r.armed("time-lease", maintenance, candidate,
                 window="lifecycle" if name == "guarded-expired" else "short") as (path, unit):
        data = json.loads((path / "expected.json").read_text())
        r.readiness(path, data)
        print("PASS GUARDED_READY_WITH_OWNED_LIVE_LEASE", name, flush=True)
        if name == "guarded-missing":
            t.nft("delete table inet kc_lease_guard\n")
        elif name == "guarded-changed":
            t.nft("add rule inet kc_lease_guard output counter accept\n")
        elif name == "guarded-recreated":
            t.nft("".join(f"delete table {f} {n}\n" for f, n in lease.TABLES)
                  + lease.install(data["context"]["interfaces"]["host0"]["ifindex"]))
        elif name == "guarded-expired":
            d.wait_for(lambda: time.monotonic() > data["qualification_guard"]["deadline"] + .2, 10, administration)
        if name == "guarded-normal":
            r.invoke_controller(path, "time-lease", "after")
            assert r.shape("time-lease") == candidate
            assert all(t.reaches(p + "2", 443) for p in PREFIXES)
            assert r.w.await_file(path / "result", 7) == "RESTORE_MAINTENANCE"
            print("PASS GUARDED_APPLY_AND_RESTORE", name, flush=True)
        else:
            result = subprocess.run([sys.executable, "-I", "-B", r.__file__, "--controller", str(path), "time-lease", "after"],
                                    capture_output=True, timeout=4)
            assert result.returncode != 0 and b"QUALIFICATION_GUARD_REQUIRED" in result.stderr, result.stderr[-1500:]
            assert not (path / "applied").exists()
            print("PASS GUARDED_REFUSED_BEFORE_CANDIDATE_MUTATION", name, flush=True)
        assert r.shape("time-lease") == maintenance
        assert all(not t.reaches(p + "2", 443) for p in PREFIXES)
        administration()
        print("PASS GUARDED_MAINTENANCE_AND_ADMIN_PRESERVED", name, flush=True)

def case(name):
    guard()
    if name in RESTART_CASES:
        restart_guard()
    if name in CLOCK_CASES:
        clock_guard()
    parent = os.environ.get("LEASE_CASE_PARENT_NETNS")
    if name not in CASES + RESTART_CASES + CLOCK_CASES or not parent or parent == os.readlink("/proc/self/ns/net"):
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
            if name in CLOCK_CASES:
                clock_case(name, maintenance, candidate, administration)
                assert r.table_shape("inet", UNRELATED) == unrelated
                return
            if name in RESTART_CASES:
                restart_case(name, maintenance, candidate, administration, stack)
                assert r.table_shape("inet", UNRELATED) == unrelated
                return
            if name.startswith("guarded-"):
                guarded_case(name, maintenance, candidate, administration)
                assert r.table_shape("inet", UNRELATED) == unrelated
                return
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
        if name in RESTART_CASES + CLOCK_CASES:
            r.empty()
            label = "CLOCK" if name in CLOCK_CASES else "RESTART"
            print(f"PASS {label}_PROCESSES_LINKS_RULES_CLAIM_AND_PRIVATE_FILES_CLEANED", name, flush=True)
    r.empty()
    print("PASS LEASE_CASE_PROCESSES_LINKS_TABLES_PRIVATE_FILES_CLEANED", name, flush=True)


def kernel(restarts=False, clocks=False):
    guard()
    if type(restarts) is not bool:
        raise ValueError("FIXED_RESTART_MODE_REQUIRED")
    if type(clocks) is not bool or (clocks and restarts):
        raise ValueError("FIXED_CLOCK_MODE_REQUIRED")
    if restarts:
        restart_guard()
    if clocks:
        clock_guard()
    r.empty()
    print("KERNEL", os.uname().release, flush=True)
    for name in CLOCK_CASES if clocks else RESTART_CASES if restarts else CASES:
        subprocess.run(["unshare", "--net", sys.executable, "-I", "-B", __file__, "--case", name],
            env=dict(os.environ, LEASE_CASE_PARENT_NETNS=os.readlink("/proc/self/ns/net")), timeout=40, check=True)
        r.empty()
    label = "SUSPEND_CLOCK_ADMISSION" if clocks else "RECOVERY_RESTART" if restarts else "KERNEL_LEASE_REVOKED"
    print("RESULT SYNTHETIC_" + label + "_NO_LIVE_APPLY", flush=True)


class Tests(unittest.TestCase):
    def test_clock_case_requires_opt_in_and_fixed_mode_before_commands(self):
        with patch(__name__ + ".guard"), patch.dict(os.environ, {"KC_SUSPEND_CLOCK_CI": "0"}), patch.object(t, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "SUSPEND_CLOCK_CI_OPT_IN_REQUIRED"):
                kernel(clocks=True)
            with self.assertRaisesRegex(ValueError, "FIXED_CLOCK_MODE_REQUIRED"):
                kernel(clocks="yes")
            run.assert_not_called()

    def test_suspend_elapsed_boottime_expires_otherwise_live_guard_receipt(self):
        reports = self.sample_reports()
        receipt = {"binding": {}, "deadline": 108, "boottime_deadline": 208, "snapshot": lease.snapshot(reports)}
        lease.require(receipt, {}, reports, 101, boottime_now=201)
        for now in (207, 209, 199, None, True, float("inf"), float("nan")):
            with self.subTest(boottime=now), self.assertRaisesRegex(RuntimeError, "GUARD_REQUIRED"):
                lease.require(receipt, {}, reports, 101, boottime_now=now)
        for deadline in (None, True, float("inf"), float("nan")):
            with self.assertRaisesRegex(RuntimeError, "GUARD_REQUIRED"):
                lease.require(dict(receipt, boottime_deadline=deadline), {}, reports, 101, boottime_now=201)
        del receipt["boottime_deadline"]
        with self.assertRaisesRegex(RuntimeError, "GUARD_REQUIRED"):
            lease.require(receipt, {}, reports, 101, boottime_now=201)

    def test_missing_invalid_or_unavailable_suspend_clock_has_no_fallback(self):
        for value in (None, True, -1, float("nan"), float("inf")):
            with patch.object(time, "clock_gettime", return_value=value):
                with self.assertRaisesRegex(RuntimeError, "SUSPEND_AWARE_CLOCK_REQUIRED"):
                    r.boottime()
        with patch.object(time, "clock_gettime", side_effect=OSError("unavailable")):
            with self.assertRaisesRegex(RuntimeError, "SUSPEND_AWARE_CLOCK_REQUIRED"):
                r.boottime()
        with patch.object(r, "boottime", return_value=201), patch.object(time, "monotonic", return_value=101):
            with self.assertRaisesRegex(RuntimeError, "WATCHDOG_NOT_ARMED"):
                r.recovery_remaining({"deadline": 122})

    def test_modeled_suspend_makes_worker_restore_before_monotonic_deadline(self):
        with tempfile.TemporaryDirectory() as value:
            path = Path(value)
            (path / "lock").touch()
            data = {"version": "time-lease", "netns": "fixture", "window": "lifecycle", "attempt": "a" * 32,
                    "context": {}, "maintenance": [], "candidate": ["candidate"]}
            (path / "expected.json").write_text(json.dumps(data))
            with patch.object(r, "guard"), patch.object(r.w, "directory", return_value=path), patch.object(os, "getppid", return_value=1), patch.object(os, "readlink", return_value="fixture"), patch.object(r, "require_context"), patch.object(r, "require_lease"), patch.object(r, "shape", side_effect=[[], ["candidate"], ["candidate"], []]), patch.object(t, "nft") as mutate, patch.object(time, "monotonic", side_effect=[100, 100, 101, 101]), patch.object(r, "boottime", side_effect=[200, 223]), patch.object(time, "sleep") as sleep:
                r.worker(value, "time-lease")
                self.assertEqual((path / "result").read_text(), "RESTORE_MAINTENANCE")
                ready = json.loads((path / "ready").read_text())
                self.assertEqual((ready["deadline"], ready["boottime_deadline"]), (122, 222))
                mutate.assert_called_once()
                sleep.assert_not_called()

    def test_restart_requires_explicit_opt_in_before_commands(self):
        with patch(__name__ + ".guard"), patch.dict(os.environ, {"KC_RECOVERY_RESTART_CI": "0"}), patch.object(t, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "RECOVERY_RESTART_CI_OPT_IN_REQUIRED"):
                kernel(True)
            with self.assertRaisesRegex(ValueError, "FIXED_RESTART_MODE_REQUIRED"):
                kernel("yes")
            run.assert_not_called()

    def test_second_worker_cannot_replace_readiness_or_rebase_deadline(self):
        with tempfile.TemporaryDirectory() as value:
            path = Path(value)
            (path / "lock").touch()
            data = {"version": "time-lease", "netns": "fixture", "window": "lifecycle", "attempt": "a" * 32,
                    "context": {}, "maintenance": [], "candidate": ["candidate"]}
            (path / "expected.json").write_text(json.dumps(data))
            with patch.object(r, "guard"), patch.object(r.w, "directory", return_value=path), patch.object(os, "getppid", return_value=1), patch.object(os, "readlink", return_value="fixture"), patch.object(r, "require_context"), patch.object(r, "require_lease"), patch.object(r, "shape", return_value=[]), patch.object(r, "process_start", return_value="start"), patch.object(t, "nft") as mutate:
                with patch.object(os, "getpid", return_value=101), patch.object(time, "monotonic", side_effect=[100, 100, 130, 130]):
                    r.worker(value, "time-lease")
                original = {f: (path / f).read_bytes() for f in ("ready", "worker.claim", "result")}
                with patch.object(os, "getpid", return_value=202), patch.object(time, "monotonic", return_value=200):
                    with self.assertRaisesRegex(RuntimeError, "WORKER_ATTEMPT_ALREADY_USED"):
                        r.worker(value, "time-lease")
                self.assertEqual(original, {f: (path / f).read_bytes() for f in original})
                self.assertEqual(json.loads(original["ready"])["deadline"], 122)
                mutate.assert_not_called()

    def test_missing_partial_or_other_worker_claim_cannot_authorize_readiness(self):
        ready = {"pid": 101, "start": "one", "binding": {"attempt": "a"}, "deadline": 20}
        with tempfile.TemporaryDirectory() as value:
            path = Path(value)
            with self.assertRaisesRegex(RuntimeError, "WORKER_CLAIM_MISMATCH"):
                r.require_worker_claim(path, ready)
            for content in ("", "{", json.dumps({"pid": 202, "start": "two", "binding": ready["binding"]})):
                (path / "worker.claim").write_text(content)
                with self.assertRaisesRegex(RuntimeError, "WORKER_CLAIM_MISMATCH"):
                    r.require_worker_claim(path, ready)
                with self.assertRaisesRegex(RuntimeError, "WORKER_ATTEMPT_ALREADY_USED"):
                    r.claim_worker(path, {"attempt": "a" * 32, "version": "time", "context": {}})

    def sample_reports(self):
        reports = []
        for family, table in lease.TABLES:
            rows = [{"table": {"family": family, "name": table, "handle": 1}},
                    {"set": {"family": family, "table": table, "name": lease.SET,
                             "handle": 2, "type": "inet_service", "flags": ["timeout"],
                             "timeout": 8, "elem": [{"elem": {"val": 443, "expires": 7}}]}}]
            rows += [{"chain": {"family": family, "table": table, "handle": n}} for n in (3, 4)]
            rows += [{"rule": {"family": family, "table": table, "handle": n,
                              "expr": [{"counter": {"packets": 0, "bytes": 0}}, {"drop": None}]}}
                     for n in range(5, 11)]
            reports.append({"nftables": rows})
        return reports

    def test_receipt_expiry_binding_and_policy_drift(self):
        reports = self.sample_reports()
        receipt = {"binding": {"attempt": "one"}, "deadline": 18, "boottime_deadline": 18, "snapshot": lease.snapshot(reports)}
        lease.require(receipt, {"attempt": "one"}, reports, 12, boottime_now=12)
        for now in (17, float("nan"), True, 9):
            with self.assertRaisesRegex(RuntimeError, "GUARD_REQUIRED"):
                lease.require(receipt, receipt["binding"], reports, now, boottime_now=12)
        for bad in (None, {}, dict(receipt, binding={"attempt": "two"})):
            with self.assertRaises(RuntimeError):
                lease.require(bad, {"attempt": "one"}, reports, 12, boottime_now=12)
        for change in ("handle", "policy", "expired", "missing", "timeout"):
            bad = copy.deepcopy(reports)
            if change == "handle":
                bad[0]["nftables"][0]["table"]["handle"] = 100
            elif change == "policy":
                bad[0]["nftables"][-1]["rule"]["expr"][-1] = {"accept": None}
            elif change == "expired":
                bad[0]["nftables"][1]["set"]["elem"][0]["elem"]["expires"] = 0
            elif change == "timeout":
                bad[0]["nftables"][1]["set"]["timeout"] = 999
            else:
                bad[0]["nftables"][1]["set"]["elem"] = []
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                lease.require(receipt, receipt["binding"], bad, 12, boottime_now=12)
        reports[0]["nftables"][1]["set"]["elem"][0]["elem"]["expires"] = 4
        reports[0]["nftables"][-1]["rule"]["expr"][0]["counter"]["packets"] = 9
        lease.require(receipt, receipt["binding"], reports, 14, boottime_now=14)

    def test_guard_is_required_for_new_profile_only(self):
        with patch.object(r, "lease_reports", return_value=self.sample_reports()):
            with self.assertRaisesRegex(RuntimeError, "GUARD_REQUIRED"):
                r.require_lease({"version": "time-lease"})
            r.require_lease({"version": "time"})
        self.assertEqual(r.lease_module().SECONDS, lease.SECONDS)
        self.assertEqual(r.tables("time"), r.tables("time-lease"))
        for mode in ("maintenance", "qualification"):
            self.assertEqual(r.profile("time", mode), r.profile("time-lease", mode))

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
    elif sys.argv[1:] == ["--restart-systemd"]:
        kernel(True)
    elif sys.argv[1:] == ["--clock-systemd"]:
        kernel(clocks=True)
    elif sys.argv[1:] == ["--peer"]:
        peer()
    elif len(sys.argv) == 3 and sys.argv[1] == "--case":
        case(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "--held-controller":
        held_controller(sys.argv[2])
    elif len(sys.argv) == 4 and sys.argv[1] == "--clock-controller":
        clock_controller(sys.argv[2], sys.argv[3])
    else:
        unittest.main(verbosity=2)
