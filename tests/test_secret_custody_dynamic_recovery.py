"""CI-only DHCPv4/IPv6 RA composition with independent restricted recovery.

Fixed synthetic peers, two owned tables, no installer or live profile. Existing
isolated protocol fixtures remain separate mandatory jobs.
"""
from contextlib import ExitStack, contextmanager
import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import patch


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


v = module("ipv6", "test_secret_custody_ipv6_control.py")
d, t, raw = v.d, v.t, v.raw
w = module("watchdog", "test_secret_custody_network_watchdog.py")
UNRELATED = "kc_dynamic_unrelated"
WINDOWS = {"short": 5, "lifecycle": 22}
GUARDED = {"time-lease": ("time", "time"), "dhcp4-lease": (4, "dhcp4"), "ra6-lease": (6, "ra6")}


def guard():
    d.guard()
    if os.environ.get("KC_DYNAMIC_RECOVERY_CI") != "1":
        raise RuntimeError("DYNAMIC_RECOVERY_CI_OPT_IN_REQUIRED")


def tables(version):
    version = GUARDED.get(version, (version, None))[0]
    if version in (4, "dhcp-dns", "rescue"):
        return (("inet", d.TABLE), ("netdev", d.LINK_TABLE))
    if version in (6, "dhcp6"):
        return (("inet", v.TABLE), ("netdev", v.LINK))
    if version == "dns":
        return (("inet", "kc_dns"), ("netdev", "kc_dns_link"))
    if version == "time":
        return (("inet", "kc_time"), ("netdev", "kc_time_link"))
    if version in ("pmtu4", "pmtu6"):
        return (("inet", "kc_pmtu"), ("netdev", "kc_pmtu_link"))
    raise ValueError("FIXED_IP_FAMILY_REQUIRED")


def profile(version, mode):
    version = GUARDED.get(version, (version, None))[0]
    owned = tables(version)
    if mode not in ("maintenance", "qualification"):
        raise ValueError("FIXED_PROFILE_REQUIRED")
    if version == "rescue":
        return module("rescue_profile", "test_secret_custody_restricted_rescue.py").policy(mode)
    if version == "dns":
        return module("dns_profile", "test_secret_custody_dns.py").policy(mode)
    if version == "time":
        return module("time_profile", "test_secret_custody_time.py").policy(mode)
    result = d.policy() + d.link_policy() if version == 4 else v.policies()
    if version == "dhcp6":
        result = module("dhcp6_profile", "test_secret_custody_dhcpv6.py").policies()
    if version == "dhcp-dns":
        result = module("dhcp_dns_profile", "test_secret_custody_dhcp_dns.py").policy()
    ip, host, peer = ("ip", d.CLIENT, d.PRIMARY) if version in (4, "dhcp-dns") else ("ip6", v.CLIENT, v.REMOTE)
    if version in ("pmtu4", "pmtu6"):
        pmtu = module("pmtu_profile", "test_secret_custody_pmtu.py")
        family = 4 if version == "pmtu4" else 6
        result = pmtu.policy(family)
        addresses = pmtu.ADDRESSES[family]
        ip, host, peer = "ip" if family == 4 else "ip6", addresses[0], addresses[3]
    if mode == "maintenance":
        return result
    inet, link = owned[0][1], owned[1][1]
    # Insert before default-denial rules in BOTH layers. No broad established
    # allowance: the fixed qualification tuple is removed in its entirety.
    result += f'''insert rule inet {inet} input iifname "host0" {ip} saddr {peer} {ip} daddr {host} tcp sport 443 ct state established accept
insert rule inet {inet} output oifname "host0" {ip} saddr {host} {ip} daddr {peer} tcp dport 443 ct state {{ new, established }} accept
insert rule netdev {link} ingress meta protocol {ip} {ip} saddr {peer} {ip} daddr {host} tcp sport 443 accept
insert rule netdev {link} egress meta protocol {ip} {ip} saddr {host} {ip} daddr {peer} tcp dport 443 accept
'''
    return result


def replacement(version, mode):
    return "".join(f"delete table {family} {name}\n" for family, name in tables(version)) + profile(version, mode)


