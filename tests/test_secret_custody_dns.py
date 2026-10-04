"""Real dig UDP/TCP behavior through restricted recovery in private CI netns.

Fixed synthetic DNS only. No host resolver configuration, cache or DNSSEC claim.
"""
from contextlib import ExitStack
import importlib.util
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("recovery", Path(__file__).with_name("test_secret_custody_dynamic_recovery.py"))
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)
t, raw = r.t, r.raw
TABLE, LINK, KEY = "kc_dns", "kc_dns_link", "dns"
FAMILIES = ((4, "ip", "192.0.2."), (6, "ip6", "2001:db8:1::"))
NAME = "fixture.invalid."
QNAME = b"\x07fixture\x07invalid\0"
DIG = "/usr/bin/dig"


def guard():
    t.guard()
    if os.environ.get("KC_DNS_CI") != "1":
        raise RuntimeError("DNS_CI_OPT_IN_REQUIRED")


def question(data):
    if not 17 <= len(data) <= 512:
        raise ValueError("BOUNDED_DNS_QUERY_REQUIRED")
    ident, flags, qd, an, ns, ar = struct.unpack("!6H", data[:12])
    if (flags not in (0, 0x100) or (qd, an, ns, ar) != (1, 0, 0, 0)
            or data[12:-4] != QNAME):
        raise ValueError("FIXED_DNS_QUERY_REQUIRED")
    kind, cls = struct.unpack("!HH", data[-4:])
    if kind not in (1, 28) or cls != 1:
        raise ValueError("FIXED_DNS_TYPE_REQUIRED")
    return ident, flags, kind


def answer_address(kind, generation):
    if kind not in (1, 28) or generation not in (0, 1):
        raise ValueError("FIXED_ANSWER_REQUIRED")
    return ("198.51.100." if kind == 1 else "2001:db8:2::") + str(60 + generation)


def response(data, truncated=False, generation=0):
    ident, flags, kind = question(data)
    header = struct.pack("!6H", ident, 0x8400 | flags | (0x200 if truncated else 0), 1, 0 if truncated else 1, 0, 0)
    if truncated:
        return header + data[12:]
    payload = socket.inet_pton(socket.AF_INET if kind == 1 else socket.AF_INET6, answer_address(kind, generation))
    return header + data[12:] + b"\xc0\x0c" + struct.pack("!HHIH", kind, 1, 0, len(payload)) + payload


def policy(mode="maintenance"):
    if mode not in ("maintenance", "qualification"):
        raise ValueError("FIXED_DNS_PROFILE_REQUIRED")
    rules = {key: [] for key in ("input", "output", "ingress", "egress")}
    for version, ip, prefix in FAMILIES:
        host, peer = prefix + "1", prefix + "2"
        incoming = f'{ip} saddr {peer} {ip} daddr {host}'
        outgoing = f'{ip} saddr {host} {ip} daddr {peer}'
        ports = "{ 22, 53, 443 }" if mode == "qualification" else "{ 22, 53 }"
        rules["input"] += [f'iifname "host0" {incoming} tcp sport {ports} ct state established accept',
                           f'iifname "host0" {incoming} udp sport 53 ct state established counter accept comment "dns{version}_in"']
        rules["output"] += [f'oifname "host0" {outgoing} tcp dport {ports} ct state {{ new, established }} accept',
                            f'oifname "host0" {outgoing} udp dport 53 ct state {{ new, established }} counter accept comment "dns{version}_out"']
        rules["ingress"] += [f'meta protocol {ip} {incoming} tcp sport {ports} accept',
                             f'meta protocol {ip} {incoming} udp sport 53 counter accept comment "link_dns{version}_in"']
        rules["egress"] += [f'meta protocol {ip} {outgoing} tcp dport {ports} accept',
                            f'meta protocol {ip} {outgoing} udp dport 53 accept']
    text = f"table inet {TABLE} {{\n"
    for chain in ("input", "output"):
        text += f" chain {chain} {{ type filter hook {chain} priority 0; policy drop;\n"
        text += ('  iifname "lo" accept\n' if chain == "input" else '  oifname "lo" accept\n')
        text += "\n".join(rules[chain]) + f'\n counter drop comment "inet_{chain}_deny"\n }}\n'
    text += " chain forward { type filter hook forward priority 0; policy drop; }\n}\n"
    text += f"table netdev {LINK} {{\n"
    for chain in ("ingress", "egress"):
        text += f' chain {chain} {{ type filter hook {chain} device "host0" priority 0; policy drop;\n'
        text += "\n".join(rules[chain]) + f'\n counter drop comment "link_{chain}_deny"\n }}\n'
    return text + "}\n"


