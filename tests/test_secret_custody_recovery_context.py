"""CI-only recovery identity and deterministic worker-loss boundary evidence.

Static synthetic traffic isolates identity/process faults from DHCP lifetimes.
The final-readiness/commit gap remains a tested BLOCKED outcome, not repaired.
"""
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

spec = importlib.util.spec_from_file_location("recovery", Path(__file__).with_name("test_secret_custody_dynamic_recovery.py"))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
t, d = r.t, r.d
UNRELATED = "kc_context_unrelated"
CHANGED_MAC = "02:00:00:00:01:77"
CASES = ("stable", "replacement", "mac-after-apply", "loss-before-final", "loss-after-final")


def guard():
    r.guard()
    if os.environ.get("KC_RECOVERY_CONTEXT_CI") != "1":
        raise RuntimeError("RECOVERY_CONTEXT_CI_OPT_IN_REQUIRED")


def blocked(reason):
    if reason not in ("RECOVERY_CONTEXT_CHANGED", "WORKER_LOST_BEFORE_APPLY", "WORKER_LOST_RECOVERY_UNVERIFIED"):
        raise ValueError("FIXED_BLOCKED_REASON_REQUIRED")
    return {"decision": "BLOCKED", "reason": reason, "qualification": False,
            "mutation": False, "apply_allowed": False, "freshness_verified": False}


def peer():
    guard()
    assert os.readlink("/proc/self/ns/net") != os.environ.get("FIXTURE_PARENT_NETNS")
    with ExitStack() as stack:
        old = None
        print("READY", flush=True)
        for line in sys.stdin:
            assert len(line) < 1024
            op = json.loads(line)
            if op == ["setup"]:
                t.run(t.IP, "link", "set", "lo", "up")
                t.run(t.IP, "link", "set", "peer0", "address", t.MAC_PEER, "addrgenmode", "none")
                t.run(t.IP, "addr", "add", d.PRIMARY + "/24", "dev", "peer0")
                t.run(t.IP, "link", "set", "peer0", "up")
                t.run(t.IP, "neigh", "replace", d.CLIENT, "lladdr", t.MAC_HOST, "nud", "permanent", "dev", "peer0")
                t.listen(stack, d.PRIMARY, 443)
                result = True
            elif op == ["open"]:
                old = stack.enter_context(t.connect(d.CLIENT, 22, d.PRIMARY))
                result = t.exchange(old)
            elif op == ["check"]:
                result = {"old": t.exchange(old), "new": t.reaches(d.CLIENT, 22, d.PRIMARY)}
            elif op == ["changed_mac"]:
                t.run(t.IP, "neigh", "replace", d.CLIENT, "lladdr", CHANGED_MAC, "nud", "permanent", "dev", "peer0")
                result = True
            else:
                raise ValueError("FIXED_PEER_OPERATION_REQUIRED")
            print(json.dumps(result), flush=True)


def close(proc):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
    for pipe in (proc.stdin, proc.stdout, proc.stderr):
        if pipe is not None:
            pipe.close()
    assert not Path(f"/proc/{proc.pid}").exists()


def held_controller(value, stage):
    guard()
    if stage not in ("loss-before-final", "loss-after-final"):
        raise ValueError("FIXED_CHECKPOINT_REQUIRED")
    path = r.w.directory(value)
    original = r.readiness
    calls = 0

    def check(*args):
        nonlocal calls
        original(*args)
        calls += 1
        if calls == (1 if stage == "loss-before-final" else 2):
            (path / "checkpoint").write_text(stage)
            assert r.w.await_file(path / "release", 2) == stage

    # Only this explicit CI child adds a deterministic scheduler barrier. The
    # ordinary controller and systemd worker have no barrier environment hook.
    with patch.object(r, "readiness", side_effect=check):
        r.controller(value, 4, "after")


