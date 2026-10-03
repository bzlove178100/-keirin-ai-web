"""Actual routed IPv4/IPv6 PMTU in three disposable CI namespaces per case."""
from contextlib import ExitStack
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

SPEC = importlib.util.spec_from_file_location("raw", Path(__file__).with_name("test_secret_custody_raw_packet.py"))
raw = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(raw)
t = raw.t
TABLE, LINK, ROUTER_TABLE = "kc_pmtu", "kc_pmtu_link", "kc_pmtu_router"
MTU = 1280
MACS = {"host0": "02:00:00:00:30:01", "rleft": "02:00:00:00:30:02",
        "rright": "02:00:00:00:30:03", "peer0": "02:00:00:00:30:04"}
ADDRESSES = {
    4: ("192.0.2.10", "192.0.2.1", "198.51.100.1", "198.51.100.10", "192.0.2.99"),
    6: ("2001:db8:10::10", "2001:db8:10::1", "2001:db8:20::1", "2001:db8:20::10", "2001:db8:10::99"),
}
PAYLOAD = bytes(range(256)) * 256


def guard():
    t.guard()
    if os.environ.get("KC_PMTU_CI") != "1":
        raise RuntimeError("PMTU_CI_OPT_IN_REQUIRED")


def family(version):
    if version not in ADDRESSES:
        raise ValueError("FIXED_IP_FAMILY_REQUIRED")
    return socket.AF_INET if version == 4 else socket.AF_INET6


def packet(version, source, destination, protocol, body):
    af = family(version)
    src, dst = socket.inet_pton(af, source), socket.inet_pton(af, destination)
    if version == 6:
        return struct.pack("!IHBB16s16s", 6 << 28, len(body), protocol, 64, src, dst) + body
    header = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(body), 1, 0x4000, 64, protocol, 0, src, dst)
    return header[:10] + struct.pack("!H", raw.checksum(header)) + header[12:] + body


def ip_fields(data):
    if len(data) < 20:
        raise ValueError("SHORT_IP_PACKET")
    version = data[0] >> 4
    if version == 4 and data[0] == 0x45:
        return version, 20, data[9], socket.inet_ntoa(data[12:16]), socket.inet_ntoa(data[16:20]), int.from_bytes(data[2:4], "big")
    if version == 6 and len(data) >= 40:
        return version, 40, data[6], socket.inet_ntop(socket.AF_INET6, data[8:24]), socket.inet_ntop(socket.AF_INET6, data[24:40]), 40 + int.from_bytes(data[4:6], "big")
    raise ValueError("FIXED_IP_HEADERS_REQUIRED")


def tcp_checksum(version, src, dst, segment):
    af = family(version)
    addresses = socket.inet_pton(af, src) + socket.inet_pton(af, dst)
    tail = struct.pack("!BBH", 0, 6, len(segment)) if version == 4 else struct.pack("!I3xB", len(segment), 6)
    return raw.checksum(addresses + tail + segment)


def forged_error(version, variant, quote):
    host, left, _, peer, wrong = ADDRESSES[version]
    v, offset, protocol, src, dst, length = ip_fields(quote)
    if (v != version or protocol != 6 or src != host or dst != peer
            or len(quote) != length or not offset + 20 <= length <= 256):
        raise ValueError("BOUNDED_REAL_TCP_QUOTE_REQUIRED")
    quote = bytearray(quote)
    if variant == "unrelated":
        quote[offset:offset + 2] = struct.pack("!H", 1)
    elif variant == "sequence":
        seq = int.from_bytes(quote[offset + 4:offset + 8], "big")
        quote[offset + 4:offset + 8] = struct.pack("!I", (seq + 0x80000000) & 0xffffffff)
    elif variant not in ("source", "code"):
        raise ValueError("FIXED_ERROR_VARIANT_REQUIRED")
    quote[offset + 16:offset + 18] = b"\0\0"
    quote[offset + 16:offset + 18] = struct.pack("!H", tcp_checksum(version, src, dst, quote[offset:]))
    source = wrong if variant == "source" else left
    kind, code = (3, 4) if version == 4 else (2, 0)
    if variant == "code":
        code = 1
    body = struct.pack("!BBHI", kind, code, 0, MTU) + quote
    pseudo = b""
    if version == 6:
        pseudo = socket.inet_pton(socket.AF_INET6, source) + socket.inet_pton(socket.AF_INET6, host) + struct.pack("!I3xB", len(body), 58)
    body = body[:2] + struct.pack("!H", raw.checksum(pseudo + body)) + body[4:]
    return packet(version, source, host, 1 if version == 4 else 58, body)


