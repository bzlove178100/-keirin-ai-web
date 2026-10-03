"""Measure packet-socket filtering and capability boundaries in CI netns only.

Fixed documentation endpoints; no live policy, DHCP authentication or installer.
"""
from contextlib import ExitStack
import errno
import importlib.util
import json
import os
from pathlib import Path
import select
import socket
import struct
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("transition", Path(__file__).with_name("test_secret_custody_network_transition.py"))
t = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(t)
HOST = "192.0.2.1"
PEER = "192.0.2.2"
WRONG = "192.0.2.9"
INET = "kc_raw_inet"
NETDEV = "kc_raw_netdev"
ETH_IP = 0x0800
ETH_ALL = 3


def guard():
    t.guard()
    if os.environ.get("KC_RAW_PACKET_CI") != "1":
        raise RuntimeError("RAW_PACKET_CI_OPT_IN_REQUIRED")


def checksum(data):
    if len(data) % 2:
        data += b"\0"
    total = sum(struct.unpack("!" + "H" * (len(data) // 2), data))
    while total >> 16:
        total = (total & 0xffff) + (total >> 16)
    return (~total) & 0xffff


def datagram(source, destination, sport, dport, token, fragment=0):
    # IPv4 UDP permits zero UDP checksum. IP header checksum remains real.
    payload = token.encode("ascii")
    udp = struct.pack("!HHHH", sport, dport, 8 + len(payload), 0) + payload
    header = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(udp), 1,
                         fragment, 64, 17, 0,
                         socket.inet_aton(source), socket.inet_aton(destination))
    return header[:10] + struct.pack("!H", checksum(header)) + header[12:] + udp


def packet_socket(stack, interface, protocol, kind=socket.SOCK_DGRAM):
    sock = stack.enter_context(socket.socket(socket.AF_PACKET, kind, socket.htons(protocol)))
    sock.bind((interface, protocol))
    return sock


def receivers(stack, interface, address, port):
    udp = stack.enter_context(socket.socket(socket.AF_INET, socket.SOCK_DGRAM))
    udp.bind((address, port))
    return {"ip": packet_socket(stack, interface, ETH_IP),
            "all": packet_socket(stack, interface, ETH_ALL, socket.SOCK_RAW),
            "udp": udp}


def collect(sockets, token):
    # Receivers exist before transmission. Exact, unique payload prevents old
    # frames from satisfying a later case. All sockets share one bounded window.
    found = dict.fromkeys(sockets, False)
    token = token.encode("ascii")
    end = time.monotonic() + 0.35
    packets = 0
    while time.monotonic() < end:
        ready, _, _ = select.select(list(sockets.values()), [], [], max(0, end - time.monotonic()))
        for sock in ready:
            data = sock.recv(2048)
            packets += 1
            if packets > 200:
                raise RuntimeError("FIXTURE_PACKET_BOUND")
            if data.endswith(token):
                found[next(k for k, v in sockets.items() if v is sock)] = True
    return found


def send_packet(interface, mac, source, destination, sport, dport, token, bypass=False, fragment=0):
    with ExitStack() as stack:
        sock = packet_socket(stack, interface, ETH_IP)
        if bypass:
            sock.setsockopt(263, 20, 1)  # SOL_PACKET / PACKET_QDISC_BYPASS
        data = datagram(source, destination, sport, dport, token, fragment)
        try:
            assert sock.sendto(data, (interface, ETH_IP, 0, 0, bytes.fromhex(mac.replace(":", "")))) == len(data)
        except OSError as exc:
            # A netdev drop may return ENOBUFS. It never counts as evidence of
            # blocking by itself: require the rule counter and remote absence.
            if exc.errno != errno.ENOBUFS:
                raise


def setup(interface, address, mac):
    t.run(t.IP, "link", "set", "lo", "up")
    t.run(t.IP, "link", "set", interface, "address", mac)
    t.run(t.IP, "addr", "add", address + "/24", "dev", interface)
    t.run(t.IP, "link", "set", interface, "up")
    remote, remote_mac = (PEER, t.MAC_PEER) if interface == "host0" else (HOST, t.MAC_HOST)
    t.run(t.IP, "neigh", "replace", remote, "lladdr", remote_mac, "nud", "permanent", "dev", interface)


def peer():
    guard()
    if os.readlink("/proc/self/ns/net") == os.environ.get("FIXTURE_PARENT_NETNS"):
        raise RuntimeError("DISTINCT_PEER_NAMESPACE_REQUIRED")
    with ExitStack() as stack:
        print("READY", flush=True)
        for line in sys.stdin:
            message = json.loads(line)
            if message[0] == "setup":
                setup("peer0", PEER, t.MAC_PEER)
                socks = receivers(stack, "peer0", PEER, 67)
                result = True
            elif message[0] == "receive":
                result = collect(socks, message[1])
            elif message[0] == "send":
                _, variant, token = message
                source, sport, fragment = {
                    "allowed": (PEER, 67, 0), "source": (WRONG, 67, 0),
                    "port": (PEER, 69, 0), "fragment": (PEER, 67, 0x2000),
                }[variant]
                send_packet("peer0", t.MAC_HOST, source, HOST, sport, 68, token, fragment=fragment)
                result = True
            else:
                raise RuntimeError("UNKNOWN_FIXED_OPERATION")
            print(json.dumps(result), flush=True)


def inet_policy():
    return '''table inet kc_raw_inet {
      chain input { type filter hook input priority 0; policy drop;
        ip protocol udp counter drop comment "inet_in"
      }
      chain output { type filter hook output priority 0; policy drop;
        ip protocol udp counter drop comment "inet_out"
      }
      chain forward { type filter hook forward priority 0; policy drop; }
    }
    '''


def netdev_policy():
    # Deliberately narrow test tuples, not a usable DHCP or host policy.
    return '''table netdev kc_raw_netdev {
      chain ingress { type filter hook ingress device "host0" priority 0; policy drop;
        ether type ip ip frag-off & 0x3fff != 0 counter drop comment "in_fragment"
        ether type ip ip saddr 192.0.2.2 ip daddr 192.0.2.1 udp sport 67 udp dport 68 counter accept comment "in_allow"
        ether type ip counter drop comment "in_deny"
      }
      chain egress { type filter hook egress device "host0" priority 0; policy drop;
        ether type ip ip frag-off & 0x3fff != 0 counter drop comment "out_fragment"
        ether type ip ip saddr 192.0.2.1 ip daddr 192.0.2.2 udp sport 68 udp dport 67 counter accept comment "out_allow"
        ether type ip counter drop comment "out_deny"
      }
    }
    '''


def counters(family, table):
    data = json.loads(t.run(t.NFT, "-j", "list", "table", family, table).stdout)
    return {obj["rule"]["comment"]: next(e["counter"]["packets"] for e in obj["rule"]["expr"] if "counter" in e)
            for obj in data["nftables"] if "rule" in obj and "comment" in obj["rule"]}


def restricted_child():
    guard()
    status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines() if ":" in line)
    assert all(int(status[k], 16) == 0 for k in ("CapEff", "CapPrm", "CapInh", "CapAmb", "CapBnd"))
    assert int(status["NoNewPrivs"]) == 1
    for fd in list(Path("/proc/self/fd").iterdir()):
        try:
            target = os.readlink(fd)
        except FileNotFoundError:
            continue
        assert not target.startswith("socket:"), "INHERITED_SOCKET_NOT_ALLOWED"
    for family, kind, protocol in (
            (socket.AF_PACKET, socket.SOCK_DGRAM, socket.htons(ETH_IP)),
            (socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_ALL)),
            (socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_UDP),
            (socket.AF_INET6, socket.SOCK_RAW, socket.IPPROTO_UDP)):
        try:
            with socket.socket(family, kind, protocol):
                raise AssertionError("RAW_SOCKET_UNEXPECTEDLY_AVAILABLE")
        except OSError as exc:
            assert exc.errno == errno.EPERM
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM):
        pass
    print("PASS EXECUTED_CHILD_NO_CAPABILITIES_NO_RAW_OR_INHERITED_SOCKET", flush=True)


