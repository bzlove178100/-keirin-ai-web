#!/usr/bin/env python3
"""Bounded local-only observation. No firewall generation or qualification.

Default output has counts/states only. --private explicitly emits selected local
IP/interface/route/DNS/NTP facts; keep that output out of public repositories.
No config files, credentials, command stderr, DNS queries, cloud calls or probes.
"""
import csv
import io
import ipaddress
import json
import os
from pathlib import Path
import re
import select
import subprocess
import sys
import time

ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "LC_ALL": "C"}
BUS = ("/usr/bin/busctl", "--system", "--auto-start=no", "--timeout=4", "--json=short")
NETWORKD = (*BUS, "call", "org.freedesktop.network1", "/org/freedesktop/network1",
            "org.freedesktop.network1.Manager", "Describe")
# Use explicit call: v255 get-property does not apply arg_auto_start, while
# call sets the message's auto-start flag. Properties.Get returns one variant.
RESOLVED = (*BUS, "call", "org.freedesktop.resolve1", "/org/freedesktop/resolve1",
            "org.freedesktop.DBus.Properties", "Get", "ss", "org.freedesktop.resolve1.Manager")
COMMANDS = {
    "addresses": ("/usr/sbin/ip", "-j", "address", "show"),
    "routes4": ("/usr/sbin/ip", "-j", "-4", "route", "show", "table", "all"),
    "routes6": ("/usr/sbin/ip", "-j", "-6", "route", "show", "table", "all"),
    "networkd": NETWORKD,
    "dns": (*RESOLVED, "DNSEx"),
    "dns_fallback": (*RESOLVED, "FallbackDNSEx"),
    "chrony": ("/usr/bin/chronyc", "-n", "-c", "-h", "/run/chrony/chronyd.sock", "sources"),
}
MAX_BYTES = 262144


class Stop(Exception):
    pass


def need(ok):
    if not ok:
        raise Stop("UNRECOGNIZED_DATA")


