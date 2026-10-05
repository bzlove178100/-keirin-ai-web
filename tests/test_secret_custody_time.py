"""CI-only chronyd source selection with no clock-setting capability."""
from contextlib import ExitStack, contextmanager
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import select
import signal
import shutil
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

SPEC = importlib.util.spec_from_file_location("recovery", Path(__file__).with_name("test_secret_custody_dynamic_recovery.py"))
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)
t, raw = r.t, r.raw
TABLE, LINK, KEY = "kc_time", "kc_time_link", "time"
FAMILIES = ((4, "ip", "192.0.2."), (6, "ip6", "2001:db8:1::"))
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "LC_ALL": "C"}
# Linux SO_TIMESTAMPNS_NEW: fixed two signed 64-bit fields, including on time32.
RX_TIMESTAMP = 64


def received_packet(sock):
    data, ancillary, flags, source = sock.recvmsg(513, socket.CMSG_SPACE(16))
    if flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC):
        raise ValueError("NTP_RX_TRUNCATED")
    stamps = [value for level, kind, value in ancillary
              if level == socket.SOL_SOCKET and kind == RX_TIMESTAMP]
    if len(stamps) != 1 or len(stamps[0]) != 16:
        raise ValueError("NTP_KERNEL_RX_TIMESTAMP_REQUIRED")
    seconds, nanos = struct.unpack("=qq", stamps[0])
    if seconds <= 0 or not 0 <= nanos < 1000000000:
        raise ValueError("NTP_KERNEL_RX_TIMESTAMP_INVALID")
    return data, source, seconds + nanos / 1000000000


def timestamp_control():
    """CI-only queued datagram proves processing delay is server residence time."""
    guard()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
        receiver.setsockopt(socket.SOL_SOCKET, RX_TIMESTAMP, 1)
        receiver.settimeout(1)
        receiver.bind(("192.0.2.1", 0))
        request = bytes([0x23]) + bytes(39) + stamp(time.time())
        sender.sendto(request, receiver.getsockname())
        assert select.select([receiver], [], [], 1)[0]
        time.sleep(0.025)
        data, _, received = received_packet(receiver)
        dequeued = time.time()
        response = reply(data, "good", received)
        assert data == request and response[32:40] == stamp(received)
        assert 0.020 <= dequeued - received < 1
        print("TIME_KERNEL_RX_CONTROL", json.dumps({"queue_seconds": dequeued - received,
              "receive_field_matches_kernel": True}), flush=True)


def guard():
    t.guard()
    if os.environ.get("KC_TIME_CI") != "1":
        raise RuntimeError("TIME_CI_OPT_IN_REQUIRED")


def stamp(now):
    seconds = int(now)
    return struct.pack("!II", (seconds + 2208988800) & 0xffffffff, int((now - seconds) * (1 << 32)))


def reply(data, mode, received):
    if len(data) != 48 or data[0] & 7 != 3 or (data[0] >> 3) & 7 != 4 or data[40:48] == bytes(8):
        raise ValueError("FIXED_NTP4_CLIENT_REQUEST_REQUIRED")
    if mode not in ("good", "silent", "origin"):
        raise ValueError("FIXED_TIME_MODE_REQUIRED")
    if mode == "silent":
        return None
    header = struct.pack("!BBbbII4s", 0x24, 1, 0, -20, 0, 655, b"TEST")
    origin = data[40:48] if mode == "good" else bytes(8)
    return header + stamp(received - 1) + origin + stamp(received) + stamp(time.time())


class Server:
    def __init__(self, stack, address):
        self.lock = threading.Lock()
        self.mode, self.requests, self.responses, self.bad, self.error = "good", 0, 0, 0, None
        af = socket.AF_INET6 if ":" in address else socket.AF_INET
        self.sock = socket.socket(af, socket.SOCK_DGRAM)
        self.stopping = threading.Event()
        self.sock.settimeout(0.1)
        self.sock.setsockopt(socket.SOL_SOCKET, RX_TIMESTAMP, 1)
        if af == socket.AF_INET6:
            self.sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        self.sock.bind((address, 123))
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()
        stack.callback(self.close)

    def close(self):
        self.stopping.set()
        self.thread.join(timeout=1)
        self.sock.close()
        assert not self.thread.is_alive(), "NTP_FAULT_THREAD_NOT_REAPED"

    def serve(self):
        try:
            while not self.stopping.is_set():
                try:
                    data, source, received = received_packet(self.sock)
                except socket.timeout:
                    continue
                with self.lock:
                    self.requests += 1
                    if self.requests > 512:
                        raise RuntimeError("NTP_REQUEST_BOUND")
                    result = reply(data, self.mode, received)
                    if result is not None:
                        self.sock.sendto(result, source)
                        self.responses += 1
                        self.bad += self.mode == "origin"
        except BaseException as exc:
            self.error = type(exc).__name__


