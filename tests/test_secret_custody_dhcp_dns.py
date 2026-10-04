"""Actual DHCPv4 DNS delivery and bounded observations in private CI only.

No SetLinkDNS, host reader, live endpoint, policy promotion or freshness claim.
Collection IDs bind one attempt, not a DHCP protocol generation or atomic view.
"""
from contextlib import ExitStack, contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


HERE = Path(__file__).resolve().parent
z = module("resolved", HERE / "test_secret_custody_resolved.py")
r, d, t = z.r, z.r.d, z.t
reader = module("reader", HERE.parent / "review/secret_custody_network_dependencies.py")
compare = module("compare", HERE.parent / "review/secret_custody_dns_reconciliation.py")


def guard():
    z.guard()
    z.dhcp_guard()


def dns_reply(data, kind, address):
    assert address in (d.PRIMARY, d.ALTERNATE)
    return d.reply(data, kind, d.PRIMARY)[:-1] + d.option(6, socket.inet_aton(address)) + b"\xff"


class DHCP(d.Server):
    def __init__(self):
        self.address, self.epoch = d.PRIMARY, 0
        super().__init__()

    def serve(self):
        try:
            while not self.stop.is_set():
                try:
                    data, ancillary, flags, source = self.sock.recvmsg(1600, 128)
                except socket.timeout:
                    continue
                if source[1] != 68 or flags & socket.MSG_TRUNC:
                    continue
                infos = [v for level, code, v in ancillary if level == socket.IPPROTO_IP and code == 8]
                assert len(infos) == 1
                index, _, dest = struct.unpack("=I4s4s", infos[0])
                try:
                    kind = d.classify(data, socket.inet_ntoa(dest))
                except ValueError:
                    continue
                with self.lock:
                    answer = self.mode == "normal"
                    payload = dns_reply(data, kind, self.address)
                    assert len(self.events) < 200
                    self.events.append({"kind": kind, "answered": answer, "dns": self.address, "epoch": self.epoch})
                if answer:
                    target = d.CLIENT if kind == "renew" else "255.255.255.255"
                    info = struct.pack("=I4s4s", index, socket.inet_aton(d.PRIMARY), d.ZERO)
                    self.sock.sendmsg([payload], [(socket.IPPROTO_IP, 8, info)], 0, (target, 68))
        except BaseException as exc:
            self.error = type(exc).__name__


def peer():
    guard()
    assert os.readlink("/proc/self/ns/net") != os.environ.get("FIXTURE_PARENT_NETNS")
    with ExitStack() as stack:
        print("READY", flush=True)
        server, old, servers = None, None, {}
        for line in sys.stdin:
            assert len(line) < 1024
            message = json.loads(line)
            op = message[0]
            if op == "setup":
                t.run(t.IP, "link", "set", "lo", "up")
                t.run(t.IP, "link", "set", "peer0", "address", t.MAC_PEER)
                for address in (d.PRIMARY, d.ALTERNATE):
                    t.run(t.IP, "addr", "add", address + "/24", "dev", "peer0")
                t.run(t.IP, "link", "set", "peer0", "up")
                server = DHCP()
                stack.callback(server.close)
                servers = {ip: z.Server(stack, ip) for ip in (d.PRIMARY, d.ALTERNATE)}
                result = True
            elif op == "change":
                assert message[1] in (d.PRIMARY, d.ALTERNATE, "silent")
                with server.lock:
                    server.epoch += 1
                    if message[1] == "silent":
                        server.mode = "silent"
                    else:
                        server.mode, server.address = "normal", message[1]
                    result = server.epoch
            elif op == "events":
                with server.lock:
                    assert server.error is None, server.error
                    result = list(server.events)
            elif op == "dns_events":
                assert message[1] in servers
                with servers[message[1]].lock:
                    result = list(servers[message[1]].events)
            elif op == "answer":
                assert message[1] in (0, 1)
                with servers[d.PRIMARY].lock:
                    servers[d.PRIMARY].generation = message[1]
                result = True
            elif op == "open":
                old = stack.enter_context(t.connect(d.CLIENT, 22, d.PRIMARY))
                result = t.exchange(old)
            elif op == "check":
                result = t.exchange(old) and t.reaches(d.CLIENT, 22, d.PRIMARY)
            elif op == "expired":
                result = not t.reaches(d.CLIENT, 22, d.PRIMARY)
            elif op == "flush_neighbors":
                t.run(t.IP, "neigh", "flush", "dev", "peer0")
                result = True
            else:
                raise RuntimeError("FIXED_OPERATION_REQUIRED")
            assert all(s.error is None for s in servers.values())
            print(json.dumps(result), flush=True)