def command(name):
    need(name in COMMANDS)
    p = None
    try:
        p = subprocess.Popen(COMMANDS[name], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, env=ENV, close_fds=True)
        os.set_blocking(p.stdout.fileno(), False)
        data = bytearray()
        deadline = time.monotonic() + 5
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise Stop("READ_TIMEOUT")
            if select.select([p.stdout], [], [], min(0.1, remaining))[0]:
                chunk = os.read(p.stdout.fileno(), min(65536, MAX_BYTES + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > MAX_BYTES:
                    raise Stop("READ_OUTPUT_TOO_LARGE")
        if p.wait(timeout=max(0.01, deadline - time.monotonic())) != 0:
            raise Stop("UNAVAILABLE")
        return bytes(data)
    except (OSError, subprocess.TimeoutExpired):
        raise Stop("UNAVAILABLE") from None
    finally:
        if p is not None:
            if p.poll() is None:
                p.kill()
                p.wait(timeout=2)
            p.stdout.close()


def unique(pairs):
    value = {}
    for key, item in pairs:
        need(key not in value)
        value[key] = item
    return value


def decode(raw):
    need(len(raw) <= MAX_BYTES)
    return json.loads(raw, object_pairs_hook=unique)


def sequence(value, bound=256):
    need(type(value) is list and len(value) <= bound)
    return value


def token(value):
    need(type(value) is str and re.fullmatch(r"[A-Za-z0-9_.:@+-]{1,64}", value) is not None)
    return value


def address(value):
    need(type(value) is str and "%" not in value)
    return str(ipaddress.ip_address(value))


def binary_address(family, value):
    need(type(family) is int and family in (2, 10))
    need(type(value) is list and len(value) == (4 if family == 2 else 16)
         and all(type(x) is int and 0 <= x <= 255 for x in value))
    return str(ipaddress.ip_address(bytes(value)))


def integer(value, minimum, maximum):
    need(type(value) is int and minimum <= value <= maximum)
    return value


def addresses(raw):
    result = []
    for interface in sequence(decode(raw), 32):
        name = token(interface["ifname"])
        index = integer(interface["ifindex"], 1, 2**31 - 1)
        entries = []
        for item in sequence(interface.get("addr_info", [])):
            if item["family"] not in ("inet", "inet6"):
                continue
            ip = address(item["local"])
            entries.append({"address": ip, "prefix": integer(item["prefixlen"], 0, 128 if ":" in ip else 32),
                            "scope": token(item["scope"])})
        result.append({"interface": name, "index": index, "addresses": entries})
    return result


def routes(raw):
    result = []
    for item in sequence(decode(raw)):
        entry = {}
        for key in ("dev", "protocol", "scope", "type"):
            if key in item:
                entry[key] = token(str(item[key]))
        destination = item.get("dst", "default")
        entry["destination"] = "default" if destination == "default" else str(ipaddress.ip_network(destination, strict=False))
        for key in ("gateway", "prefsrc"):
            if key in item:
                entry[key] = address(item[key])
        if "table" in item:
            entry["table"] = token(str(item["table"]))
        # Do not silently treat complex routes as a complete simple-route model.
        entry["complex_route_unmodeled"] = any(k in item for k in ("multipath", "nexthops", "encap", "via", "nhid"))
        result.append(entry)
    return result


def bus_value(raw, signature):
    data = decode(raw)
    need(type(data) is dict and data.get("type") == signature)
    values = sequence(data["data"], 1)
    need(len(values) == 1)
    return values[0]


def dns(raw):
    result = []
    variant = bus_value(raw, "v")
    need(type(variant) is dict)
    signature = variant.get("type")
    need(signature in ("a(iiay)", "a(iiayqs)"))
    for value in sequence(variant["data"]):
        need(type(value) is list and len(value) == (5 if signature == "a(iiayqs)" else 3))
        result.append({"index": integer(value[0], 0, 2**31 - 1),
                       "address": binary_address(value[1], value[2])})
        if len(value) == 5:
            result[-1]["port_zero_means_default"] = integer(value[3], 0, 65535)
            name = value[4]
            need(type(name) is str and len(name) <= 253 and re.fullmatch(r"[A-Za-z0-9_.-]*", name) is not None)
            result[-1]["server_name"] = name
    return result


def networkd(raw):
    text = bus_value(raw, "s")
    need(type(text) is str)
    data = decode(text)
    result = []
    for interface in sequence(data["Interfaces"], 32):
        entry = {"index": integer(interface["Index"], 1, 2**31 - 1), "interface": token(interface["Name"])}
        for key in ("AdministrativeState", "OperationalState"):
            if key in interface:
                entry[key] = token(interface[key])
        selected = []
        # ConfigProvider is evidence of origin (e.g. DHCP), not an approved peer.
        for kind in ("Addresses", "Routes", "DNS", "NTP"):
            for item in sequence(interface.get(kind, [])):
                fact = {"kind": kind}
                if "ConfigSource" in item:
                    fact["source"] = token(item["ConfigSource"])
                for key in ("Address", "Gateway", "ConfigProvider"):
                    if key in item:
                        value = item[key]
                        family = item.get("Family", 2 if len(value) == 4 else 10)
                        fact[key] = binary_address(family, value)
                if "Port" in item:
                    fact["port"] = integer(item["Port"], 0, 65535)
                if "Server" in item:
                    # Keep hostname values private; do not resolve them.
                    name = item["Server"]
                    need(type(name) is str and len(name) <= 253
                         and re.fullmatch(r"[A-Za-z0-9_.-]+", name) is not None)
                    fact["server_name_unresolved"] = name
                selected.append(fact)
        entry["observations"] = selected
        result.append(entry)
    return result


def chrony(raw):
    need(len(raw) <= MAX_BYTES)
    result = []
    for row in csv.reader(io.StringIO(raw.decode("ascii"))):
        need(len(result) < 64 and len(row) == 10 and row[0] in ("^", "=", "#")
             and row[1] in ("*", "+", "-", "?", "x", "~"))
        # A refclock may have a non-IP reference ID, not a network destination.
        if row[0] == "#":
            result.append({"kind": "refclock", "state": row[1]})
        else:
            result.append({"kind": "server" if row[0] == "^" else "peer", "state": row[1], "address": address(row[2])})
    return result


def ssh(value):
    need(type(value) is str and len(value) <= 160)
    parts = value.split()
    need(len(parts) == 4 and parts[1].isascii() and parts[1].isdigit()
         and parts[3].isascii() and parts[3].isdigit())
    return [{"peer": address(parts[0]), "peer_port": integer(int(parts[1]), 1, 65535),
             "local": address(parts[2]), "local_port": integer(int(parts[3]), 1, 65535),
             "source": "caller_supplied_unverified"}]


PARSERS = {"addresses": addresses, "routes4": routes, "routes6": routes,
           "networkd": networkd, "dns": dns, "dns_fallback": dns, "chrony": chrony}
UNKNOWN = ["independent_recovery", "cloud_browser_ssh_ranges_and_lifecycle",
           "dhcp_renewal_and_ipv6_control_packet_policy", "dns_ntp_address_lifecycle",
           "dns_transport_policy_and_ntp_ports_nts", "bootstrap_and_runtime_destinations",
           "other_time_services", "initial_maintenance_anchor"]


def observe(private=False):
    need(os.geteuid() == 0 and Path("/proc/1/comm").read_text().strip() == "systemd"
         and os.readlink("/proc/self/ns/net") == os.readlink("/proc/1/ns/net"))
    result = {"schema": "LOCAL_NETWORK_DEPENDENCIES_V1", "sections": {},
              "unresolved": UNKNOWN, "qualification": False, "mutation": False}
    for name in (*PARSERS, "ssh"):
        try:
            values = ssh(os.environ.get("KC_SSH_CONNECTION", "")) if name == "ssh" else PARSERS[name](command(name))
            section = {"status": "observed", "count": len(values)}
            if private:
                section["private_values"] = values
        except Exception as error:
            # No raw diagnostic/config/output/exception text crosses this boundary.
            code = str(error) if isinstance(error, Stop) else "UNRECOGNIZED_DATA"
            section = {"status": "unknown", "reason": code}
        result["sections"][name] = section
    return result


def main(args):
    if args not in ([], ["--private"]):
        print("STOP EXPECT_NO_ARGUMENT_OR_PRIVATE")
        return 1
    try:
        report = observe(args == ["--private"])
    except Exception:
        print("STOP HOST_SYSTEMD_ROOT_CONTEXT_REQUIRED")
        return 1
    print("PRIVATE_NETWORK_VALUES_KEEP_OUT_OF_PUBLIC_REPO" if args else "SANITIZED_COUNTS_ONLY")
    print(json.dumps(report, sort_keys=True, indent=2))
    print("RESULT LOCAL_DEPENDENCIES_OBSERVED_WITH_UNRESOLVED_ITEMS_NO_MUTATION")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
