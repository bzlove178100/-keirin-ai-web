"""Local parser/bounds/privacy tests; --ci-host checks actual Ubuntu readers."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("dependencies", Path(__file__).resolve().parents[1] / "review/secret_custody_network_dependencies.py")
d = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(d)

def raw(value):
    return json.dumps(value).encode()

def dns_reply(signature, values):
    # busctl call Properties.Get -> one typed variant, whose array is unwrapped.
    # Pinned v255 busctl.c json_transform_message / json_transform_variant.
    return raw({"type": "v", "data": [{"type": signature, "data": values}]})


class Tests(unittest.TestCase):
    def test_typed_resolved_ipv4_ipv6_and_invalid_family(self):
        self.assertEqual(d.dns(dns_reply("a(iiay)", [[2, 2, [192, 0, 2, 53]],
                          [2, 10, list(bytes.fromhex("20010db8000000000000000000000053"))]])),
                         [{"index": 2, "address": "192.0.2.53"}, {"index": 2, "address": "2001:db8::53"}])
        self.assertEqual(d.dns(dns_reply("a(iiayqs)", [[2, 2, [192, 0, 2, 53], 853, "dns.example.invalid"]]))[0]["port_zero_means_default"], 853)
        self.assertEqual(d.dns(dns_reply("a(iiayqs)", [])), [])
        with self.assertRaises(d.Stop):
            d.dns(dns_reply("a(iiay)", [[2, 99, [192, 0, 2, 53]]]))

    def test_networkd_origin_fields_are_selected_not_raw_config(self):
        value = {"Interfaces": [{"Index": 2, "Name": "eth0", "AdministrativeState": "configured",
                  "HardwareAddress": "PRIVATE-MAC", "SSID": "PRIVATE-SSID",
                  "DHCPv6Client": {"VendorOptions": ["SECRET-SENTINEL"]},
                  "Addresses": [{"Family": 2, "Address": [192, 0, 2, 1], "ConfigSource": "DHCPv4",
                                 "ConfigProvider": [192, 0, 2, 254]}],
                  "NTP": [{"Server": "clock.example.invalid", "ConfigSource": "runtime"}]}]}
        result = d.networkd(raw({"type": "s", "data": [json.dumps(value)]}))
        text = json.dumps(result)
        self.assertIn("192.0.2.254", text)
        self.assertIn("server_name_unresolved", text)
        for secret in ("PRIVATE-MAC", "PRIVATE-SSID", "SECRET-SENTINEL", "VendorOptions"):
            self.assertNotIn(secret, text)

    def test_chrony_csv_source_and_refclock(self):
        self.assertEqual(d.chrony(b"^,*,192.0.2.123,2,6,377,12,0.1,0.1,0.2\n"),
                         [{"kind": "server", "state": "*", "address": "192.0.2.123"}])
        self.assertEqual(d.chrony(b"#,*,GPS,0,0,0,0,0,0,0\n"), [{"kind": "refclock", "state": "*"}])
        with self.assertRaises(ValueError):
            d.chrony(b"^,*,secret.invalid,2,6,377,12,0,0,0\n")

    def test_address_route_scope_and_complex_routes(self):
        self.assertEqual(d.addresses(raw([{"ifindex": 2, "ifname": "eth0", "address": "PRIVATE-MAC",
                            "addr_info": [{"family": "inet6", "local": "fe80::1", "prefixlen": 64, "scope": "link"}]}]))[0]["addresses"][0]["scope"], "link")
        route = d.routes(raw([{"dst": "default", "gateway": "fe80::2", "dev": "eth0", "protocol": "ra"}]))[0]
        self.assertEqual(route["gateway"], "fe80::2")
        self.assertFalse(route["complex_route_unmodeled"])
        self.assertTrue(d.routes(raw([{"nexthops": [{}]}]))[0]["complex_route_unmodeled"])

    def test_duplicate_keys_overflow_and_shell_strings_rejected(self):
        for data in (b'{"Interfaces":[],"Interfaces":[]}', b"x" * (d.MAX_BYTES + 1)):
            with self.assertRaises(d.Stop):
                d.decode(data)
        for name in ("eth0;touch /tmp/x", "x\nFAKE", "x" * 65):
            with self.assertRaises(d.Stop):
                d.token(name)

    def test_ssh_is_validated_caller_evidence(self):
        value = d.ssh("192.0.2.2 50000 192.0.2.1 22")[0]
        self.assertEqual(value["source"], "caller_supplied_unverified")
        for item in ("", "a b c d", "192.0.2.2 0 192.0.2.1 22", "192.0.2.2 5 192.0.2.1 22 extra"):
            with self.assertRaises((d.Stop, ValueError)):
                d.ssh(item)

    def test_default_report_never_exposes_private_values_or_errors(self):
        parsers = {"test": lambda _: [{"address": "192.0.2.77"}], "error": lambda _: 1/0}
        with patch.dict(d.PARSERS, parsers, clear=True), patch.object(d, "command", return_value=b"SECRET"), \
                patch.object(os, "geteuid", return_value=0), patch.object(Path, "read_text", return_value="systemd"), \
                patch.object(os, "readlink", return_value="same"), patch.dict(os.environ, {"KC_SSH_CONNECTION": "BAD-SECRET"}):
            report = d.observe()
            private = d.observe(True)
        text = json.dumps(report)
        self.assertNotIn("192.0.2.77", text)
        self.assertNotIn("SECRET", text)
        self.assertFalse(report["qualification"])
        self.assertEqual(report["sections"]["error"], {"status": "unknown", "reason": "UNRECOGNIZED_DATA"})
        self.assertIn("192.0.2.77", json.dumps(private))

    def test_output_bound_and_unavailable_do_not_return_partial_output(self):
        with patch.dict(d.COMMANDS, {"test": (sys.executable, "-I", "-c", "print('x'*100)")}), patch.object(d, "MAX_BYTES", 64):
            with self.assertRaisesRegex(d.Stop, "READ_OUTPUT_TOO_LARGE"):
                d.command("test")
        with patch.dict(d.COMMANDS, {"test": ("/not/a/command",)}):
            with self.assertRaisesRegex(d.Stop, "UNAVAILABLE"):
                d.command("test")

    def test_command_timeout_kills_and_reaps_reader(self):
        with patch.dict(d.COMMANDS, {"test": (sys.executable, "-I", "-c", "import time; time.sleep(10)")}):
            with self.assertRaisesRegex(d.Stop, "READ_TIMEOUT"):
                d.command("test")

    def test_no_network_fallback_no_autostart_no_arbitrary_command(self):
        self.assertEqual(d.COMMANDS["chrony"], ("/usr/bin/chronyc", "-n", "-c", "-h", "/run/chrony/chronyd.sock", "sources"))
        self.assertIn("--auto-start=no", d.NETWORKD)
        self.assertIn("call", d.RESOLVED)
        self.assertNotIn("get-property", d.RESOLVED)
        with patch.object(d.subprocess, "Popen") as start:
            with self.assertRaises(d.Stop):
                d.command("restart")
            start.assert_not_called()


def ci_host():
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("CI_REQUIRED")
    report = d.observe()
    for name in ("addresses", "routes4", "routes6"):
        assert report["sections"][name]["status"] == "observed", name
    assert report["sections"]["addresses"]["count"] >= 1
    for name in ("networkd", "dns", "dns_fallback", "chrony"):
        section = report["sections"][name]
        # Uninstalled/inactive managers may be unavailable; a parser failure on
        # available Ubuntu output is a real failure, never a skipped success.
        assert section["status"] == "observed" or section.get("reason") == "UNAVAILABLE", name
    print(json.dumps(report, sort_keys=True))
    print("RESULT CI_LOCAL_DEPENDENCY_READERS_OK_NO_PRIVATE_VALUES")


if __name__ == "__main__":
    if sys.argv[1:] == ["--ci-host"]:
        ci_host()
    else:
        unittest.main(verbosity=2)
