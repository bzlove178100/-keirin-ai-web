"""Real networkd DHCPv4 lifecycle in disposable CI namespaces only.

Synthetic local server; real installed networkd client, address/route changes,
renew/rebind/expiry and TCP transport. No live installer or arbitrary inputs.
"""
from contextlib import ExitStack, contextmanager
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("transition", Path(__file__).with_name("test_secret_custody_network_transition.py"))
t = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(t)
CLIENT = "192.0.2.10"
PRIMARY = "192.0.2.2"
ALTERNATE = "192.0.2.3"
TABLE = "kc_dhcp_fixture"
COOKIE = b"\x63\x82\x53\x63"
ZERO = b"\0" * 4
LEASE = 32
T1 = 8
T2 = 16


def guard():
    t.guard()
    if (os.environ.get("KC_DHCP_CI") != "1"
            or Path("/proc/1/comm").read_text().strip() != "systemd"):
        raise RuntimeError("CI_SYSTEMD_DHCP_FIXTURE_REQUIRED")


def option(code, data):
    return bytes((code, len(data))) + data


def request(data):
    # Fixed Ethernet fixture only, bounded options, no overload/relay support.
    if (not 241 <= len(data) <= 1500 or data[:3] != b"\x01\x01\x06"
            or data[24:28] != ZERO or data[236:240] != COOKIE):
        raise ValueError("INVALID_FIXTURE_DHCP")
    options = {}
    pos = 240
    while pos < len(data):
        code = data[pos]
        pos += 1
        if code == 255:
            break
        if code == 0:
            continue
        if pos == len(data):
            raise ValueError("TRUNCATED_OPTION")
        size = data[pos]
        pos += 1
        if pos + size > len(data) or code in options:
            raise ValueError("INVALID_OPTION")
        options[code] = data[pos:pos + size]
        pos += size
    else:
        raise ValueError("MISSING_END")
    if options.get(53) not in (b"\x01", b"\x03"):
        raise ValueError("UNSUPPORTED_MESSAGE")
    return options


def classify(data, destination):
    opts = request(data)
    if opts[53] == b"\x01" and data[12:16] == ZERO:
        return "discover"
    if data[12:16] == ZERO and opts.get(54) == socket.inet_aton(PRIMARY) and opts.get(50) == socket.inet_aton(CLIENT):
        return "select"
    if data[12:16] == socket.inet_aton(CLIENT) and 54 not in opts and 50 not in opts:
        if destination in (PRIMARY, ALTERNATE):
            return "renew"
        if destination == "255.255.255.255":
            return "rebind"
    raise ValueError("UNEXPECTED_CLIENT_STATE")


def reply(data, kind, server):
    result = bytearray(240)
    result[:3] = b"\x02\x01\x06"
    result[4:12] = data[4:12]
    result[12:16] = data[12:16]
    result[16:20] = socket.inet_aton(CLIENT)
    result[20:24] = socket.inet_aton(server)
    result[28:44] = data[28:44]
    result[236:240] = COOKIE
    result += option(53, b"\x02" if kind == "discover" else b"\x05")
    result += option(54, socket.inet_aton(server))
    result += option(1, socket.inet_aton("255.255.255.0"))
    result += option(3, socket.inet_aton(PRIMARY))
    for code, value in ((51, LEASE), (58, T1), (59, T2)):
        result += option(code, struct.pack("!I", value))
    return bytes(result) + b"\xff"