def policy():
    # Keep the existing actual-ARP/DHCP bootstrap rules, remove unused NTP.
    text = (d.policy() + d.link_policy()).replace("{ 53, 123 }", "53")
    text += f'''insert rule inet {d.TABLE} input iifname "host0" ip saddr {d.PRIMARY} ip daddr {d.CLIENT} tcp sport 53 ct state established accept
insert rule inet {d.TABLE} output oifname "host0" ip saddr {d.CLIENT} ip daddr {d.PRIMARY} tcp dport 53 ct state {{ new, established }} accept
insert rule netdev {d.LINK_TABLE} ingress meta protocol ip ip saddr {d.PRIMARY} ip daddr {d.CLIENT} tcp sport 53 accept
insert rule netdev {d.LINK_TABLE} egress meta protocol ip ip saddr {d.CLIENT} ip daddr {d.PRIMARY} tcp dport 53 accept
add rule inet {d.TABLE} output counter drop comment "dns_output_deny"
'''
    return text


def dns_values(res):
    value = res.read()
    assert value is not None
    return reader.dns(json.dumps(value).encode())


def expected_dns(res, address):
    return [] if address is None else [{"index": res.index, "address": address,
        "port_zero_means_default": 0, "server_name": ""}]


def network_values(res):
    result = res.bus("org.freedesktop.network1.Manager", "Describe", networkd=True)
    assert len(result.stdout) < 65536
    return [v for v in reader.networkd(result.stdout) if v["interface"] == "host0"]


def lease_dns(res):
    path = res.root / f"run/systemd/netif/leases/{res.index}"
    if not path.exists():
        return None
    text = path.read_text()
    assert len(text) < 8192
    entries = [line[4:] for line in text.splitlines() if line.startswith("DNS=")]
    return entries[0] if len(entries) == 1 else None


def stamp(res):
    res.check()
    processes = {}
    for name, pid in {"wrapper": res.pid, **res.children}.items():
        processes[name] = {"pid": pid, "start": r.process_start(pid),
            "exe": os.readlink(f"/proc/{pid}/exe"), "net": os.readlink(f"/proc/{pid}/ns/net"),
            "mount": os.readlink(f"/proc/{pid}/ns/mnt"), "cgroup": Path(f"/proc/{pid}/cgroup").read_text()}
    link = json.loads(t.run(t.IP, "-j", "link", "show", "dev", "host0").stdout)
    assert len(link) == 1 and link[0]["ifindex"] == res.index and link[0]["address"] == t.MAC_HOST
    files = {}
    for name in (f"systemd/netif/leases/{res.index}", f"systemd/netif/links/{res.index}"):
        path = res.root / "run" / name
        if path.exists():
            value = path.read_bytes()
            assert len(value) < 16384
            st = path.stat()
            files[name] = [st.st_dev, st.st_ino, st.st_mtime_ns, hashlib.sha256(value).hexdigest()]
        else:
            files[name] = None
    bus = (res.root / z.BUS.lstrip("/")).stat()
    return {"boot": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
            "processes": processes, "interface": [res.index, "host0", t.MAC_HOST],
            "bus": [bus.st_dev, bus.st_ino], "files": files}


def finish(before, after, start, end, first_dns, last_dns):
    if before != after:
        raise RuntimeError("OBSERVATION_IDENTITY_OR_LEASE_CHANGED")
    if not 0 <= end - start <= 4_000_000_000:
        raise RuntimeError("OBSERVATION_WINDOW_EXCEEDED")
    if first_dns != last_dns:
        raise RuntimeError("OBSERVATION_SOURCE_CHANGED")


