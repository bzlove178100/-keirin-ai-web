"""Real networkd DHCPv6 IA_NA lifecycle, fixed disposable CI link only."""
from contextlib import ExitStack
import errno
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import struct
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("ipv6", Path(__file__).with_name("test_secret_custody_ipv6_control.py"))
v = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v)
d, t, raw = v.d, v.t, v.raw
MULTICAST = "ff02::1:2"
ALTERNATE = "fe80::3"
SERVERS = {"primary": bytes.fromhex("00030001020000000102"),
           "alternate": bytes.fromhex("00030001020000000103")}
# The minimum randomized T2 (21.6s) stays over 10s beyond maximum T1 (8s),
# avoiding v255's 10-second timer-coalescing window even with the getter fixed.
T1, T2, LEASE = 8, 24, 48


def guard():
    v.guard()
    if os.environ.get("KC_DHCP6_CI") != "1":
        raise RuntimeError("DHCP6_CI_OPT_IN_REQUIRED")


def option(code, data):
    return struct.pack("!HH", code, len(data)) + data


def options(data):
    if len(data) > 1500:
        raise ValueError("OPTION_BOUND")
    result = {}
    while data:
        if len(data) < 4:
            raise ValueError("TRUNCATED_OPTION")
        code, size = struct.unpack("!HH", data[:4])
        if len(data) < size + 4 or code in result:
            raise ValueError("INVALID_OPTION")
        result[code], data = data[4:4 + size], data[4 + size:]
    return result


def request(data, destination):
    if not 4 <= len(data) <= 1500 or data[0] not in (1, 3, 5, 6) or destination != MULTICAST:
        raise ValueError("FIXED_CLIENT_MESSAGE_REQUIRED")
    opts = options(data[4:])
    if not 4 <= len(opts.get(1, b"")) <= 128 or len(opts.get(3, b"")) < 12:
        raise ValueError("CLIENT_ID_AND_IA_NA_REQUIRED")
    kind = {1: "solicit", 3: "request", 5: "renew", 6: "rebind"}[data[0]]
    server = next((name for name, value in SERVERS.items() if opts.get(2) == value), None)
    if (data[0] in (1, 6) and 2 in opts) or (data[0] in (3, 5) and server is None):
        raise ValueError("SERVER_ID_STATE_MISMATCH")
    nested = options(opts[3][12:])
    if data[0] != 1 and (len(nested.get(5, b"")) != 24 or nested[5][:16] != v.packed(v.CLIENT)):
        raise ValueError("FIXED_IA_ADDRESS_REQUIRED")
    return kind, server, opts


def reply(data, kind, server, opts):
    ia = opts[3][:4] + struct.pack("!II", T1, T2)
    ia += option(5, v.packed(v.CLIENT) + struct.pack("!II", LEASE, LEASE))
    body = option(1, opts[1]) + option(2, SERVERS[server]) + option(3, ia)
    if kind == "solicit":
        body += option(7, b"\xff")  # Immediate selection of this local fixture.
    return bytes((2 if kind == "solicit" else 7,)) + data[1:4] + body


def send_frame(interface, packet, *, allow_drop=False):
    destination = packet[24:40]
    mac = b"\x33\x33" + destination[-4:] if destination[0] == 255 else bytes.fromhex((t.MAC_HOST if interface == "peer0" else t.MAC_PEER).replace(":", ""))
    with ExitStack() as stack:
        sock = raw.packet_socket(stack, interface, v.ETH_IPV6)
        try:
            assert sock.sendto(packet, (interface, v.ETH_IPV6, 0, 0, mac)) == len(packet)
        except OSError as exc:
            # Never count a send error alone as enforcement: the caller also
            # requires an exact counter increment and absence at the peer.
            if not allow_drop or exc.errno != errno.ENOBUFS:
                raise


def managed_ra():
    packet = bytearray(v.control_packet("ra"))
    packet[45] = 0x80  # Managed address configuration.
    packet[67] = 0x80  # Prefix is on-link, not autonomous SLAAC.
    packet[42:44] = b"\0\0"
    pseudo = packet[8:40] + struct.pack("!I3xB", len(packet) - 40, 58)
    packet[42:44] = struct.pack("!H", raw.checksum(pseudo + packet[40:]))
    return bytes(packet)


