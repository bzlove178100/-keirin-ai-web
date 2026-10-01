#!/usr/bin/env python3
"""Read-only host network inventory, not firewall qualification or authorization.

Fixed commands only; no addresses, rule contents, names, counters or diagnostics
are emitted. No packet probe, listener, firewall mutation or service action.
"""
from collections import Counter
import ipaddress
import json
import os
from pathlib import Path
import select
import subprocess
import time

ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "LC_ALL": "C"}
NFT = ("/usr/sbin/nft", "-j", "list", "ruleset")
SS4 = ("/usr/bin/ss", "-H", "-n", "-l", "-t", "-u", "-4")
SS6 = (*SS4[:-1], "-6")
SERVICE = ("/usr/bin/systemctl", "show", "--property=LoadState,ActiveState,UnitFileState")
COMMANDS = (NFT, SS4, SS6, (*SERVICE, "nftables.service"), (*SERVICE, "ufw.service"))
FAMILIES = {"ip", "ip6", "inet", "arp", "bridge", "netdev"}
HOOKS = {"input", "output", "forward", "prerouting", "postrouting", "ingress", "egress"}
FILES = {
    "/proc/1/comm", "/proc/net/ip_tables_names", "/proc/net/ip6_tables_names",
    "/proc/sys/net/ipv4/ip_forward", "/proc/sys/net/ipv6/conf/all/forwarding",
    "/proc/sys/net/ipv6/conf/all/disable_ipv6",
}


class Stop(Exception):
    pass


def need(ok, code):
    if not ok:
        raise Stop(code)


def command(args, limit=1048576, timeout=5):
    need(tuple(args) in COMMANDS, "COMMAND_NOT_ALLOWED")
    p = None
    try:
        p = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, env=ENV, close_fds=True)
        os.set_blocking(p.stdout.fileno(), False)
        output = bytearray()
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            need(remaining > 0, "READ_TIMEOUT")
            if select.select([p.stdout], [], [], min(remaining, 0.1))[0]:
                chunk = os.read(p.stdout.fileno(), min(65536, limit + 1 - len(output)))
                if not chunk:
                    break
                output.extend(chunk)
                need(len(output) <= limit, "READ_OUTPUT_TOO_LARGE")
        need(p.wait(timeout=max(0.01, deadline - time.monotonic())) == 0, "READ_COMMAND_FAILED")
        return bytes(output)
    except (OSError, subprocess.TimeoutExpired):
        raise Stop("READ_COMMAND_UNAVAILABLE") from None
    finally:
        if p is not None:
            try:
                if p.poll() is None:
                    p.kill()
                    p.wait(timeout=2)
            finally:
                p.stdout.close()


def read_file(path, optional=False):
    need(path in FILES, "PATH_NOT_ALLOWED")
    try:
        with open(path, "rb") as stream:
            data = stream.read(4097)
    except FileNotFoundError:
        if optional:
            return None
        raise Stop("HOST_FILE_MISSING") from None
    need(len(data) <= 4096, "HOST_FILE_TOO_LARGE")
    return data.decode("ascii", errors="strict").strip()


def unique_object(pairs):
    out = {}
    for key, value in pairs:
        need(key not in out, "NFT_JSON_INVALID")
        out[key] = value
    return out


def nft_summary(raw):
    need(len(raw) <= 1048576, "NFT_OUTPUT_TOO_LARGE")
    data = json.loads(raw, object_pairs_hook=unique_object)
    need(type(data) is dict and set(data) == {"nftables"} and type(data["nftables"]) is list,
         "NFT_JSON_INVALID")
    counts, bases = Counter(), Counter()
    for item in data["nftables"]:
        need(type(item) is dict and len(item) == 1, "NFT_JSON_INVALID")
        kind, value = next(iter(item.items()))
        need(type(value) is dict, "NFT_JSON_INVALID")
        if kind == "metainfo":
            continue
        counts[kind if kind in ("table", "chain", "rule") else "other"] += 1
        if kind == "chain" and "hook" in value:
            family, hook, policy = (value.get(k) for k in ("family", "hook", "policy"))
            priority, chain_type = value.get("prio"), value.get("type")
            need(family in FAMILIES and hook in HOOKS and policy in ("accept", "drop")
                 and type(priority) is int and -(2**31) <= priority < 2**31
                 and chain_type in ("filter", "route", "nat"), "NFT_BASE_CHAIN_UNRECOGNIZED")
            bases[(family, chain_type, hook, priority, policy)] += 1
    need(len(bases) <= 32, "NFT_SUMMARY_TOO_LARGE")
    lines = ["FACT nft_objects=" + ",".join(k + ":" + str(counts[k])
                                           for k in ("table", "chain", "rule", "other"))]
    lines.append("FACT nft_base_chains=" + str(sum(bases.values())))
    lines.extend("FACT nft_base=" + ",".join(map(str, key)) + ",count:" + str(count)
                 for key, count in sorted(bases.items()))
    return lines