def collect(directory):
    guard()
    path = Path(directory)
    assert path.parent == Path("/tmp") and re.fullmatch(r"kc-dhcp-dns-observe-[a-z0-9_]+", path.name)
    assert stat.S_ISDIR(path.lstat().st_mode) and path.stat().st_uid == 0 and path.stat().st_mode & 0o777 == 0o700
    data = (path / "request.json").read_bytes()
    assert len(data) < 4096
    request = json.loads(data)
    assert re.fullmatch(r"[0-9a-f]{32}", request["id"])
    assert set(request["children"]) == {"bus", "daemon", "networkd"}
    assert all(type(p) is int and p > 1 for p in [request["pid"], *request["children"].values()])
    res = z.Resolver(request["pid"], request["children"])
    started = time.monotonic_ns()
    before = stamp(res)
    first_dns = dns_values(res)
    net = network_values(res)
    (path / "partial.json").write_text(json.dumps({"id": request["id"], "networkd": net}))
    if request["pause"]:
        d.wait_for(lambda: (path / "release").exists(), 25)
    last_dns = dns_values(res)
    fallback = reader.dns(res.bus("org.freedesktop.DBus.Properties", "Get", "ss", "org.freedesktop.resolve1.Manager", "FallbackDNSEx").stdout)
    addresses = reader.addresses(t.run(t.IP, "-j", "address", "show", "dev", "host0").stdout)
    after = stamp(res)
    ended = time.monotonic_ns()
    finish(before, after, started, ended, first_dns, last_dns)
    parts = {"addresses": addresses, "dns": last_dns, "dns_fallback": fallback, "networkd": net}
    report = {"schema": "LOCAL_NETWORK_DEPENDENCIES_V1", "qualification": False, "mutation": False,
              "sections": {k: {"status": "observed", "count": len(v), "private_values": v} for k, v in parts.items()}}
    result = {"id": request["id"], "collector": os.getpid(), "start": started, "end": ended,
              "identity": before, "report": report, "review": compare.compare(report, report),
              "freshness_verified": False, "apply_allowed": False}
    (path / "complete.tmp").write_text(json.dumps(result))
    (path / "complete.tmp").replace(path / "complete.json")


@contextmanager
def collector(res, pause=False):
    guard()
    with tempfile.TemporaryDirectory(prefix="kc-dhcp-dns-observe-", dir="/tmp") as directory:
        path = Path(directory)
        generation = uuid.uuid4().hex
        (path / "request.json").write_text(json.dumps({"id": generation, "pid": res.pid, "children": res.children, "pause": pause}))
        proc = subprocess.Popen([sys.executable, "-I", "-B", __file__, "--collect", directory], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            d.wait_for(lambda: (path / "partial.json").exists() or proc.poll() is not None, 5)
            if not (path / "partial.json").exists():
                raise AssertionError(proc.communicate(timeout=1))
            assert json.loads((path / "partial.json").read_text())["id"] == generation
            yield proc, path, generation
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=2)
            proc.stdout.close()
            proc.stderr.close()
    assert not path.exists()


def observation(res):
    with collector(res) as (proc, path, generation):
        out, error = proc.communicate(timeout=6)
        assert proc.returncode == 0, (out, error)
        value = json.loads((path / "complete.json").read_text())
        assert value["id"] == generation and value["collector"] == proc.pid
        assert value["freshness_verified"] is False and value["apply_allowed"] is False
        print("OBSERVATION", generation, value["end"] - value["start"],
              value["review"]["reason"], hashlib.sha256(json.dumps(value["identity"], sort_keys=True).encode()).hexdigest(), flush=True)
        return value


def accepted(proc, epoch, address):
    return any(e["epoch"] == epoch and e["answered"] and e["kind"] == "renew" and e["dns"] == address for e in t.rpc(proc, "events"))