class Server:
    def __init__(self):
        self.mode = "normal"
        self.events = []
        self.error = None
        self.lock = threading.Lock()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, b"peer0\0")
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.setsockopt(socket.IPPROTO_IP, 8, 1)  # Linux IP_PKTINFO
        self.sock.bind(("0.0.0.0", 67))
        self.sock.settimeout(0.2)
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

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
                if len(infos) != 1:
                    raise RuntimeError("DESTINATION_EVIDENCE_REQUIRED")
                index, _, dest = struct.unpack("=I4s4s", infos[0])
                destination = socket.inet_ntoa(dest)
                try:
                    kind = classify(data, destination)
                except ValueError:
                    continue
                with self.lock:
                    mode = self.mode
                    answer = mode == "normal" or (mode == "rebind" and kind == "rebind")
                    server = ALTERNATE if mode == "rebind" else PRIMARY
                    self.events.append({"kind": kind, "answered": answer, "server": server})
                    if len(self.events) > 200:
                        raise RuntimeError("FIXTURE_EVENT_BOUND")
                if answer:
                    target = CLIENT if kind == "renew" else "255.255.255.255"
                    pktinfo = struct.pack("=I4s4s", index, socket.inet_aton(server), ZERO)
                    self.sock.sendmsg([reply(data, kind, server)], [(socket.IPPROTO_IP, 8, pktinfo)], 0, (target, 68))
        except BaseException as exc:
            self.error = type(exc).__name__

    def close(self):
        self.stop.set()
        self.thread.join(1)
        self.sock.close()
        assert not self.thread.is_alive()


def peer():
    guard()
    if os.readlink("/proc/self/ns/net") == os.environ.get("FIXTURE_PARENT_NETNS"):
        raise RuntimeError("DISTINCT_PEER_NAMESPACE_REQUIRED")
    with ExitStack() as stack:
        print("READY", flush=True)
        server = None
        old = None
        for line in sys.stdin:
            message = json.loads(line)
            op = message[0]
            if op == "setup":
                t.run(t.IP, "link", "set", "lo", "up")
                for address in (PRIMARY, ALTERNATE):
                    t.run(t.IP, "addr", "add", address + "/24", "dev", "peer0")
                t.run(t.IP, "link", "set", "peer0", "up")
                server = Server()
                stack.callback(server.close)
                for port in (53, 123, 9999):
                    t.listen(stack, PRIMARY, port, udp=True)
                result = True
            elif op == "events":
                with server.lock:
                    if server.error:
                        raise RuntimeError(server.error)
                    result = list(server.events)
            elif op == "mode":
                if message[1] not in ("normal", "rebind", "silent"):
                    raise RuntimeError("FIXED_MODE_REQUIRED")
                with server.lock:
                    server.mode = message[1]
                    server.events.clear()
                result = True
            elif op == "open":
                old = stack.enter_context(t.connect(CLIENT, 22, PRIMARY))
                result = t.exchange(old)
            elif op == "check":
                result = t.exchange(old) and t.reaches(CLIENT, 22, PRIMARY)
            elif op == "denied":
                result = not t.reaches(CLIENT, 80, PRIMARY)
            elif op == "stop":
                break
            else:
                raise RuntimeError("UNKNOWN_OPERATION")
            print(json.dumps(result), flush=True)


def policy():
    return '''table inet kc_dhcp_fixture {
      chain input { type filter hook input priority 0; policy drop;
        iifname "lo" accept
        iifname "host0" ip saddr 192.0.2.2 tcp dport 22 ct state { new, established } accept
        iifname "host0" ip saddr { 192.0.2.2, 192.0.2.3 } udp sport 67 udp dport 68 counter accept comment "dhcp_in"
        iifname "host0" ip saddr 192.0.2.2 udp sport { 53, 123 } ct state established accept
      }
      chain output { type filter hook output priority 0; policy drop;
        oifname "lo" accept
        oifname "host0" ip daddr 192.0.2.2 tcp sport 22 ct state established accept
        oifname "host0" ip daddr { 192.0.2.2, 192.0.2.3, 255.255.255.255 } udp sport 68 udp dport 67 counter accept comment "dhcp_out"
        oifname "host0" ip daddr 192.0.2.2 udp dport { 53, 123 } ct state { new, established } accept
      }
      chain forward { type filter hook forward priority 0; policy drop; }
    }
    '''