def stable(value):
    """Exclude nft handles and only anonymous-counter measurement fields."""
    if isinstance(value, list):
        return [stable(item) for item in value]
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key == "handle":
                continue
            if key == "counter" and isinstance(item, dict):
                item = {k: v for k, v in item.items() if k not in ("packets", "bytes")}
            result[key] = stable(item)
        return result
    return value


def table_shape(family, name):
    entries = json.loads(t.run(t.NFT, "-j", "list", "table", family, name).stdout)["nftables"]
    return stable([item for item in entries if "metainfo" not in item])


def shape(version):
    return [table_shape(family, name) for family, name in tables(version)]


def transition(version, expected, mode, verify=None):
    if shape(version) != expected:
        raise RuntimeError("OWNED_TABLES_CHANGED_STOP")
    if verify is not None:
        verify()
    # One nft transaction covers both inet and netdev; never sequential calls.
    t.nft(replacement(version, mode))


def process_start(pid):
    # Linux proc stat comm may contain spaces/parentheses; field 22 follows it.
    return Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()[19]


def recovery_context(version):
    tables(version)
    boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    if str(uuid.UUID(boot)) != boot:
        raise ValueError("BOOT_ID_REQUIRED")
    interfaces = {}
    for name in (("host0", "rescue0") if version == "rescue" else ("host0",)):
        output = t.run(t.IP, "-j", "-d", "link", "show", "dev", name).stdout
        if len(output) > 16384:
            raise ValueError("INTERFACE_REPORT_BOUND")
        rows = json.loads(output)
        if len(rows) != 1:
            raise ValueError("ONE_FIXED_INTERFACE_REQUIRED")
        link = rows[0]
        if (link["ifname"] != name or type(link["ifindex"]) is not int or link["ifindex"] <= 0
                or link["link_type"] != "ether" or link["linkinfo"]["info_kind"] != "veth"
                or not isinstance(link["address"], str) or len(link["address"]) != 17):
            raise ValueError("FIXED_VETH_IDENTITY_REQUIRED")
        interfaces[name] = {"ifindex": link["ifindex"], "address": link["address"],
                            "kind": link["linkinfo"]["info_kind"]}
    # Address/route/lease, MTU and administrative up/down are intentionally not
    # identity: existing dynamic and broken-rescue-path tests exercise them.
    return {"boot": boot, "netns": os.readlink("/proc/self/ns/net"), "interfaces": interfaces}


def binding(data):
    attempt = data["attempt"]
    if not isinstance(attempt, str) or len(attempt) != 32 or uuid.UUID(hex=attempt).hex != attempt:
        raise ValueError("RECOVERY_ATTEMPT_REQUIRED")
    return {"attempt": attempt, "version": data["version"], "context": data["context"]}


def require_context(data):
    try:
        if recovery_context(data["version"]) == data["context"]:
            return
    except (OSError, ValueError, KeyError, TypeError, RuntimeError):
        pass
    raise RuntimeError("RECOVERY_CONTEXT_CHANGED_STOP")