def kernel():
    guard()
    z.y.empty()
    print("KERNEL", os.uname().release, flush=True)
    print(t.run(z.NETWORKD, "--version").stdout.decode(), flush=True)
    for binary in (z.NETWORKD, z.DAEMON, z.BUS_DAEMON):
        print("CLIENT", binary, hashlib.sha256(Path(binary).read_bytes()).hexdigest(), flush=True)
    proc = subprocess.Popen(["unshare", "--net", sys.executable, "-I", "-B", __file__, "--peer"], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, text=True, env=dict(os.environ, FIXTURE_PARENT_NETNS=os.readlink("/proc/self/ns/net")))
    try:
        assert t.read_line(proc).strip() == "READY"
        t.run(t.IP, "link", "add", "host0", "type", "veth", "peer", "name", "peer0")
        t.run(t.IP, "link", "set", "peer0", "netns", str(proc.pid))
        t.run(t.IP, "link", "set", "host0", "addrgenmode", "none")
        t.run(t.IP, "link", "set", "host0", "address", t.MAC_HOST)
        t.run(t.IP, "link", "set", "host0", "up")
        t.run(t.IP, "link", "set", "lo", "up")
        assert t.rpc(proc, "setup")
        # Prove both synthetic DNS endpoints before restrictions/networkd.
        t.run(t.IP, "addr", "add", d.CLIENT + "/24", "dev", "host0")
        for endpoint in (d.PRIMARY, d.ALTERNATE):
            z.query(endpoint=endpoint)
            z.query(kind=28, tcp=True, endpoint=endpoint)
        t.run(t.IP, "addr", "del", d.CLIENT + "/24", "dev", "host0")
        t.run(t.IP, "neigh", "flush", "dev", "host0")
        assert t.rpc(proc, "flush_neighbors")
        print("PASS DHCP_DNS_UNFILTERED_BOTH_UPSTREAMS", flush=True)
        t.nft(policy())
        shape = r.shape(4)
        with ExitStack() as stack:
            t.listen(stack, "0.0.0.0", 22)
            res = stack.enter_context(z.resolver(dhcp=True))
            def check():
                res.check()
                assert r.shape(4) == shape
            d.wait_for(lambda: d.address_present() and d.default_route_present() and lease_dns(res) == d.PRIMARY
                       and dns_values(res) == expected_dns(res, d.PRIMARY), 20, check)
            original = stamp(res)
            assert t.rpc(proc, "open")
            assert d.link_counters()["link_in_arp"] > 0 and d.link_counters()["link_out_arp"] > 0
            print("PASS REAL_DHCP_DNS_LEASE_ARP_PRIVATE_RESOLVER_DELIVERY", flush=True)
            initial = observation(res)
            assert initial["review"]["decision"] == "OBSERVATIONS_MATCH_REVIEW_ONLY", initial["report"]
            dns_facts = [x for v in network_values(res) for x in v["observations"] if x["kind"] == "DNS"]
            assert dns_facts == [{"kind": "DNS", "source": "DHCPv4", "Address": d.PRIMARY, "ConfigProvider": d.PRIMARY}], dns_facts
            print("PASS ACTUAL_DNS_ORIGIN_AGREEMENT_IDENTITY_AND_COLLECTION_BINDING", flush=True)
            before = len(t.rpc(proc, "dns_events", d.PRIMARY))
            z.query()
            z.query(kind=28, tcp=True)
            assert len(t.rpc(proc, "dns_events", d.PRIMARY)) >= before + 2
            print("PASS DHCP_CONFIGURED_STUB_A_AAAA_AND_TCP", flush=True)

            with collector(res, pause=True) as (child, path, _):
                child.kill()
                assert child.wait(timeout=2) == -signal.SIGKILL
                assert (path / "partial.json").exists() and not (path / "complete.json").exists()
                assert t.rpc(proc, "check")
                check()
            print("PASS SIGKILL_PARTIAL_OBSERVATION_NEVER_COMPLETES", flush=True)

            with collector(res, pause=True) as (child, path, _):
                epoch = t.rpc(proc, "change", d.ALTERNATE)
                d.wait_for(lambda: accepted(proc, epoch, d.ALTERNATE) and lease_dns(res) == d.ALTERNATE
                           and dns_values(res) == expected_dns(res, d.ALTERNATE), 18, check)
                (path / "release").touch()
                _, error = child.communicate(timeout=5)
                assert child.returncode != 0 and b"OBSERVATION_IDENTITY_OR_LEASE_CHANGED" in error, error
                assert not (path / "complete.json").exists()
            print("PASS REAL_RENEWAL_DURING_COLLECTION_REJECTS_MIXED_OBSERVATION", flush=True)
            changed = observation(res)
            result = compare.compare(initial["report"], changed["report"])
            assert result["decision"] == "CHANGE_REVIEW_REQUIRED", result
            assert not any(result[k] for k in ("qualification", "mutation", "apply_allowed", "freshness_verified"))
            print("PASS DHCP_CHANGED_DNS_REQUIRES_REVIEW_WITH_ALL_GATES_FALSE", flush=True)

            res.call("FlushCaches")
            unapproved = t.rpc(proc, "dns_events", d.ALTERNATE)
            drops = d.raw.counters("inet", d.TABLE)["dns_output_deny"]
            z.query(success=False)
            assert d.raw.counters("inet", d.TABLE)["dns_output_deny"] > drops
            assert t.rpc(proc, "dns_events", d.ALTERNATE) == unapproved
            assert t.rpc(proc, "check")
            check()
            print("PASS DHCP_UNAPPROVED_DNS_DENIED_WITHOUT_POLICY_EXPANSION", flush=True)

            epoch = t.rpc(proc, "change", d.PRIMARY)
            assert t.rpc(proc, "answer", 1)
            d.wait_for(lambda: accepted(proc, epoch, d.PRIMARY) and lease_dns(res) == d.PRIMARY
                       and dns_values(res) == expected_dns(res, d.PRIMARY), 18, check)
            d.wait_for(lambda: res.active_transactions() == 0, 15, check)
            res.call("FlushCaches")
            before = len(t.rpc(proc, "dns_events", d.PRIMARY))
            z.query(generation=1)
            z.query(kind=28, generation=1, tcp=True)
            assert len(t.rpc(proc, "dns_events", d.PRIMARY)) >= before + 2
            restored = observation(res)
            assert compare.compare(initial["report"], restored["report"])["decision"] == "OBSERVATIONS_MATCH_REVIEW_ONLY"
            assert len({initial["id"], changed["id"], restored["id"]}) == 3
            assert stamp(res)["processes"] == original["processes"]
            assert t.rpc(proc, "check")
            check()
            print("PASS DHCP_APPROVED_RETURN_FRESH_ANSWERS_SAME_DAEMONS_AND_ADMIN", flush=True)

            t.rpc(proc, "change", "silent")
            d.wait_for(lambda: not d.address_present() and not d.default_route_present()
                       and lease_dns(res) is None and dns_values(res) == [], d.LEASE + 8, check)
            expired = observation(res)
            assert expired["review"]["decision"] == "BLOCKED" and expired["review"]["reason"] == "EMPTY_RESOLVER_SET"
            assert t.rpc(proc, "expired")
            res.call("FlushCaches")
            before = {ip: t.rpc(proc, "dns_events", ip) for ip in (d.PRIMARY, d.ALTERNATE)}
            z.query(success=False)
            assert before == {ip: t.rpc(proc, "dns_events", ip) for ip in before}
            check()
            print("PASS LEASE_EXPIRY_WITHDRAWS_DNS_ADDRESS_ROUTE_AND_BLOCKS_REVIEW", flush=True)
        print("PASS DHCP_RESOLVED_BUS_PROCESSES_CGROUP_AND_PRIVATE_FILES_CLEANED", flush=True)
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
    print("PASS DHCP_DNS_PEER_LINK_RULE_CLEANUP", flush=True)
    print("RESULT SYNTHETIC_DHCP_DNS_OBSERVATION_OK_NO_LIVE_APPLY", flush=True)