def no_clock_args(daemon, version, config):
    return ["/usr/bin/setpriv", "--reuid=65534", "--regid=65534", "--clear-groups",
            "--bounding-set=-all", "--inh-caps=-all", "--ambient-caps=-all", "--no-new-privs",
            str(daemon), "-x", "-U", "-d", "-u", "nobody", "-" + str(version), "-f", str(config)]


def server_config(address, directory):
    if address not in {prefix + suffix for _, _, prefix in FAMILIES for suffix in ("2", "3")}:
        raise ValueError("FIXED_CHRONY_SERVER_ADDRESS_REQUIRED")
    host = "2001:db8:1::1" if ":" in address else "192.0.2.1"
    # A same-clock isolated reference, not proof of external UTC accuracy.
    return (f"bindaddress {address}\nallow {host}\nlocal stratum 1\nport 123\ncmdport 0\n"
            f"bindcmdaddress {directory}/command.sock\npidfile {directory}/pid\n"
            f"driftfile {directory}/drift\n")


class ChronyServer:
    """Healthy real chronyd; explicit socket handoff to malformed/silent peer."""
    def __init__(self, stack, address, daemon, ctl):
        self.address, self.daemon, self.ctl = address, daemon, ctl
        self.directory = Path(tempfile.mkdtemp(prefix="kc-time-server-", dir="/run"))
        os.chown(self.directory, 65534, 65534)
        self.proc, self.fault, self.mode = None, None, None
        self.fault_stack = ExitStack()
        self.counts = {"requests": 0, "responses": 0, "bad": 0}
        stack.callback(self.close)
        self.change("good")

    def stop(self):
        if self.fault is not None:
            self.fault_stack.close()
            self.counts = {key: self.counts[key] + getattr(self.fault, key) for key in self.counts}
            self.fault = None
        if self.proc is not None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=2)
            assert not Path(f"/proc/{self.proc.pid}").exists()
            self.proc = None

    def close(self):
        self.stop()
        shutil.rmtree(self.directory)
        assert not self.directory.exists()

    def change(self, mode):
        if mode not in ("good", "silent", "origin"):
            raise ValueError("FIXED_TIME_MODE_REQUIRED")
        self.stop()
        self.mode = mode
        if mode == "good":
            config = self.directory / "config"
            config.write_text(server_config(self.address, self.directory))
            config.chmod(0o644)
            with (self.directory / "log").open("ab") as log:
                self.proc = subprocess.Popen(no_clock_args(self.daemon, 6 if ":" in self.address else 4, config),
                    stdin=subprocess.DEVNULL, stdout=log, stderr=log, env=ENV)
            try:
                r.d.wait_for(lambda: (self.directory / "command.sock").exists() or self.proc.poll() is not None, 5)
                self.check()
            except BaseException:
                print((self.directory / "log").read_text(errors="replace")[-5000:], file=sys.stderr)
                raise
        else:
            self.fault = Server(self.fault_stack, self.address)
            with self.fault.lock:
                self.fault.mode = mode
        return self.report()

    def check(self):
        if self.mode == "good":
            Client(self.proc, self.directory, self.ctl, "").check()
        else:
            assert self.fault.error is None, "NTP_FAULT_SERVER_FAILED"

    def timestamping(self):
        self.check()
        assert self.mode == "good"
        output = t.run(str(self.ctl), "-n", "-h", str(self.directory / "command.sock"), "serverstats").stdout.decode()
        assert len(output) < 4096
        fields = {key.strip(): int(value.strip()) for key, value in
                  (line.split(":", 1) for line in output.splitlines() if ":" in line)}
        return {key: fields[key] for key in ("Interleaved NTP packets", "NTP kernel RX timestamps",
                                            "NTP kernel TX timestamps", "NTP daemon TX timestamps")}

    def report(self):
        self.check()
        if self.fault is None:
            return dict(self.counts)
        with self.fault.lock:
            return {key: self.counts[key] + getattr(self.fault, key) for key in self.counts}