def counts():
    return raw.counters("inet", TABLE) | raw.counters("netdev", LINK)


class Server:
    def __init__(self, stack, address):
        self.lock = threading.Lock()
        self.mode, self.generation, self.events, self.error = "answer", 0, [], None
        self.sockets = {}
        for transport in ("udp", "tcp"):
            af = socket.AF_INET6 if ":" in address else socket.AF_INET
            sock = stack.enter_context(socket.socket(af, socket.SOCK_DGRAM if transport == "udp" else socket.SOCK_STREAM))
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if af == socket.AF_INET6:
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            sock.bind((address, 53))
            if transport == "tcp":
                sock.listen(8)
            self.sockets[transport] = sock
            threading.Thread(target=self.serve, args=(transport, sock), daemon=True).start()

    def reply(self, data, transport):
        _, _, kind = question(data)
        with self.lock:
            if len(self.events) >= 128:
                raise RuntimeError("DNS_EVENT_BOUND")
            self.events.append([transport, kind, self.mode, self.generation])
            if self.mode == "silent":
                return None
            return response(data, self.mode == "truncate" and transport == "udp", self.generation)

    @staticmethod
    def read_exact(conn, length):
        data = bytearray()
        while len(data) < length:
            part = conn.recv(length - len(data))
            if not part:
                raise ValueError("SHORT_DNS_TCP_MESSAGE")
            data += part
        return bytes(data)

    def serve(self, transport, sock):
        try:
            while True:
                if transport == "udp":
                    data, source = sock.recvfrom(513)
                    reply = self.reply(data, transport)
                    if reply is not None:
                        sock.sendto(reply, source)
                else:
                    conn, _ = sock.accept()
                    with conn:
                        conn.settimeout(2)
                        length = int.from_bytes(self.read_exact(conn, 2), "big")
                        if not 17 <= length <= 512:
                            raise ValueError("DNS_TCP_BOUND")
                        reply = self.reply(self.read_exact(conn, length), transport)
                        if reply is not None:
                            conn.sendall(struct.pack("!H", len(reply)) + reply)
        except BaseException as exc:
            self.error = type(exc).__name__


def peer():
    guard()
    assert os.readlink("/proc/self/ns/net") != os.environ.get("FIXTURE_PARENT_NETNS")
    with ExitStack() as stack:
        servers = {}
        print("READY", flush=True)
        for line in sys.stdin:
            if len(line) > 1024:
                raise RuntimeError("DNS_RPC_BOUND")
            msg = json.loads(line)
            op = msg[0]
            if op == "setup":
                t.run(t.IP, "link", "set", "peer0", "addrgenmode", "none")
                t.run("sysctl", "-qw", "net.ipv6.conf.peer0.accept_ra=0")
                t.setup("peer0", t.MAC_PEER, ("2", "3", "9"))
                for _, _, prefix in FAMILIES:
                    for suffix in ("2", "3"):
                        servers[prefix + suffix] = Server(stack, prefix + suffix)
                    for port in (22, 443):
                        t.listen(stack, prefix + "2", port)
                result = True
            elif op == "configure":
                _, address, mode, generation = msg
                if mode not in ("answer", "truncate", "silent") or generation not in (0, 1):
                    raise ValueError("FIXED_DNS_MODE_REQUIRED")
                server = servers[address]
                with server.lock:
                    server.mode, server.generation, server.events = mode, generation, []
                result = True
            elif op == "events":
                server = servers[msg[1]]
                with server.lock:
                    result = list(server.events)
            elif op == "unsolicited":
                _, address, destination, port = msg
                assert destination in ("192.0.2.1", "2001:db8:1::1") and 1024 <= port <= 65535
                query = struct.pack("!6H", 1234, 0, 1, 0, 0, 0) + QNAME + struct.pack("!HH", 1, 1)
                servers[address].sockets["udp"].sendto(response(query), (destination, port))
                result = True
            elif op == "stop":
                break
            else:
                raise RuntimeError("FIXED_DNS_RPC_REQUIRED")
            assert all(server.error is None for server in servers.values()), "DNS_SERVER_THREAD_FAILED"
            print(json.dumps(result), flush=True)