class Tests(unittest.TestCase):
    def test_host_namespace_rejected_before_commands(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), patch.object(os, "geteuid", return_value=0), patch.object(os, "readlink", return_value="same"), patch.object(t, "run") as run:
            with self.assertRaises(RuntimeError):
                kernel()
            run.assert_not_called()

    def test_dhcp_opt_in_before_daemon_launch(self):
        with patch.object(z, "guard"), patch.object(d, "guard"), patch.dict(os.environ, {"KC_DHCP_DNS_CI": "0"}), patch.object(subprocess, "Popen") as launch:
            with self.assertRaisesRegex(RuntimeError, "DHCP_DNS_CI_OPT_IN_REQUIRED"):
                with z.resolver(dhcp=True):
                    pass
            launch.assert_not_called()

    def test_dhcp_option_six_fixed_address_and_lease_preserved(self):
        data = bytearray(240)
        data[4:8] = b"TEST"
        for address in (d.PRIMARY, d.ALTERNATE):
            payload = dns_reply(data, "renew", address)
            self.assertEqual(payload[:240], d.reply(data, "renew", d.PRIMARY)[:240])
            self.assertEqual(payload[-7:], bytes((6, 4)) + socket.inet_aton(address) + b"\xff")
            self.assertIn(d.option(51, struct.pack("!I", d.LEASE)), payload)
        with self.assertRaises(AssertionError):
            dns_reply(data, "renew", "8.8.8.8")

    def test_changed_identity_or_lease_cannot_complete(self):
        for key in ("boot", "pid_start", "netns", "mount", "bus", "interface", "lease"):
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, "IDENTITY_OR_LEASE_CHANGED"):
                finish({key: 1}, {key: 2}, 0, 1, [], [])

    def test_monotonic_window_and_changed_sources_rejected(self):
        finish({}, {}, 1, 4_000_000_001, [], [])
        for start, end in ((2, 1), (0, 4_000_000_001)):
            with self.assertRaisesRegex(RuntimeError, "WINDOW_EXCEEDED"):
                finish({}, {}, start, end, [], [])
        with self.assertRaisesRegex(RuntimeError, "SOURCE_CHANGED"):
            finish({}, {}, 0, 1, [1], [2])


if __name__ == "__main__":
    if sys.argv[1:] == ["--systemd"]:
        kernel()
    elif sys.argv[1:] == ["--peer"]:
        peer()
    elif len(sys.argv) == 3 and sys.argv[1] == "--collect":
        collect(sys.argv[2])
    else:
        unittest.main(verbosity=2)