def validate_ptb(data, version, sport):
    host, left, right, peer, _ = ADDRESSES[version]
    v, offset, protocol, source, dest, length = ip_fields(data)
    assert v == version and protocol == (1 if version == 4 else 58)
    assert source in (left, right) and dest == host and len(data) == length
    body = data[offset:]
    assert body[:2] == (b"\x03\x04" if version == 4 else b"\x02\0")
    assert int.from_bytes(body[4:8], "big") == MTU
    pseudo = b"" if version == 4 else data[8:40] + struct.pack("!I3xB", len(body), 58)
    assert raw.checksum(pseudo + body) == 0
    quote = body[8:]
    inner_v, inner_offset, inner_protocol, src, dst, original_length = ip_fields(quote)
    assert inner_v == version and inner_protocol == 6 and src == host and dst == peer
    assert struct.unpack("!HH", quote[inner_offset:inner_offset + 4]) == (sport, 22)
    assert original_length > MTU
    if version == 4:
        assert raw.checksum(data[:offset]) == 0 and int.from_bytes(quote[6:8], "big") & 0x4000
    return {"source": source, "mtu": MTU, "quoted_length": original_length}


def captures(sock, duration=0.25):
    result, deadline = [], time.monotonic() + duration
    while time.monotonic() < deadline:
        if not select.select([sock], [], [], max(0, deadline - time.monotonic()))[0]:
            break
        data = sock.recv(65536)
        if len(result) >= 1000:
            raise RuntimeError("PACKET_CAPTURE_BOUND")
        # SOCK_RAW/ETH_P_ALL includes the Ethernet header.
        if len(data) > 14 and data[12:14] in (b"\x08\0", b"\x86\xdd"):
            result.append(data[14:])
    return result


def counts():
    return raw.counters("netdev", LINK) | raw.counters("inet", TABLE)


def gate(allow):
    verdict, comment = ("accept", "ptb_accept") if allow else ("drop", "ptb_block")
    t.nft(f'flush chain inet {TABLE} pmtu_gate\nadd rule inet {TABLE} pmtu_gate counter {verdict} comment "{comment}"\n')


def policy(version):
    host, left, right, peer, _ = ADDRESSES[version]
    ip = "ip" if version == 4 else "ip6"
    proto = "ip protocol icmp" if version == 4 else "ip6 nexthdr ipv6-icmp"
    error = "icmp type destination-unreachable icmp code frag-needed" if version == 4 else "icmpv6 type packet-too-big icmpv6 code 0"
    tcp = "ip protocol tcp" if version == 4 else "ip6 nexthdr tcp"
    exact = f"{proto} {error} {ip} saddr {{ {left}, {right} }} {ip} daddr {host}"
    return f'''table netdev {LINK} {{
      chain ingress {{ type filter hook ingress device "host0" priority 0; policy drop;
        {exact} counter accept comment "link_ptb"
        {proto} counter drop comment "link_bad_error"
        {tcp} {ip} saddr {peer} {ip} daddr {host} tcp sport 22 accept
      }}
      chain egress {{ type filter hook egress device "host0" priority 0; policy drop;
        {tcp} {ip} saddr {host} {ip} daddr {peer} tcp dport 22 accept
        counter drop comment "link_data_deny"
      }}
    }}
    table inet {TABLE} {{
      chain pmtu_gate {{ counter accept comment "ptb_accept"; }}
      chain input {{ type filter hook input priority 0; policy drop;
        iifname "lo" accept
        iifname "host0" {exact} ct state related counter jump pmtu_gate comment "related_ptb"
        {proto} counter drop comment "inet_unrelated_error"
        iifname "host0" {ip} saddr {peer} {ip} daddr {host} tcp sport 22 ct state established accept
      }}
      chain output {{ type filter hook output priority 0; policy drop;
        oifname "lo" accept
        oifname "host0" {ip} saddr {host} {ip} daddr {peer} tcp dport 22 ct state {{ new, established }} accept
        oifname "host0" {ip} saddr {host} {ip} daddr {peer} tcp dport 443 counter drop comment "inet_data_deny"
      }}
      chain forward {{ type filter hook forward priority 0; policy drop; }}
    }}\n'''


