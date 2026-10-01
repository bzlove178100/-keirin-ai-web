"""Real nft/packet rehearsal, confined to two disposable CI network namespaces.

No skipped success: --kernel requires root, CI and an already-isolated namespace.
Default mode checks the guard and pure renderer without requiring privilege.
"""
from contextlib import ExitStack
import importlib.util
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("rehearsal", ROOT / "review/secret_custody_network_rehearsal.py")
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)
IP = "/usr/sbin/ip"
NFT = "/usr/sbin/nft"
MAC_HOST = "02:00:00:00:01:01"
MAC_PEER = "02:00:00:00:01:02"


def guard():
    if (os.environ.get("GITHUB_ACTIONS") != "true" or os.geteuid() != 0
            or os.readlink("/proc/self/ns/net") == os.readlink("/proc/1/ns/net")):
        raise RuntimeError("DISPOSABLE_CI_NETWORK_NAMESPACE_REQUIRED")


def run(*args, data=None, success=True):
    result = subprocess.run(args, input=data, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=5)
    if success and result.returncode != 0:
        raise RuntimeError("FIXTURE_COMMAND_FAILED:" + Path(args[0]).name)
    return result


def nft(text, success=True):
    return run(NFT, "-f", "-", data=text.encode(), success=success)


def shape(table):
    data = json.loads(run(NFT, "-j", "list", "table", "inet", table).stdout)
    def clean(value):
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items() if k != "handle"}
        if isinstance(value, list):
            return [clean(v) for v in value]
        return value
    return clean([x for x in data["nftables"] if "metainfo" not in x])


def owned_transition(expected, mode):
    if shape(r.TABLE) != expected:
        raise RuntimeError("OWNED_TABLE_CHANGED_STOP")
    nft(r.replacement(mode))
    return shape(r.TABLE)


def setup(interface, mac, suffixes):
    run(IP, "link", "set", "lo", "up")
    run(IP, "link", "set", interface, "address", mac)
    for suffix in suffixes:
        run(IP, "addr", "add", "192.0.2." + suffix + "/24", "dev", interface)
        run(IP, "-6", "addr", "add", "2001:db8:1::" + suffix + "/64", "dev", interface, "nodad")
    run(IP, "link", "set", interface, "up")
    # Static fixture neighbours intentionally avoid claiming DHCP/RA/ND coverage.
    remote = ("1",) if interface == "peer0" else ("2", "3", "9")
    remote_mac = MAC_HOST if interface == "peer0" else MAC_PEER
    for suffix in remote:
        for flag, address in (("-4", "192.0.2." + suffix), ("-6", "2001:db8:1::" + suffix)):
            run(IP, flag, "neigh", "replace", address, "lladdr", remote_mac,
                "nud", "permanent", "dev", interface)


def listen(stack, address, port, udp=False):
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    sock = stack.enter_context(socket.socket(family, socket.SOCK_DGRAM if udp else socket.SOCK_STREAM))
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if family == socket.AF_INET6:
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
    sock.bind((address, port))
    if not udp:
        sock.listen(16)

    def echo(conn):
        with conn:
            conn.settimeout(20)
            try:
                while True:
                    data = conn.recv(64)
                    if not data:
                        break
                    conn.sendall(data)
            except OSError:
                pass

    def serve():
        try:
            while True:
                if udp:
                    data, addr = sock.recvfrom(64)
                    sock.sendto(data, addr)
                else:
                    conn, _ = sock.accept()
                    threading.Thread(target=echo, args=(conn,), daemon=True).start()
        except OSError:
            pass
    threading.Thread(target=serve, daemon=True).start()


def connect(address, port, source=None):
    sock = socket.socket(socket.AF_INET6 if ":" in address else socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.4)
    try:
        if source is not None:
            sock.bind((source, 0))
        sock.connect((address, port))
        return sock
    except BaseException:
        sock.close()
        raise


def exchange(sock):
    try:
        sock.sendall(b"probe")
        return sock.recv(5) == b"probe"
    except OSError:
        return False


