"""Network readback parsing/redaction; optional isolated real-kernel CI fixture."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("network_readback", ROOT / "review/secret_custody_network_readback.py")
n = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(n)


def sample():
    return {"nftables": [
        {"metainfo": {"json_schema_version": 1}},
        {"table": {"family": "inet", "name": "private-table"}},
        {"chain": {"family": "inet", "name": "private-chain", "table": "private-table",
                   "type": "filter", "hook": "input", "prio": 0, "policy": "drop"}},
        {"rule": {"family": "inet", "expr": [{"comment": "private-rule-and-address-192.0.2.1"}]}},
        {"set": {"name": "private-set", "elem": ["192.0.2.1"]}},
    ]}


class NetworkReadbackTests(unittest.TestCase):
    def test_nft_summary_never_renders_rules_names_or_addresses(self):
        lines = n.nft_summary(json.dumps(sample()).encode())
        self.assertEqual(lines, ["FACT nft_objects=table:1,chain:1,rule:1,other:1",
                                "FACT nft_base_chains=1", "FACT nft_base=inet,filter,input,0,drop,count:1"])
        self.assertNotIn("private", "\n".join(lines))
        self.assertNotIn("192.0.2.1", "\n".join(lines))
        self.assertNotIn("PASS", "\n".join(lines))

    def test_empty_ruleset_is_an_observation_not_a_security_pass(self):
        self.assertEqual(n.nft_summary(b'{"nftables":[]}'),
                         ["FACT nft_objects=table:0,chain:0,rule:0,other:0", "FACT nft_base_chains=0"])

    def test_duplicate_and_unrecognized_schema_rejected(self):
        for raw in (b'{"nftables":[],"nftables":[]}', b'[]', b'{"nftables":{}}',
                    b'{"nftables":[{"rule":[],"chain":{}}]}'):
            with self.assertRaises(n.Stop):
                n.nft_summary(raw)
        for key, value in (("policy", "private-text"), ("prio", True), ("hook", "unknown"),
                           ("family", "unknown"), ("type", "unknown")):
            data = sample()
            data["nftables"][2]["chain"][key] = value
            with self.assertRaisesRegex(n.Stop, "NFT_BASE_CHAIN_UNRECOGNIZED"):
                n.nft_summary(json.dumps(data).encode())

    def test_listener_scope_is_separate_from_packet_reachability(self):
        data = b'udp UNCONN 0 0 127.0.0.53%lo:53 0.0.0.0:*\ntcp LISTEN 0 128 0.0.0.0:22 0.0.0.0:*\ntcp LISTEN 0 128 192.0.2.44:443 0.0.0.0:*\n'
        lines = n.listener_summary(data, 4)
        self.assertEqual(lines, ["FACT ipv4_listeners=3", "FACT listener=ipv4,tcp,specific,443,count:1",
                                "FACT listener=ipv4,tcp,wildcard,22,count:1", "FACT listener=ipv4,udp,loopback,53,count:1"])
        self.assertNotIn("192.0.2.44", "\n".join(lines))
        self.assertNotIn("lo:", "\n".join(lines))
        data = b'tcp LISTEN 0 128 [::]:22 [::]:*\nudp UNCONN 0 0 [fe80::1234%eth0]:546 [::]:*\ntcp LISTEN 0 128 [::1]:80 [::]:*\n'
        self.assertIn("FACT listener=ipv6,udp,link_local,546,count:1", n.listener_summary(data, 6))

    def test_listener_bad_shape_address_family_and_ports_rejected(self):
        for raw in (b'tcp LISTEN 0 128 192.0.2.1:70000 0.0.0.0:*\n',
                    b'tcp LISTEN 0 128 [::]:22 [::]:*\n',
                    b'tcp LISTEN 0 128 0.0.0.0:22 0.0.0.0:* extra\n'):
            with self.assertRaises(n.Stop):
                n.listener_summary(raw, 4)

    def test_ipv6_zone_outside_or_inside_brackets_and_scoped_wildcard(self):
        # The old strip('[]').split('%')[0] raised ValueError for [addr]%zone.
        for host in ("[fe80::1234]%fixture0", "[fe80::1234%fixture0]",
                     "fe80::1234%fixture0", "[fe80::1234]%7"):
            raw = ("udp UNCONN 0 0 " + host + ":546 [::]:*\n").encode()
            self.assertEqual(n.listener_summary(raw, 6), ["FACT ipv6_listeners=1",
                             "FACT listener=ipv6,udp,link_local,546,count:1"])
        self.assertEqual(n.listener_summary(b'udp UNCONN 0 0 *%fixture0:546 *:*\n', 6),
                         ["FACT ipv6_listeners=1", "FACT listener=ipv6,udp,wildcard,546,count:1"])

    def test_ipv6_invalid_brackets_zones_and_addresses_still_rejected(self):
        for host in ("[fe80::1234", "fe80::1234]", "[[fe80::1234]]", "[fe80::1234]junk",
                     "[fe80::1234]%", "[fe80::1234%]", "[fe80::1234%a]%b",
                     "[fe80::1234]%a%b", "[not-an-address]%private"):
            with self.assertRaisesRegex(n.Stop, "^LISTENER_ADDRESS_UNRECOGNIZED$"):
                n.listener_summary(("udp UNCONN 0 0 " + host + ":546 [::]:*\n").encode(), 6)

    def test_failure_has_fixed_stage_and_category_without_raw_values(self):
        cases = ((json.JSONDecodeError("private", "private", 0), "JSON_SYNTAX"),
                 (UnicodeDecodeError("ascii", b'\xff', 0, 1, "private"), "TEXT_ENCODING"),
                 (PermissionError("private"), "OS_READ_ERROR"),
                 (ValueError("private"), "INVALID_VALUE"),
                 (TypeError("private"), "INVALID_TYPE"),
                 (RuntimeError("private"), "UNEXPECTED_EXCEPTION"),
                 (n.Stop("NFT_JSON_INVALID"), "NFT_JSON_INVALID"))
        for error, code in cases:
            def failed_snapshot():
                return n.checked("NFT_PARSE", lambda: (_ for _ in ()).throw(error))
            out = io.StringIO()
            with patch.object(n, "snapshot", side_effect=failed_snapshot), redirect_stdout(out):
                self.assertEqual(n.main(), 1)
            self.assertEqual(out.getvalue(), "STOP " + code + "\nSTAGE NFT_PARSE\n"
                             "RESULT H3_NETWORK_OBSERVATION_INCOMPLETE_NO_MUTATION\n")

    def test_real_snapshot_attributes_read_and_parse_stages_and_buffers_facts(self):
        valid = {n.NFT: b'{"nftables":[]}', n.SS4: b'', n.SS6: b'',
                 (*n.SERVICE, "nftables.service"): b'LoadState=loaded\nActiveState=inactive\nUnitFileState=disabled\n',
                 (*n.SERVICE, "ufw.service"): b'LoadState=loaded\nActiveState=inactive\nUnitFileState=disabled\n'}
        for target, value, stage, code in (
                (n.NFT, b'private-not-json', "NFT_PARSE", "JSON_SYNTAX"),
                (n.SS4, n.Stop("READ_TIMEOUT"), "IPV4_LISTENERS_READ", "READ_TIMEOUT"),
                (n.SS6, b'udp UNCONN 0 0 [bad]%private:546 [::]:*\n',
                 "IPV6_LISTENERS_PARSE", "LISTENER_ADDRESS_UNRECOGNIZED"),
                ((*n.SERVICE, "ufw.service"), b'LoadState=private\n',
                 "UFW_SERVICE_PARSE", "SERVICE_OUTPUT_INVALID")):
            def command(args, **kwargs):
                result = value if args == target else valid[args]
                if isinstance(result, Exception):
                    raise result
                return result
            out = io.StringIO()
            with patch.object(n.os, "geteuid", return_value=0), \
                    patch.object(n.os, "readlink", return_value="net:[1]"), \
                    patch.object(n, "read_file", side_effect=lambda p, **kw: "systemd" if p == "/proc/1/comm" else None), \
                    patch.object(n, "command", side_effect=command), redirect_stdout(out):
                self.assertEqual(n.main(), 1)
            self.assertEqual(out.getvalue(), "STOP " + code + "\nSTAGE " + stage + "\n"
                             "RESULT H3_NETWORK_OBSERVATION_INCOMPLETE_NO_MUTATION\n")

    def test_service_unknown_or_missing_is_not_silently_normalized(self):
        raw = b'LoadState=not-found\nActiveState=inactive\nUnitFileState=\n'
        self.assertEqual(n.service_summary("ufw", raw), "FACT ufw_service=not-found,inactive,none")
        for raw in (b'LoadState=loaded\n', b'LoadState=loaded\nActiveState=private\nUnitFileState=enabled\n'):
            with self.assertRaises(n.Stop):
                n.service_summary("ufw", raw)

    def test_missing_legacy_proc_file_is_distinct_from_empty(self):
        with patch("builtins.open", side_effect=FileNotFoundError):
            self.assertIsNone(n.read_file("/proc/net/ip_tables_names", optional=True))
        with patch("builtins.open", return_value=io.BytesIO(b"")):
            self.assertEqual(n.read_file("/proc/net/ip_tables_names", optional=True), "")
        with patch("builtins.open", side_effect=PermissionError):
            with self.assertRaises(PermissionError):
                n.read_file("/proc/net/ip_tables_names", optional=True)

    def test_no_arbitrary_commands_or_files(self):
        with patch.object(n.subprocess, "Popen") as spawn, patch("builtins.open") as open_file:
            for args in (("/usr/sbin/nft", "flush", "ruleset"), ("/bin/sh", "-c", "true")):
                with self.assertRaisesRegex(n.Stop, "COMMAND_NOT_ALLOWED"):
                    n.command(args)
            with self.assertRaisesRegex(n.Stop, "PATH_NOT_ALLOWED"):
                n.read_file("/etc/shadow")
            spawn.assert_not_called()
            open_file.assert_not_called()

    def test_wrong_namespace_stops_before_any_commands(self):
        with patch.object(n.os, "geteuid", return_value=0), \
                patch.object(n, "read_file", return_value="systemd"), \
                patch.object(n.os, "readlink", side_effect=["net:[1]", "net:[2]"]), \
                patch.object(n, "command") as command:
            with self.assertRaisesRegex(n.Stop, "HOST_NETWORK_NAMESPACE_REQUIRED"):
                n.snapshot()
            command.assert_not_called()

    def test_partial_read_or_parser_error_does_not_print_evidence_or_raw_error(self):
        out = io.StringIO()
        with patch.object(n, "snapshot", side_effect=ValueError("private-material")), redirect_stdout(out):
            self.assertEqual(n.main(), 1)
        self.assertEqual(out.getvalue(), "STOP NETWORK_READBACK_UNAVAILABLE\n"
                         "RESULT H3_NETWORK_OBSERVATION_INCOMPLETE_NO_MUTATION\n")

    def test_command_output_cap_terminates_only_its_own_reader(self):
        real = subprocess.Popen
        def spawn(*args, **kwargs):
            return real([sys.executable, "-c", "import os,time; os.write(1,b'x'*1024); time.sleep(60)"], **kwargs)
        with patch.object(n.subprocess, "Popen", side_effect=spawn):
            with self.assertRaisesRegex(n.Stop, "READ_OUTPUT_TOO_LARGE"):
                n.command(n.NFT, limit=16)

    def test_command_timeout_and_nonzero_output_are_redacted(self):
        real = subprocess.Popen
        def spawn(*args, **kwargs):
            return real([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)
        with patch.object(n.subprocess, "Popen", side_effect=spawn):
            with self.assertRaisesRegex(n.Stop, "READ_TIMEOUT"):
                n.command(n.NFT, timeout=0.05)
        def fail(*args, **kwargs):
            return real([sys.executable, "-c", "import sys; print('private'); sys.exit(9)"], **kwargs)
        with patch.object(n.subprocess, "Popen", side_effect=fail):
            with self.assertRaisesRegex(n.Stop, "READ_COMMAND_FAILED"):
                n.command(n.NFT)


def namespace_fixture():
    # All mutations below occur only inside unshare's disposable network namespace.
    if (os.environ.get("GITHUB_ACTIONS") != "true" or os.geteuid() != 0
            or os.readlink("/proc/self/ns/net") == os.readlink("/proc/1/ns/net")):
        raise RuntimeError("DISPOSABLE_NETWORK_NAMESPACE_REQUIRED")
    assert n.nft_summary(n.command(n.NFT)) == ["FACT nft_objects=table:0,chain:0,rule:0,other:0",
                                             "FACT nft_base_chains=0"]
    rules = '''table inet private_fixture {
      chain hidden_input { type filter hook input priority 0; policy drop;
        ip saddr 192.0.2.1 tcp dport 22 accept
      }
      chain hidden_output { type filter hook output priority 0; policy drop; }
    }'''
    subprocess.run(["/usr/sbin/nft", "-f", "-"], input=rules.encode(), check=True, timeout=5)
    lines = n.nft_summary(n.command(n.NFT))
    assert lines == ["FACT nft_objects=table:1,chain:2,rule:1,other:0", "FACT nft_base_chains=2",
                     "FACT nft_base=inet,filter,input,0,drop,count:1", "FACT nft_base=inet,filter,output,0,drop,count:1"]
    subprocess.run(["/usr/sbin/ip", "link", "set", "lo", "up"], check=True, timeout=5)
    # Scope-bearing real socket: previous CI covered only loopback literals.
    # The address and interface are confined to this disposable net namespace.
    subprocess.run(["/usr/sbin/ip", "-6", "addr", "add", "fe80::1234/64", "dev", "lo", "nodad"],
                   check=True, timeout=5)
    sockets = []
    try:
        for family, flag, address in ((4, socket.AF_INET, "127.0.0.1"), (6, socket.AF_INET6, "::1")):
            for proto, kind in (("tcp", socket.SOCK_STREAM), ("udp", socket.SOCK_DGRAM)):
                sock = socket.socket(flag, kind)
                sockets.append(sock)
                sock.bind((address, 0))
                if proto == "tcp":
                    sock.listen(1)
                port = sock.getsockname()[1]
                lines = n.listener_summary(n.command(n.SS4 if family == 4 else n.SS6), family)
                assert "FACT listener=ipv" + str(family) + "," + proto + ",loopback," + str(port) + ",count:1" in lines
        scoped = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        sockets.append(scoped)
        scoped.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, b"lo\x00")
        scoped.bind(("fe80::1234", 0, 0, socket.if_nametoindex("lo")))
        port = scoped.getsockname()[1]
        raw = n.command(n.SS6)
        assert any(b"%lo" in line and (":" + str(port)).encode() in line for line in raw.splitlines())
        assert "FACT listener=ipv6,udp,link_local," + str(port) + ",count:1" in n.listener_summary(raw, 6)
        print("REAL_SCOPED_IPV6_LISTENER_READBACK_OK")
    finally:
        for sock in sockets:
            sock.close()
    print("REAL_NFT_AND_IPV4_IPV6_LISTENER_READBACK_OK")


if __name__ == "__main__":
    if sys.argv[1:] == ["--namespace-fixture"]:
        namespace_fixture()
    else:
        unittest.main(verbosity=2)