def query(version, endpoint=2, kind=1, tcp=False, success=True, generation=0):
    guard()
    if version not in (4, 6) or endpoint not in (2, 3) or kind not in (1, 28):
        raise ValueError("FIXED_DNS_QUERY_TARGET_REQUIRED")
    prefix = FAMILIES[0 if version == 4 else 1][2]
    result = t.run(DIG, "-r", "-" + str(version), "@" + prefix + str(endpoint), NAME,
                   "A" if kind == 1 else "AAAA", "+noedns", "+nocookie", "+noadflag", "+nocdflag", "+norecurse",
                   "+nosearch", "+tries=1", "+time=1", "+short", "+tcp" if tcp else "+notcp", success=False)
    validate_result(result, success, kind, generation)


def validate_result(result, success, kind=1, generation=0):
    assert len(result.stdout) + len(result.stderr) < 4096
    # dig emits both single- and double-semicolon diagnostics on timeout.
    lines = [line for line in result.stdout.decode().splitlines() if line and not line.startswith(";")]
    if success:
        assert result.returncode == 0 and lines == [answer_address(kind, generation)], (result.returncode, result.stdout[:1000], result.stderr[:1000])
    else:
        assert result.returncode == 9 and not lines, (result.returncode, result.stdout[:1000])


def transport(proc, version, phase, generation=0):
    address = FAMILIES[0 if version == 4 else 1][2] + "2"
    for mode, tcp, expected in (("answer", False, ["udp"]), ("answer", True, ["tcp"]), ("truncate", False, ["udp", "tcp"])):
        assert t.rpc(proc, "configure", address, mode, generation)
        for kind in (1, 28):
            query(version, kind=kind, tcp=tcp, generation=generation)
        events = t.rpc(proc, "events", address)
        assert events == [[way, kind, mode, generation] for kind in (1, 28) for way in expected], events
    print(f"PASS IPv{version}_DNS_{phase}_A_AAAA_UDP_TCP_TRUNCATION_FALLBACK", flush=True)


def empty():
    assert {x["ifname"] for x in json.loads(t.run(t.IP, "-j", "link").stdout)} == {"lo"}
    assert all("metainfo" in x for x in json.loads(t.run(t.NFT, "-j", "list", "ruleset").stdout)["nftables"])