def reaches(address, port, source=None, udp=False):
    try:
        if udp:
            with socket.socket(socket.AF_INET6 if ":" in address else socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(0.4)
                sock.sendto(b"probe", (address, port))
                return sock.recvfrom(5)[0] == b"probe"
        with connect(address, port, source) as sock:
            return exchange(sock)
    except OSError:
        return False


def peer():
    guard()
    if os.readlink("/proc/self/ns/net") == os.environ.get("FIXTURE_PARENT_NETNS"):
        raise RuntimeError("DISTINCT_PEER_NAMESPACE_REQUIRED")
    with ExitStack() as stack:
        connections = {}
        print("READY", flush=True)
        for line in sys.stdin:
            message = json.loads(line)
            op = message[0]
            if op == "setup":
                setup("peer0", MAC_PEER, ("2", "3", "9"))
                for prefix in ("192.0.2.", "2001:db8:1::"):
                    for suffix in ("2", "3"):
                        for port in (53, 443, 8443):
                            listen(stack, prefix + suffix, port)
                    for port in (53, 123):
                        listen(stack, prefix + "2", port, udp=True)
                result = True
            elif op == "open":
                _, key, address, source = message
                connections[key] = stack.enter_context(connect(address, 22, source))
                result = exchange(connections[key])
            elif op == "exchange":
                result = exchange(connections[message[1]])
            elif op == "reaches":
                _, address, port, source = message
                result = reaches(address, port, source)
            elif op == "stop":
                break
            else:
                raise RuntimeError("UNKNOWN_FIXTURE_OPERATION")
            print(json.dumps(result), flush=True)


def read_line(proc):
    if not select.select([proc.stdout], [], [], 5)[0]:
        raise RuntimeError("PEER_DEADLINE")
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError("PEER_EXITED")
    return line


def rpc(proc, *message):
    proc.stdin.write(json.dumps(message) + "\n")
    proc.stdin.flush()
    return json.loads(read_line(proc))


def kernel_rehearsal():
    guard()
    interfaces = json.loads(run(IP, "-j", "link", "show").stdout)
    if {x["ifname"] for x in interfaces} != {"lo"}:
        raise RuntimeError("EMPTY_FIXTURE_NAMESPACE_REQUIRED")
    initial = json.loads(run(NFT, "-j", "list", "ruleset").stdout)
    if any("metainfo" not in obj for obj in initial["nftables"]):
        raise RuntimeError("EMPTY_FIXTURE_RULESET_REQUIRED")
    env = dict(os.environ, FIXTURE_PARENT_NETNS=os.readlink("/proc/self/ns/net"))
    proc = subprocess.Popen(["unshare", "--net", sys.executable, "-I", "-B", __file__, "--peer"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env)
    try:
        assert read_line(proc).strip() == "READY"
        run(IP, "link", "add", "host0", "type", "veth", "peer", "name", "peer0")
        run(IP, "link", "set", "peer0", "netns", str(proc.pid))
        setup("host0", MAC_HOST, ("1",))
        assert rpc(proc, "setup") is True
        # Unrelated table also registers conntrack before pre-policy flows open.
        nft('table inet unrelated_fixture { chain input { type filter hook input priority 300; policy accept; ct state invalid drop; } }')
        unrelated = shape("unrelated_fixture")
        with ExitStack() as stack:
            for address in ("192.0.2.1", "2001:db8:1::1"):
                listen(stack, address, 22)
                listen(stack, address, 80)
            old_unapproved = []
            for family, prefix in r.FAMILIES:
                for suffix in ("2", "3"):
                    assert rpc(proc, "open", family + suffix, prefix + "1", prefix + suffix)
                # Establish both the allowed and denied positive controls first.
                assert rpc(proc, "reaches", prefix + "1", 80, prefix + "2")
                assert rpc(proc, "reaches", prefix + "1", 22, prefix + "9")
                old = stack.enter_context(connect(prefix + "2", 8443))
                assert exchange(old)
                old_unapproved.append(old)
                assert reaches(prefix + "3", 443)
                for port, udp in ((53, False), (53, True), (123, True)):
                    assert reaches(prefix + "2", port, udp=udp)
            nft(r.profile("maintenance"))
            maintenance = shape(r.TABLE)

            def assert_administration_and_deny():
                for family, prefix in r.FAMILIES:
                    for suffix in ("2", "3"):
                        assert rpc(proc, "exchange", family + suffix)
                        assert rpc(proc, "reaches", prefix + "1", 22, prefix + suffix)
                    assert not rpc(proc, "reaches", prefix + "1", 22, prefix + "9")
                    assert not rpc(proc, "reaches", prefix + "1", 80, prefix + "2")
                    assert not reaches(prefix + "2", 8443)
                    assert not reaches(prefix + "3", 443)
                    for port, udp in ((53, False), (53, True), (123, True)):
                        assert reaches(prefix + "2", port, udp=udp)
                assert shape("unrelated_fixture") == unrelated

            assert_administration_and_deny()
            assert all(not exchange(sock) for sock in old_unapproved)
            for _, prefix in r.FAMILIES:
                assert not reaches(prefix + "2", 443)
            print("PASS MAINTENANCE_IPV4_IPV6_NEW_AND_EXISTING_ADMIN_TRANSPORT", flush=True)
            print("PASS DEFAULT_DENY_AND_PREEXISTING_UNAPPROVED_FLOW_BLOCKED", flush=True)

            # Parsing succeeds, but deleting an absent chain fails in the kernel.
            # The first delete must NOT commit on this failed transaction.
            bad = r.replacement("qualification") + f'delete chain inet {r.TABLE} absent_chain\n'
            assert nft(bad, success=False).returncode != 0
            assert shape(r.TABLE) == maintenance
            assert_administration_and_deny()
            print("PASS INVALID_TRANSACTION_PRESERVES_PREVIOUS_TABLE", flush=True)

            candidate = owned_transition(maintenance, "qualification")
            approved = []
            for _, prefix in r.FAMILIES:
                sock = stack.enter_context(connect(prefix + "2", 443))
                assert exchange(sock)
                approved.append(sock)
            assert_administration_and_deny()
            print("PASS EXACT_QUALIFICATION_DESTINATION_ONLY", flush=True)

            # Rollback keeps management/bootstrap controls and default deny.
            restored = owned_transition(candidate, "maintenance")
            assert restored == maintenance
            assert all(not exchange(sock) for sock in approved)
            for _, prefix in r.FAMILIES:
                assert not reaches(prefix + "2", 443)
            assert_administration_and_deny()
            print("PASS ROLLBACK_REVOKES_NEW_AND_ESTABLISHED_QUALIFICATION_FLOWS", flush=True)
            print("PASS ROLLBACK_PRESERVES_ADMIN_AND_UNRELATED_TABLE", flush=True)

            # A name match is insufficient ownership. Unknown edits stop rollback.
            nft(f'add rule inet {r.TABLE} output tcp dport 9443 drop\n')
            changed = shape(r.TABLE)
            try:
                owned_transition(restored, "qualification")
            except RuntimeError as exc:
                assert str(exc) == "OWNED_TABLE_CHANGED_STOP"
            else:
                raise AssertionError("DRIFT_WAS_OVERWRITTEN")
            assert shape(r.TABLE) == changed
            assert shape("unrelated_fixture") == unrelated
            print("PASS OWNED_TABLE_DRIFT_STOPS_WITHOUT_MUTATION", flush=True)
        rpc_stop = json.dumps(["stop"]) + "\n"
        proc.stdin.write(rpc_stop)
        proc.stdin.flush()
        assert proc.wait(timeout=5) == 0
        print("RESULT SYNTHETIC_NETWORK_TRANSITION_OK_NO_LIVE_APPLY", flush=True)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
        proc.stdin.close()
        proc.stdout.close()
        # veth, routes, sockets and both rulesets vanish with their namespaces.


class OfflineTests(unittest.TestCase):
    def test_guard_rejects_host_namespace_and_non_ci_before_commands(self):
        cases = (("true", 0, ["same", "same"]), ("false", 0, []), ("true", 1000, []))
        for ci, uid, namespaces in cases:
            with patch.dict(os.environ, {"GITHUB_ACTIONS": ci}), patch.object(os, "geteuid", return_value=uid), \
                    patch.object(os, "readlink", side_effect=namespaces), patch(__name__ + ".run") as command:
                with self.assertRaisesRegex(RuntimeError, "DISPOSABLE_CI_NETWORK_NAMESPACE_REQUIRED"):
                    kernel_rehearsal()
                command.assert_not_called()

    def test_pure_fixture_rejects_arbitrary_modes(self):
        for mode in ("apply", "live", "maintenance; flush ruleset", None):
            with self.assertRaisesRegex(ValueError, "UNKNOWN_FIXTURE_PROFILE"):
                r.profile(mode)

    def test_table_drift_prevents_mutation(self):
        with patch(__name__ + ".shape", return_value={"unexpected": True}), patch(__name__ + ".nft") as mutate:
            with self.assertRaisesRegex(RuntimeError, "OWNED_TABLE_CHANGED_STOP"):
                owned_transition({}, "maintenance")
            mutate.assert_not_called()

    def test_no_live_cli(self):
        result = subprocess.run([sys.executable, "-I", "-B", str(ROOT / "review/secret_custody_network_rehearsal.py")],
                                capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b"STOP CI_REHEARSAL_ONLY_NO_LIVE_APPLY\n")


if __name__ == "__main__":
    if sys.argv[1:] == ["--peer"]:
        peer()
    elif sys.argv[1:] == ["--kernel"]:
        kernel_rehearsal()
    else:
        unittest.main(verbosity=2)