def rejected_controller(path):
    result = subprocess.run([sys.executable, "-I", "-B", r.__file__, "--controller", str(path), "4", "after"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=4)
    assert result.returncode != 0 and b"RECOVERY_CONTEXT_CHANGED_STOP" in result.stderr, result.stderr[-1500:]
    assert not (path / "applied").exists()


def case(name):
    guard()
    parent = os.environ.get("CONTEXT_CASE_PARENT_NETNS")
    if name not in CASES or not parent or parent == os.readlink("/proc/self/ns/net"):
        raise RuntimeError("DISTINCT_CONTEXT_CASE_NAMESPACE_REQUIRED")
    r.empty()
    try:
        with ExitStack() as stack:
            proc = subprocess.Popen(["unshare", "--net", sys.executable, "-I", "-B", __file__, "--peer"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                env=dict(os.environ, FIXTURE_PARENT_NETNS=os.readlink("/proc/self/ns/net")))
            stack.callback(close, proc)
            assert t.read_line(proc).strip() == "READY"
            t.run(t.IP, "link", "add", "host0", "type", "veth", "peer", "name", "peer0")
            t.run(t.IP, "link", "set", "peer0", "netns", str(proc.pid))
            t.run(t.IP, "link", "set", "host0", "address", t.MAC_HOST, "addrgenmode", "none")
            t.run(t.IP, "addr", "add", d.CLIENT + "/24", "dev", "host0")
            t.run(t.IP, "link", "set", "host0", "up")
            t.run(t.IP, "link", "set", "lo", "up")
            t.run(t.IP, "neigh", "replace", d.PRIMARY, "lladdr", t.MAC_PEER, "nud", "permanent", "dev", "host0")
            assert t.rpc(proc, "setup")
            t.listen(stack, d.CLIENT, 22)
            assert t.rpc(proc, "open") and t.reaches(d.PRIMARY, 443)
            t.nft(r.profile(4, "maintenance"))
            maintenance = r.shape(4)
            t.nft(r.replacement(4, "qualification"))
            candidate = r.shape(4)
            t.nft(r.replacement(4, "maintenance"))
            t.nft(f"table inet {UNRELATED} {{ chain sentinel {{ counter drop; }}; }}\n")
            unrelated = r.table_shape("inet", UNRELATED)
            assert not t.reaches(d.PRIMARY, 443) and t.rpc(proc, "check") == {"old": True, "new": True}
            with r.armed(4, maintenance, candidate) as (path, unit):
                ready = json.loads((path / "ready").read_text())
                expected = json.loads((path / "expected.json").read_text())
                assert ready["binding"] == r.binding(expected)
                assert expected["context"] == r.recovery_context(4)
                r.readiness(path, expected)
                print("PASS CONTEXT_BOUND_STATIC_ADMIN_AND_RESTRICTED_ANCHOR", name, flush=True)
                if name == "stable":
                    r.invoke_controller(path, 4, "after")
                    old = stack.enter_context(t.connect(d.PRIMARY, 443))
                    assert t.exchange(old)
                    d.wait_for(lambda: (path / "result").exists(), 8)
                    assert (path / "result").read_text() == "RESTORE_MAINTENANCE"
                    assert r.shape(4) == maintenance and not t.exchange(old) and not t.reaches(d.PRIMARY, 443)
                    assert t.rpc(proc, "check") == {"old": True, "new": True}
                    print("PASS CONTEXT_STABLE_PID1_RESTORE_AND_OLD_NEW_REVOCATION", flush=True)
                elif name == "replacement":
                    t.run(t.IP, "link", "set", "host0", "down")
                    t.run(t.IP, "link", "set", "host0", "name", "prior0")
                    t.run(t.IP, "link", "add", "host0", "type", "veth", "peer", "name", "replacement0")
                    t.run(t.IP, "link", "set", "host0", "address", t.MAC_HOST, "addrgenmode", "none")
                    changed = r.recovery_context(4)
                    assert changed["interfaces"]["host0"]["ifindex"] != expected["context"]["interfaces"]["host0"]["ifindex"]
                    assert changed["interfaces"]["host0"]["address"] == t.MAC_HOST
                    print("RECOVERY_INTERFACE_REPLACEMENT", json.dumps({"before": expected["context"]["interfaces"]["host0"],
                        "after": changed["interfaces"]["host0"]}), flush=True)
                    before = r.shape(4)
                    rejected_controller(path)
                    d.wait_for(lambda: (path / "result").exists(), 8)
                    assert (path / "result").read_text() == "STOP_RECOVERY_CONTEXT_CHANGED"
                    assert r.shape(4) == before
                    print("PASS SAME_NAME_SAME_MAC_REPLACEMENT_REFUSED_NO_OVERWRITE", json.dumps(blocked("RECOVERY_CONTEXT_CHANGED")), flush=True)
                elif name == "mac-after-apply":
                    r.invoke_controller(path, 4, "after")
                    old = stack.enter_context(t.connect(d.PRIMARY, 443))
                    assert t.exchange(old)
                    t.run(t.IP, "link", "set", "host0", "address", CHANGED_MAC)
                    assert t.rpc(proc, "changed_mac")
                    assert r.shape(4) == candidate
                    d.wait_for(lambda: (path / "result").exists(), 8)
                    assert (path / "result").read_text() == "STOP_RECOVERY_CONTEXT_CHANGED"
                    assert r.shape(4) == candidate and t.exchange(old) and t.reaches(d.PRIMARY, 443)
                    print("PASS POST_APPLY_IDENTITY_DRIFT_BLOCKED_QUALIFICATION_STILL_ACTIVE", json.dumps(blocked("RECOVERY_CONTEXT_CHANGED")), flush=True)
                else:
                    controller = subprocess.Popen([sys.executable, "-I", "-B", __file__, "--held-controller", str(path), name],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    stack.callback(close, controller)
                    assert r.w.await_file(path / "checkpoint", 2) == name
                    t.run("/usr/bin/systemctl", "kill", "--signal=SIGKILL", unit)
                    d.wait_for(lambda: t.run("/usr/bin/systemctl", "show", unit, "--property=MainPID", "--value").stdout == b"0\n", 2)
                    assert not Path(f'/proc/{ready["pid"]}').exists()
                    assert not (path / "result").exists()
                    (path / "release").write_text(name)
                    _, error = controller.communicate(timeout=4)
                    if name == "loss-before-final":
                        assert controller.returncode != 0 and b"WATCHDOG_DEAD" in error, error[-1500:]
                        assert not (path / "applied").exists() and r.shape(4) == maintenance
                        assert not t.reaches(d.PRIMARY, 443) and t.rpc(proc, "check") == {"old": True, "new": True}
                        print("PASS WORKER_LOSS_AFTER_PREFLIGHT_FINAL_CHECK_REFUSES_APPLY", json.dumps(blocked("WORKER_LOST_BEFORE_APPLY")), flush=True)
                    else:
                        assert controller.returncode == -signal.SIGKILL, error[-1500:]
                        assert (path / "applied").read_text() == "after" and r.shape(4) == candidate
                        old = stack.enter_context(t.connect(d.PRIMARY, 443))
                        assert t.exchange(old)
                        d.wait_for(lambda: time.monotonic() > ready["deadline"] + 1, 8)
                        assert not (path / "result").exists() and r.shape(4) == candidate
                        assert t.exchange(old) and t.reaches(d.PRIMARY, 443)
                        assert t.rpc(proc, "check") == {"old": True, "new": True}
                        print("PASS LAST_CHECK_GAP_BLOCKED_NO_FALSE_RECOVERY_QUALIFICATION_ACTIVE", json.dumps(blocked("WORKER_LOST_RECOVERY_UNVERIFIED")), flush=True)
            assert not path.exists() and not Path(f'/proc/{ready["pid"]}').exists()
            assert r.table_shape("inet", UNRELATED) == unrelated
    finally:
        # Observing-fixture teardown, never represented as independent recovery.
        for interface in ("host0", "prior0"):
            t.run(t.IP, "link", "del", interface, success=False)
        for family, table in (*r.tables(4), ("inet", UNRELATED)):
            t.nft(f"delete table {family} {table}\n", success=False)
    r.empty()
    print("PASS CONTEXT_CASE_WORKER_CONTROLLER_PEER_LINKS_RULES_FILES_CLEANED", name, flush=True)


def kernel():
    guard()
    r.empty()
    print("KERNEL", os.uname().release, flush=True)
    for name in CASES:
        subprocess.run(["unshare", "--net", sys.executable, "-I", "-B", __file__, "--case", name],
            env=dict(os.environ, CONTEXT_CASE_PARENT_NETNS=os.readlink("/proc/self/ns/net")), timeout=45, check=True)
        r.empty()
    print("RESULT SYNTHETIC_RECOVERY_CONTEXT_OK_LAST_CHECK_GAP_UNQUALIFIED", flush=True)


class Tests(unittest.TestCase):
    def test_host_namespace_refused_before_commands(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), patch.object(os, "geteuid", return_value=0), patch.object(os, "readlink", return_value="same"), patch.object(t, "run") as run:
            with self.assertRaises(RuntimeError):
                kernel()
            run.assert_not_called()

    def test_explicit_opt_in_required(self):
        with patch.object(r, "guard"), patch.dict(os.environ, {"KC_RECOVERY_CONTEXT_CI": "0"}), patch.object(t, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "OPT_IN_REQUIRED"):
                kernel()
            run.assert_not_called()

    def test_distinct_case_namespace_required(self):
        with patch(__name__ + ".guard"), patch.object(os, "readlink", return_value="same"), patch.dict(os.environ, {"CONTEXT_CASE_PARENT_NETNS": "same"}), patch.object(t, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "DISTINCT_CONTEXT_CASE_NAMESPACE_REQUIRED"):
                case("stable")
            run.assert_not_called()

    def test_changed_boot_namespace_index_mac_or_missing_context_refused(self):
        expected = {"boot": "original", "netns": "ns1", "time_ns": "time:[1]", "interfaces": {"host0": {"ifindex": 2, "address": t.MAC_HOST, "kind": "veth"}}}
        variants = [dict(expected, boot="changed"), dict(expected, netns="ns2"), dict(expected, time_ns="time:[2]"), {}]
        for key, value in (("ifindex", 3), ("address", CHANGED_MAC), ("kind", "dummy")):
            variant = copy.deepcopy(expected)
            variant["interfaces"]["host0"][key] = value
            variants.append(variant)
        for variant in variants:
            with patch.object(r, "recovery_context", return_value=variant):
                with self.assertRaisesRegex(RuntimeError, "RECOVERY_CONTEXT_CHANGED_STOP"):
                    r.require_context({"version": 4, "context": expected})
        with patch.object(r, "recovery_context", side_effect=RuntimeError("read-failed")):
            with self.assertRaisesRegex(RuntimeError, "RECOVERY_CONTEXT_CHANGED_STOP"):
                r.require_context({"version": 4, "context": expected})

    def test_failed_final_check_prevents_nft_mutation(self):
        with patch.object(r, "shape", return_value=[]), patch.object(t, "nft") as mutate:
            with self.assertRaisesRegex(RuntimeError, "worker-lost"):
                r.transition(4, [], "qualification", verify=lambda: (_ for _ in ()).throw(RuntimeError("worker-lost")))
            mutate.assert_not_called()

    def test_guarded_rescue_binds_both_links_and_refuses_rescue_only_drift(self):
        links = {name: {"ifname": name, "ifindex": index, "address": mac,
                       "link_type": "ether", "linkinfo": {"info_kind": "veth"}}
                 for name, index, mac in (("host0", 2, t.MAC_HOST), ("rescue0", 4, "02:00:00:00:02:01"))}
        def report(*args):
            return subprocess.CompletedProcess(args, 0, stdout=json.dumps([links[args[-1]]]))
        with patch.object(t, "run", side_effect=report), patch.object(r.Path, "read_text", return_value="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"), patch.object(os, "readlink", return_value="net:[123]"):
            for version in ("rescue", "rescue-lease"):
                expected = r.recovery_context(version)
                self.assertEqual(set(expected["interfaces"]), {"host0", "rescue0"})
                data = {"version": version, "context": expected}
                r.require_context(data)
                for field, changed in (("ifindex", 6), ("address", CHANGED_MAC)):
                    original = links["rescue0"][field]
                    links["rescue0"][field] = changed
                    with self.assertRaisesRegex(RuntimeError, "RECOVERY_CONTEXT_CHANGED_STOP"):
                        r.require_context(data)
                    links["rescue0"][field] = original

    def test_other_attempt_or_context_cannot_reuse_readiness(self):
        data = {"version": 4, "attempt": "a" * 32, "context": {"boot": "a"}, "netns": "net:[2]"}
        with tempfile.TemporaryDirectory() as value:
            path = Path(value)
            for changed in ({}, dict(r.binding(data), attempt="b" * 32), dict(r.binding(data), context={"boot": "b"})):
                (path / "ready").write_text(json.dumps({"pid": 123, "start": "456", "deadline": time.monotonic() + 5, "boottime_deadline": r.boottime() + 5, "binding": changed}))
                with patch.object(os, "pidfd_open", return_value=7), patch.object(os, "close"), patch.object(r.select, "select", return_value=([], [], [])), patch.object(r, "process_start", return_value="456"), patch.object(os, "readlink", return_value=data["netns"]), patch.object(r, "require_context") as context:
                    with self.assertRaisesRegex(RuntimeError, "READINESS_BINDING_MISMATCH"):
                        r.readiness(path, data)
                    context.assert_not_called()

    def test_nonfinite_deadline_refused_before_process_probe(self):
        with tempfile.TemporaryDirectory() as value:
            path = Path(value)
            for deadline in (float("nan"), float("inf"), True):
                (path / "ready").write_text(json.dumps({"deadline": deadline}))
                with patch.object(os, "pidfd_open") as probe:
                    with self.assertRaisesRegex(RuntimeError, "WATCHDOG_NOT_ARMED"):
                        r.readiness(path, {})
                    probe.assert_not_called()

    def test_blocked_outcomes_never_enable_gates(self):
        for reason in ("RECOVERY_CONTEXT_CHANGED", "WORKER_LOST_BEFORE_APPLY", "WORKER_LOST_RECOVERY_UNVERIFIED"):
            value = blocked(reason)
            self.assertEqual(value["decision"], "BLOCKED")
            self.assertFalse(any(value[k] for k in ("qualification", "mutation", "apply_allowed", "freshness_verified")))


if __name__ == "__main__":
    if sys.argv[1:] == ["--systemd"]:
        kernel()
    elif sys.argv[1:] == ["--peer"]:
        peer()
    elif len(sys.argv) == 3 and sys.argv[1] == "--case":
        case(sys.argv[2])
    elif len(sys.argv) == 4 and sys.argv[1] == "--held-controller":
        held_controller(sys.argv[2], sys.argv[3])
    else:
        unittest.main(verbosity=2)
