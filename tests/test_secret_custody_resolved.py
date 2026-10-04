"""Real resolved stub/cache/configuration in private CI mount/network/IPC state."""
from contextlib import ExitStack, contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import shutil
import signal
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("dns", Path(__file__).with_name("test_secret_custody_dns.py"))
y = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(y)
r, t = y.r, y.t
DAEMON = "/usr/lib/systemd/systemd-resolved"
BUS_DAEMON = "/usr/bin/dbus-daemon"
BUS = "/run/dbus/system_bus_socket"
NAME, QNAME, TTL = "fixture.test.", b"\x07fixture\x04test\0", 8
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "LC_ALL": "C",
       "SYSTEMD_LOG_LEVEL": "debug", "SYSTEMD_LOG_TARGET": "console"}


def guard():
    t.guard()
    if os.environ.get("KC_RESOLVED_CI") != "1":
        raise RuntimeError("RESOLVED_CI_OPT_IN_REQUIRED")


def private_guard():
    guard()
    if os.readlink("/proc/self/ns/mnt") == os.readlink("/proc/1/ns/mnt"):
        raise RuntimeError("PRIVATE_MOUNT_NAMESPACE_REQUIRED")
    if Path("/run").stat().st_dev == Path("/proc/1/root/run").stat().st_dev:
        raise RuntimeError("PRIVATE_RUNTIME_REQUIRED")
    if Path("/etc/kc-owned").read_text() != "RESOLVED_CI_ONLY\n":
        raise RuntimeError("PRIVATE_CONFIG_REQUIRED")


def question(data):
    if not 17 <= len(data) <= 512:
        raise ValueError("BOUNDED_QUERY_REQUIRED")
    ident, flags, qd, an, ns, ar = struct.unpack("!6H", data[:12])
    end = 12 + len(QNAME) + 4
    if len(data) < end or flags & ~0x130 or (qd, an, ns) != (1, 0, 0) or ar not in (0, 1) or data[12:end-4].lower() != QNAME:
        raise ValueError("FIXED_QUERY_REQUIRED")
    kind, cls = struct.unpack("!HH", data[end-4:end])
    if kind not in (1, 28) or cls != 1:
        raise ValueError("FIXED_TYPE_REQUIRED")
    extra = data[end:]
    if ar:
        if len(extra) < 11 or extra[0] != 0:
            raise ValueError("BOUNDED_OPT_REQUIRED")
        typ, size, version_flags, length = struct.unpack("!HHIH", extra[1:11])
        if typ != 41 or not 512 <= size <= 4096 or version_flags not in (0, 0x8000) or len(extra) != 11 + length:
            raise ValueError("BOUNDED_OPT_REQUIRED")
        pos = 11
        while pos < len(extra):
            if pos + 4 > len(extra):
                raise ValueError("TRUNCATED_OPT_OPTION")
            length = struct.unpack("!H", extra[pos+2:pos+4])[0]
            pos += 4 + length
            if pos > len(extra):
                raise ValueError("TRUNCATED_OPT_OPTION")
    elif extra:
        raise ValueError("TRAILING_QUERY_BYTES")
    return ident, flags, kind, end


def response(data, truncated=False, generation=0):
    ident, flags, kind, end = question(data)
    payload = socket.inet_pton(socket.AF_INET if kind == 1 else socket.AF_INET6, y.answer_address(kind, generation))
    header = struct.pack("!6H", ident, 0x8080 | (flags & 0x100) | (0x200 if truncated else 0), 1, 0 if truncated else 1, 0, 0)
    answer = b"" if truncated else b"\xc0\x0c" + struct.pack("!HHIH", kind, 1, TTL, len(payload)) + payload
    return header + data[12:end] + answer


class Server(y.Server):
    def reply(self, data, transport):
        _, _, kind, _ = question(data)
        with self.lock:
            if len(self.events) >= 256:
                raise RuntimeError("DNS_EVENT_BOUND")
            self.events.append([transport, kind, self.mode, self.generation])
            return response(data, self.mode == "truncate" and transport == "udp", self.generation)