def policy(mode="maintenance"):
    if mode not in ("maintenance", "qualification"):
        raise ValueError("FIXED_TIME_PROFILE_REQUIRED")
    rules = {key: [] for key in ("input", "output", "ingress", "egress")}
    for version, ip, prefix in FAMILIES:
        host, peer = prefix + "1", prefix + "2"
        sources = "{ " + prefix + "2, " + prefix + "3 }"
        incoming = f"{ip} saddr {sources} {ip} daddr {host} udp sport 123"
        outgoing = f"{ip} saddr {host} {ip} daddr {sources} udp dport 123"
        ports = "{ 22, 443 }" if mode == "qualification" else "22"
        rules["input"] += [f'iifname "host0" {incoming} ct state established counter accept comment "ntp{version}_in"',
                           f'iifname "host0" {ip} saddr {peer} {ip} daddr {host} tcp sport {ports} ct state established accept']
        rules["output"] += [f'oifname "host0" {outgoing} ct state {{ new, established }} counter accept comment "ntp{version}_out"',
                            f'oifname "host0" {ip} saddr {host} {ip} daddr {peer} tcp dport {ports} ct state {{ new, established }} accept']
        rules["ingress"] += [f'meta protocol {ip} {incoming} accept', f'meta protocol {ip} {ip} saddr {peer} {ip} daddr {host} tcp sport {ports} accept']
        rules["egress"] += [f'meta protocol {ip} {outgoing} accept', f'meta protocol {ip} {ip} saddr {host} {ip} daddr {peer} tcp dport {ports} accept']
    text = f"table inet {TABLE} {{\n"
    for chain in ("input", "output"):
        text += f" chain {chain} {{ type filter hook {chain} priority 0; policy drop;\n"
        text += ('iifname "lo" accept\n' if chain == "input" else 'oifname "lo" accept\n')
        text += "\n".join(rules[chain]) + f'\n counter drop comment "inet_{chain}_deny"\n }}\n'
    text += " chain forward { type filter hook forward priority 0; policy drop; }\n}\n"
    text += f"table netdev {LINK} {{\n"
    for chain in ("ingress", "egress"):
        text += f' chain {chain} {{ type filter hook {chain} device "host0" priority 0; policy drop;\n'
        text += "\n".join(rules[chain]) + f'\n counter drop comment "link_{chain}_deny"\n }}\n'
    return text + "}\n"


def peer():
    guard()
    assert os.readlink("/proc/self/ns/net") != os.environ.get("FIXTURE_PARENT_NETNS")
    def shutdown(_signal, _frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, shutdown)
    daemon, ctl = binaries(report=False)
    with ExitStack() as stack:
        servers = {}
        print("READY", flush=True)
        for line in sys.stdin:
            if len(line) > 1024:
                raise ValueError("TIME_RPC_BOUND")
            msg = json.loads(line)
            if msg[0] == "setup":
                t.run(t.IP, "link", "set", "peer0", "addrgenmode", "none")
                t.run("sysctl", "-qw", "net.ipv6.conf.peer0.accept_ra=0")
                t.setup("peer0", t.MAC_PEER, ("2", "3", "9"))
                # Only this private peer namespace: permit port 123 without caps.
                t.run("sysctl", "-qw", "net.ipv4.ip_unprivileged_port_start=0")
                for _, _, prefix in FAMILIES:
                    for suffix in ("2", "3", "9"):
                        servers[prefix + suffix] = (Server(stack, prefix + suffix) if suffix == "9"
                                                    else ChronyServer(stack, prefix + suffix, daemon, ctl))
                    for port in (22, 123, 443):
                        t.listen(stack, prefix + "2", port)
                result = True
            elif msg[0] == "mode":
                _, address, mode = msg
                assert mode in ("good", "silent", "origin")
                result = servers[address].change(mode)
            elif msg[0] == "timestamping":
                result = servers[msg[1]].timestamping()
            elif msg[0] == "counts":
                server = servers[msg[1]]
                if isinstance(server, ChronyServer):
                    result = server.report()
                else:
                    with server.lock:
                        result = {"requests": server.requests, "responses": server.responses, "bad": server.bad}
            else:
                raise ValueError("FIXED_TIME_RPC_REQUIRED")
            for server in servers.values():
                if isinstance(server, ChronyServer):
                    server.check()
                else:
                    assert server.error is None, "NTP_SERVER_FAILED"
            print(json.dumps(result), flush=True)


def probe(address, success=True):
    af = socket.AF_INET6 if ":" in address else socket.AF_INET
    data = bytes([0x23]) + bytes(39) + stamp(time.time())
    with socket.socket(af, socket.SOCK_DGRAM) as sock:
        sock.settimeout(0.4)
        try:
            sock.sendto(data, (address, 123))
            result, source = sock.recvfrom(512)
        except socket.timeout:
            assert not success
        except OSError as exc:
            if success or exc.errno != errno.EPERM:
                raise
        else:
            assert success and source[0] == address and source[1] == 123
            assert len(result) == 48 and result[0] == 0x24 and result[24:32] == data[40:48]


def binaries(report=True):
    root = Path(os.environ.get("KC_TIME_CLIENT_ROOT", ""))
    if not re.fullmatch(r"/run/kc-chrony-ci-[0-9]+-[0-9]+", str(root)):
        raise ValueError("FIXED_CI_CLIENT_DIRECTORY_REQUIRED")
    paths = [root, root / "usr/sbin/chronyd", root / "usr/bin/chronyc"]
    for path in paths:
        st = path.lstat()
        assert not stat.S_ISLNK(st.st_mode) and st.st_uid == 0 and not st.st_mode & 0o022
    assert (root / "owned").read_text() == "KC_TIME_CI_ONLY\n"
    for path in paths[1:]:
        assert path.is_file()
        if report:
            print("CLIENT", path.name, hashlib.sha256(path.read_bytes()).hexdigest(), flush=True)
    return paths[1:]