def kernel():
    guard()
    r.guard()
    empty()
    # Keep unsolicited replies outside all automatically chosen dig source ports.
    assert int(Path("/proc/sys/net/ipv4/ip_local_port_range").read_text().split()[1]) < 62000
    version = t.run(DIG, "-v")
    identity = (version.stdout + version.stderr).decode().strip()
    assert identity.startswith("DiG ") and len(identity) < 256
    print("DIG", identity, "KERNEL", os.uname().release, flush=True)
    env = dict(os.environ, FIXTURE_PARENT_NETNS=os.readlink("/proc/self/ns/net"))
    proc = subprocess.Popen(["unshare", "--net", sys.executable, "-I", "-B", __file__, "--peer"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env)
    try:
        assert t.read_line(proc).strip() == "READY"
        t.run(t.IP, "link", "add", "host0", "type", "veth", "peer", "name", "peer0")
        t.run(t.IP, "link", "set", "peer0", "netns", str(proc.pid))
        t.run(t.IP, "link", "set", "host0", "addrgenmode", "none")
        t.run("sysctl", "-qw", "net.ipv6.conf.host0.accept_ra=0")
        t.setup("host0", t.MAC_HOST, ("1",))
        assert t.rpc(proc, "setup")
        for version, _, prefix in FAMILIES:
            for endpoint in (2, 3):
                query(version, endpoint=endpoint)
                query(version, endpoint=endpoint, tcp=True)
            assert t.reaches(prefix + "2", 22) and t.reaches(prefix + "2", 443)
        print("PASS DNS_UNFILTERED_BOTH_ENDPOINTS_AND_TRANSPORTS", flush=True)
        t.nft(policy())
        maintenance = r.shape(KEY)
        t.nft(r.replacement(KEY, "qualification"))
        candidate = r.shape(KEY)
        t.nft(r.replacement(KEY, "maintenance"))
        assert maintenance != candidate and r.shape(KEY) == maintenance
        with ExitStack() as stack:
            admin = [stack.enter_context(t.connect(prefix + "2", 22)) for _, _, prefix in FAMILIES]
            def check():
                assert all(t.exchange(conn) for conn in admin)
            for version, _, _ in FAMILIES:
                transport(proc, version, "MAINTENANCE")
            old = []
            with r.armed(KEY, maintenance, candidate) as (path, _):
                r.invoke_controller(path, KEY, "after")
                assert r.shape(KEY) == candidate
                for version, _, prefix in FAMILIES:
                    conn = stack.enter_context(t.connect(prefix + "2", 443))
                    assert t.exchange(conn)
                    old.append(conn)
                    transport(proc, version, "AFTER_CONTROLLER_SIGKILL")
                check()
                assert not (path / "result").exists()
                r.d.wait_for(lambda: (path / "result").exists(), 10, check)
                assert (path / "result").read_text() == "RESTORE_MAINTENANCE"
            assert r.shape(KEY) == maintenance and all(not t.exchange(conn) for conn in old)
            check()
            print("PASS DNS_PID1_TWO_TABLE_RESTORE_OLD_QUALIFICATION_REVOKED", flush=True)
            for version, _, prefix in FAMILIES:
                address, host = prefix + "2", prefix + "1"
                assert t.reaches(address, 22) and not t.reaches(address, 443)
                transport(proc, version, "POST_RESTORE")
                assert t.rpc(proc, "configure", address, "silent", 0)
                query(version, success=False)
                assert t.rpc(proc, "events", address) == [["udp", 1, "silent", 0]]
                # A resolver address change is not permission to widen policy.
                assert t.rpc(proc, "configure", prefix + "3", "answer", 0)
                before = counts()["inet_output_deny"]
                query(version, endpoint=3, success=False)
                query(version, endpoint=3, tcp=True, success=False)
                assert t.rpc(proc, "events", prefix + "3") == []
                assert counts()["inet_output_deny"] > before
                check()
                assert r.shape(KEY) == maintenance
                transport(proc, version, "REANSWER_CHANGED_DATA", generation=1)
                print(f"PASS IPv{version}_DNS_OUTAGE_CHANGED_ENDPOINT_DENIED_AND_REQUERY", flush=True)
                af = socket.AF_INET if version == 4 else socket.AF_INET6
                with socket.socket(af, socket.SOCK_DGRAM) as udp:
                    udp.bind((host, 62000))
                    udp.settimeout(0.4)
                    before = counts()
                    assert t.rpc(proc, "unsolicited", address, host, udp.getsockname()[1])
                    try:
                        udp.recv(512)
                    except socket.timeout:
                        pass
                    else:
                        raise AssertionError("UNSOLICITED_DNS_DELIVERED")
                    after = counts()
                    assert after[f"link_dns{version}_in"] == before[f"link_dns{version}_in"] + 1
                    assert after["inet_input_deny"] == before["inet_input_deny"] + 1
                    before = after
                    assert t.rpc(proc, "unsolicited", prefix + "3", host, udp.getsockname()[1])
                    try:
                        udp.recv(512)
                    except socket.timeout:
                        pass
                    else:
                        raise AssertionError("WRONG_DNS_SOURCE_DELIVERED")
                    assert counts()["link_ingress_deny"] == before["link_ingress_deny"] + 1
                print(f"PASS IPv{version}_DNS_UNSOLICITED_AND_WRONG_SOURCE_DENIED", flush=True)
            check()
            assert r.shape(KEY) == maintenance
            assert all(not t.exchange(conn) for conn in old)
            assert all(not t.reaches(prefix + "2", 443) for _, _, prefix in FAMILIES)
            print("PASS DNS_FINAL_RESTRICTED_SHAPE_ADMIN_AND_OLD_NEW_DENIAL", flush=True)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
        proc.stdin.close()
        proc.stdout.close()
        t.run(t.IP, "link", "del", "host0", success=False)
        t.run(t.IP, "link", "del", "peer0", success=False)
        for family, table in (("inet", TABLE), ("netdev", LINK)):
            t.nft(f"delete table {family} {table}\n", success=False)
        empty()
    print("PASS DNS_PROCESSES_LINKS_TABLES_CLEANED", flush=True)
    print("RESULT SYNTHETIC_DNS_INDEPENDENT_RECOVERY_OK_NO_LIVE_APPLY", flush=True)


class Tests(unittest.TestCase):
    def test_host_namespace_refused_before_commands(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), patch.object(os, "geteuid", return_value=0), patch.object(os, "readlink", return_value="same"), patch.object(t, "run") as command:
            with self.assertRaises(RuntimeError):
                kernel()
            command.assert_not_called()

    def test_opt_in_required_before_commands(self):
        with patch.object(t, "guard"), patch.dict(os.environ, {"KC_DNS_CI": "0"}), patch.object(t, "run") as command:
            with self.assertRaisesRegex(RuntimeError, "DNS_CI_OPT_IN_REQUIRED"):
                kernel()
            command.assert_not_called()

    def test_bounded_question_and_fixed_record(self):
        query = struct.pack("!6H", 4567, 0x100, 1, 0, 0, 0) + QNAME + struct.pack("!HH", 1, 1)
        self.assertEqual(question(query), (4567, 0x100, 1))
        self.assertEqual(struct.unpack("!6H", response(query, True)[:12]), (4567, 0x8700, 1, 0, 0, 0))
        self.assertTrue(response(query, generation=1).endswith(socket.inet_aton("198.51.100.61")))
        for data in (b"", query + b"x", bytes(513), response(query), query[:-4] + struct.pack("!HH", 252, 1)):
            with self.assertRaises(ValueError):
                question(data)

    def test_timeout_diagnostics_are_not_answers_or_arbitrary_failure_success(self):
        diagnostics = b";; communications error: timed out\n\n; <<>> DiG 9.18 <<>>\n; (1 server found)\n;; no servers could be reached\n"
        validate_result(subprocess.CompletedProcess([], 9, diagnostics, b""), False)
        for code, output in ((1, diagnostics), (0, diagnostics), (9, diagnostics + b"198.51.100.60\n")):
            with self.assertRaises(AssertionError):
                validate_result(subprocess.CompletedProcess([], code, output, b""), False)
        with self.assertRaises(AssertionError):
            validate_result(subprocess.CompletedProcess([], 0, diagnostics, b""), True)

    def test_tcp_framing_handles_fragmentation_and_rejects_eof(self):
        with patch.object(socket.socket, "recv", side_effect=[b"a", b"bc"]) as receive:
            with socket.socket() as conn:
                self.assertEqual(Server.read_exact(conn, 3), b"abc")
            self.assertEqual([call.args[0] for call in receive.call_args_list], [3, 2])
        with socket.socket() as conn, patch.object(socket.socket, "recv", return_value=b""):
            with self.assertRaisesRegex(ValueError, "SHORT_DNS_TCP_MESSAGE"):
                Server.read_exact(conn, 2)


if __name__ == "__main__":
    if sys.argv[1:] == ["--systemd"]:
        kernel()
    elif sys.argv[1:] == ["--peer"]:
        peer()
    else:
        unittest.main(verbosity=2)