def peer():
    guard()
    assert os.readlink("/proc/self/ns/net") != os.environ.get("FIXTURE_PARENT_NETNS")
    with ExitStack() as stack:
        servers = {}
        print("READY", flush=True)
        for line in sys.stdin:
            assert len(line) <= 1024
            msg = json.loads(line)
            if msg[0] == "setup":
                t.run(t.IP, "link", "set", "peer0", "addrgenmode", "none")
                t.run("sysctl", "-qw", "net.ipv6.conf.peer0.accept_ra=0")
                t.setup("peer0", t.MAC_PEER, ("2", "3"))
                for _, _, prefix in y.FAMILIES:
                    for suffix in ("2", "3"):
                        servers[prefix + suffix] = Server(stack, prefix + suffix)
                    for port in (22, 443):
                        t.listen(stack, prefix + "2", port)
                result = True
            elif msg[0] == "configure":
                _, address, mode, generation = msg
                assert address in servers and mode in ("answer", "truncate") and generation in (0, 1)
                with servers[address].lock:
                    servers[address].mode, servers[address].generation = mode, generation
                result = True
            elif msg[0] == "events":
                with servers[msg[1]].lock:
                    result = list(servers[msg[1]].events)
            else:
                raise ValueError("FIXED_RPC_REQUIRED")
            assert all(s.error is None for s in servers.values()), "UPSTREAM_SERVER_FAILED"
            print(json.dumps(result), flush=True)


def validate_query(result, generation, kind, success=True):
    assert len(result.stdout) + len(result.stderr) < 4096
    text = result.stdout.decode()
    lines = [line.split() for line in text.splitlines() if line and not line.startswith(";")]
    if success:
        assert result.returncode == 0 and "status: NOERROR" in text and len(lines) == 1, text
        fields = lines[0]
        assert len(fields) == 5 and fields[0].lower() == NAME and fields[1].isdigit(), fields
        assert 0 <= int(fields[1]) <= TTL and fields[2:4] == ["IN", "A" if kind == 1 else "AAAA"]
        assert fields[4] == y.answer_address(kind, generation), fields
    else:
        # A bounded no-response or an explicit SERVFAIL, never NXDOMAIN/empty success.
        assert not lines and ((result.returncode == 9 and "status:" not in text)
                              or (result.returncode == 0 and "status: SERVFAIL" in text)), text


def query(kind=1, generation=0, tcp=False, endpoint="127.0.0.53", success=True):
    guard()
    assert kind in (1, 28) and endpoint in ("127.0.0.53", "192.0.2.2", "192.0.2.3", "2001:db8:1::2", "2001:db8:1::3")
    result = t.run(y.DIG, "-r", "@" + endpoint, NAME, "A" if kind == 1 else "AAAA",
                   "+noedns", "+nocookie", "+noadflag", "+nocdflag", "+recurse", "+nosearch",
                   "+tries=1", "+time=1", "+noall", "+comments", "+answer", "+tcp" if tcp else "+notcp", success=False)
    validate_query(result, generation, kind, success)


def fingerprint(path):
    p = Path(path)
    st = p.stat()
    return (str(p.resolve()), st.st_dev, st.st_ino, hashlib.sha256(p.read_bytes()).hexdigest())


def ensure_directory(path):
    path.mkdir(exist_ok=True)
    assert stat.S_ISDIR(path.lstat().st_mode), "REAL_RUNTIME_DIRECTORY_REQUIRED"


def child():
    private_guard()
    Path("/run/kc-sys").mkdir()
    t.run("mount", "-t", "sysfs", "-o", "nosuid,nodev,noexec", "sysfs", "/run/kc-sys")
    t.run("mount", "--bind", "/run/kc-sys", "/sys")
    t.run("mount", "-o", "remount,bind,ro", "/sys")
    Path("/run/dbus").mkdir()
    ensure_directory(Path("/run/systemd"))
    processes = []
    def stop(*_):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    try:
        bus = subprocess.Popen([BUS_DAEMON, "--nofork", "--nopidfile", "--config-file=/etc/dbus.conf"], env=ENV)
        processes.append(bus)
        r.d.wait_for(lambda: Path(BUS).exists() or bus.poll() is not None, 4)
        assert bus.poll() is None
        daemon = subprocess.Popen([DAEMON], env=ENV)
        processes.append(daemon)
        Path("/run/kc-ready").write_text(json.dumps({"bus": bus.pid, "daemon": daemon.pid}))
        while True:
            assert all(p.poll() is None for p in processes), "PRIVATE_DAEMON_EXITED"
            time.sleep(0.2)
    finally:
        for p in reversed(processes):
            if p.poll() is None:
                p.terminate()
            try:
                p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(timeout=2)