def sources(text, prefix):
    result = {}
    for line in text.splitlines():
        if line.startswith("^"):
            fields = line.split()
            assert len(fields) >= 7 and fields[0] in ("^*", "^+", "^-", "^?", "^x", "^~")
            assert fields[1] in (prefix + "2", prefix + "3") and fields[1] not in result
            result[fields[1]] = {"state": fields[0][1], "reach": int(fields[4], 8), "poll": int(fields[3])}
    assert set(result) == {prefix + "2", prefix + "3"}, text
    return result


class Client:
    def __init__(self, proc, directory, ctl, prefix):
        self.proc, self.directory, self.ctl, self.prefix = proc, directory, ctl, prefix

    def check(self):
        assert self.proc.poll() is None, "CHRONYD_EXITED"
        data = dict(line.split(":", 1) for line in Path(f"/proc/{self.proc.pid}/status").read_text().splitlines() if ":" in line)
        assert [int(x) for x in data["Uid"].split()] == [65534] * 4
        assert [int(x) for x in data["Gid"].split()] == [65534] * 4
        assert not data["Groups"].strip()
        assert all(int(data[key], 16) == 0 for key in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb"))
        assert data["NoNewPrivs"].strip() == "1"
        assert os.readlink(f"/proc/{self.proc.pid}/ns/net") == os.readlink("/proc/self/ns/net")

    def state(self):
        self.check()
        result = t.run(str(self.ctl), "-n", "-h", str(self.directory / "command.sock"), "sources")
        assert len(result.stdout) < 4096
        return sources(result.stdout.decode(), self.prefix)

    def ntpdata(self, suffix):
        self.check()
        result = t.run(str(self.ctl), "-n", "-h", str(self.directory / "command.sock"), "ntpdata", self.prefix + suffix)
        assert len(result.stdout) < 4096
        fields = dict(line.split(":", 1) for line in result.stdout.decode().splitlines() if ":" in line)
        fields = {key.strip(): value.strip() for key, value in fields.items()}
        assert fields["Remote address"].split()[0] == self.prefix + suffix
        return fields

    def ntpstats(self, suffix):
        fields = self.ntpdata(suffix)
        return {key: int(fields[key]) for key in ("Total RX", "Total valid RX", "Total good RX")}

    def prepare_samples(self):
        self.check()
        # One bounded acquisition per healthy preparation, never a CI retry or
        # filter change. chronyd still requires its own full good-packet tests.
        for suffix in ("2", "3"):
            result = t.run(str(self.ctl), "-n", "-h", str(self.directory / "command.sock"),
                           "burst", "4/16", self.prefix + suffix)
            assert result.stdout.strip() == b"200 OK", "BURST_REQUEST_REJECTED"

    def sampling_idle(self):
        self.check()
        result = t.run(str(self.ctl), "-n", "-h", str(self.directory / "command.sock"), "activity")
        return burst_idle(result.stdout.decode())

    def measurements(self):
        path = self.directory / "measurements.log"
        if not path.exists():
            return {"counts": {}, "tail": []}
        with path.open("r") as source:
            text = source.read(262145)
        return measurement_summary(text, self.prefix)

    def selected(self, suffix):
        result = self.state()
        return result[self.prefix + suffix]["state"] == "*" and result[self.prefix + suffix]["reach"] > 0


def fresh_sources(before, after, state, primary):
    return (state[primary]["state"] == "*" and all(state[ip]["reach"] > 0
            and after[ip]["Total good RX"] >= before[ip]["Total good RX"] + 4 for ip in before))


def burst_idle(text):
    if len(text) > 4096:
        raise ValueError("ACTIVITY_REPORT_BOUND")
    counts = re.findall(r"^(\d+) sources doing burst \(return to (online|offline)\)$", text, re.M)
    if len(counts) != 2 or {kind for _, kind in counts} != {"online", "offline"}:
        raise ValueError("ACTIVITY_BURST_STATES_REQUIRED")
    return all(int(value) == 0 for value, _ in counts)


def measurement_summary(text, prefix):
    if len(text) > 262144:
        raise ValueError("MEASUREMENT_LOG_BOUND")
    counts, rows = {}, []
    for line in text.splitlines():
        if not re.match(r"^\d{4}-\d{2}-\d{2} ", line):
            continue
        fields = line.split()
        if (len(fields) != 20 or fields[2] not in (prefix + "2", prefix + "3")
                or not all(re.fullmatch(r"[01]{%d}" % width, fields[index])
                           for index, width in ((5, 3), (6, 3), (7, 4)))):
            raise ValueError("FIXED_MEASUREMENT_RECORD_REQUIRED")
        key = "/".join(fields[5:8])
        source = counts.setdefault(fields[2], {})
        source[key] = source.get(key, 0) + 1
        rows.append(line)
    return {"counts": counts, "tail": rows[-16:]}


def selection_wait(clock, proc, phase, predicate, timeout, check, baseline=None):
    """One source-state read per predicate; retain bounded failure evidence."""
    latest = {}
    def ready():
        nonlocal latest
        latest = clock.state()
        return predicate(latest)
    try:
        r.d.wait_for(ready, timeout, check)
    except BaseException:
        def sample(read):
            try:
                return read()
            except Exception as error:
                return {"diagnostic_error": type(error).__name__}
        print("TIME_SELECTION_DIAGNOSTIC", json.dumps({"phase": phase, "sources": latest, "baseline": baseline,
            "client": {clock.prefix + s: sample(lambda: clock.ntpstats(s)) for s in ("2", "3")},
            "raw_measurements": sample(clock.measurements),
            "last_ntpdata": {clock.prefix + s: sample(lambda: clock.ntpdata(s)) for s in ("2", "3")},
            "server": {clock.prefix + s: sample(lambda: t.rpc(proc, "counts", clock.prefix + s)) for s in ("2", "3")}}), flush=True)
        raise


@contextmanager
def client(version, daemon, ctl):
    guard()
    prefix = FAMILIES[0 if version == 4 else 1][2]
    directory = Path(tempfile.mkdtemp(prefix="kc-time-client-", dir="/run"))
    os.chown(directory, 65534, 65534)
    proc = None
    try:
        config = directory / "config"
        config.write_text(f'''server {prefix}2 iburst minpoll 0 maxpoll 0 xleave prefer
server {prefix}3 iburst minpoll 0 maxpoll 0 xleave
minsamples 4
maxsamples 8
port 0
cmdport 0
bindcmdaddress {directory}/command.sock
pidfile {directory}/pid
driftfile {directory}/drift
log rawmeasurements
logdir {directory}
''')
        config.chmod(0o644)
        with (directory / "log").open("wb") as log:
            args = no_clock_args(daemon, version, config)
            proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=log, stderr=log, env=ENV)
            r.d.wait_for(lambda: (directory / "command.sock").exists() or proc.poll() is not None, 5)
            value = Client(proc, directory, ctl, prefix)
            value.check()
            yield value
    except BaseException:
        if (directory / "log").exists():
            print((directory / "log").read_text(errors="replace")[-5000:], file=sys.stderr)
        raise
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
        shutil.rmtree(directory)