def setup_link(interface, version, address):
    t.run(t.IP, "link", "set", "lo", "up")
    t.run(t.IP, "link", "set", interface, "address", MACS[interface], "mtu", "1500", "addrgenmode", "none")
    t.run("sysctl", "-qw", f"net.ipv6.conf.{interface}.disable_ipv6=" + ("1" if version == 4 else "0"))
    t.run(t.IP, "-" + str(version), "addr", "add", address + ("/24" if version == 4 else "/64"), "dev", interface, *(("nodad",) if version == 6 else ()))
    t.run(t.IP, "link", "set", interface, "up")
    t.run("ethtool", "-K", interface, "tso", "off", "gso", "off", "gro", "off", "tx", "off")
    features = t.run("ethtool", "-k", interface).stdout.decode().splitlines()
    for name in ("tcp-segmentation-offload", "generic-segmentation-offload", "generic-receive-offload", "tx-checksumming"):
        assert any(line.startswith(name + ": off") for line in features), (interface, name)


def neighbor(interface, address, remote_interface):
    t.run(t.IP, "-6" if ":" in address else "-4", "neigh", "replace", address, "lladdr", MACS[remote_interface], "nud", "permanent", "dev", interface)


def child(role, version):
    guard()
    if os.readlink("/proc/self/ns/net") == os.environ.get("FIXTURE_PARENT_NETNS"):
        raise RuntimeError("DISTINCT_CHILD_NAMESPACE_REQUIRED")
    host, left, right, peer, _ = ADDRESSES[version]
    with ExitStack() as stack:
        tap = None
        print("READY", flush=True)
        for line in sys.stdin:
            if len(line) > 4096:
                raise RuntimeError("RPC_BOUND")
            msg = json.loads(line)
            op = msg[0]
            if op == "setup" and role == "router":
                setup_link("rleft", version, left)
                setup_link("rright", version, right)
                neighbor("rleft", host, "host0")
                neighbor("rright", peer, "peer0")
                t.run("sysctl", "-qw", "net.ipv4.ip_forward=1" if version == 4 else "net.ipv6.conf.all.forwarding=1")
                proto = "icmp type destination-unreachable icmp code frag-needed" if version == 4 else "icmpv6 type packet-too-big icmpv6 code 0"
                t.nft(f'table inet {ROUTER_TABLE} {{ chain output {{ type filter hook output priority 0; policy accept; oifname "rleft" {proto} counter accept comment "router_ptb"; }} }}')
                result = True
            elif op == "setup" and role == "peer":
                setup_link("peer0", version, peer)
                neighbor("peer0", right, "rright")
                t.run(t.IP, "-" + str(version), "route", "add", host + ("/32" if version == 4 else "/128"), "via", right, "dev", "peer0")
                for port in (22, 443):
                    t.listen(stack, peer, port)
                tap = raw.packet_socket(stack, "peer0", raw.ETH_ALL, socket.SOCK_RAW)
                tap.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)
                result = True
            elif op == "constrain":
                t.run(t.IP, "link", "set", "rright" if role == "router" else "peer0", "mtu", str(MTU))
                if tap:
                    captures(tap)
                result = True
            elif op == "router_count" and role == "router":
                result = raw.counters("inet", ROUTER_TABLE)["router_ptb"]
            elif op == "inject" and role == "router":
                data = forged_error(version, msg[1], bytes.fromhex(msg[2]))
                protocol = 0x800 if version == 4 else 0x86dd
                with ExitStack() as send_stack:
                    sock = raw.packet_socket(send_stack, "rleft", protocol)
                    assert sock.sendto(data, ("rleft", protocol, 0, 0, bytes.fromhex(MACS["host0"].replace(":", "")))) == len(data)
                result = data.hex()
            elif op == "sizes" and role == "peer":
                result = []
                for data in captures(tap):
                    v, offset, proto, src, dst, length = ip_fields(data)
                    if v == version and proto == 6 and src == host and dst == peer and data[offset + 2:offset + 4] == b"\0\x16":
                        assert len(data) == length
                        if version == 4:
                            assert not int.from_bytes(data[6:8], "big") & 0x3fff
                        if length > offset + (data[offset + 12] >> 4) * 4:
                            result.append(length)
            elif op == "stop":
                break
            else:
                raise RuntimeError("FIXED_RPC_OPERATION_REQUIRED")
            print(json.dumps(result), flush=True)