class Server:
    def __init__(self):
        self.mode, self.ra, self.error = "normal", False, None
        self.events, self.identity = [], None
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.index = socket.if_nametoindex("peer0")
        self.sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, b"peer0\0")
        self.sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_RECVPKTINFO, 1)
        self.sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, v.packed(MULTICAST) + struct.pack("=I", self.index))
        self.sock.bind(("::", 547))
        self.sock.settimeout(0.2)
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def serve(self):
        next_ra = 0
        try:
            while not self.stop.is_set():
                with self.lock:
                    ra = self.ra
                if ra and time.monotonic() >= next_ra:
                    send_frame("peer0", managed_ra())
                    next_ra = time.monotonic() + 3
                try:
                    data, ancillary, flags, source = self.sock.recvmsg(1600, 128)
                except socket.timeout:
                    continue
                if flags & socket.MSG_TRUNC or source[0].split("%", 1)[0] != v.HOST_LL or source[1] != 546:
                    continue
                infos = [x for level, code, x in ancillary if level == socket.IPPROTO_IPV6 and code == socket.IPV6_PKTINFO]
                if len(infos) != 1 or len(infos[0]) != 20 or struct.unpack("=I", infos[0][16:])[0] != self.index:
                    raise RuntimeError("DESTINATION_EVIDENCE_REQUIRED")
                destination = socket.inet_ntop(socket.AF_INET6, infos[0][:16])
                try:
                    kind, requested, opts = request(data, destination)
                except ValueError:
                    continue
                identity = (opts[1], opts[3][:4])
                with self.lock:
                    if self.identity is None:
                        self.identity = identity
                    if identity != self.identity:
                        raise RuntimeError("CLIENT_IDENTITY_CHANGED")
                    mode = self.mode
                    answer = mode == "normal" or (mode == "rebind" and (kind == "rebind" or requested == "alternate"))
                    server = "alternate" if mode == "rebind" else "primary"
                    self.events.append({"kind": kind, "requested_server": requested,
                                        "answered": answer, "reply_server": server,
                                        "multicast": destination == MULTICAST})
                    if len(self.events) > 200:
                        raise RuntimeError("EVENT_BOUND")
                if answer:
                    address = ALTERNATE if server == "alternate" else v.ROUTER
                    pktinfo = v.packed(address) + struct.pack("=I", self.index)
                    self.sock.sendmsg([reply(data, kind, server, opts)],
                                      [(socket.IPPROTO_IPV6, socket.IPV6_PKTINFO, pktinfo)], 0,
                                      (v.HOST_LL, 546, 0, self.index))
        except BaseException as exc:
            self.error = type(exc).__name__

    def close(self):
        self.stop.set()
        self.thread.join(1)
        self.sock.close()
        assert not self.thread.is_alive()


def policies():
    return v.policies() + f'''
insert rule netdev {v.LINK} ingress meta protocol ip6 ip6 nexthdr udp ip6 saddr {{ {v.ROUTER}, {ALTERNATE} }} ip6 daddr {v.HOST_LL} udp sport 547 udp dport 546 counter accept comment "in_dhcp6"
insert rule netdev {v.LINK} egress meta protocol ip6 ip6 nexthdr udp ip6 saddr {v.HOST_LL} ip6 daddr {MULTICAST} udp sport 546 udp dport 547 counter accept comment "out_dhcp6"
insert rule netdev {v.LINK} ingress meta protocol ip6 ip6 nexthdr ipv6-icmp ip6 saddr {ALTERNATE} ip6 daddr {{ {v.HOST_LL}, {v.ALL_NODES}, {v.SOLICITED} }} ip6 hoplimit 255 icmpv6 code 0 icmpv6 type {{ nd-neighbor-solicit, nd-neighbor-advert }} counter accept comment "in_alt_nd"
insert rule netdev {v.LINK} egress meta protocol ip6 ip6 nexthdr ipv6-icmp ip6 saddr {v.HOST_LL} ip6 daddr {ALTERNATE} ip6 hoplimit 255 icmpv6 code 0 icmpv6 type {{ nd-neighbor-solicit, nd-neighbor-advert }} counter accept comment "out_alt_nd"
insert rule inet {v.TABLE} input iifname "host0" ip6 saddr {{ {v.ROUTER}, {ALTERNATE} }} ip6 daddr {v.HOST_LL} udp sport 547 udp dport 546 counter accept comment "in_dhcp6"
insert rule inet {v.TABLE} output oifname "host0" ip6 saddr {v.HOST_LL} ip6 daddr {MULTICAST} udp sport 546 udp dport 547 counter accept comment "out_dhcp6"
'''


