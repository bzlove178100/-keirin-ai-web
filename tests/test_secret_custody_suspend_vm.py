"""Opt-in diskless QEMU guest qualification; no host power/network changes.

This first VM slice qualifies actual guest S3, clock observation and a fresh boot.
It deliberately contains no nft policy or worker and cannot qualify packet expiry.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import select
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parent
QEMU = "/usr/bin/qemu-system-x86_64"
SUSPEND_SECONDS = 12


def guard():
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("KC_SUSPEND_VM_CI") != "1":
        raise RuntimeError("DISPOSABLE_VM_CI_OPT_IN_REQUIRED")
    if os.geteuid() == 0 or platform.machine() != "x86_64":
        raise RuntimeError("UNPRIVILEGED_X86_VM_SUPERVISOR_REQUIRED")


def initramfs(init):
    """A newc archive with static /init and the initial console only."""
    result = bytearray()
    for name, content, mode, major, minor in (
            ("dev", b"", stat.S_IFDIR | 0o755, 0, 0),
            ("dev/console", b"", stat.S_IFCHR | 0o600, 5, 1),
            ("init", init, stat.S_IFREG | 0o755, 0, 0),
            ("TRAILER!!!", b"", 0, 0, 0)):
        fields = [1, mode, 0, 0, 1, 0, len(content), 0, 0, major, minor, len(name) + 1, 0]
        result.extend(("070701" + "".join(f"{v:08x}" for v in fields)).encode())
        result.extend(name.encode() + b"\0")
        result.extend(b"\0" * (-len(result) % 4))
        result.extend(content)
        result.extend(b"\0" * (-len(result) % 4))
    return bytes(result)


def command(path):
    # All arguments are fixed, private-directory outputs or read-only guest input.
    return [QEMU, "-no-user-config", "-nodefaults", "-machine", "pc,accel=tcg", "-cpu", "qemu64",
            "-m", "256M", "-smp", "1", "-display", "none", "-monitor", "none", "-nic", "none",
            "-sandbox", "on,obsolete=deny,elevateprivileges=deny,spawn=deny,resourcecontrol=deny",
            "-kernel", str(path / "vmlinuz"), "-initrd", str(path / "initramfs"),
            "-append", "console=ttyS0 rdinit=/init panic=-1 quiet kc_vm_probe=1 end=1",
            "-serial", f"unix:{path / 'serial'},server=on,wait=off",
            "-qmp", f"unix:{path / 'qmp'},server=on,wait=off"]


class Lines:
    def __init__(self, conn):
        self.conn, self.buffer = conn, b""

    def line(self, deadline):
        while b"\n" not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.conn], [], [], remaining)[0]:
                raise RuntimeError("VM_OBSERVATION_DEADLINE")
            data = self.conn.recv(8192)
            if not data:
                raise RuntimeError("VM_CHANNEL_CLOSED")
            self.buffer += data
            if len(self.buffer) > 65536:
                raise RuntimeError("VM_LINE_BOUND")
        value, self.buffer = self.buffer.split(b"\n", 1)
        return value.decode("utf-8", errors="strict").strip()


class QMP:
    def __init__(self, conn):
        self.conn, self.lines, self.events, self.number = conn, Lines(conn), [], 0
        if "QMP" not in json.loads(self.lines.line(time.monotonic() + 5)):
            raise RuntimeError("QMP_GREETING_REQUIRED")
        self.call("qmp_capabilities")

    def read(self, deadline):
        value = json.loads(self.lines.line(deadline))
        if "event" in value:
            self.events.append(value)
            if len(self.events) > 128:
                raise RuntimeError("QMP_EVENT_BOUND")
        return value

    def call(self, name):
        if name not in ("qmp_capabilities", "query-status", "query-current-machine", "query-block", "system_wakeup"):
            raise ValueError("FIXED_QMP_COMMAND_REQUIRED")
        self.number += 1
        self.conn.sendall(json.dumps({"execute": name, "id": self.number}).encode() + b"\n")
        deadline = time.monotonic() + 5
        while True:
            value = self.read(deadline)
            if value.get("id") == self.number:
                if "return" not in value:
                    raise RuntimeError("QMP_COMMAND_FAILED: " + json.dumps(value))
                return value["return"]

    def event(self, name, deadline):
        while True:
            for value in self.events:
                if value.get("event") == name:
                    self.events.remove(value)
                    return value
            self.read(deadline)


def connect(path, process):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("QEMU_EXITED_BEFORE_CHANNEL")
        conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            conn.connect(str(path))
            return conn
        except (FileNotFoundError, ConnectionRefusedError):
            conn.close()
            time.sleep(0.05)
    raise RuntimeError("QEMU_CHANNEL_DEADLINE")


def record(lines, event, seconds=90):
    deadline = time.monotonic() + seconds
    while True:
        line = lines.line(deadline)
        if line.startswith("VM_FAIL") or "Kernel panic" in line:
            raise RuntimeError(line)
        if line.startswith("VM_RECORD "):
            value = json.loads(line[len("VM_RECORD "):])
            if value.get("event") != event or value.get("only_loopback") is not True:
                raise RuntimeError("VM_RECORD_SEQUENCE_OR_ISOLATION")
            if str(uuid.UUID(value["boot"])) != value["boot"]:
                raise RuntimeError("VM_BOOT_ID_REQUIRED")
            for key in ("monotonic", "boottime"):
                if type(value.get(key)) not in (int, float) or not math.isfinite(value[key]) or value[key] < 0:
                    raise RuntimeError("VM_FINITE_CLOCK_REQUIRED")
            if type(value.get("marker")) is not int or value["marker"] not in (0, 1):
                raise RuntimeError("VM_MARKER_REQUIRED")
            print(line, flush=True)
            return value


def suspend_delta(before, after, host_elapsed):
    mono = after["monotonic"] - before["monotonic"]
    boot = after["boottime"] - before["boottime"]
    # A QMP pause, fake offset, unsupported S3 or missed clock injection must fail.
    if (before["boot"] != after["boot"] or before["marker"] != 1 or after["marker"] != 1
            or not 0 <= mono < 5 or not 10 <= boot - mono <= host_elapsed + 5):
        raise RuntimeError("REAL_SUSPEND_CLOCK_DELTA_REQUIRED")
    return {"monotonic_elapsed": mono, "boottime_elapsed": boot, "host_elapsed": host_elapsed}


def run_vm():
    guard()
    host_boot = Path("/proc/sys/kernel/random/boot_id").read_text()
    host_ns = os.readlink("/proc/self/ns/net")
    process = None
    with tempfile.TemporaryDirectory(prefix="kc-suspend-vm-") as value:
        path = Path(value)
        # Read the already-installed CI kernel. Never install a host kernel/service.
        source = Path("/boot") / ("vmlinuz-" + os.uname().release)
        if not source.is_file() or not stat.S_ISREG(source.stat().st_mode):
            raise RuntimeError("INSTALLED_CI_KERNEL_REQUIRED")
        data = subprocess.run(["sudo", "-n", "/usr/bin/cat", str(source)], check=True, capture_output=True, timeout=10).stdout
        if not 1024 * 1024 <= len(data) <= 64 * 1024 * 1024:
            raise RuntimeError("KERNEL_SIZE_BOUND")
        (path / "vmlinuz").write_bytes(data)
        subprocess.run(["/usr/bin/gcc", "-static", "-O2", "-Wall", "-Wextra", "-Werror", "-o", str(path / "init"),
                        str(HERE / "fixtures/secret_custody_suspend_guest.c")], check=True, timeout=30)
        refused = subprocess.run([str(path / "init")], capture_output=True, timeout=5)
        if refused.returncode != 2 or refused.stderr != b"VM_GUEST_PID1_REQUIRED\n":
            raise RuntimeError("GUEST_BINARY_HOST_REFUSAL_REQUIRED")
        print("PASS VM_GUEST_BINARY_REFUSES_HOST_EXECUTION", flush=True)
        (path / "initramfs").write_bytes(initramfs((path / "init").read_bytes()))
        provenance = {"kernel_release": os.uname().release,
                      "kernel_sha256": hashlib.sha256(data).hexdigest(),
                      "initramfs_sha256": hashlib.sha256((path / "initramfs").read_bytes()).hexdigest(),
                      "qemu_sha256": hashlib.sha256(Path(QEMU).read_bytes()).hexdigest(),
                      "qemu_version": subprocess.run([QEMU, "--version"], capture_output=True, check=True, text=True, timeout=5).stdout.splitlines()[0]}
        print("VM_PROVENANCE", json.dumps(provenance), flush=True)
        try:
            with (path / "stderr").open("wb") as err:
                process = subprocess.Popen(command(path), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                           stderr=err, cwd=path, env={"PATH": "/usr/bin:/bin", "LANG": "C"})
                with connect(path / "qmp", process) as monitor, connect(path / "serial", process) as serial:
                    qmp, lines = QMP(monitor), Lines(serial)
                    if qmp.call("query-block") != [] or qmp.call("query-current-machine").get("wakeup-suspend-support") is not True:
                        raise RuntimeError("DISKLESS_WAKEUP_MACHINE_REQUIRED")
                    first = record(lines, "boot")
                    if first["marker"] != 0 or first["boot"] == host_boot.strip():
                        raise RuntimeError("DISTINCT_FRESH_GUEST_BOOT_REQUIRED")
                    print("PASS VM_DISKLESS_UNPRIVILEGED_BOOT_ONLY_LOOPBACK", flush=True)
                    serial.sendall(b"s\n")
                    before = record(lines, "before_suspend", 10)
                    if before["boot"] != first["boot"]:
                        raise RuntimeError("SAME_GUEST_BOOT_REQUIRED")
                    qmp.event("SUSPEND", time.monotonic() + 20)
                    if qmp.call("query-status").get("status") != "suspended":
                        raise RuntimeError("ACPI_SUSPENDED_STATE_REQUIRED")
                    started = time.monotonic()
                    print("PASS VM_REAL_ACPI_S3_SUSPEND_OBSERVED", flush=True)
                    time.sleep(SUSPEND_SECONDS)
                    qmp.call("system_wakeup")
                    qmp.event("WAKEUP", time.monotonic() + 10)
                    after = record(lines, "after_suspend", 20)
                    print("PASS VM_BOOTTIME_COUNTS_SUSPEND", json.dumps(suspend_delta(before, after, time.monotonic() - started)), flush=True)
                    if qmp.call("query-status").get("status") != "running":
                        raise RuntimeError("RESUMED_GUEST_REQUIRED")
                    qmp.events = [event for event in qmp.events if event.get("event") != "RESET"]
                    serial.sendall(b"r\n")
                    rebooting = record(lines, "before_reboot", 10)
                    if rebooting["boot"] != first["boot"] or rebooting["marker"] != 1:
                        raise RuntimeError("REBOOT_MARKER_REQUIRED")
                    reset = qmp.event("RESET", time.monotonic() + 20)
                    if reset.get("data", {}).get("guest") is not True:
                        raise RuntimeError("GUEST_INITIATED_REBOOT_REQUIRED")
                    second = record(lines, "boot")
                    if second["boot"] in (first["boot"], host_boot.strip()) or second["marker"] != 0:
                        raise RuntimeError("NEW_BOOT_AND_FRESH_RUN_REQUIRED")
                    print("PASS VM_GUEST_REBOOT_NEW_BOOT_ID_FRESH_RUN", flush=True)
        except Exception:
            print((path / "stderr").read_text(errors="replace")[-4000:], flush=True)
            raise
        finally:
            if process is not None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
    if path.exists() or (process is not None and Path(f"/proc/{process.pid}").exists()):
        raise RuntimeError("VM_OWNED_CLEANUP_REQUIRED")
    if Path("/proc/sys/kernel/random/boot_id").read_text() != host_boot or os.readlink("/proc/self/ns/net") != host_ns:
        raise RuntimeError("HOST_CONTEXT_CHANGED")
    print("PASS VM_PROCESS_CHANNELS_IMAGES_CLEANED_HOST_CONTEXT_UNCHANGED", flush=True)
    print("RESULT DISPOSABLE_GUEST_SUSPEND_BOOT_ONLY_NO_PACKET_QUALIFICATION_NO_LIVE_APPLY", flush=True)


class Tests(unittest.TestCase):
    def test_opt_in_and_unprivileged_gate_precede_commands(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "KC_SUSPEND_VM_CI": "0"}), patch.object(subprocess, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "OPT_IN"):
                run_vm()
            run.assert_not_called()
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "KC_SUSPEND_VM_CI": "1"}), patch.object(os, "geteuid", return_value=0):
            with self.assertRaisesRegex(RuntimeError, "UNPRIVILEGED"):
                guard()

    def test_supervisor_cannot_attach_network_disk_or_issue_host_power_command(self):
        args = command(Path("/tmp/owned"))
        self.assertEqual(args[args.index("-nic") + 1], "none")
        self.assertEqual(args[args.index("-machine") + 1], "pc,accel=tcg")
        for forbidden in ("-drive", "-blockdev", "-netdev", "-fsdev", "-virtfs", "-device", "-enable-kvm", "-readconfig"):
            self.assertNotIn(forbidden, args)
        for required in ("-nodefaults", "-no-user-config", "-sandbox"):
            self.assertIn(required, args)
        with self.assertRaisesRegex(ValueError, "FIXED_QMP"):
            QMP.call(object(), "system_reset")

    def test_cpio_contains_only_init_and_required_console(self):
        archive = initramfs(b"guest")
        offset, names = 0, []
        while offset < len(archive):
            self.assertEqual(archive[offset:offset + 6], b"070701")
            fields = [int(archive[offset + 6 + i * 8:offset + 14 + i * 8], 16) for i in range(13)]
            name = archive[offset + 110:offset + 110 + fields[11] - 1].decode()
            names.append(name)
            offset = (offset + 110 + fields[11] + 3) & ~3
            content = archive[offset:offset + fields[6]]
            if name == "init":
                self.assertEqual((content, fields[1]), (b"guest", stat.S_IFREG | 0o755))
            offset = (offset + fields[6] + 3) & ~3
        self.assertEqual(names, ["dev", "dev/console", "init", "TRAILER!!!"])

    def test_pause_or_reboot_or_lost_marker_is_not_suspend_proof(self):
        before = {"boot": "one", "monotonic": 10., "boottime": 10., "marker": 1}
        good = {"boot": "one", "monotonic": 11., "boottime": 23., "marker": 1}
        self.assertEqual(suspend_delta(before, good, 13)["boottime_elapsed"], 13)
        for bad in (dict(good, boottime=11), dict(good, monotonic=23), dict(good, boot="two"), dict(good, marker=0), dict(good, boottime=1000)):
            with self.assertRaisesRegex(RuntimeError, "REAL_SUSPEND"):
                suspend_delta(before, bad, 13)

    def test_closed_channel_and_oversized_line_fail(self):
        for data, message in ((b"", "CHANNEL_CLOSED"), (b"a" * 65537, "LINE_BOUND")):
            conn = Mock()
            conn.recv.return_value = data
            with patch.object(select, "select", return_value=([conn], [], [])):
                with self.assertRaisesRegex(RuntimeError, message):
                    Lines(conn).line(time.monotonic() + 1)

    def test_guest_record_rejects_nonfinite_clock_wrong_event_and_interface(self):
        good = {"event": "boot", "boot": "12345678-1234-1234-1234-123456789abc",
                "monotonic": 1, "boottime": 1, "marker": 0, "only_loopback": True}
        for change in ({"boottime": float("nan")}, {"monotonic": True}, {"event": "after_suspend"},
                       {"only_loopback": False}, {"marker": True}):
            lines = Mock()
            lines.line.return_value = "VM_RECORD " + json.dumps(dict(good, **change))
            with self.assertRaises(RuntimeError):
                record(lines, "boot")


if __name__ == "__main__":
    if sys.argv[1:] == ["--vm"]:
        run_vm()
    else:
        unittest.main(verbosity=2)