class Resolver:
    def __init__(self, pid, children):
        self.pid, self.children = pid, children
        self.root = Path(f"/proc/{pid}/root")
        self.index = socket.if_nametoindex("host0")

    def check(self):
        assert os.readlink(f"/proc/{self.pid}/ns/net") == os.readlink("/proc/self/ns/net")
        assert os.readlink(f"/proc/{self.pid}/ns/mnt") != os.readlink("/proc/1/ns/mnt")
        assert (self.root / "run").stat().st_dev != Path("/run").stat().st_dev
        assert (self.root / "etc/kc-owned").read_text() == "RESOLVED_CI_ONLY\n"
        assert os.statvfs(self.root / "sys").f_flag & os.ST_RDONLY
        for name, pid in self.children.items():
            assert os.readlink(f"/proc/{pid}/ns/net") == os.readlink(f"/proc/{self.pid}/ns/net")
            assert os.readlink(f"/proc/{pid}/ns/mnt") == os.readlink(f"/proc/{self.pid}/ns/mnt")
            assert os.readlink(f"/proc/{pid}/exe") == (DAEMON if name == "daemon" else BUS_DAEMON)
        host_bus = Path(BUS)
        if host_bus.exists():
            private_bus = self.root / BUS.lstrip("/")
            assert (private_bus.stat().st_dev, private_bus.stat().st_ino) != (host_bus.stat().st_dev, host_bus.stat().st_ino)
        assert (self.root / "etc/resolv.conf").read_text() == "nameserver 127.0.0.53\n"

    def bus(self, *args, success=True):
        self.check()
        return t.run("/usr/bin/nsenter", "--target=" + str(self.pid), "--mount", "--net", "--root", "--wd=/",
                     "/usr/bin/busctl", "--address=unix:path=" + BUS, "--auto-start=no", "--timeout=2", "--json=short",
                     "call", "org.freedesktop.resolve1", "/org/freedesktop/resolve1", *args, success=success)

    def call(self, method, *args):
        return self.bus("org.freedesktop.resolve1.Manager", method, *args)

    def read(self):
        result = self.bus("org.freedesktop.DBus.Properties", "Get", "ss", "org.freedesktop.resolve1.Manager", "DNSEx", success=False)
        if result.returncode:
            return None
        assert len(result.stdout) < 4096
        return json.loads(result.stdout)

    def set_source(self, address):
        assert address in ("192.0.2.2", "192.0.2.3", "2001:db8:1::2", "2001:db8:1::3")
        family = socket.AF_INET6 if ":" in address else socket.AF_INET
        packed = socket.inet_pton(family, address)
        self.call("SetLinkDNS", "ia(iay)", str(self.index), "1", str(family), str(len(packed)), *map(str, packed))
        self.call("SetLinkDomains", "ia(sb)", str(self.index), "1", ".", "true")
        expected = {"type": "v", "data": [{"type": "a(iiayqs)", "data": [[self.index, family, list(packed), 0, ""]]}]}
        r.d.wait_for(lambda: self.read() == expected, 3, self.check)
        self.call("FlushCaches")