def empty():
    assert {x["ifname"] for x in json.loads(t.run(t.IP, "-j", "link").stdout)} == {"lo"}
    assert all("metainfo" in x for x in json.loads(t.run(t.NFT, "-j", "list", "ruleset").stdout)["nftables"])


def kernel():
    guard()
    r.guard()
    empty()
    daemon, ctl = binaries()
    identity = t.run(str(daemon), "-v")
    print("CHRONY", (identity.stdout + identity.stderr).decode().strip(), "KERNEL", os.uname().release, flush=True)
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
        timestamp_control()
        for _, _, prefix in FAMILIES:
            for suffix in ("2", "3", "9"):
                probe(prefix + suffix)
            assert all(t.reaches(prefix + "2", port) for port in (22, 123, 443))
        print("PASS TIME_UNFILTERED_ALL_SOURCES_AND_TRANSPORT_CONTROLS", flush=True)
        t.nft(policy())
        maintenance = r.shape(KEY)
        t.nft(r.replacement(KEY, "qualification"))
        candidate = r.shape(KEY)
        t.nft(r.replacement(KEY, "maintenance"))
        assert maintenance != candidate and r.shape(KEY) == maintenance
        for version, _, prefix in FAMILIES:
            with ExitStack() as stack:
                admin = stack.enter_context(t.connect(prefix + "2", 22))
                clock = stack.enter_context(client(version, daemon, ctl))
                def check():
                    clock.check()
                    assert t.exchange(admin)
                r.d.wait_for(lambda: clock.selected("2"), 20, check)
                print(f"PASS IPv{version}_CHRONY_PRIMARY_SELECTED_NO_CLOCK_CAPABILITIES", flush=True)
                with r.armed(KEY, maintenance, candidate) as (path, _):
                    r.invoke_controller(path, KEY, "after")
                    assert r.shape(KEY) == candidate
                    old = stack.enter_context(t.connect(prefix + "2", 443))
                    assert t.exchange(old)
                    before = clock.ntpstats("2")["Total good RX"]
                    selection_wait(clock, proc, "post-controller-sample", lambda state:
                        clock.ntpstats("2")["Total good RX"] > before and state[prefix + "2"]["state"] == "*"
                        and state[prefix + "2"]["reach"] > 0, 3, check, baseline={prefix + "2": {"Total good RX": before}})
                    assert not (path / "result").exists()
                    print(f"PASS IPv{version}_CHRONY_FRESH_SAMPLES_AFTER_CONTROLLER_SIGKILL", flush=True)
                    r.d.wait_for(lambda: (path / "result").exists(), 10, check)
                    assert (path / "result").read_text() == "RESTORE_MAINTENANCE"
                assert r.shape(KEY) == maintenance and not t.exchange(old)
                assert not t.reaches(prefix + "2", 443) and t.reaches(prefix + "2", 22)
                before = clock.ntpstats("2")["Total good RX"]
                selection_wait(clock, proc, "post-restore-samples", lambda state:
                    clock.ntpstats("2")["Total good RX"] >= before + 2 and state[prefix + "2"]["state"] == "*"
                    and state[prefix + "2"]["reach"] > 0, 5, check, baseline={prefix + "2": {"Total good RX": before}})
                print(f"PASS IPv{version}_CHRONY_SAME_CLIENT_POST_RESTORE_SAMPLES_AND_DENIAL", flush=True)
                for mode in ("silent", "origin"):
                    # Selection can reuse retained samples. Require fresh good
                    # measurements from BOTH sources before each fault phase.
                    baseline = {prefix + s: clock.ntpstats(s) for s in ("2", "3")}
                    clock.prepare_samples()
                    def primed(state):
                        current = {prefix + s: clock.ntpstats(s) for s in ("2", "3")}
                        return fresh_sources(baseline, current, state, prefix + "2") and clock.sampling_idle()
                    selection_wait(clock, proc, mode + "-prime", primed, 12, check, baseline=baseline)
                    interleaved = {prefix + s: clock.ntpdata(s)["Interleaved"] for s in ("2", "3")}
                    assert set(interleaved.values()) == {"Yes"}, "KERNEL_TX_INTERLEAVED_PEERS_REQUIRED"
                    server_stamps = {prefix + s: t.rpc(proc, "timestamping", prefix + s) for s in ("2", "3")}
                    assert all(x["NTP kernel TX timestamps"] > 0 and x["NTP kernel RX timestamps"] > 0
                               for x in server_stamps.values()), "REAL_SERVER_KERNEL_TIMESTAMPS_REQUIRED"
                    print("TIME_INTERLEAVED_PEERS", version, mode, json.dumps({"client": interleaved,
                          "server": server_stamps}), flush=True)
                    print("TIME_FRESH_PHASE", version, mode, json.dumps({"before": baseline,
                          "after": {prefix + s: clock.ntpstats(s) for s in ("2", "3")}, "sources": clock.state(),
                          "raw_measurements": clock.measurements(), "acquisition": "one-burst-4/16-per-source",
                          "burst_finished": clock.sampling_idle()}), flush=True)
                    before = t.rpc(proc, "mode", prefix + "2", mode)
                    selection_wait(clock, proc, mode + "-failover", lambda state:
                        state[prefix + "3"]["state"] == "*" and state[prefix + "3"]["reach"] > 0
                        and state[prefix + "2"]["reach"] == 0, 35, check)
                    after = t.rpc(proc, "counts", prefix + "2")
                    assert after["requests"] > before["requests"]
                    if mode == "origin":
                        assert after["bad"] > before["bad"]
                        rejected = clock.ntpstats("2")
                        r.d.wait_for(lambda: clock.ntpstats("2")["Total RX"] >= rejected["Total RX"] + 2, 5, check)
                        current = clock.ntpstats("2")
                        assert current["Total valid RX"] == rejected["Total valid RX"]
                        assert current["Total good RX"] == rejected["Total good RX"]
                    else:
                        assert after["responses"] == before["responses"]
                    print(f"PASS IPv{version}_CHRONY_{mode.upper()}_PRIMARY_ALTERNATE_SELECTED", flush=True)
                    assert t.rpc(proc, "mode", prefix + "2", "good")
                    selection_wait(clock, proc, mode + "-return", lambda state:
                        state[prefix + "2"]["state"] == "*" and state[prefix + "2"]["reach"] > 0, 20, check)
                before = raw.counters("inet", TABLE)["inet_output_deny"]
                denied = t.rpc(proc, "counts", prefix + "9")
                probe(prefix + "9", success=False)
                assert not t.reaches(prefix + "2", 123)
                assert t.rpc(proc, "counts", prefix + "9") == denied
                assert raw.counters("inet", TABLE)["inet_output_deny"] > before
                assert r.shape(KEY) == maintenance and not t.exchange(old)
                check()
                print(f"PASS IPv{version}_CHRONY_PRIMARY_RETURN_UNAPPROVED_SOURCE_TRANSPORT_DENIED", flush=True)
        print("PASS TIME_BOTH_CLIENTS_REAPED_PRIVATE_FILES_REMOVED", flush=True)
    finally:
        proc.stdin.close()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
        proc.stdout.close()
        t.run(t.IP, "link", "del", "host0", success=False)
        t.run(t.IP, "link", "del", "peer0", success=False)
        for family, name in (("inet", TABLE), ("netdev", LINK)):
            t.nft(f"delete table {family} {name}\n", success=False)
        empty()
        assert proc.returncode == 0, "TIME_PEER_OR_SERVER_CLEANUP_FAILED"
    print("PASS TIME_PEER_LINKS_AND_RULES_CLEANED", flush=True)
    print("RESULT SYNTHETIC_TIME_RECOVERY_OK_NO_CLOCK_OR_LIVE_APPLY", flush=True)


