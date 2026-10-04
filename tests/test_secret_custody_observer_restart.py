"""Caller-bound observer restart/reuse rejection, disposable CI only."""
from contextlib import ExitStack
from copy import deepcopy
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

spec = importlib.util.spec_from_file_location("dhcp_dns", Path(__file__).with_name("test_secret_custody_dhcp_dns.py"))
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
z, r, d, t = h.z, h.r, h.d, h.t


def rejected(value, request, current, reason, now=None):
    try:
        h.consume(value, request, current, time.monotonic_ns() if now is None else now)
    except RuntimeError as exc:
        assert str(exc) == reason, str(exc)
    else:
        raise AssertionError("STALE_OBSERVATION_ACCEPTED")


def ready(res, expected_shape):
    def check():
        res.check()
        assert r.shape(4) == expected_shape
    d.wait_for(lambda: d.address_present() and d.default_route_present()
               and h.lease_dns(res) == d.PRIMARY and h.dns_values(res) == h.expected_dns(res, d.PRIMARY), 20, check)


def kernel():
    h.guard()
    z.y.empty()
    proc = subprocess.Popen(["unshare", "--net", sys.executable, "-I", "-B", h.__file__, "--peer"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
        env=dict(os.environ, FIXTURE_PARENT_NETNS=os.readlink("/proc/self/ns/net")))
    try:
        assert t.read_line(proc).strip() == "READY"
        t.run(t.IP, "link", "add", "host0", "type", "veth", "peer", "name", "peer0")
        t.run(t.IP, "link", "set", "peer0", "netns", str(proc.pid))
        t.run(t.IP, "link", "set", "host0", "addrgenmode", "none")
        t.run(t.IP, "link", "set", "host0", "address", t.MAC_HOST)
        t.run(t.IP, "link", "set", "host0", "up")
        t.run(t.IP, "link", "set", "lo", "up")
        assert t.rpc(proc, "setup")
        t.nft(h.policy())
        shape = r.shape(4)
        with ExitStack() as stack:
            t.listen(stack, "0.0.0.0", 22)
            with z.resolver(dhcp=True) as res:
                ready(res, shape)
                assert t.rpc(proc, "open")
                with h.collector(res) as (child, path, old_request):
                    old = h.completed(child, path, old_request, res)
                assert old["review"]["decision"] == "OBSERVATIONS_MATCH_REVIEW_ONLY"
                print("PASS OBSERVER_EXPECTED_IDENTITIES_BOUND_AT_COLLECTION_AND_CONSUMPTION", flush=True)

                with h.collector(res, pause=True) as (child, path, killed_request):
                    child.kill()
                    assert child.wait(timeout=2) == -signal.SIGKILL
                    partial = json.loads((path / "partial.json").read_text())
                    assert not (path / "complete.json").exists()
                    rejected(partial, killed_request, h.stamp(res), "OBSERVATION_COMPLETE_REQUIRED")
                with h.collector(res) as (child, path, restarted_request):
                    current = h.completed(child, path, restarted_request, res)
                    assert current["id"] != old["id"] and current["id"] != partial["id"]
                    assert restarted_request["collector"] != killed_request["collector"]
                    rejected(old, restarted_request, h.stamp(res), "OBSERVATION_ATTEMPT_MISMATCH")
                    rejected(partial, restarted_request, h.stamp(res), "OBSERVATION_COMPLETE_REQUIRED")
                assert t.rpc(proc, "check") and r.shape(4) == shape
                print("PASS OBSERVER_SIGKILL_RESTART_REJECTS_OLD_COMPLETE_AND_PARTIAL", flush=True)
            old_pids = [v["pid"] for v in old_request["expected"]["processes"].values()]
            assert all(not Path(f"/proc/{pid}").exists() for pid in old_pids)
            print("PASS OBSERVER_OLD_DAEMONS_AND_PRIVATE_RUNTIME_CLEANED", flush=True)

            with z.resolver(dhcp=True) as res:
                ready(res, shape)
                changed = h.stamp(res)
                assert h.identity(changed) != old_request["expected"]
                assert all(changed["processes"][name] != value
                           for name, value in old_request["expected"]["processes"].items())
                rejected(old, old_request, changed, "OBSERVATION_EXPECTED_IDENTITY_MISMATCH")
                with h.attempt(res, expected=old_request["expected"]) as (child, path, _):
                    _, error = child.communicate(timeout=6)
                    assert child.returncode != 0 and b"OBSERVATION_EXPECTED_IDENTITY_MISMATCH" in error, error
                    assert not any((path / name).exists() for name in ("partial.json", "complete.tmp", "complete.json"))
                print("PASS OBSERVER_REPLACED_DAEMONS_REJECT_OLD_EXPECTATION_AND_RESULT", flush=True)

                with h.collector(res) as (child, path, new_request):
                    new = h.completed(child, path, new_request, res)
                    rejected(old, new_request, h.stamp(res), "OBSERVATION_ATTEMPT_MISMATCH")
                    rejected(partial, new_request, h.stamp(res), "OBSERVATION_COMPLETE_REQUIRED")
                assert new["review"]["decision"] == "OBSERVATIONS_MATCH_REVIEW_ONLY"
                assert h.compare.compare(old["report"], new["report"])["decision"] == "OBSERVATIONS_MATCH_REVIEW_ONLY"
                res.call("FlushCaches")
                before = len(t.rpc(proc, "dns_events", d.PRIMARY))
                z.query()
                z.query(kind=28, tcp=True)
                assert len(t.rpc(proc, "dns_events", d.PRIMARY)) >= before + 2
                assert t.rpc(proc, "open") and t.rpc(proc, "check") and r.shape(4) == shape
                print("PASS OBSERVER_NEW_EXPECTATION_SAME_DNS_FACTS_FRESH_QUERIES_AND_ADMIN", flush=True)
        print("PASS OBSERVER_REPLACEMENT_DAEMONS_AND_PRIVATE_RUNTIME_CLEANED", flush=True)
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
        for family, name in r.tables(4):
            t.nft(f"delete table {family} {name}\n", success=False)
    z.y.empty()
    print("PASS OBSERVER_PEER_LINK_RULE_CLEANUP", flush=True)
    print("RESULT SYNTHETIC_OBSERVER_RESTART_IDENTITY_OK_NO_LIVE_APPLY", flush=True)


class Tests(unittest.TestCase):
    def setUp(self):
        self.current = {"boot": "boot", "processes": {"daemon": {"pid": 123, "start": "42",
            "exe": "/fixture", "net": "net:[1]", "mount": "mnt:[2]", "cgroup": "owned"}},
            "interface": [2, "host0", t.MAC_HOST], "bus": [1, 2], "files": {"lease": [1, 2, 3, "hash"]}}
        self.request = {"id": "a" * 32, "collector": {"pid": 456, "start": "43"},
                        "expected": h.identity(deepcopy(self.current)), "issued": 100}
        report = {"schema": "LOCAL_NETWORK_DEPENDENCIES_V1", "qualification": False, "mutation": False, "sections": {}}
        self.value = {"schema": "CI_DHCP_DNS_OBSERVATION_V2", "id": "a" * 32,
            "collector": {"pid": 456, "start": "43"}, "start": 101, "end": 110,
            "identity": deepcopy(self.current), "report": report, "review": h.compare.compare(report, report),
            "freshness_verified": False, "apply_allowed": False}

    def test_host_namespace_rejected_before_launch(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), patch.object(os, "geteuid", return_value=0), patch.object(os, "readlink", return_value="same"), patch.object(subprocess, "Popen") as launch:
            with self.assertRaises(RuntimeError):
                kernel()
            launch.assert_not_called()

    def test_valid_result_remains_review_only(self):
        self.assertIs(h.consume(self.value, self.request, self.current, 111), self.value)
        self.assertFalse(self.value["apply_allowed"])
        self.assertFalse(self.value["freshness_verified"])

    def test_partial_missing_and_legacy_results_rejected(self):
        for value in (None, {}, {"id": self.request["id"], "networkd": []}, {**self.value, "schema": "old"}):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                h.consume(value, self.request, self.current, 111)

    def test_old_attempt_and_reused_collector_pid_rejected(self):
        for field, replacement in (("id", "b" * 32), ("collector", {"pid": 456, "start": "44"})):
            value = deepcopy(self.value)
            value[field] = replacement
            rejected(value, self.request, self.current, "OBSERVATION_ATTEMPT_MISMATCH", 111)

    def test_daemon_same_pid_different_start_and_all_identity_fields_rejected(self):
        for field in self.current["processes"]["daemon"]:
            for target in ("current", "result"):
                current, value = deepcopy(self.current), deepcopy(self.value)
                (current if target == "current" else value["identity"])["processes"]["daemon"][field] = "changed"
                with self.subTest(field=field, target=target):
                    rejected(value, self.request, current, "OBSERVATION_EXPECTED_IDENTITY_MISMATCH", 111)
        for field in ("boot", "interface", "bus"):
            current = deepcopy(self.current)
            current[field] = "changed"
            rejected(self.value, self.request, current, "OBSERVATION_EXPECTED_IDENTITY_MISMATCH", 111)

    def test_lease_change_is_not_daemon_change_but_result_is_rejected(self):
        self.current["files"]["lease"][-1] = "new hash"
        h.require_identity(self.request["expected"], self.current)
        rejected(self.value, self.request, self.current, "OBSERVATION_CURRENT_BRACKET_CHANGED", 111)

    def test_stale_future_reversed_long_and_noninteger_times_rejected(self):
        for start, end, now in ((99, 110, 111), (101, 100, 111), (101, 112, 111),
                                (101, 110, 5_000_000_101), (101, 4_000_000_102, 4_000_000_103),
                                (True, 110, 111), (101, 110, 111.0)):
            value = {**self.value, "start": start, "end": end}
            rejected(value, self.request, self.current, "OBSERVATION_RESULT_EXPIRED_OR_INVALID_TIME", now)

    def test_gate_or_review_changes_rejected(self):
        for field in ("apply_allowed", "freshness_verified", "qualification", "mutation", "review"):
            value = deepcopy(self.value)
            if field in ("qualification", "mutation"):
                value["report"][field] = True
            else:
                value[field] = True
            rejected(value, self.request, self.current, "OBSERVATION_REVIEW_ONLY_REQUIRED", 111)


if __name__ == "__main__":
    if sys.argv[1:] == ["--systemd"]:
        kernel()
    else:
        unittest.main(verbosity=2)