def state(sock, version):
    level, option = (socket.IPPROTO_IP, 14) if version == 4 else (socket.IPPROTO_IPV6, 24)
    info = sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_INFO, 104)
    assert len(info) >= 64
    return {"socket_mtu": sock.getsockopt(level, option),
            "tcp_pmtu": struct.unpack_from("=I", info, 60)[0],
            "snd_mss": struct.unpack_from("=I", info, 16)[0]}


def out_of_window():
    lines = Path("/proc/net/netstat").read_text().splitlines()
    for index in range(0, len(lines), 2):
        names, values = lines[index].split(), lines[index + 1].split()
        if names[0] == "TcpExt:":
            return int(dict(zip(names[1:], values[1:]))["OutOfWindowIcmps"])
    raise RuntimeError("TCP_REJECTION_COUNTER_REQUIRED")


def finish(proc):
    proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2)
    assert proc.poll() is not None


def empty():
    assert {x["ifname"] for x in json.loads(t.run(t.IP, "-j", "link").stdout)} == {"lo"}
    assert all("metainfo" in x for x in json.loads(t.run(t.NFT, "-j", "list", "ruleset").stdout)["nftables"])


def run_case(version):
    guard()
    family(version)
    empty()
    host, left, _, peer, _ = ADDRESSES[version]
    env = dict(os.environ, FIXTURE_PARENT_NETNS=os.readlink("/proc/self/ns/net"))
    processes = []
    phase = "setup"
    try:
        for role in ("router", "peer"):
            proc = subprocess.Popen(["unshare", "--net", sys.executable, "-I", "-B", __file__, "--" + role, str(version)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env)
            processes.append(proc)
            assert t.read_line(proc).strip() == "READY"
        router, receiver = processes
        t.run(t.IP, "link", "add", "host0", "type", "veth", "peer", "name", "rleft")
        t.run(t.IP, "link", "set", "rleft", "netns", str(router.pid))
        t.run(t.IP, "link", "add", "rright", "type", "veth", "peer", "name", "peer0")
        t.run(t.IP, "link", "set", "rright", "netns", str(router.pid))
        t.run(t.IP, "link", "set", "peer0", "netns", str(receiver.pid))
        setup_link("host0", version, host)
        neighbor("host0", left, "rleft")
        t.run(t.IP, "-" + str(version), "route", "add", peer + ("/32" if version == 4 else "/128"), "via", left, "dev", "host0")
        t.run("sysctl", "-qw", "net.ipv4.tcp_mtu_probing=0")
        assert t.rpc(router, "setup") and t.rpc(receiver, "setup")
        assert t.reaches(peer, 443) and t.reaches(peer, 22)
        print(f"PASS IPv{version}_ROUTED_UNFILTERED_POSITIVE_CONTROLS", flush=True)
        t.nft(policy(version))
        with ExitStack() as stack:
            tap = raw.packet_socket(stack, "host0", raw.ETH_ALL, socket.SOCK_RAW)
            tap.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)
            admin = stack.enter_context(t.connect(peer, 22))
            bulk = stack.enter_context(t.connect(peer, 22))
            sport = bulk.getsockname()[1]
            assert t.exchange(admin) and t.exchange(bulk)
            assert not t.reaches(peer, 443)
            initial = state(bulk, version)
            assert initial["socket_mtu"] == initial["tcp_pmtu"] == 1500 and initial["snd_mss"] > MTU
            quotes = []
            for data in captures(tap):
                v, offset, proto, src, dst, length = ip_fields(data)
                if v == version and proto == 6 and src == host and dst == peer and data[offset:offset + 4] == struct.pack("!HH", sport, 22) and length <= 256:
                    quotes.append(data)
            assert quotes, "REAL_TCP_QUOTE_REQUIRED"
            for variant in ("source", "code", "unrelated", "sequence"):
                phase = "forged-" + variant
                before, rejected = counts(), out_of_window()
                data = bytes.fromhex(t.rpc(router, "inject", variant, quotes[-1].hex()))
                assert data in captures(tap), "FORGED_ERROR_NOT_OBSERVED_AT_LINK"
                after = counts()
                if variant in ("source", "code"):
                    assert after["link_bad_error"] == before["link_bad_error"] + 1
                    assert after["link_ptb"] == before["link_ptb"]
                else:
                    assert after["link_ptb"] == before["link_ptb"] + 1
                    key = "inet_unrelated_error" if variant == "unrelated" else "ptb_accept"
                    assert after[key] == before[key] + 1
                    if variant == "sequence":
                        assert out_of_window() == rejected + 1
                assert state(bulk, version)["socket_mtu"] == 1500
                assert t.exchange(admin)
            print(f"PASS IPv{version}_FORGED_HEADER_UNRELATED_QUOTE_AND_SEQUENCE_REJECTION", flush=True)
            phase = "blocked-real-ptb"
            gate(False)
            assert t.rpc(router, "constrain") and t.rpc(receiver, "constrain")
            assert state(bulk, version)["socket_mtu"] == 1500
            assert json.loads(t.run(t.IP, "-j", "link", "show", "host0").stdout)[0]["mtu"] == 1500
            captures(tap)
            before, generated = counts(), t.rpc(router, "router_count")
            bulk.sendall(PAYLOAD)
            try:
                data = bulk.recv(1)
            except socket.timeout:
                pass
            else:
                raise AssertionError(("PTB_BLOCK_MUST_STALL_SAME_FLOW", len(data)))
            errors = []
            for data in captures(tap):
                _, _, proto, _, _, _ = ip_fields(data)
                if proto == (1 if version == 4 else 58):
                    errors.append(validate_ptb(data, version, sport))
            assert errors, "REAL_ROUTER_PTB_REQUIRED"
            blocked = counts()
            assert t.rpc(router, "router_count") > generated
            assert blocked["link_ptb"] > before["link_ptb"] and blocked["ptb_block"] > before["ptb_block"]
            assert state(bulk, version)["socket_mtu"] == 1500
            assert t.exchange(admin) and t.reaches(peer, 22)
            print(f"PASS IPv{version}_REAL_ROUTER_PTB_BLOCK_STALL", json.dumps(errors), flush=True)
            phase = "same-flow-recovery"
            gate(True)
            bulk.settimeout(8)
            received = bytearray()
            deadline = time.monotonic() + 8
            while len(received) < len(PAYLOAD):
                bulk.settimeout(max(0.01, deadline - time.monotonic()))
                chunk = bulk.recv(len(PAYLOAD) - len(received))
                assert chunk and time.monotonic() < deadline
                received += chunk
            assert received == PAYLOAD
            final = state(bulk, version)
            assert final["socket_mtu"] == final["tcp_pmtu"] == MTU
            assert 0 < final["snd_mss"] <= MTU - (40 if version == 4 else 60)
            assert counts()["ptb_accept"] > 0
            sizes = t.rpc(receiver, "sizes")
            assert sizes and max(sizes) == MTU and all(size <= MTU for size in sizes)
            assert t.exchange(admin) and t.reaches(peer, 22)
            denied_before = counts()["inet_data_deny"]
            assert not t.reaches(peer, 443)
            assert counts()["inet_data_deny"] > denied_before
            print(f"PASS IPv{version}_SAME_FLOW_RECOVERY_PMTU_MSS_WIRE_SIZE_AND_DENIAL", json.dumps({"initial": initial, "final": final, "received_bytes": len(received), "max_wire_ip_length": max(sizes)}), flush=True)
    except BaseException:
        print("PMTU_FAILURE", version, phase, file=sys.stderr)
        print(t.run(t.IP, "-" + str(version), "route", "get", peer, success=False).stdout[:2000].decode(), file=sys.stderr)
        print(t.run(t.NFT, "list", "ruleset", success=False).stdout[:7000].decode(), file=sys.stderr)
        raise
    finally:
        for proc in reversed(processes):
            finish(proc)
        for interface in ("host0", "rright", "peer0", "rleft"):
            t.run(t.IP, "link", "del", interface, success=False)
        for nft_family, table in (("inet", TABLE), ("netdev", LINK)):
            t.nft(f"delete table {nft_family} {table}\n", success=False)
        empty()
    print(f"PASS IPv{version}_PMTU_NAMESPACES_PROCESSES_LINKS_RULES_CLEANED", flush=True)