def udp_packet(direction, variant, token):
    source, destination, sport, dport = (v.ROUTER, v.HOST_LL, 547, 546) if direction == "in" else (v.HOST_LL, MULTICAST, 546, 547)
    if variant == "alternate":
        source = ALTERNATE
    elif variant == "source":
        source = "fe80::99"
    elif variant == "destination":
        destination = "fe80::99"
    elif variant == "sport":
        sport = 9999
    elif variant == "dport":
        dport = 9999
    elif variant == "unicast":
        destination = v.ROUTER
    elif variant != "good":
        raise ValueError("FIXED_VARIANT_REQUIRED")
    body = struct.pack("!HHHH", sport, dport, 8 + len(token), 0) + token.encode("ascii")
    pseudo = v.packed(source) + v.packed(destination) + struct.pack("!I3xB", len(body), 17)
    checksum = raw.checksum(pseudo + body) or 0xffff
    body = body[:6] + struct.pack("!H", checksum) + body[8:]
    return struct.pack("!IHBB16s16s", 6 << 28, len(body), 17, 1, v.packed(source), v.packed(destination)) + body


def peer():
    guard()
    assert os.readlink("/proc/self/ns/net") != os.environ.get("FIXTURE_PARENT_NETNS")
    with ExitStack() as stack:
        print("READY", flush=True)
        for line in sys.stdin:
            msg = json.loads(line)
            op = msg[0]
            if op == "setup":
                t.run(t.IP, "link", "set", "lo", "up")
                t.run(t.IP, "link", "set", "peer0", "address", t.MAC_PEER, "addrgenmode", "none")
                t.run("sysctl", "-qw", "net.ipv6.conf.peer0.disable_ipv6=0", "net.ipv6.conf.peer0.accept_ra=0")
                for address in (v.ROUTER + "/64", ALTERNATE + "/64", v.PEER + "/64", v.REMOTE + "/128"):
                    t.run(t.IP, "-6", "addr", "add", address, "dev", "peer0", "nodad")
                t.run(t.IP, "link", "set", "peer0", "up")
                packets = {"ip": raw.packet_socket(stack, "peer0", v.ETH_IPV6), "all": raw.packet_socket(stack, "peer0", raw.ETH_ALL, socket.SOCK_RAW)}
                server = Server()
                stack.callback(server.close)
                result = True
            elif op == "send":
                send_frame("peer0", udp_packet("in", msg[1], msg[2]))
                result = True
            elif op == "receive":
                result = raw.collect(packets, msg[1])
            elif op == "ra":
                with server.lock:
                    server.ra = True
                result = True
            elif op == "mode":
                if msg[1] not in ("rebind", "silent"):
                    raise RuntimeError("FIXED_MODE_REQUIRED")
                with server.lock:
                    server.mode = msg[1]
                    server.events.clear()
                result = True
            elif op == "events":
                with server.lock:
                    if server.error:
                        raise RuntimeError(server.error)
                    result = list(server.events)
            elif op == "open":
                old = stack.enter_context(t.connect(v.CLIENT, 22, v.REMOTE))
                result = t.exchange(old)
            elif op == "check":
                result = t.exchange(old) and t.reaches(v.CLIENT, 22, v.REMOTE)
            elif op == "denied":
                result = not t.reaches(v.CLIENT, 80, v.REMOTE)
            elif op == "expired":
                result = not t.reaches(v.CLIENT, 22, v.REMOTE)
            else:
                raise RuntimeError("FIXED_OPERATION_REQUIRED")
            print(json.dumps(result), flush=True)