class Tests(unittest.TestCase):
    def test_real_peers_have_fixed_scope_no_upstream_and_no_clock_privileges(self):
        for address in ("192.0.2.2", "2001:db8:1::3"):
            config = server_config(address, Path("/private"))
            self.assertIn("bindaddress " + address + "\n", config)
            self.assertIn("local stratum 1\n", config)
            for bad in ("server ", "pool ", "makestep", "rtcsync", "maxdelaydevratio", "noclientlog"):
                self.assertNotIn(bad, config)
        with self.assertRaises(ValueError):
            server_config("8.8.8.8", Path("/private"))
        args = no_clock_args(Path("/chronyd"), 4, Path("/config"))
        for expected in ("-x", "-U", "--bounding-set=-all", "--no-new-privs", "--reuid=65534"):
            self.assertIn(expected, args)

    def test_bounded_burst_targets_only_fixed_sources_and_rejects_failure(self):
        for prefix in ("192.0.2.", "2001:db8:1::"):
            clock = Client(Mock(), Path("/private"), Path("/chronyc"), prefix)
            with patch.object(clock, "check"), patch.object(t, "run", return_value=Mock(stdout=b"200 OK\n")) as run:
                clock.prepare_samples()
                self.assertEqual([call.args[-3:] for call in run.call_args_list],
                                 [("burst", "4/16", prefix + "2"), ("burst", "4/16", prefix + "3")])
            with patch.object(clock, "check"), patch.object(t, "run", return_value=Mock(stdout=b"501 Not authorised\n")):
                with self.assertRaisesRegex(AssertionError, "BURST_REQUEST_REJECTED"):
                    clock.prepare_samples()

    def test_fault_phase_requires_burst_finished_not_just_good_count(self):
        idle = "200 OK\n2 sources online\n0 sources doing burst (return to online)\n0 sources doing burst (return to offline)\n"
        self.assertTrue(burst_idle(idle))
        self.assertFalse(burst_idle(idle.replace("0 sources doing burst (return to online)", "1 sources doing burst (return to online)")))
        for text in ("", idle + "0 sources doing burst (return to online)\n", "x" * 4097):
            with self.assertRaises(ValueError):
                burst_idle(text)

    def test_kernel_receive_time_excludes_delayed_userspace_processing(self):
        request = bytes([0x23]) + bytes(39) + stamp(1700000000.0)
        sock = Mock()
        sock.recvmsg.return_value = (request, [(socket.SOL_SOCKET, RX_TIMESTAMP,
            struct.pack("=qq", 1700000000, 100000000))], 0, ("192.0.2.1", 12345))
        with patch.object(time, "time", return_value=1700000000.6):
            data, _, received = received_packet(sock)
            response = reply(data, "good", received)
        self.assertEqual(response[32:40], stamp(1700000000.1))
        self.assertEqual(response[40:48], stamp(1700000000.6))
        # The 0.5s dequeue delay is now T3-T2, subtracted from NTP RTT.
        self.assertAlmostEqual(1700000000.6 - received, 0.5)

    def test_receive_timestamp_missing_duplicate_malformed_or_truncated_rejected(self):
        good = (socket.SOL_SOCKET, RX_TIMESTAMP, struct.pack("=qq", 1700000000, 0))
        sock = Mock()
        for controls, flags in (([], 0), ([good, good], 0), ([good], socket.MSG_TRUNC),
                ([good], socket.MSG_CTRUNC), ([(socket.SOL_SOCKET, RX_TIMESTAMP, b"short")], 0),
                ([(socket.SOL_SOCKET, RX_TIMESTAMP, struct.pack("=qq", 1, 1000000000))], 0),
                ([(socket.SOL_SOCKET, RX_TIMESTAMP, struct.pack("=qq", -1, 0))], 0)):
            with self.subTest(controls=controls, flags=flags):
                sock.recvmsg.return_value = (bytes(48), controls, flags, ("192.0.2.1", 1))
                with self.assertRaises(ValueError):
                    received_packet(sock)

    def test_probe_accepts_only_expected_denial_and_requires_positive_reply(self):
        with patch.object(socket, "socket") as factory:
            sock = factory.return_value.__enter__.return_value
            sock.sendto.side_effect = PermissionError(errno.EPERM, "denied")
            probe("192.0.2.9", success=False)
            sock.recvfrom.assert_not_called()
            with self.assertRaises(PermissionError):
                probe("192.0.2.2")
            sock.sendto.side_effect = OSError(errno.ENETUNREACH, "no route")
            with self.assertRaises(OSError):
                probe("192.0.2.9", success=False)
            sock.sendto.side_effect = None
            sock.recvfrom.side_effect = socket.timeout()
            probe("192.0.2.9", success=False)
            with self.assertRaises(AssertionError):
                probe("192.0.2.2")
            sock.recvfrom.side_effect = None
            sock.recvfrom.return_value = (bytes(48), ("192.0.2.9", 123))
            with self.assertRaises(AssertionError):
                probe("192.0.2.9", success=False)

    def test_host_namespace_refused_before_commands(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), patch.object(os, "geteuid", return_value=0), patch.object(os, "readlink", return_value="same"), patch.object(t, "run") as command:
            with self.assertRaises(RuntimeError):
                kernel()
            command.assert_not_called()

    def test_opt_in_required_before_commands(self):
        with patch.object(t, "guard"), patch.dict(os.environ, {"KC_TIME_CI": "0"}), patch.object(t, "run") as command:
            with self.assertRaisesRegex(RuntimeError, "TIME_CI_OPT_IN_REQUIRED"):
                kernel()
            command.assert_not_called()

    def test_ntp_timestamp_origin_and_bounded_packet(self):
        data = bytes([0x23]) + bytes(39) + stamp(1700000000.25)
        with patch.object(time, "time", return_value=1700000000.5):
            result = reply(data, "good", 1700000000.4)
        self.assertEqual(len(result), 48)
        self.assertEqual(result[24:32], data[40:48])
        self.assertEqual(result[40:48], stamp(1700000000.5))
        self.assertEqual(reply(data, "origin", 1700000000.4)[24:32], bytes(8))
        self.assertIsNone(reply(data, "silent", 1700000000.4))
        for bad in (b"", data + b"x", bytes(48), bytes([0x24]) + data[1:]):
            with self.assertRaises(ValueError):
                reply(bad, "good", 0)

    def test_source_report_requires_exact_peers_and_octal_reach(self):
        text = "MS Name/IP address\n^* 192.0.2.2 1 0 377 0 +1us\n^- 192.0.2.3 1 0 7 0 +2us\n"
        self.assertEqual(sources(text, "192.0.2.")["192.0.2.2"], {"state": "*", "reach": 255, "poll": 0})
        for bad in ("", text.replace("192.0.2.3", "192.0.2.9"), text + text):
            with self.assertRaises(AssertionError):
                sources(bad, "192.0.2.")

    def test_selection_with_old_samples_does_not_satisfy_fresh_phase(self):
        state = {"primary": {"state": "*", "reach": 255}, "alternate": {"state": "+", "reach": 255}}
        before = {ip: {"Total good RX": 10} for ip in state}
        for primary, alternate, expected in ((10, 10, False), (14, 10, False), (10, 14, False), (14, 14, True)):
            after = {"primary": {"Total good RX": primary}, "alternate": {"Total good RX": alternate}}
            self.assertEqual(fresh_sources(before, after, state, "primary"), expected)
        state["alternate"]["reach"] = 0
        self.assertFalse(fresh_sources(before, after, state, "primary"))

    def test_preparation_failure_retains_baseline_and_last_ntpdata(self):
        clock = Mock(prefix="192.0.2.")
        clock.ntpstats.return_value = {"Total good RX": 13}
        clock.ntpdata.return_value = {"NTP tests": "111 111 1111", "Total good RX": "13"}
        clock.measurements.return_value = {"counts": {"192.0.2.2": {"111/111/1101": 8}}, "tail": []}
        baseline = {"192.0.2.2": {"Total good RX": 10}}
        for error in (None, RuntimeError("diagnostic-read-failed")):
            clock.ntpdata.side_effect = error
            with patch.object(r.d, "wait_for", side_effect=RuntimeError("original-deadline")), patch.object(t, "rpc", return_value={}), patch("builtins.print") as output:
                with self.assertRaisesRegex(RuntimeError, "original-deadline"):
                    selection_wait(clock, None, "origin-prime", lambda _: False, 12, lambda: None, baseline)
                diagnostic = json.loads(output.call_args.args[1])
            self.assertEqual(diagnostic["baseline"], baseline)
            self.assertEqual(diagnostic["raw_measurements"], clock.measurements.return_value)
            self.assertEqual(diagnostic["last_ntpdata"]["192.0.2.2"],
                {"diagnostic_error": "RuntimeError"} if error else clock.ntpdata.return_value)

    def test_raw_measurements_keep_rejection_groups_and_reject_unknown_rows(self):
        row = "2026-10-04 09:00:00 192.0.2.2 N 1 111 111 1101 0 0 1.0 1e-6 2e-4 1e-6 0 0.01 54455354 4B K K"
        text = row + "\n" + row.replace("1101", "1111") + "\n" + row.replace("111 111 1101", "101 000 0000")
        result = measurement_summary(text, "192.0.2.")
        self.assertEqual(result["counts"], {"192.0.2.2": {"111/111/1101": 1, "111/111/1111": 1, "101/000/0000": 1}})
        self.assertEqual(len(result["tail"]), 3)
        for bad in (row.replace("192.0.2.2", "192.0.2.9"), row + " unexpected", "x" * 262145):
            with self.assertRaises(ValueError):
                measurement_summary(bad, "192.0.2.")


if __name__ == "__main__":
    if sys.argv[1:] == ["--systemd"]:
        kernel()
    elif sys.argv[1:] == ["--peer"]:
        peer()
    else:
        unittest.main(verbosity=2)