class Tests(unittest.TestCase):
    def test_host_namespace_refused_before_commands(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), patch.object(os, "geteuid", return_value=0), patch.object(os, "readlink", return_value="same"), patch.object(t, "run") as run:
            with self.assertRaises(RuntimeError):
                run_case(4)
            run.assert_not_called()

    def test_opt_in_required_before_commands(self):
        with patch.object(t, "guard"), patch.dict(os.environ, {"KC_PMTU_CI": "0"}), patch.object(t, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "PMTU_CI_OPT_IN_REQUIRED"):
                run_case(6)
            run.assert_not_called()

    def test_fixed_headers_and_bounded_quotes_required(self):
        for data in (b"", b"\x45" * 8, b"\x47" + bytes(39)):
            with self.assertRaises(ValueError):
                ip_fields(data)
        with self.assertRaises(ValueError):
            family(7)
        with self.assertRaises(ValueError):
            forged_error(4, "sequence", packet(4, ADDRESSES[4][0], ADDRESSES[4][3], 6, bytes(300)))

    def test_forged_errors_have_real_checksums_and_changed_sequence(self):
        for version in (4, 6):
            host, _, _, peer, _ = ADDRESSES[version]
            segment = struct.pack("!HHIIBBHHH", 40000, 22, 100, 1, 0x50, 0x10, 1000, 0, 0)
            quote = packet(version, host, peer, 6, segment)
            for variant in ("source", "code", "unrelated", "sequence"):
                error = forged_error(version, variant, quote)
                _, offset, _, src, dst, length = ip_fields(error)
                body = error[offset:]
                pseudo = b"" if version == 4 else error[8:40] + struct.pack("!I3xB", len(body), 58)
                self.assertEqual(length, len(error))
                self.assertEqual(raw.checksum(pseudo + body), 0)
                if version == 4:
                    self.assertEqual(raw.checksum(error[:offset]), 0)
                inner = body[8:]
                self.assertEqual(tcp_checksum(version, host, peer, inner[offset:]), 0)
                if variant == "sequence":
                    self.assertEqual(int.from_bytes(inner[offset + 4:offset + 8], "big"), 0x80000064)


if __name__ == "__main__":
    if sys.argv[1:] == ["--kernel"]:
        guard()
        print("KERNEL", os.uname().release, flush=True)
        for version in (4, 6):
            run_case(version)
        print("RESULT SYNTHETIC_ROUTED_PMTU_OK_NO_LIVE_APPLY", flush=True)
    elif len(sys.argv) == 3 and sys.argv[1] in ("--router", "--peer") and sys.argv[2] in ("4", "6"):
        child(sys.argv[1][2:], int(sys.argv[2]))
    else:
        unittest.main(verbosity=2)