def packet_controls(proc, filtered):
    with ExitStack() as stack:
        sockets = {"ip": raw.packet_socket(stack, "host0", v.ETH_IPV6), "all": raw.packet_socket(stack, "host0", raw.ETH_ALL, socket.SOCK_RAW)}
        for direction in ("in", "out"):
            variants = ("good", "source", "destination", "sport", "dport", "alternate" if direction == "in" else "unicast")
            for variant in variants:
                accepted = variant in ("good", "alternate")
                token = f"kc-dhcp6-{filtered}-{direction}-{variant}"
                key = direction + ("_dhcp6" if accepted else "_deny")
                before = v.counters()[key] if filtered else None
                if direction == "in":
                    assert t.rpc(proc, "send", variant, token)
                    seen = raw.collect(sockets, token)
                    expected = {"ip": not filtered or accepted, "all": True}
                else:
                    send_frame("host0", udp_packet(direction, variant, token), allow_drop=filtered and not accepted)
                    seen = t.rpc(proc, "receive", token)
                    expected = dict.fromkeys(("ip", "all"), not filtered or accepted)
                assert seen == expected, (direction, variant, seen)
                if filtered:
                    assert v.counters()[key] == before + 1, (key, before, v.counters())
    print("PASS DHCP6_" + ("EXACT_TUPLE_ALLOW_DENY_COUNTERS" if filtered else "UNFILTERED_UDP_PACKET_BASELINE"), flush=True)


def remaining():
    return next((a["valid_life_time"] for a in v.addresses() if a["local"] == v.CLIENT), 0)


def counts():
    return v.counters() | {"inet_" + k: value for k, value in raw.counters("inet", v.TABLE).items()}


def increased(before):
    after = counts()
    return all(after[key] > before[key] for key in ("in_dhcp6", "out_dhcp6", "inet_in_dhcp6", "inet_out_dhcp6"))


class ClientTimerError(RuntimeError):
    def __init__(self, pair):
        self.pair = pair
        super().__init__("DHCP6_CLIENT_TIMER_CONTRACT: expected T1=7..8 T2=21..24 seconds; reported=" + str(pair))


def require_client_timers(log):
    # v255 subtracts at most 10% before logging whole seconds. A known upstream
    # getter defect returns T1 as T2; an occasional Renew must not qualify it.
    reported = re.findall(rb"DHCPv6 client: T([12]) expires in (\d+)s(?:\r?\n|$)", log)
    pair = [(int(kind), int(value)) for kind, value in reported[-2:]]
    if (len(pair) != 2 or pair[0][0] != 1 or pair[1][0] != 2
            or not 7 <= pair[0][1] <= 8 or not 21 <= pair[1][1] <= 24):
        raise ClientTimerError(pair)