@contextmanager
def resolver():
    guard()
    path = Path(tempfile.mkdtemp(prefix="kc-resolved-ci-", dir="/tmp"))
    path.chmod(0o755)
    unit = path.name + ".service"
    children, group = {}, None
    host_conf = fingerprint("/etc/resolv.conf")
    try:
        account = pwd.getpwnam("systemd-resolve")
        etc = path / "etc"
        (etc / "systemd").mkdir(parents=True)
        (etc / "kc-owned").write_text("RESOLVED_CI_ONLY\n")
        (etc / "passwd").write_text(f"root:x:0:0:root:/:/bin/false\nsystemd-resolve:x:{account.pw_uid}:{account.pw_gid}:fixture:/:/bin/false\n")
        (etc / "group").write_text(f"root:x:0:\nsystemd-resolve:x:{account.pw_gid}:\n")
        (etc / "nsswitch.conf").write_text("passwd: files\ngroup: files\nhosts: files dns\n")
        (etc / "machine-id").write_text("f" * 32 + "\n")
        (etc / "resolv.conf").write_text("nameserver 127.0.0.53\n")
        (etc / "hosts").write_text("127.0.0.1 localhost\n::1 localhost\n")
        (etc / "systemd/resolved.conf").write_text('''[Resolve]
DNS=
FallbackDNS=
Domains=
LLMNR=no
MulticastDNS=no
DNSSEC=no
DNSOverTLS=no
Cache=yes
DNSStubListener=yes
ReadEtcHosts=no
''')
        (etc / "dbus.conf").write_text('''<busconfig>
<type>system</type><listen>unix:path=/run/dbus/system_bus_socket</listen><auth>EXTERNAL</auth>
<policy context="default"><allow user="root"/><allow user="systemd-resolve"/><deny own="*"/><deny send_destination="*"/><deny receive_sender="*"/></policy>
<policy user="root"><allow own="*"/><allow send_destination="*"/><allow receive_sender="*"/></policy>
<policy user="systemd-resolve"><allow own="org.freedesktop.resolve1"/><allow send_destination="*"/><allow receive_sender="*"/></policy>
</busconfig>''')
        t.run("/usr/bin/systemd-run", "--quiet", "--unit=" + unit,
              "--property=Type=exec", "--property=Restart=no", "--property=RuntimeMaxSec=150",
              "--property=TimeoutStopSec=5", "--property=KillMode=control-group", "--property=PrivateMounts=yes",
              "--property=ProtectSystem=strict", "--property=NoNewPrivileges=yes",
              "--property=TemporaryFileSystem=/run:mode=0755 /var:mode=0755",
              "--property=BindReadOnlyPaths=" + str(etc) + ":/etc",
              "--property=InaccessiblePaths=-/usr/lib/systemd/resolved.conf.d -/usr/local/lib/systemd/resolved.conf.d",
              "--property=NetworkNamespacePath=/proc/" + str(os.getpid()) + "/ns/net",
              "--setenv=GITHUB_ACTIONS=true", "--setenv=KC_RESOLVED_CI=1",
              sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--daemon")
        pid = int(t.run("/usr/bin/systemctl", "show", unit, "--property=MainPID", "--value").stdout)
        assert pid > 1
        group = t.run("/usr/bin/systemctl", "show", unit, "--property=ControlGroup", "--value").stdout.decode().strip()
        assert group.startswith("/system.slice/kc-resolved-ci-")
        root = Path(f"/proc/{pid}/root")
        r.d.wait_for(lambda: (root / "run/kc-ready").exists(), 5)
        children = json.loads((root / "run/kc-ready").read_text())
        assert set(children) == {"bus", "daemon"} and all(type(v) is int and v > 1 for v in children.values())
        value = Resolver(pid, children)
        r.d.wait_for(lambda: value.read() is not None, 5)
        yield value
    except BaseException:
        log = t.run("/usr/bin/journalctl", "--no-pager", "-u", unit, "-n", "150", success=False)
        print(log.stdout[:4000].decode(errors="replace"), file=sys.stderr)
        print(log.stdout[-9000:].decode(errors="replace"), file=sys.stderr)
        raise
    finally:
        t.run("/usr/bin/systemctl", "stop", unit, success=False)
        t.run("/usr/bin/systemctl", "reset-failed", unit, success=False)
        assert t.run("/usr/bin/systemctl", "show", unit, "--property=MainPID", "--value").stdout == b"0\n"
        if group:
            assert not Path("/sys/fs/cgroup" + group).exists()
        assert all(not Path(f"/proc/{pid}").exists() for pid in children.values())
        assert fingerprint("/etc/resolv.conf") == host_conf
        shutil.rmtree(path)
        assert not path.exists()


def kernel():
    guard()
    r.guard()
    y.empty()
    for binary in (DAEMON, BUS_DAEMON):
        print("CLIENT", binary, hashlib.sha256(Path(binary).read_bytes()).hexdigest(), flush=True)
    print(t.run(DAEMON, "--version").stdout.decode(), "KERNEL", os.uname().release, flush=True)
    proc = subprocess.Popen(["unshare", "--net", sys.executable, "-I", "-B", __file__, "--peer"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            text=True, env=dict(os.environ, FIXTURE_PARENT_NETNS=os.readlink("/proc/self/ns/net")))
    try:
        assert t.read_line(proc).strip() == "READY"
        t.run(t.IP, "link", "add", "host0", "type", "veth", "peer", "name", "peer0")
        t.run(t.IP, "link", "set", "peer0", "netns", str(proc.pid))
        t.run(t.IP, "link", "set", "host0", "addrgenmode", "none")
        t.run("sysctl", "-qw", "net.ipv6.conf.host0.accept_ra=0")
        t.setup("host0", t.MAC_HOST, ("1",))
        t.run(t.IP, "link", "set", "lo", "up")
        assert t.rpc(proc, "setup")
        for _, _, prefix in y.FAMILIES:
            for suffix in ("2", "3"):
                query(endpoint=prefix + suffix)
        print("PASS RESOLVED_UNFILTERED_APPROVED_AND_UNAPPROVED_DNS", flush=True)
        t.nft(y.policy())
        maintenance = r.shape(y.KEY)
        t.nft(r.replacement(y.KEY, "qualification"))
        candidate = r.shape(y.KEY)
        t.nft(r.replacement(y.KEY, "maintenance"))
        for version, _, prefix in y.FAMILIES:
            with ExitStack() as stack:
                admin = stack.enter_context(t.connect(prefix + "2", 22))
                res = stack.enter_context(resolver())
                def check():
                    res.check()
                    assert t.exchange(admin)
                res.set_source(prefix + "2")
                print(f"PASS IPv{version}_RESOLVED_PRIVATE_BUS_CONFIG_AND_SOURCE_READBACK", flush=True)
                assert t.rpc(proc, "configure", prefix + "2", "answer", 0)
                for kind in (1, 28):
                    query(kind)
                before = t.rpc(proc, "events", prefix + "2")
                assert t.rpc(proc, "configure", prefix + "2", "answer", 1)
                for kind in (1, 28):
                    query(kind)
                assert t.rpc(proc, "events", prefix + "2") == before
                until = time.monotonic() + TTL + 1
                r.d.wait_for(lambda: time.monotonic() >= until, TTL + 2, check)
                for kind in (1, 28):
                    query(kind, generation=1)
                after = t.rpc(proc, "events", prefix + "2")
                assert len(after) >= len(before) + 2 and {e[1] for e in after[len(before):]} == {1, 28}
                print(f"PASS IPv{version}_RESOLVED_A_AAAA_WARM_CACHE_AND_REAL_TTL_EXPIRY", flush=True)
                assert t.rpc(proc, "configure", prefix + "2", "truncate", 1)
                res.call("FlushCaches")
                before = len(t.rpc(proc, "events", prefix + "2"))
                for kind in (1, 28):
                    query(kind, generation=1)
                events = t.rpc(proc, "events", prefix + "2")[before:]
                assert all(any(e[:2] == [transport, kind] for e in events) for transport in ("udp", "tcp") for kind in (1, 28)), events
                before_tcp = t.rpc(proc, "events", prefix + "2")
                for kind in (1, 28):
                    query(kind, generation=1, tcp=True)
                assert t.rpc(proc, "events", prefix + "2") == before_tcp
                print(f"PASS IPv{version}_RESOLVED_STUB_TCP_AND_UPSTREAM_TRUNCATION_FALLBACK", flush=True)
                assert t.rpc(proc, "configure", prefix + "2", "answer", 0)
                res.call("FlushCaches")
                with r.armed(y.KEY, maintenance, candidate) as (path, _):
                    r.invoke_controller(path, y.KEY, "after")
                    assert r.shape(y.KEY) == candidate
                    old = stack.enter_context(t.connect(prefix + "2", 443))
                    assert t.exchange(old)
                    before = len(t.rpc(proc, "events", prefix + "2"))
                    query()
                    assert len(t.rpc(proc, "events", prefix + "2")) > before and not (path / "result").exists()
                    print(f"PASS IPv{version}_RESOLVED_FRESH_QUERY_AFTER_CONTROLLER_SIGKILL", flush=True)
                    r.d.wait_for(lambda: (path / "result").exists(), 10, check)
                    assert (path / "result").read_text() == "RESTORE_MAINTENANCE"
                assert r.shape(y.KEY) == maintenance and not t.exchange(old) and not t.reaches(prefix + "2", 443)
                assert t.reaches(prefix + "2", 22)
                res.call("FlushCaches")
                before = len(t.rpc(proc, "events", prefix + "2"))
                for kind in (1, 28):
                    query(kind)
                assert len(t.rpc(proc, "events", prefix + "2")) >= before + 2
                print(f"PASS IPv{version}_RESOLVED_SAME_PROCESS_POST_RESTORE_FRESH_QUERIES", flush=True)
                res.set_source(prefix + "3")
                before = t.rpc(proc, "events", prefix + "3")
                drops = y.counts()["inet_output_deny"]
                query(success=False)
                assert t.rpc(proc, "events", prefix + "3") == before and y.counts()["inet_output_deny"] > drops
                assert r.shape(y.KEY) == maintenance
                print(f"PASS IPv{version}_RESOLVED_CHANGED_UNAPPROVED_SOURCE_DENIED_NO_WIDENING", flush=True)
                res.set_source(prefix + "2")
                for kind in (1, 28):
                    query(kind)
                assert r.shape(y.KEY) == maintenance and not t.exchange(old)
                check()
                print(f"PASS IPv{version}_RESOLVED_APPROVED_SOURCE_RETURN_AND_ADMIN_SURVIVAL", flush=True)
            print(f"PASS IPv{version}_RESOLVED_PROCESSES_CGROUP_PRIVATE_FILES_CLEANED", flush=True)
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
        for family, table in (("inet", y.TABLE), ("netdev", y.LINK)):
            t.nft(f"delete table {family} {table}\n", success=False)
        y.empty()
    print("PASS RESOLVED_PEER_LINKS_AND_RULES_CLEANED", flush=True)
    print("RESULT SYNTHETIC_RESOLVED_CACHE_SWITCH_RECOVERY_OK_NO_LIVE_APPLY", flush=True)


class Tests(unittest.TestCase):
    def test_existing_real_runtime_directory_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime"
            ensure_directory(path)
            ensure_directory(path)
            link = Path(directory) / "link"
            link.symlink_to(path)
            with self.assertRaisesRegex(AssertionError, "REAL_RUNTIME_DIRECTORY_REQUIRED"):
                ensure_directory(link)
            regular = Path(directory) / "file"
            regular.write_text("fixture")
            with self.assertRaises(FileExistsError):
                ensure_directory(regular)

    def test_host_namespace_refused_before_commands(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), patch.object(os, "geteuid", return_value=0), patch.object(os, "readlink", return_value="same"), patch.object(t, "run") as run:
            with self.assertRaises(RuntimeError):
                kernel()
            run.assert_not_called()

    def test_opt_in_required(self):
        with patch.object(t, "guard"), patch.dict(os.environ, {"KC_RESOLVED_CI": "0"}), patch.object(t, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "RESOLVED_CI_OPT_IN_REQUIRED"):
                kernel()
            run.assert_not_called()

    def test_private_mount_and_runtime_required_before_daemons(self):
        with patch(__name__ + ".guard"), patch.object(os, "readlink", return_value="same"), patch.object(subprocess, "Popen") as start:
            with self.assertRaisesRegex(RuntimeError, "PRIVATE_MOUNT_NAMESPACE_REQUIRED"):
                child()
            start.assert_not_called()
        with patch(__name__ + ".guard"), patch.object(os, "readlink", side_effect=["child", "host"]), patch.object(Path, "stat") as st, patch.object(subprocess, "Popen") as start:
            st.return_value.st_dev = 1
            with self.assertRaisesRegex(RuntimeError, "PRIVATE_RUNTIME_REQUIRED"):
                child()
            start.assert_not_called()

    def test_bounded_query_edns_and_positive_ttl(self):
        for kind in (1, 28):
            data = struct.pack("!6H", 1, 0x100, 1, 0, 0, 0) + QNAME + struct.pack("!HH", kind, 1)
            result = response(data)
            self.assertEqual(struct.unpack("!I", result[len(data)+6:len(data)+10])[0], TTL)
            opt = data[:10] + b"\0\1" + data[12:] + b"\0" + struct.pack("!HHIH", 41, 1232, 0, 0)
            self.assertEqual(question(opt)[2], kind)
            self.assertEqual(response(opt), result)
            for bad in (b"", data + b"x", opt[:-1], data.replace(QNAME, b"\x07unknown\x04test\0"), data[:2] + b"\x81\x00" + data[4:]):
                with self.assertRaises(ValueError):
                    question(bad)

    def test_negative_result_never_accepts_empty_success_or_nxdomain(self):
        def result(code, text):
            return subprocess.CompletedProcess([], code, text.encode(), b"")
        validate_query(result(9, ";; no servers could be reached\n"), 0, 1, False)
        validate_query(result(0, ";; ->>HEADER<<- opcode: QUERY, status: SERVFAIL, id: 1\n"), 0, 1, False)
        for bad in (result(0, ""), result(1, ""), result(0, ";; status: NXDOMAIN\n"), result(9, "fixture.test. 1 IN A 198.51.100.60\n")):
            with self.assertRaises(AssertionError):
                validate_query(bad, 0, 1, False)


if __name__ == "__main__":
    if sys.argv[1:] == ["--systemd"]:
        kernel()
    elif sys.argv[1:] == ["--peer"]:
        peer()
    elif sys.argv[1:] == ["--daemon"]:
        child()
    else:
        unittest.main(verbosity=2)