@contextmanager
def networkd():
    guard()
    # Private /run hides host D-Bus, netif leases and network configs. Read-only
    # /sys makes networkd use its no-udev path, matching container semantics.
    path = Path(tempfile.mkdtemp(prefix="kc-dhcp-ci-", dir="/tmp"))
    unit = path.name + ".service"
    try:
        path.chmod(0o755)
        (path / "network").mkdir()
        (path / "empty").mkdir()
        (path / "networkd.conf").write_text("[Network]\n")
        (path / "network/10-fixture.network").write_text('''[Match]
Name=host0
[Network]
DHCP=ipv4
LinkLocalAddressing=no
IPv6AcceptRA=no
[DHCPv4]
ClientIdentifier=mac
SendHostname=no
UseDNS=no
UseNTP=no
UseHostname=no
UseMTU=no
UseRoutes=yes
''')
        t.run("/usr/bin/systemd-run", "--quiet", "--unit=" + unit,
              "--property=Type=exec", "--property=Restart=no",
              "--property=RuntimeMaxSec=110", "--property=TimeoutStopSec=2",
              "--property=KillMode=control-group", "--property=PrivateMounts=yes",
              "--property=TemporaryFileSystem=/run:mode=0755",
              "--property=BindReadOnlyPaths=" + str(path / "network") + ":/etc/systemd/network " + str(path / "empty") + ":/usr/lib/systemd/network " + str(path / "networkd.conf") + ":/etc/systemd/networkd.conf " + str(path / "empty") + ":/etc/systemd/networkd.conf.d " + str(path / "empty") + ":/usr/lib/systemd/networkd.conf.d",
              "--property=NetworkNamespacePath=/proc/" + str(os.getpid()) + "/ns/net",
              "--setenv=SYSTEMD_LOG_LEVEL=debug", "--setenv=SYSTEMD_LOG_TARGET=console",
              "--setenv=GITHUB_ACTIONS=true", "--setenv=KC_DHCP_CI=1",
              sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--networkd")
        pid = int(t.run("/usr/bin/systemctl", "show", unit, "--property=MainPID", "--value").stdout)
        assert pid > 1 and os.readlink(f"/proc/{pid}/ns/net") == os.readlink("/proc/self/ns/net")
        assert os.readlink(f"/proc/{pid}/ns/mnt") != os.readlink("/proc/1/ns/mnt")
        # Verify isolation, not merely the requested unit options.
        root = Path(f"/proc/{pid}/root")
        wait_for(lambda: bool(os.statvfs(root / "sys").f_flag & os.ST_RDONLY), 3)
        assert not (root / "run/dbus/system_bus_socket").exists()
        assert not (root / "run/systemd/network").exists()
        assert [x.name for x in (root / "etc/systemd/network").iterdir()] == ["10-fixture.network"]
        yield root, unit
    except BaseException:
        # This unit sees only synthetic namespaces and private /run/config.
        log = t.run("/usr/bin/journalctl", "--no-pager", "-u", unit, "-n", "60", success=False)
        print(log.stdout[-12000:].decode("utf-8", "replace"), file=sys.stderr)
        raise
    finally:
        t.run("/usr/bin/systemctl", "stop", unit, success=False)
        t.run("/usr/bin/systemctl", "reset-failed", unit, success=False)
        assert t.run("/usr/bin/systemctl", "show", unit, "--property=MainPID", "--value").stdout == b"0\n"
        shutil.rmtree(path)


def networkd_child():
    guard()
    # A fresh sysfs view belongs to the fixture netns. Set per-mount read-only
    # after mounting: an existing sysfs superblock may already be read-write.
    # Refuse to mount anything in PID 1's mount namespace.
    if os.readlink("/proc/self/ns/mnt") == os.readlink("/proc/1/ns/mnt"):
        raise RuntimeError("PRIVATE_MOUNT_NAMESPACE_REQUIRED")
    t.run("mount", "-t", "sysfs", "-o", "nosuid,nodev,noexec", "sysfs", "/sys")
    t.run("mount", "-o", "remount,bind,ro", "/sys")
    assert os.statvfs("/sys").f_flag & os.ST_RDONLY
    print("PASS NETWORKD_FRESH_READONLY_SYSFS", flush=True)
    print(t.run("/usr/lib/systemd/systemd-networkd", "--version").stdout.decode(), flush=True)
    os.execv("/usr/lib/systemd/systemd-networkd", ["systemd-networkd"])


def address_present():
    data = json.loads(t.run(t.IP, "-j", "-4", "addr", "show", "dev", "host0").stdout)
    return any(a["local"] == CLIENT for i in data for a in i.get("addr_info", []))


def default_route_present():
    data = json.loads(t.run(t.IP, "-j", "-4", "route", "show", "default").stdout)
    return any(r.get("gateway") == PRIMARY and r.get("protocol") == "dhcp" for r in data)


def lease_server(root):
    for path in (root / "run/systemd/netif/leases").glob("*"):
        if path.is_file():
            for line in path.read_text().splitlines():
                if line.startswith("SERVER_ADDRESS="):
                    return str(ipaddress.ip_address(line.split("=", 1)[1]))
    return None


def wait_for(predicate, timeout, check=None):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        if check:
            check()
        time.sleep(0.2)
    raise RuntimeError("FIXTURE_LIFECYCLE_DEADLINE")


def counters():
    data = json.loads(t.run(t.NFT, "-j", "list", "table", "inet", TABLE).stdout)
    return {x["rule"]["comment"]: next(e["counter"]["packets"] for e in x["rule"]["expr"] if "counter" in e)
            for x in data["nftables"] if "rule" in x and x["rule"].get("comment") in ("dhcp_in", "dhcp_out")}


def lifecycle():
    guard()
    assert {x["ifname"] for x in json.loads(t.run(t.IP, "-j", "link", "show").stdout)} == {"lo"}
    assert all("metainfo" in x for x in json.loads(t.run(t.NFT, "-j", "list", "ruleset").stdout)["nftables"])
    env = dict(os.environ, FIXTURE_PARENT_NETNS=os.readlink("/proc/self/ns/net"))
    proc = subprocess.Popen(["unshare", "--net", sys.executable, "-I", "-B", __file__, "--peer"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env)
    try:
        assert t.read_line(proc).strip() == "READY"
        t.run(t.IP, "link", "add", "host0", "type", "veth", "peer", "name", "peer0")
        t.run(t.IP, "link", "set", "peer0", "netns", str(proc.pid))
        t.run(t.IP, "link", "set", "lo", "up")
        t.run(t.IP, "link", "set", "host0", "up")
        assert t.rpc(proc, "setup")
        t.nft(policy())
        with ExitStack() as stack:
            t.listen(stack, "0.0.0.0", 22)
            t.listen(stack, "0.0.0.0", 80)
            root, _ = stack.enter_context(networkd())
            try:
                wait_for(lambda: address_present() and default_route_present() and lease_server(root) == PRIMARY, 20)
            except RuntimeError:
                # Fixed synthetic state only; never a live diagnostic path.
                print("FIXTURE_ACQUIRE_STATE", json.dumps({"address": address_present(),
                      "route": default_route_present(), "lease_server": lease_server(root),
                      "events": t.rpc(proc, "events")}), file=sys.stderr)
                raise
            assert t.rpc(proc, "open")

            def check():
                assert address_present() and default_route_present()
                assert t.rpc(proc, "check"), "ADMIN_TRANSPORT_LOST"

            def denied():
                assert t.rpc(proc, "denied")
                assert not t.reaches(PRIMARY, 9999, udp=True)
                assert t.reaches(PRIMARY, 53, udp=True) and t.reaches(PRIMARY, 123, udp=True)

            denied()
            print("PASS NETWORKD_PRIVATE_RUNTIME_AND_REAL_LEASE", flush=True)
            before = counters()
            wait_for(lambda: any(e["kind"] == "renew" and e["answered"] for e in t.rpc(proc, "events")), 18, check)
            wait_for(lambda: counters()["dhcp_in"] > before["dhcp_in"] and counters()["dhcp_out"] > before["dhcp_out"], 3, check)
            check()
            print("PASS DHCPV4_UNICAST_RENEWAL_TRAVERSES_INET_POLICY", flush=True)
            assert t.rpc(proc, "mode", "rebind")
            wait_for(lambda: lease_server(root) == ALTERNATE, 28, check)
            events = t.rpc(proc, "events")
            assert any(e["kind"] == "renew" and not e["answered"] for e in events)
            assert any(e["kind"] == "rebind" and e["answered"] for e in events)
            check()
            denied()
            print("PASS DHCPV4_BROADCAST_REBIND_TO_ALTERNATE_PRESERVES_ADMIN", flush=True)
            assert t.rpc(proc, "mode", "silent")
            wait_for(lambda: not address_present() and not default_route_present(), LEASE + 8)
            assert any(e["kind"] == "renew" and not e["answered"] for e in t.rpc(proc, "events"))
            print("PASS DHCPV4_LEASE_EXPIRY_REMOVES_DYNAMIC_ADDRESS_AND_ROUTE", flush=True)
        assert t.rpc(proc, "events") is not None
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
        t.run(t.IP, "link", "del", "host0", success=False)
        t.nft("delete table inet " + TABLE + "\n", success=False)
    assert {x["ifname"] for x in json.loads(t.run(t.IP, "-j", "link", "show").stdout)} == {"lo"}
    print("PASS DHCP_FIXTURE_UNITS_PROCESSES_LINKS_AND_FILES_CLEANED", flush=True)
    print("RESULT SYNTHETIC_NETWORKD_DHCPV4_LIFECYCLE_OK_NO_LIVE_APPLY", flush=True)


class Tests(unittest.TestCase):
    def test_host_mount_namespace_refused_before_mount(self):
        with patch(__name__ + ".guard"), patch.object(os, "readlink", return_value="same"), patch.object(t, "run") as mutate:
            with self.assertRaises(RuntimeError):
                networkd_child()
            mutate.assert_not_called()

    def test_host_namespace_refused_before_mutation(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "KC_DHCP_CI": "1"}), patch.object(os, "geteuid", return_value=0), patch.object(os, "readlink", return_value="same"), patch.object(t, "run") as mutate:
            with self.assertRaises(RuntimeError):
                lifecycle()
            mutate.assert_not_called()

    def test_malformed_dhcp_never_classifies(self):
        for value in (b"", b"x" * 1600, bytes(240)):
            with self.assertRaises(ValueError):
                classify(value, PRIMARY)

    def test_renewal_requires_ciaddr_and_destination(self):
        data = bytearray(240)
        data[:3] = b"\x01\x01\x06"
        data[12:16] = socket.inet_aton(CLIENT)
        data[236:] = COOKIE
        data += b"\x35\x01\x03\xff"
        self.assertEqual(classify(data, PRIMARY), "renew")
        self.assertEqual(classify(data, "255.255.255.255"), "rebind")
        for destination in (CLIENT, "192.0.2.99"):
            with self.assertRaises(ValueError):
                classify(data, destination)
        data[12:16] = ZERO
        with self.assertRaises(ValueError):
            classify(data, PRIMARY)


if __name__ == "__main__":
    if sys.argv[1:] == ["--systemd"]:
        lifecycle()
    elif sys.argv[1:] == ["--peer"]:
        peer()
    elif sys.argv[1:] == ["--networkd"]:
        networkd_child()
    else:
        unittest.main(verbosity=2)