def lifecycle(*, client="installed"):
    guard()
    print("KERNEL", os.uname().release, flush=True)
    assert {x["ifname"] for x in json.loads(t.run(t.IP, "-j", "link", "show").stdout)} == {"lo"}
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
        t.nft(policies())
        packet_controls(proc, True)
        with ExitStack() as stack:
            t.listen(stack, "::", 22)
            t.listen(stack, "::", 80)
            before = counts()
            _, unit = stack.enter_context(d.networkd(ipv6=True, dhcp6=True, client=client))
            try:
                d.wait_for(lambda: v.usable(v.HOST_LL) and v.counters()["out_rs"] > 0, 12)
                assert not t.rpc(proc, "events") and not v.usable(v.CLIENT)
                assert t.rpc(proc, "ra")
                d.wait_for(lambda: v.usable(v.CLIENT) and v.route_present(), 25)
                events = t.rpc(proc, "events")
                assert all(e["multicast"] for e in events)
                assert all(any(e["kind"] == kind and e["answered"] for e in events) for kind in ("solicit", "request"))
                assert increased(before)
                assert t.rpc(proc, "open") and t.rpc(proc, "denied")
                print("PASS REAL_DHCP6_FOUR_MESSAGE_ACQUISITION_AND_RA_ROUTE", flush=True)
                require_client_timers(t.run("/usr/bin/journalctl", "--no-pager", "-u", unit, "-n", "120").stdout)
                print("PASS DHCP6_CLIENT_DISTINCT_T1_T2_CONFIRMED", flush=True)

                def check():
                    assert v.usable(v.CLIENT) and v.route_present()
                    assert t.rpc(proc, "check"), "DHCP6_ADMIN_TRANSPORT_LOST"

                before = counts()
                d.wait_for(lambda: any(e["kind"] == "renew" and e["requested_server"] == "primary" and e["answered"] for e in t.rpc(proc, "events")), 25, check)
                d.wait_for(lambda: remaining() > LEASE - 4 and increased(before), 3, check)
                print("PASS DHCP6_MULTICAST_RENEW_REFRESHES_ACTUAL_ADDRESS_LIFETIME", flush=True)
                before = counts()
                assert t.rpc(proc, "mode", "rebind")
                d.wait_for(lambda: any(e["kind"] == "rebind" and e["answered"] for e in t.rpc(proc, "events")), 40, check)
                d.wait_for(lambda: any(e["kind"] == "renew" and e["requested_server"] == "alternate" and e["answered"] for e in t.rpc(proc, "events")), 25, check)
                events = t.rpc(proc, "events")
                assert any(e["kind"] == "renew" and e["requested_server"] == "primary" and not e["answered"] for e in events)
                assert any(e["kind"] == "rebind" and e["requested_server"] is None and e["reply_server"] == "alternate" and e["answered"] for e in events)
                assert all(e["multicast"] for e in events)
                d.wait_for(lambda: remaining() > LEASE - 4 and increased(before), 3, check)
                check()
                assert t.rpc(proc, "denied")
                print("PASS DHCP6_REBIND_ADOPTS_ALTERNATE_DUID_PRESERVES_ADMIN", flush=True)
                assert t.rpc(proc, "mode", "silent")
                d.wait_for(lambda: not any(a["local"] == v.CLIENT for a in v.addresses()), LEASE + 8)
                assert v.route_present() and v.usable(v.HOST_LL)
                assert t.rpc(proc, "expired")
                events = t.rpc(proc, "events")
                assert any(e["kind"] == "renew" and e["requested_server"] == "alternate" and not e["answered"] for e in events)
                assert any(e["kind"] == "rebind" and not e["answered"] for e in events)
                print("PASS DHCP6_EXPIRY_REMOVES_ADDRESS_WHILE_RA_ROUTE_REMAINS", flush=True)
            except BaseException:
                print("FIXTURE_DHCP6_STATE", json.dumps({"addresses": v.addresses(), "routes": v.routes(), "counters": counts(), "events": t.rpc(proc, "events")}), file=sys.stderr)
                raise
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
        t.run(t.IP, "link", "del", "host0", success=False)
        for family, table in (("inet", v.TABLE), ("netdev", v.LINK)):
            t.nft("delete table " + family + " " + table + "\n", success=False)
        assert {x["ifname"] for x in json.loads(t.run(t.IP, "-j", "link", "show").stdout)} == {"lo"}
        assert all("metainfo" in x for x in json.loads(t.run(t.NFT, "-j", "list", "ruleset").stdout)["nftables"])
        print("PASS DHCP6_FIXTURE_UNITS_PROCESSES_LINKS_RULES_CLEANED", flush=True)
    print("RESULT SYNTHETIC_DHCP6_LIFECYCLE_OK_NO_LIVE_APPLY", flush=True)


def original_control():
    # Same compiler/options as the patched client. Only this measured getter
    # defect is the required negative result; unrelated failures still fail CI.
    try:
        lifecycle(client="original")
    except ClientTimerError as exc:
        if (len(exc.pair) != 2 or exc.pair[0][0] != 1 or exc.pair[1][0] != 2
                or not 6 <= exc.pair[0][1] <= 8 or not 7 <= exc.pair[1][1] <= 8):
            raise
        print("RESULT ORIGINAL_BUILD_DHCP6_TIMER_DEFECT_CONFIRMED_NOT_QUALIFIED", flush=True)
    else:
        raise RuntimeError("ORIGINAL_BUILD_NEGATIVE_CONTROL_DID_NOT_REPRODUCE")


