"""Real networkd RA/SLAAC and kernel ND/DAD in disposable CI namespaces.

Fixed synthetic Ethernet link only. No DHCPv6/PMTU/recovery or live installer.
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

SPEC = importlib.util.spec_from_file_location("dhcp", Path(__file__).with_name("test_secret_custody_network_dhcp.py"))
d = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(d)
t, raw = d.t, d.raw
TABLE = "kc_ipv6_control"
LINK = "kc_ipv6_link"
CLIENT = "2001:db8:6::10"
PEER = "2001:db8:6::2"
REMOTE = "2001:db8:7::2"
DUPLICATE = "2001:db8:6::20"
HOST_LL = "fe80::ff:fe00:101"
ROUTER = "fe80::2"
ALL_NODES = "ff02::1"
SOLICITED = "ff02::1:ff00:0/104"
LIFETIME = 12
ETH_IPV6 = 0x86dd


def guard():
    d.guard()
    if os.environ.get("KC_IPV6_CI") != "1":
        raise RuntimeError("IPV6_CI_OPT_IN_REQUIRED")


def packed(address):
    return socket.inet_pton(socket.AF_INET6, address)


def control_packet(kind, variant="good"):
    source, hop, code = ROUTER, 255, 0
    if variant == "source":
        source = "fe80::99"
    elif variant == "hop":
        hop = 254
    elif variant == "code":
        code = 1
    elif variant != "good":
        raise ValueError("FIXED_VARIANT_REQUIRED")
    if kind == "ra":
        destination = ALL_NODES
        body = struct.pack("!BBHBBHII", 134, code, 0, 64, 0, LIFETIME, 0, 0)
        body += b"\x01\x01" + bytes.fromhex(t.MAC_PEER.replace(":", ""))
        body += struct.pack("!BBBBIII16s", 3, 4, 64, 0xc0, 90, 90, 0, packed("2001:db8:6::"))
    elif kind == "ns":
        destination = "ff02::1:ff00:10"
        body = struct.pack("!BBHI16s", 135, code, 0, 0, packed(CLIENT))
        body += b"\x01\x01" + bytes.fromhex(t.MAC_PEER.replace(":", ""))
    elif kind == "na":
        destination = HOST_LL
        body = struct.pack("!BBHI16s", 136, code, 0, 0x60000000, packed(ROUTER))
        body += b"\x02\x01" + bytes.fromhex(t.MAC_PEER.replace(":", ""))
    elif kind == "echo":
        destination = HOST_LL
        body = struct.pack("!BBHHH", 128, 0, 0, 1, 1) + b"kc-ipv6-echo"
    else:
        raise ValueError("FIXED_CONTROL_REQUIRED")
    pseudo = packed(source) + packed(destination) + struct.pack("!I3xB", len(body), 58)
    body = body[:2] + struct.pack("!H", raw.checksum(pseudo + body)) + body[4:]
    return struct.pack("!IHBB16s16s", 6 << 28, len(body), 58, hop, packed(source), packed(destination)) + body


def send_control(kind, variant):
    packet = control_packet(kind, variant)
    destination = socket.inet_ntop(socket.AF_INET6, packet[24:40])
    mac = b"\x33\x33" + packet[36:40] if destination.startswith("ff") else bytes.fromhex(t.MAC_HOST.replace(":", ""))
    with ExitStack() as stack:
        sock = raw.packet_socket(stack, "peer0", ETH_IPV6)
        assert sock.sendto(packet, ("peer0", ETH_IPV6, 0, 0, mac)) == len(packet)


def capture(sockets, packet):
    seen = dict.fromkeys(sockets, False)
    deadline = time.monotonic() + 0.3
    count = 0
    while time.monotonic() < deadline:
        ready, _, _ = select.select(list(sockets.values()), [], [], max(0, deadline - time.monotonic()))
        for sock in ready:
            data = sock.recv(2048)
            count += 1
            if count > 200:
                raise RuntimeError("FIXTURE_PACKET_BOUND")
            if data.endswith(packet):
                seen[next(k for k, s in sockets.items() if s is sock)] = True
    return seen


def counters():
    return raw.counters("netdev", LINK)


def policies():
    return f'''table netdev {LINK} {{
      chain ingress {{ type filter hook ingress device "host0" priority 0; policy drop;
        meta protocol ip6 ip6 nexthdr ipv6-icmp icmpv6 type nd-router-advert ip6 saddr {ROUTER} ip6 daddr {{ {HOST_LL}, {ALL_NODES} }} ip6 hoplimit 255 icmpv6 code 0 counter accept comment "in_ra"
        meta protocol ip6 ip6 nexthdr ipv6-icmp icmpv6 type nd-router-advert counter drop comment "in_bad_ra"
        meta protocol ip6 ip6 nexthdr ipv6-icmp icmpv6 type {{ nd-neighbor-solicit, nd-neighbor-advert }} ip6 saddr {{ ::, {ROUTER}, {PEER}, {REMOTE}, {DUPLICATE} }} ip6 daddr {{ {HOST_LL}, {CLIENT}, {DUPLICATE}, {ALL_NODES}, {SOLICITED} }} ip6 hoplimit 255 icmpv6 code 0 counter accept comment "in_nd"
        meta protocol ip6 ip6 nexthdr ipv6-icmp icmpv6 type {{ nd-neighbor-solicit, nd-neighbor-advert }} counter drop comment "in_bad_nd"
        meta protocol ip6 ip6 nexthdr tcp ip6 saddr {REMOTE} ip6 daddr {CLIENT} tcp dport 22 accept
        meta protocol ip6 counter drop comment "in_deny"
      }}
      chain egress {{ type filter hook egress device "host0" priority 0; policy drop;
        meta protocol ip6 ip6 nexthdr ipv6-icmp icmpv6 type nd-router-solicit ip6 saddr {{ ::, {HOST_LL} }} ip6 daddr ff02::2 ip6 hoplimit 255 icmpv6 code 0 counter accept comment "out_rs"
        meta protocol ip6 ip6 nexthdr ipv6-icmp icmpv6 type {{ nd-neighbor-solicit, nd-neighbor-advert }} ip6 saddr {{ ::, {HOST_LL}, {CLIENT}, {DUPLICATE} }} ip6 daddr {{ {ROUTER}, {PEER}, {REMOTE}, {DUPLICATE}, {ALL_NODES}, {SOLICITED} }} ip6 hoplimit 255 icmpv6 code 0 counter accept comment "out_nd"
        meta protocol ip6 ip6 nexthdr tcp ip6 saddr {CLIENT} ip6 daddr {REMOTE} tcp sport 22 accept
        meta protocol ip6 counter drop comment "out_deny"
      }}
    }}
    table inet {TABLE} {{
      chain input {{ type filter hook input priority 0; policy drop;
        iifname "lo" accept
        iifname "host0" meta l4proto ipv6-icmp icmpv6 type {{ nd-router-advert, nd-neighbor-solicit, nd-neighbor-advert }} accept
        iifname "host0" ip6 saddr {REMOTE} ip6 daddr {CLIENT} tcp dport 22 ct state {{ new, established }} accept
      }}
      chain output {{ type filter hook output priority 0; policy drop;
        oifname "lo" accept
        oifname "host0" meta l4proto ipv6-icmp icmpv6 type {{ nd-router-solicit, nd-neighbor-solicit, nd-neighbor-advert }} accept
        oifname "host0" ip6 saddr {CLIENT} ip6 daddr {REMOTE} tcp sport 22 ct state established accept
      }}
      chain forward {{ type filter hook forward priority 0; policy drop; }}
    }}
    '''


def peer():
    guard()
    assert os.readlink("/proc/self/ns/net") != os.environ.get("FIXTURE_PARENT_NETNS")
    with ExitStack() as stack:
        print("READY", flush=True)
        old = None
        for line in sys.stdin:
            msg = json.loads(line)
            op = msg[0]
            if op == "setup":
                t.run(t.IP, "link", "set", "lo", "up")
                t.run(t.IP, "link", "set", "peer0", "address", t.MAC_PEER, "addrgenmode", "none")
                t.run("sysctl", "-qw", "net.ipv6.conf.peer0.disable_ipv6=0", "net.ipv6.conf.peer0.accept_ra=0")
                for address in (ROUTER + "/64", PEER + "/64", REMOTE + "/128", DUPLICATE + "/64"):
                    t.run(t.IP, "-6", "addr", "add", address, "dev", "peer0", "nodad")
                t.run(t.IP, "link", "set", "peer0", "up")
                result = True
            elif op == "send":
                send_control(msg[1], msg[2])
                result = True
            elif op == "open":
                old = stack.enter_context(t.connect(CLIENT, 22, REMOTE))
                result = t.exchange(old)
            elif op == "check":
                result = t.exchange(old) and t.reaches(CLIENT, 22, REMOTE)
            elif op == "denied":
                result = not t.reaches(CLIENT, 80, REMOTE)
            elif op == "expired":
                result = not t.reaches(CLIENT, 22, REMOTE)
            elif op == "flush":
                t.run(t.IP, "-6", "neigh", "flush", "dev", "peer0")
                result = True
            else:
                raise RuntimeError("FIXED_OPERATION_REQUIRED")
            print(json.dumps(result), flush=True)


def addresses():
    links = json.loads(t.run(t.IP, "-j", "-6", "addr", "show", "dev", "host0").stdout)
    return [address for link in links for address in link.get("addr_info", [])]


def flagged(address, flag):
    return address.get(flag, False) or flag in address.get("flags", [])


def usable(address):
    return any(a["local"] == address and not flagged(a, "tentative") and not flagged(a, "dadfailed") for a in addresses())


def routes():
    return json.loads(t.run(t.IP, "-j", "-6", "route", "show", "default").stdout)


def route_present():
    return any(r.get("gateway") == ROUTER and r.get("protocol") == "ra" and r.get("dev") == "host0" for r in routes())


def packet_controls(proc, filtered):
    with ExitStack() as stack:
        socks = {"ip": raw.packet_socket(stack, "host0", ETH_IPV6),
                 "all": raw.packet_socket(stack, "host0", raw.ETH_ALL, socket.SOCK_RAW)}
        for kind in ("ra", "ns", "na", "echo"):
            for variant in (("good",) if kind == "echo" else ("good", "source", "hop", "code")):
                permitted = kind != "echo" and variant == "good"
                key = "in_deny" if kind == "echo" else ("in_" + ("" if permitted else "bad_") + ("ra" if kind == "ra" else "nd"))
                before = counters()[key] if filtered else None
                assert t.rpc(proc, "send", kind, variant)
                seen = capture(socks, control_packet(kind, variant))
                assert seen == {"ip": not filtered or permitted, "all": True}, (kind, variant, seen)
                if filtered:
                    assert counters()[key] == before + 1, (kind, variant, key, before, counters())
    print("PASS IPV6_" + ("EXACT_CONTROL_ALLOW_DENY_COUNTERS" if filtered else "UNFILTERED_CONTROL_PACKET_BASELINE"), flush=True)


def kernel():
    guard()
    print("KERNEL", os.uname().release, flush=True)
    assert {i["ifname"] for i in json.loads(t.run(t.IP, "-j", "link", "show").stdout)} == {"lo"}
    assert all("metainfo" in x for x in json.loads(t.run(t.NFT, "-j", "list", "ruleset").stdout)["nftables"])
    env = dict(os.environ, FIXTURE_PARENT_NETNS=os.readlink("/proc/self/ns/net"))
    proc = subprocess.Popen(["unshare", "--net", sys.executable, "-I", "-B", __file__, "--peer"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env)
    try:
        assert t.read_line(proc).strip() == "READY"
        t.run(t.IP, "link", "add", "host0", "type", "veth", "peer", "name", "peer0")
        t.run(t.IP, "link", "set", "peer0", "netns", str(proc.pid))
        t.run(t.IP, "link", "set", "lo", "up")
        t.run(t.IP, "link", "set", "host0", "address", t.MAC_HOST, "addrgenmode", "none")
        t.run("sysctl", "-qw", "net.ipv6.conf.host0.disable_ipv6=0", "net.ipv6.conf.host0.accept_ra=0")
        t.run(t.IP, "link", "set", "host0", "up")
        assert t.rpc(proc, "setup")
        packet_controls(proc, False)
        assert not routes() and not usable(CLIENT)
        t.nft(policies())
        packet_controls(proc, True)
        with ExitStack() as stack:
            t.listen(stack, "::", 22)
            t.listen(stack, "::", 80)
            stack.enter_context(d.networkd(ipv6=True))
            try:
                d.wait_for(lambda: usable(HOST_LL), 8)
                d.wait_for(lambda: counters()["out_rs"] > 0, 5)
                for variant in ("source", "hop", "code"):
                    before = counters()["in_bad_ra"]
                    assert t.rpc(proc, "send", "ra", variant)
                    d.wait_for(lambda: counters()["in_bad_ra"] == before + 1, 2)
                    assert not routes() and not usable(CLIENT)
                print("PASS INVALID_RA_CREATES_NO_ADDRESS_OR_ROUTE", flush=True)
                before = counters()["in_ra"]
                started = time.monotonic()
                assert t.rpc(proc, "send", "ra", "good")
                d.wait_for(lambda: usable(CLIENT) and route_present(), 8)
                assert counters()["in_ra"] == before + 1
                assert t.rpc(proc, "open")

                def check():
                    assert usable(CLIENT) and route_present()
                    assert t.rpc(proc, "check"), "IPV6_ADMIN_TRANSPORT_LOST"

                assert t.rpc(proc, "denied")
                print("PASS NETWORKD_SLAAC_DAD_AND_RA_ROUTE_UNDER_POLICY", flush=True)
                before = counters()
                t.run(t.IP, "-6", "neigh", "flush", "dev", "host0")
                assert t.rpc(proc, "flush")
                check()
                assert counters()["in_nd"] > before["in_nd"] and counters()["out_nd"] > before["out_nd"]
                neighbors = json.loads(t.run(t.IP, "-j", "-6", "neigh", "show", "dev", "host0").stdout)
                assert any(n.get("dst") == ROUTER and n.get("lladdr") == t.MAC_PEER and "PERMANENT" not in n.get("state", []) for n in neighbors)
                print("PASS DYNAMIC_NEIGHBOR_REDISCOVERY_PRESERVES_ADMIN", flush=True)
                # Refresh before the first lifetime, then exceed that original
                # deadline with transport checks. Never edit the route manually.
                d.wait_for(lambda: time.monotonic() >= started + 7, 8, check)
                assert t.rpc(proc, "send", "ra", "good")
                d.wait_for(lambda: time.monotonic() >= started + LIFETIME + 1, 8, check)
                check()
                print("PASS RA_REFRESH_EXTENDS_ROUTE_AND_ADMIN_TRANSPORT", flush=True)
                before = counters()
                t.run(t.IP, "-6", "addr", "add", DUPLICATE + "/64", "dev", "host0")
                d.wait_for(lambda: any(a["local"] == DUPLICATE and flagged(a, "dadfailed") for a in addresses()), 5)
                assert not usable(DUPLICATE)
                with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock:
                    try:
                        sock.bind((DUPLICATE, 0))
                    except OSError as exc:
                        assert exc.errno == errno.EADDRNOTAVAIL
                    else:
                        raise AssertionError("DUPLICATE_ADDRESS_BOUND")
                assert counters()["in_nd"] > before["in_nd"] and counters()["out_nd"] > before["out_nd"]
                t.run(t.IP, "-6", "addr", "del", DUPLICATE + "/64", "dev", "host0")
                check()
                print("PASS REAL_DUPLICATE_ADDRESS_DETECTED_AND_UNUSABLE", flush=True)
                d.wait_for(lambda: not route_present(), LIFETIME + 3)
                assert usable(CLIENT) and not routes()
                assert t.rpc(proc, "expired")
                assert Path("/proc/sys/net/ipv6/conf/host0/forwarding").read_text().strip() == "0"
                print("PASS RA_EXPIRY_REMOVES_ROUTE_AND_OFFLINK_REACHABILITY", flush=True)
            except BaseException:
                print("FIXTURE_IPV6_STATE", json.dumps({"addresses": addresses(), "routes": routes(), "counters": counters()}), file=sys.stderr)
                raise
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
        t.run(t.IP, "link", "del", "host0", success=False)
        for family, table in (("inet", TABLE), ("netdev", LINK)):
            t.nft("delete table " + family + " " + table + "\n", success=False)
    assert {i["ifname"] for i in json.loads(t.run(t.IP, "-j", "link", "show").stdout)} == {"lo"}
    assert all("metainfo" in x for x in json.loads(t.run(t.NFT, "-j", "list", "ruleset").stdout)["nftables"])
    print("PASS IPV6_FIXTURE_UNITS_PROCESSES_LINKS_RULES_CLEANED", flush=True)
    print("RESULT SYNTHETIC_IPV6_RA_ND_DAD_OK_NO_LIVE_APPLY", flush=True)


class Tests(unittest.TestCase):
    def test_no_ipv6_address_is_a_valid_empty_state(self):
        result = subprocess.CompletedProcess([], 0, stdout=b"[]")
        with patch.object(t, "run", return_value=result):
            self.assertEqual(addresses(), [])
            self.assertFalse(usable(CLIENT))

    def test_host_namespace_refused_before_commands(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "KC_DHCP_CI": "1", "KC_IPV6_CI": "1"}), patch.object(os, "geteuid", return_value=0), patch.object(os, "readlink", return_value="same"), patch.object(t, "run") as run:
            with self.assertRaises(RuntimeError):
                kernel()
            run.assert_not_called()

    def test_explicit_ipv6_opt_in_required(self):
        with patch.object(d, "guard"), patch.dict(os.environ, {"KC_IPV6_CI": "0"}), patch.object(t, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "IPV6_CI_OPT_IN_REQUIRED"):
                kernel()
            run.assert_not_called()

    def test_all_controls_have_valid_ipv6_length_and_icmp_checksum(self):
        for kind in ("ra", "ns", "na", "echo"):
            for variant in ("good", "source", "hop", "code"):
                packet = control_packet(kind, variant)
                self.assertEqual(struct.unpack("!H", packet[4:6])[0], len(packet) - 40)
                pseudo = packet[8:40] + struct.pack("!I3xB", len(packet) - 40, 58)
                self.assertEqual(raw.checksum(pseudo + packet[40:]), 0)


if __name__ == "__main__":
    if sys.argv[1:] == ["--kernel"]:
        kernel()
    elif sys.argv[1:] == ["--peer"]:
        peer()
    else:
        unittest.main(verbosity=2)