def kernel():
    guard()
    assert {i["ifname"] for i in json.loads(t.run(t.IP, "-j", "link", "show").stdout)} == {"lo"}
    assert all("metainfo" in x for x in json.loads(t.run(t.NFT, "-j", "list", "ruleset").stdout)["nftables"])
    print("KERNEL", os.uname().release, flush=True)
    env = dict(os.environ, FIXTURE_PARENT_NETNS=os.readlink("/proc/self/ns/net"))
    proc = subprocess.Popen(["unshare", "--net", sys.executable, "-I", "-B", __file__, "--peer"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env)
    try:
        assert t.read_line(proc).strip() == "READY"
        t.run(t.IP, "link", "add", "host0", "type", "veth", "peer", "name", "peer0")
        t.run(t.IP, "link", "set", "peer0", "netns", str(proc.pid))
        setup("host0", HOST, t.MAC_HOST)
        assert t.rpc(proc, "setup")
        with ExitStack() as stack:
            socks = receivers(stack, "host0", HOST, 68)

            def incoming(variant, token, expected):
                assert t.rpc(proc, "send", variant, token)
                got = collect(socks, token)
                assert got == dict(zip(("ip", "all", "udp"), expected)), (token, got)

            def outgoing(token, bypass=False, variant="allowed", expected=True):
                source, destination, dport, fragment = {
                    "allowed": (HOST, PEER, 67, 0), "destination": (HOST, WRONG, 67, 0),
                    "port": (HOST, PEER, 69, 0), "source": (WRONG, PEER, 67, 0),
                    "fragment": (HOST, PEER, 67, 0x2000),
                }[variant]
                send_packet("host0", t.MAC_PEER, source, destination, 68, dport, token, bypass, fragment)
                got = t.rpc(proc, "receive", token)
                assert got == dict.fromkeys(("ip", "all", "udp"), expected), (token, got)

            incoming("allowed", "kc-baseline-in", (True, True, True))
            outgoing("kc-baseline-out")
            print("PASS VALID_IPV4_UDP_PACKET_AND_RECEIVER_CONTROLS", flush=True)
            t.nft(inet_policy())
            before = counters("inet", INET)
            socks["udp"].sendto(b"kc-normal-udp-denied", (PEER, 67))
            assert not any(t.rpc(proc, "receive", "kc-normal-udp-denied").values())
            assert counters("inet", INET)["inet_out"] == before["inet_out"] + 1
            before = counters("inet", INET)
            incoming("allowed", "kc-inet-in", (True, True, False))
            outgoing("kc-inet-out")
            after = counters("inet", INET)
            assert after["inet_in"] == before["inet_in"] + 1 and after["inet_out"] == before["inet_out"]
            print("PASS INET_BLOCKS_UDP_BUT_NOT_PACKET_SOCKET_PATHS", flush=True)
            t.nft(netdev_policy())
            before = counters("netdev", NETDEV)
            incoming("allowed", "kc-netdev-in-allow", (True, True, False))
            assert counters("netdev", NETDEV)["in_allow"] == before["in_allow"] + 1
            for variant in ("source", "port", "fragment"):
                key = "in_fragment" if variant == "fragment" else "in_deny"
                before = counters("netdev", NETDEV)[key]
                incoming(variant, "kc-netdev-in-" + variant, (False, True, False))
                assert counters("netdev", NETDEV)[key] == before + 1
            print("PASS NETDEV_INGRESS_FILTERS_IP_SOCKET_BUT_NOT_ALL_PROTOCOL_TAP", flush=True)
            for bypass in (False, True):
                before = counters("netdev", NETDEV)["out_allow"]
                outgoing("kc-out-allow-" + str(bypass), bypass)
                assert counters("netdev", NETDEV)["out_allow"] == before + 1
                for variant in ("source", "destination", "port", "fragment"):
                    key = "out_fragment" if variant == "fragment" else "out_deny"
                    before = counters("netdev", NETDEV)[key]
                    outgoing("kc-out-deny-" + variant + str(bypass), bypass, variant, False)
                    assert counters("netdev", NETDEV)[key] == before + 1
            print("PASS NETDEV_EGRESS_FILTERS_NORMAL_AND_QDISC_BYPASS_PACKET_SEND", flush=True)
            child = t.run("/usr/bin/setpriv", "--bounding-set=-all", "--inh-caps=-all", "--ambient-caps=-all",
                          "--no-new-privs", "--", sys.executable, "-I", "-B", __file__, "--restricted")
            assert child.stdout == b"PASS EXECUTED_CHILD_NO_CAPABILITIES_NO_RAW_OR_INHERITED_SOCKET\n"
            print(child.stdout.decode(), end="", flush=True)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
        t.run(t.IP, "link", "del", "host0", success=False)
        for family, table in (("inet", INET), ("netdev", NETDEV)):
            t.nft("delete table " + family + " " + table + "\n", success=False)
    assert {i["ifname"] for i in json.loads(t.run(t.IP, "-j", "link", "show").stdout)} == {"lo"}
    assert all("metainfo" in x for x in json.loads(t.run(t.NFT, "-j", "list", "ruleset").stdout)["nftables"])
    print("PASS RAW_PACKET_FIXTURE_PROCESSES_LINKS_RULES_CLEANED", flush=True)
    print("RESULT SYNTHETIC_RAW_PACKET_BOUNDARY_OK_NO_LIVE_APPLY", flush=True)


class Tests(unittest.TestCase):
    def test_host_namespace_refused_before_commands(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "KC_RAW_PACKET_CI": "1"}), patch.object(os, "geteuid", return_value=0), patch.object(os, "readlink", return_value="host"), patch.object(t, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "DISPOSABLE_CI_NETWORK_NAMESPACE_REQUIRED"):
                kernel()
            run.assert_not_called()

    def test_explicit_opt_in_required_before_commands(self):
        with patch.object(t, "guard"), patch.dict(os.environ, {"KC_RAW_PACKET_CI": "0"}), patch.object(t, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "RAW_PACKET_CI_OPT_IN_REQUIRED"):
                kernel()
            run.assert_not_called()

    def test_packet_has_real_ip_checksum_and_exact_udp_lengths(self):
        data = datagram(HOST, PEER, 68, 67, "kc-check")
        self.assertEqual(checksum(data[:20]), 0)
        self.assertEqual(struct.unpack("!H", data[2:4])[0], len(data))
        self.assertEqual(struct.unpack("!HHHH", data[20:28]), (68, 67, len(data) - 20, 0))
        self.assertEqual(data[28:], b"kc-check")


if __name__ == "__main__":
    if sys.argv[1:] == ["--kernel"]:
        kernel()
    elif sys.argv[1:] == ["--peer"]:
        peer()
    elif sys.argv[1:] == ["--restricted"]:
        restricted_child()
    else:
        unittest.main(verbosity=2)