class Tests(unittest.TestCase):
    def test_host_namespace_refused(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), patch.object(os, "geteuid", return_value=0), patch.object(os, "readlink", return_value="same"), patch.object(t, "run") as run:
            with self.assertRaises(RuntimeError):
                lifecycle()
            run.assert_not_called()

    def test_explicit_opt_in_required(self):
        with patch.object(v, "guard"), patch.dict(os.environ, {"KC_DHCP6_CI": "0"}), patch.object(t, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "DHCP6_CI_OPT_IN_REQUIRED"):
                lifecycle()
            run.assert_not_called()

    def test_truncation_and_duplicate_options_refused(self):
        for data in (b"x", b"\x00\x01\x00\x08x", option(1, b"a") * 2, b"x" * 1501):
            with self.assertRaises(ValueError):
                options(data)

    def test_renew_rebind_server_id_and_nested_address_contract(self):
        opts = option(1, b"test-client") + option(3, b"iaid" + bytes(8) + option(5, v.packed(v.CLIENT) + bytes(8)))
        renew = b"\x05\x01\x02\x03" + opts + option(2, SERVERS["primary"])
        self.assertEqual(request(renew, MULTICAST)[:2], ("renew", "primary"))
        rebind = b"\x06\x01\x02\x03" + opts
        self.assertEqual(request(rebind, MULTICAST)[:2], ("rebind", None))
        for data, dest in ((renew, v.ROUTER), (rebind + option(2, SERVERS["primary"]), MULTICAST), (renew[:4] + opts, MULTICAST)):
            with self.assertRaises(ValueError):
                request(data, dest)

    def test_managed_ra_and_ipv6_udp_have_valid_checksums(self):
        for packet, protocol in ((managed_ra(), 58), (udp_packet("out", "good", "probe"), 17)):
            pseudo = packet[8:40] + struct.pack("!I3xB", len(packet) - 40, protocol)
            self.assertEqual(raw.checksum(pseudo + packet[40:]), 0)
        self.assertEqual(managed_ra()[45], 0x80)
        self.assertEqual(managed_ra()[67], 0x80)

    def test_reply_encodes_distinct_timers_and_alternate_identity(self):
        opts = {1: b"test-client", 3: b"iaid" + bytes(8)}
        packet = reply(b"\x06\x01\x02\x03", "rebind", "alternate", opts)
        self.assertEqual(packet[:4], b"\x07\x01\x02\x03")
        fields = options(packet[4:])
        self.assertEqual(fields[1], b"test-client")
        self.assertEqual(fields[2], SERVERS["alternate"])
        self.assertEqual(struct.unpack("!4sII", fields[3][:12]), (b"iaid", 8, 24))
        self.assertEqual(options(fields[3][12:])[5], v.packed(v.CLIENT) + struct.pack("!II", 48, 48))
        self.assertGreater(T2 * 0.9 - T1, 10)

    def test_correct_client_timer_jitter_is_accepted(self):
        for t1, t2 in ((7, 21), (8, 24)):
            require_client_timers(f"DHCPv6 client: T1 expires in {t1}s\nDHCPv6 client: T2 expires in {t2}s\n".encode())

    def test_known_client_timer_defect_and_missing_evidence_are_rejected(self):
        for log in (b"", b"DHCPv6 client: T1 expires in 7s\n", b"DHCPv6 client: T1 expires in 7s\nDHCPv6 client: T2 expires in 7s\n"):
            with self.assertRaisesRegex(RuntimeError, "DHCP6_CLIENT_TIMER_CONTRACT"):
                require_client_timers(log)

    def test_original_control_does_not_swallow_unrelated_or_missing_evidence(self):
        for error in (RuntimeError("other"), ClientTimerError([])):
            with patch(__name__ + ".lifecycle", side_effect=error):
                with self.assertRaises(RuntimeError):
                    original_control()
        with patch(__name__ + ".lifecycle", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "DID_NOT_REPRODUCE"):
                original_control()


if __name__ == "__main__":
    if sys.argv[1:] == ["--kernel"]:
        lifecycle()
    elif sys.argv[1:] == ["--original-control"]:
        original_control()
    elif sys.argv[1:] == ["--patched-kernel"]:
        lifecycle(client="patched")
    elif sys.argv[1:] == ["--peer"]:
        peer()
    else:
        unittest.main(verbosity=2)