def listener_summary(raw, family):
    need(family in (4, 6) and len(raw) <= 131072, "LISTENER_OUTPUT_INVALID")
    found = Counter()
    for line in raw.decode("ascii", errors="strict").splitlines():
        fields = line.split()
        need(len(fields) == 6 and fields[0] in ("tcp", "udp")
             and fields[1] in ("LISTEN", "UNCONN") and fields[2].isdigit() and fields[3].isdigit(),
             "LISTENER_FORMAT_UNRECOGNIZED")
        host, port = fields[4].rsplit(":", 1)
        need(port.isdigit() and 0 < int(port) <= 65535, "LISTENER_PORT_UNRECOGNIZED")
        host = host.strip("[]").split("%", 1)[0]
        if host == "*":
            scope = "wildcard"
        else:
            address = ipaddress.ip_address(host)
            need(address.version == family, "LISTENER_FAMILY_MISMATCH")
            scope = ("wildcard" if address.is_unspecified else "loopback" if address.is_loopback
                     else "link_local" if address.is_link_local else "specific")
        found[(fields[0], scope, int(port))] += 1
    need(len(found) <= 32, "LISTENER_SUMMARY_TOO_LARGE")
    lines = ["FACT ipv" + str(family) + "_listeners=" + str(sum(found.values()))]
    lines.extend("FACT listener=ipv" + str(family) + "," + ",".join(map(str, key))
                 + ",count:" + str(count) for key, count in sorted(found.items()))
    return lines


def service_summary(name, raw):
    need(name in ("nftables", "ufw") and len(raw) <= 4096, "SERVICE_OUTPUT_INVALID")
    state = unique_object(line.split("=", 1) for line in raw.decode("ascii").splitlines())
    need(set(state) == {"LoadState", "ActiveState", "UnitFileState"}, "SERVICE_OUTPUT_INVALID")
    need(state["LoadState"] in ("loaded", "not-found", "masked", "error", "bad-setting", "stub", "merged")
         and state["ActiveState"] in ("active", "inactive", "failed", "activating", "deactivating", "reloading", "maintenance", "refreshing")
         and state["UnitFileState"] in ("", "enabled", "enabled-runtime", "disabled", "static", "masked",
                                           "masked-runtime", "indirect", "linked", "linked-runtime",
                                           "alias", "generated", "transient", "bad"), "SERVICE_STATE_UNRECOGNIZED")
    return "FACT " + name + "_service=" + ",".join(state[k] or "none"
                                                   for k in ("LoadState", "ActiveState", "UnitFileState"))


def snapshot():
    need(os.geteuid() == 0, "ROOT_READ_REQUIRED")
    need(read_file("/proc/1/comm") == "systemd", "SYSTEMD_HOST_REQUIRED")
    need(os.readlink("/proc/self/ns/net") == os.readlink("/proc/1/ns/net"), "HOST_NETWORK_NAMESPACE_REQUIRED")
    lines = nft_summary(command(NFT))
    for family in (4, 6):
        path = "/proc/net/" + ("ip" if family == 4 else "ip6") + "_tables_names"
        names = read_file(path, optional=True)
        # Nonempty legacy tables require separate inspection; never infer accept
        # or deny from table count, absent proc entry, or an nft-only snapshot.
        lines.append("FACT legacy_ipv" + str(family) + "_tables="
                     + ("not_exposed" if names is None else str(len(names.splitlines()))))
    lines += listener_summary(command(SS4, limit=131072), 4)
    lines += listener_summary(command(SS6, limit=131072), 6)
    for key, path in (("ipv4_forwarding", "/proc/sys/net/ipv4/ip_forward"),
                      ("ipv6_forwarding", "/proc/sys/net/ipv6/conf/all/forwarding"),
                      ("ipv6_disabled_all", "/proc/sys/net/ipv6/conf/all/disable_ipv6")):
        value = read_file(path, optional=True)
        need(value in (None, "0", "1"), "FORWARDING_VALUE_UNRECOGNIZED")
        lines.append("FACT " + key + "=" + ("not_exposed" if value is None else value))
    for name in ("nftables", "ufw"):
        lines.append(service_summary(name, command((*SERVICE, name + ".service"), limit=4096)))
    lines += ["FACT cloud_firewall=not_observed", "FACT effective_packet_policy=not_qualified"]
    return lines


def main():
    try:
        lines = snapshot()
        print("\n".join(lines))  # Buffer all evidence; a partial read is not success.
        print("RESULT H3_HOST_NETWORK_OBSERVED_NO_MUTATION")
        return 0
    except Exception as error:
        print("STOP " + (str(error) if isinstance(error, Stop) else "NETWORK_READBACK_UNAVAILABLE"))
        print("RESULT H3_NETWORK_OBSERVATION_INCOMPLETE_NO_MUTATION")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