def lease_module():
    spec = importlib.util.spec_from_file_location(
        "qualification_lease", Path(__file__).resolve().parents[1] / "review/secret_custody_qualification_lease.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def lease_reports():
    return [json.loads(t.run(t.NFT, "-j", "list", "table", family, name).stdout)
            for family, name in lease_module().TABLES]


def require_lease(data):
    if data["version"] in GUARDED:
        try:
            reports = lease_reports()
            lease_module().require(data.get("qualification_guard"), binding(data), reports, time.monotonic(), GUARDED[data["version"]][1])
        except (RuntimeError, ValueError, KeyError, TypeError) as exc:
            raise RuntimeError("QUALIFICATION_GUARD_REQUIRED") from exc

def readiness(path, data):
    report = (path / "ready").read_text()
    if len(report) > 16384:
        raise RuntimeError("READINESS_REPORT_BOUND")
    ready = json.loads(report)
    if (type(ready["deadline"]) not in (int, float) or not math.isfinite(ready["deadline"])
            or ready["deadline"] - time.monotonic() < 2):
        raise RuntimeError("WATCHDOG_NOT_ARMED")
    try:
        fd = os.pidfd_open(ready["pid"])
    except ProcessLookupError as exc:
        raise RuntimeError("WATCHDOG_DEAD_BEFORE_APPLY") from exc
    try:
        if (select.select([fd], [], [], 0)[0]
                or process_start(ready["pid"]) != ready["start"]
                or os.readlink(f'/proc/{ready["pid"]}/ns/net') != data["netns"]):
            raise RuntimeError("WATCHDOG_DEAD_OR_CHANGED_BEFORE_APPLY")
    except FileNotFoundError as exc:
        raise RuntimeError("WATCHDOG_DEAD_BEFORE_APPLY") from exc
    finally:
        os.close(fd)
    if ready.get("binding") != binding(data):
        raise RuntimeError("READINESS_BINDING_MISMATCH")
    require_context(data)
    require_lease(data)


def worker(value, version):
    guard()
    tables(version)
    path = w.directory(value)
    data = json.loads((path / "expected.json").read_text())
    if (data["version"] != version or data["netns"] != os.readlink("/proc/self/ns/net")
            or os.getppid() != 1):
        raise RuntimeError("INDEPENDENT_SUPERVISOR_AND_NAMESPACE_REQUIRED")
    maintenance, candidate = data["maintenance"], data["candidate"]
    with w.locked(path):
        require_context(data)
        if shape(version) != maintenance:
            raise RuntimeError("MAINTENANCE_ANCHOR_REQUIRED")
        require_lease(data)
        deadline = time.monotonic() + WINDOWS[data["window"]]
        ready = {"pid": os.getpid(), "start": process_start(os.getpid()), "deadline": deadline,
                 "binding": binding(data)}
        temporary = path / "ready.tmp"
        temporary.write_text(json.dumps(ready))
        temporary.replace(path / "ready")
    while time.monotonic() < deadline:
        time.sleep(max(0, min(0.05, deadline - time.monotonic())))
    with w.locked(path):
        try:
            require_context(data)
            result = w.decide(shape(version), maintenance, candidate)
            if result == "RESTORE_MAINTENANCE":
                transition(version, candidate, "maintenance", verify=lambda: require_context(data))
                if shape(version) != maintenance:
                    raise RuntimeError("FALLBACK_READBACK_MISMATCH")
        except RuntimeError as error:
            if str(error) != "RECOVERY_CONTEXT_CHANGED_STOP":
                raise
            result = "STOP_RECOVERY_CONTEXT_CHANGED"
        temporary = path / "result.tmp"
        temporary.write_text(result)
        temporary.replace(path / "result")


def controller(value, version, mode):
    guard()
    tables(version)
    if mode not in ("before", "after"):
        raise ValueError("FIXED_DEATH_PHASE_REQUIRED")
    path = w.directory(value)
    data = json.loads((path / "expected.json").read_text())
    if data["version"] != version or data["netns"] != os.readlink("/proc/self/ns/net"):
        raise RuntimeError("CONTROLLER_NAMESPACE_MISMATCH")
    with w.locked(path):
        readiness(path, data)
        if mode == "after":
            transition(version, data["maintenance"], "qualification", verify=lambda: readiness(path, data))
            if shape(version) != data["candidate"]:
                raise RuntimeError("CANDIDATE_READBACK_MISMATCH")
    (path / "applied").write_text(mode)
    os.kill(os.getpid(), signal.SIGKILL)


@contextmanager
def armed(version, maintenance, candidate, window="short"):
    guard()
    if window not in WINDOWS:
        raise ValueError("FIXED_RECOVERY_WINDOW_REQUIRED")
    path = Path(tempfile.mkdtemp(prefix="kc-watchdog-ci-", dir="/run"))
    path.chmod(0o700)
    unit = path.name + ".service"
    try:
        (path / "lock").touch(mode=0o600)
        data = {
            "version": version, "window": window, "netns": os.readlink("/proc/self/ns/net"),
            "attempt": uuid.uuid4().hex, "context": recovery_context(version),
            "maintenance": maintenance, "candidate": candidate}
        if version in GUARDED:
            lease = lease_module()
            # Fixed create transaction must succeed: never adopt an old guard.
            started = time.monotonic()
            t.nft(lease.install(data["context"]["interfaces"]["host0"]["ifindex"], GUARDED[version][1]))
            data["qualification_guard"] = {
                "binding": binding(data), "deadline": started + lease.SECONDS,
                "snapshot": lease.snapshot(lease_reports(), GUARDED[version][1])}
            require_lease(data)
        (path / "expected.json").write_text(json.dumps(data))
        (path / "expected.json").chmod(0o600)
        t.run("/usr/bin/systemd-run", "--quiet", "--unit=" + unit,
              "--property=Type=exec", "--property=Restart=no", "--property=RuntimeMaxSec=35",
              "--property=TimeoutStopSec=2", "--property=KillMode=control-group", "--property=UMask=0077",
              "--property=StandardOutput=null", "--property=StandardError=journal",
              "--property=NetworkNamespacePath=/proc/" + str(os.getpid()) + "/ns/net",
              "--setenv=GITHUB_ACTIONS=true", "--setenv=KC_DHCP_CI=1",
              "--setenv=KC_DYNAMIC_RECOVERY_CI=1",
              sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--worker", str(path), str(version))
        ready = json.loads(w.await_file(path / "ready", 4))
        status = t.run("/usr/bin/systemctl", "show", unit, "--property=MainPID,ActiveState,Restart").stdout.decode()
        assert ready["pid"] != os.getpid() and f'MainPID={ready["pid"]}\n' in status
        assert "ActiveState=active\n" in status and "Restart=no\n" in status
        yield path, unit
    except BaseException:
        log = t.run("/usr/bin/journalctl", "--no-pager", "-u", unit, "-n", "30", success=False)
        print(log.stdout[-6000:].decode("utf-8", "replace"), file=sys.stderr)
        raise
    finally:
        t.run("/usr/bin/systemctl", "stop", unit, success=False)
        t.run("/usr/bin/systemctl", "reset-failed", unit, success=False)
        assert t.run("/usr/bin/systemctl", "show", unit, "--property=MainPID", "--value").stdout == b"0\n"
        shutil.rmtree(path)


def invoke_controller(path, version, mode, dead_worker=False):
    result = subprocess.run([sys.executable, "-I", "-B", __file__, "--controller", str(path), str(version), mode],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=4)
    if dead_worker:
        assert result.returncode != 0 and b"WATCHDOG_DEAD" in result.stderr, result.stderr[-1500:]
        assert not (path / "applied").exists()
    else:
        assert result.returncode == -signal.SIGKILL, result.stderr[-1500:]
        assert (path / "applied").read_text() == mode


class Advertiser:
    def __init__(self):
        self.enabled = False
        self.sent = 0
        self.error = None
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def serve(self):
        try:
            while not self.stop.wait(1):
                with self.lock:
                    if self.enabled:
                        v.send_control("ra", "good")
                        self.sent += 1
                        if self.sent > 200:
                            raise RuntimeError("RA_EVENT_BOUND")
        except BaseException as exc:
            self.error = type(exc).__name__

    def close(self):
        self.stop.set()
        self.thread.join(2)
        assert not self.thread.is_alive()


def peer(version):
    guard()
    tables(version)
    assert os.readlink("/proc/self/ns/net") != os.environ.get("FIXTURE_PARENT_NETNS")
    host, source = (d.CLIENT, d.PRIMARY) if version == 4 else (v.CLIENT, v.REMOTE)
    with ExitStack() as stack:
        print("READY", flush=True)
        old, service = None, None
        for line in sys.stdin:
            if len(line) > 4096:
                raise RuntimeError("RPC_BOUND")
            msg = json.loads(line)
            op = msg[0]
            if op == "setup":
                t.run(t.IP, "link", "set", "lo", "up")
                t.run(t.IP, "link", "set", "peer0", "address", t.MAC_PEER, "addrgenmode", "none")
                t.run("sysctl", "-qw", "net.ipv6.conf.peer0.disable_ipv6=" + ("1" if version == 4 else "0"), "net.ipv6.conf.peer0.accept_ra=0")
                addresses = (d.PRIMARY + "/24", d.ALTERNATE + "/24") if version == 4 else (v.ROUTER + "/64", v.PEER + "/64", v.REMOTE + "/128", v.DUPLICATE + "/64")
                for address in addresses:
                    t.run(t.IP, "-" + str(version), "addr", "add", address, "dev", "peer0", *(("nodad",) if version == 6 else ()))
                t.run(t.IP, "link", "set", "peer0", "up")
                service = d.Server() if version == 4 else Advertiser()
                stack.callback(service.close)
                t.listen(stack, source, 443)
                result = True
            elif op == "mode" and version == 4:
                if msg[1] not in ("normal", "rebind", "silent"):
                    raise RuntimeError("FIXED_DHCP_MODE_REQUIRED")
                with service.lock:
                    service.mode = msg[1]
                    service.events.clear()
                result = True
            elif op == "events" and version == 4:
                with service.lock:
                    if service.error:
                        raise RuntimeError(service.error)
                    result = list(service.events)
            elif op == "ra" and version == 6:
                if type(msg[1]) is not bool:
                    raise RuntimeError("BOOLEAN_RA_MODE_REQUIRED")
                with service.lock:
                    if service.error:
                        raise RuntimeError(service.error)
                    service.enabled = msg[1]
                    result = service.sent
            elif op == "bad" and version == 4:
                d.send_case("in", "source", "kc-composed-bad-dhcp")
                result = True
            elif op == "bad" and version == 6:
                for variant in ("source", "hop", "code"):
                    v.send_control("ra", variant)
                result = True
            elif op == "open":
                old = stack.enter_context(t.connect(host, 22, source))
                result = t.exchange(old)
            elif op == "check":
                result = t.exchange(old) and t.reaches(host, 22, source)
            elif op == "denied":
                result = not t.reaches(host, 80, source)
            elif op == "expired":
                result = not t.reaches(host, 22, source)
            elif op == "flush":
                t.run(t.IP, "-" + str(version), "neigh", "flush", "dev", "peer0")
                result = True
            else:
                raise RuntimeError("FIXED_RPC_OPERATION_REQUIRED")
            print(json.dumps(result), flush=True)


def counters(version):
    return raw.counters(*tables(version)[1])


def neighbors(version, proc):
    before = counters(version)
    t.run(t.IP, "-" + str(version), "neigh", "flush", "dev", "host0")
    assert t.rpc(proc, "flush") and t.rpc(proc, "check")
    keys = ("link_in_arp", "link_out_arp") if version == 4 else ("in_nd", "out_nd")
    after = counters(version)
    assert all(after[k] > before[k] for k in keys), (before, after)
    rows = json.loads(t.run(t.IP, "-j", "-" + str(version), "neigh", "show", "dev", "host0").stdout)
    router = d.PRIMARY if version == 4 else v.ROUTER
    assert any(n.get("dst") == router and n.get("lladdr") == t.MAC_PEER and "PERMANENT" not in n.get("state", []) for n in rows)


def empty():
    assert {x["ifname"] for x in json.loads(t.run(t.IP, "-j", "link").stdout)} == {"lo"}
    assert all("metainfo" in x for x in json.loads(t.run(t.NFT, "-j", "list", "ruleset").stdout)["nftables"])


def run_case(version):
    guard()
    tables(version)
    empty()
    peer_address = d.PRIMARY if version == 4 else v.REMOTE
    env = dict(os.environ, FIXTURE_PARENT_NETNS=os.readlink("/proc/self/ns/net"))
    proc = subprocess.Popen(["unshare", "--net", sys.executable, "-I", "-B", __file__, "--peer", str(version)],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env)
    phase = "setup"
    try:
        assert t.read_line(proc).strip() == "READY"
        t.run(t.IP, "link", "add", "host0", "type", "veth", "peer", "name", "peer0")
        t.run(t.IP, "link", "set", "peer0", "netns", str(proc.pid))
        t.run(t.IP, "link", "set", "lo", "up")
        t.run(t.IP, "link", "set", "host0", "address", t.MAC_HOST, "addrgenmode", "none")
        t.run("sysctl", "-qw", "net.ipv6.conf.host0.disable_ipv6=" + ("1" if version == 4 else "0"), "net.ipv6.conf.host0.accept_ra=0")
        t.run(t.IP, "link", "set", "host0", "up")
        assert t.rpc(proc, "setup")
        # Compile both exact shapes before any dynamic client or test listener
        # exists. The actual lifecycle starts in restricted maintenance.
        t.nft(profile(version, "maintenance"))
        maintenance = shape(version)
        t.nft(replacement(version, "qualification"))
        candidate = shape(version)
        t.nft(replacement(version, "maintenance"))
        assert maintenance != candidate and shape(version) == maintenance
        t.nft(f'table inet {UNRELATED} {{ chain output {{ type filter hook output priority 10; policy accept; tcp dport 9443 drop; }}; }}\n')
        unrelated = table_shape("inet", UNRELATED)
        with ExitStack() as stack:
            for port in (22, 80):
                t.listen(stack, "0.0.0.0" if version == 4 else "::", port)
            root, _ = stack.enter_context(d.networkd(ipv6=version == 6))
            if version == 4:
                d.wait_for(lambda: d.address_present() and d.default_route_present() and d.lease_server(root) == d.PRIMARY, 20)
            else:
                d.wait_for(lambda: v.usable(v.HOST_LL), 8)
                t.rpc(proc, "ra", True)
                d.wait_for(lambda: v.usable(v.CLIENT) and v.route_present(), 8)
            assert t.rpc(proc, "open")

            def check():
                assert (d.address_present() and d.default_route_present()) if version == 4 else (v.usable(v.CLIENT) and v.route_present())
                assert t.rpc(proc, "check"), "ADMIN_TRANSPORT_LOST"
                assert table_shape("inet", UNRELATED) == unrelated

            def restricted():
                assert shape(version) == maintenance
                assert not t.reaches(peer_address, 443)
                assert t.rpc(proc, "denied")
                check()

            restricted()
            print(f"PASS IPv{version}_DYNAMIC_MAINTENANCE_ANCHOR", flush=True)
            phase = "controller-death-during-lifecycle"
            with armed(version, maintenance, candidate, "lifecycle") as (path, _):
                invoke_controller(path, version, "after")
                assert shape(version) == candidate
                old = stack.enter_context(t.connect(peer_address, 443))
                assert t.exchange(old)
                before = counters(version)
                if version == 4:
                    assert t.rpc(proc, "mode", "normal")
                    d.wait_for(lambda: any(e["kind"] == "renew" and e["answered"] for e in t.rpc(proc, "events")), 18, check)
                    assert counters(version)["link_in_dhcp"] > before["link_in_dhcp"]
                    assert d.lease_server(root) == d.PRIMARY
                else:
                    start = time.monotonic()
                    d.wait_for(lambda: time.monotonic() > start + v.LIFETIME + 1, v.LIFETIME + 3, check)
                    assert counters(version)["in_ra"] > before["in_ra"]
                    neighbors(version, proc)
                assert shape(version) == candidate and not (path / "result").exists()
                assert t.exchange(old)
                print(f"PASS IPv{version}_DYNAMIC_REFRESH_AFTER_CONTROLLER_SIGKILL", flush=True)
                d.wait_for(lambda: (path / "result").exists(), 25, check)
                assert (path / "result").read_text() == "RESTORE_MAINTENANCE"
            assert not t.exchange(old) and not t.reaches(peer_address, 443)
            restricted()
            neighbors(version, proc)
            print(f"PASS IPv{version}_PID1_ATOMIC_TWO_TABLE_RESTORE_REVOKES_OLD_NEW_DATA", flush=True)
            phase = "dynamic-controls-after-restore"
            before = counters(version)
            if version == 4:
                assert t.rpc(proc, "mode", "normal")
                d.wait_for(lambda: any(e["kind"] == "renew" and e["answered"] for e in t.rpc(proc, "events")), 18, restricted)
                assert counters(version)["link_in_dhcp"] > before["link_in_dhcp"]
                assert counters(version)["link_out_bound"] > before["link_out_bound"]
                assert t.rpc(proc, "mode", "rebind")
                d.wait_for(lambda: d.lease_server(root) == d.ALTERNATE, 28, restricted)
                events = t.rpc(proc, "events")
                assert any(e["kind"] == "renew" and not e["answered"] for e in events)
                assert any(e["kind"] == "rebind" and e["answered"] for e in events)
                assert t.rpc(proc, "mode", "normal")
                with ExitStack() as packets:
                    receivers = d.packet_receivers(packets, "host0")
                    rejected = counters(version)["link_in_deny"]
                    assert t.rpc(proc, "bad")
                    assert raw.collect(receivers, "kc-composed-bad-dhcp") == {"ip": False, "all": True}
                    assert counters(version)["link_in_deny"] == rejected + 1
                print("PASS IPv4_POST_RESTORE_RENEW_REBIND_AND_INVALID_DHCP_DENIAL", flush=True)
            else:
                start = time.monotonic()
                d.wait_for(lambda: time.monotonic() > start + v.LIFETIME + 1, v.LIFETIME + 3, restricted)
                assert counters(version)["in_ra"] > before["in_ra"]
                rejected = counters(version)["in_bad_ra"]
                assert t.rpc(proc, "bad")
                d.wait_for(lambda: counters(version)["in_bad_ra"] == rejected + 3, 2, restricted)
                print("PASS IPv6_POST_RESTORE_RA_REFRESH_ND_AND_INVALID_RA_DENIAL", flush=True)
            restricted()
            phase = "worker-death-and-drift"
            with armed(version, maintenance, candidate) as (path, unit):
                t.run("/usr/bin/systemctl", "kill", "--signal=SIGKILL", unit)
                d.wait_for(lambda: t.run("/usr/bin/systemctl", "show", unit, "--property=MainPID", "--value").stdout == b"0\n", 2)
                invoke_controller(path, version, "after", dead_worker=True)
                assert shape(version) == maintenance and not (path / "result").exists()
            restricted()
            print(f"PASS IPv{version}_DEAD_WORKER_REFUSES_APPLY", flush=True)
            with armed(version, maintenance, candidate) as (path, _):
                invoke_controller(path, version, "before")
                d.wait_for(lambda: (path / "result").exists(), 8, restricted)
                assert (path / "result").read_text() == "ALREADY_MAINTENANCE"
            print(f"PASS IPv{version}_PREAPPLY_CONTROLLER_DEATH_NO_MUTATION", flush=True)
            for family, name in tables(version):
                with armed(version, maintenance, candidate) as (path, _):
                    invoke_controller(path, version, "after")
                    with w.locked(path):
                        chain = "output" if family == "inet" else "egress"
                        t.nft(f"add rule {family} {name} {chain} tcp dport 9443 drop\n")
                        changed = shape(version)
                    d.wait_for(lambda: (path / "result").exists(), 8, check)
                    assert (path / "result").read_text() == "STOP_OWNED_TABLE_DRIFT"
                    assert shape(version) == changed
                # Explicit observing-fixture teardown after a fail-stop; never
                # represented as worker recovery from an unknown table shape.
                t.nft(replacement(version, "maintenance"))
                restricted()
            print(f"PASS IPv{version}_EITHER_TABLE_DRIFT_STOPS_WITHOUT_OVERWRITE", flush=True)
            if version == 6:
                phase = "ra-expiry-after-recovery"
                assert t.rpc(proc, "ra", False) > 0
                d.wait_for(lambda: not v.route_present(), v.LIFETIME + 3)
                assert v.usable(v.CLIENT) and not v.routes() and t.rpc(proc, "expired")
                assert shape(version) == maintenance and not t.reaches(peer_address, 443)
                assert Path("/proc/sys/net/ipv6/conf/host0/forwarding").read_text().strip() == "0"
                print("PASS IPv6_POST_RESTORE_RA_EXPIRY_REMOVES_OFFLINK_ACCESS", flush=True)
            assert table_shape("inet", UNRELATED) == unrelated
    except BaseException:
        print("DYNAMIC_RECOVERY_FAILURE", version, phase, file=sys.stderr)
        print(t.run(t.NFT, "list", "ruleset", success=False).stdout[:9000].decode(), file=sys.stderr)
        raise
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
        assert proc.poll() is not None
        t.run(t.IP, "link", "del", "host0", success=False)
        for family, name in (*tables(version), ("inet", UNRELATED)):
            t.nft(f"delete table {family} {name}\n", success=False)
        empty()
    print(f"PASS IPv{version}_DYNAMIC_RECOVERY_UNITS_PROCESSES_LINKS_FILES_CLEANED", flush=True)


class Tests(unittest.TestCase):
    def test_host_namespace_rejected_before_commands(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), patch.object(os, "geteuid", return_value=0), patch.object(os, "readlink", return_value="same"), patch.object(t, "run") as run:
            with self.assertRaises(RuntimeError):
                run_case(4)
            run.assert_not_called()

    def test_opt_in_and_fixed_profiles_required(self):
        with patch.object(d, "guard"), patch.dict(os.environ, {"KC_DYNAMIC_RECOVERY_CI": "0"}), patch.object(t, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "OPT_IN_REQUIRED"):
                run_case(6)
            run.assert_not_called()
        for version, mode in ((5, "maintenance"), (4, "open"), (6, "open")):
            with self.assertRaises(ValueError):
                profile(version, mode)

    def test_counter_progress_is_not_rule_drift_but_policy_changes_are(self):
        original = {"rule": {"handle": 1, "expr": [{"counter": {"packets": 1, "bytes": 64}}, {"accept": None}]}}
        changed = copy.deepcopy(original)
        changed["rule"]["handle"] = 9
        changed["rule"]["expr"][0]["counter"] = {"packets": 55, "bytes": 3520}
        self.assertEqual(stable(original), stable(changed))
        changed["rule"]["expr"][1] = {"drop": None}
        self.assertNotEqual(stable(original), stable(changed))
        self.assertNotEqual(stable({"limit": {"bytes": 1}}), stable({"limit": {"bytes": 2}}))

    def test_either_owned_table_drift_prevents_transaction(self):
        for index in (0, 1):
            expected = [[{"safe": 1}], [{"safe": 2}]]
            changed = copy.deepcopy(expected)
            changed[index].append({"unexpected": 1})
            with patch(__name__ + ".shape", return_value=changed), patch.object(t, "nft") as mutate:
                with self.assertRaisesRegex(RuntimeError, "OWNED_TABLES_CHANGED_STOP"):
                    transition(4, expected, "maintenance")
                mutate.assert_not_called()

    def test_expired_readiness_refuses_before_process_probe(self):
        with tempfile.TemporaryDirectory() as value:
            path = Path(value)
            (path / "ready").write_text('{"deadline":0}')
            with patch.object(os, "pidfd_open") as probe:
                with self.assertRaisesRegex(RuntimeError, "WATCHDOG_NOT_ARMED"):
                    readiness(path, {})
                probe.assert_not_called()

    def test_missing_or_dead_worker_readiness_refuses(self):
        with tempfile.TemporaryDirectory() as value:
            path = Path(value)
            with self.assertRaises(FileNotFoundError):
                readiness(path, {})
            (path / "ready").write_text(json.dumps({"deadline": time.monotonic() + 10, "pid": 1234}))
            with patch.object(os, "pidfd_open", side_effect=ProcessLookupError):
                with self.assertRaisesRegex(RuntimeError, "WATCHDOG_DEAD_BEFORE_APPLY"):
                    readiness(path, {})


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["--systemd"]:
        guard()
        print("KERNEL", os.uname().release, flush=True)
        for version in (4, 6):
            run_case(version)
        print("RESULT SYNTHETIC_DYNAMIC_RECOVERY_OK_NO_LIVE_APPLY", flush=True)
    elif len(args) == 2 and args[0] == "--peer" and args[1] in ("4", "6"):
        peer(int(args[1]))
    elif len(args) == 3 and args[0] == "--worker" and args[2] in ("4", "6", "dhcp6", "pmtu4", "pmtu6", "dns", "time", "time-lease", "dhcp4-lease", "ra6-lease", "dhcp-dns", "rescue"):
        worker(args[1], int(args[2]) if args[2] in ("4", "6") else args[2])
    elif len(args) == 4 and args[0] == "--controller" and args[2] in ("4", "6", "dhcp6", "pmtu4", "pmtu6", "dns", "time", "time-lease", "dhcp4-lease", "ra6-lease", "dhcp-dns", "rescue") and args[3] in ("before", "after"):
        controller(args[1], int(args[2]) if args[2] in ("4", "6") else args[2], args[3])
    else:
        unittest.main(verbosity=2)
