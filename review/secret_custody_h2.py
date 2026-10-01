#!/usr/bin/env python3
"""H2a: fixed identity/files only. No runtime, network, secret or package actions.

Default inspect and verify are read-only. Apply/rollback need separate operator
authorization; a CLI acknowledgement is an accident guard, not authorization.
Run with the system interpreter: /usr/bin/python3 -I -B <this file>.
"""
import argparse
import grp
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import sys
import uuid

NAME = "keirin-custody"
UNIT_NAME = NAME + ".service"
STATE = "/var/lib/keirin-custody-h2"
RECEIPT = STATE + "/receipt.json"
UNIT_PATH = "/etc/systemd/system/" + UNIT_NAME
APPROVE = "H2_IDENTITY_FILES_V1"
UNDO = "H2_REMOVE_OWNED_FILES_V1"
SCHEMA = "keirin-custody-h2a-v1"
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "LC_ALL": "C"}
UNIT = """[Unit]
Description=Keirin custody H2a disabled placeholder (no runtime payload)
RefuseManualStart=yes

[Service]
Type=oneshot
User=keirin-custody
Group=keirin-custody
ExecStart=/usr/bin/false
Restart=no
NoNewPrivileges=yes
CapabilityBoundingSet=
AmbientCapabilities=
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
PrivateNetwork=yes
RestrictAddressFamilies=AF_UNIX
RestrictNamespaces=yes
RestrictRealtime=yes
RestrictSUIDSGID=yes
LockPersonality=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectKernelLogs=yes
ProtectControlGroups=yes
ProtectClock=yes
ProtectHostname=yes
ProtectProc=invisible
ProcSubset=pid
SystemCallArchitectures=native
UMask=0077
LimitCORE=0
MemoryMax=128M
MemorySwapMax=0
TasksMax=24
CPUQuota=50%
KillMode=control-group
TimeoutStartSec=10s
TimeoutStopSec=10s
StandardOutput=null
StandardError=null
"""
GATES = json.dumps({"schema": SCHEMA, "runtime": False, "provider": False,
                    "prediction": False, "data_fetch": False,
                    "scheduler": False, "report_delivery": False,
                    "credential_binding": False}, sort_keys=True, indent=2) + "\n"
FILES = {"/etc/keirin-custody/gates.json": (GATES.encode(), 0o640),
         UNIT_PATH: (UNIT.encode(), 0o644)}
DIRS = {"/opt/keirin-custody": 0o755, "/etc/keirin-custody": 0o750}
PARENTS = ("/opt", "/etc", "/etc/systemd", "/etc/systemd/system",
           "/var", "/var/lib")


class Stop(Exception):
    """Only fixed, non-sensitive error codes may escape to CLI output."""


def need(condition, code):
    if not condition:
        raise Stop(code)


class Host:
    """Fixed host operations; tests substitute this adapter, never CLI paths."""
    def path(self, path):
        return Path(path)

    def run(self, *args):
        try:
            result = subprocess.run(args, env=ENV, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    timeout=20, check=False)
        except (OSError, subprocess.TimeoutExpired):
            raise Stop("HOST_COMMAND_UNAVAILABLE") from None
        need(result.returncode == 0, "HOST_COMMAND_FAILED")
        need(len(result.stdout) < 65536, "HOST_COMMAND_OUTPUT_TOO_LARGE")
        return result.stdout.decode("utf-8", errors="strict")

    def platform(self):
        need(os.geteuid() == 0, "ROOT_REQUIRED")
        values = {}
        for line in self.path("/etc/os-release").read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep:
                values[key] = value.strip('"')
        need(values.get("ID") == "ubuntu" and values.get("VERSION_ID") == "24.04",
             "UNREVIEWED_OS")
        need(self.path("/proc/1/comm").read_text().strip() == "systemd", "SYSTEMD_PID1_REQUIRED")
        need(self.path("/sys/fs/cgroup/cgroup.controllers").is_file(), "CGROUP_V2_REQUIRED")
        need(len(self.path("/proc/swaps").read_text().splitlines()) == 1, "SWAP_MUST_BE_DISABLED")
        version = self.run("/usr/bin/systemctl", "--version").splitlines()[0]
        need(re.match(r"systemd 255\b", version) is not None, "UNREVIEWED_SYSTEMD")
        for command in ("/usr/sbin/useradd", "/usr/sbin/userdel", "/usr/sbin/groupdel",
                        "/usr/sbin/nologin", "/usr/bin/passwd", "/usr/bin/false", "/usr/bin/systemd-analyze"):
            need(os.path.isfile(command) and os.access(command, os.X_OK), "REQUIRED_COMMAND_MISSING")

    def user(self):
        try:
            p = pwd.getpwnam(NAME)
        except KeyError:
            return None
        # Request only the account status; never read or emit a shadow hash.
        status = self.run("/usr/bin/passwd", "-S", NAME).split()
        locked = len(status) >= 2 and status[0] == NAME and status[1] == "L"
        return {"uid": p.pw_uid, "gid": p.pw_gid, "tag": p.pw_gecos,
                "home": p.pw_dir, "shell": p.pw_shell, "locked": locked,
                "groups": os.getgrouplist(NAME, p.pw_gid)}

    def group(self):
        try:
            g = grp.getgrnam(NAME)
            others = [p.pw_name for p in pwd.getpwall()
                      if p.pw_gid == g.gr_gid and p.pw_name != NAME]
            return {"gid": g.gr_gid, "members": g.gr_mem, "other_primary": others}
        except KeyError:
            return None

    def no_processes(self, uid):
        for entry in self.path("/proc").iterdir():
            if not entry.name.isdecimal():
                continue
            try:
                lines = (entry / "status").read_text().splitlines()
            except FileNotFoundError:
                continue
            for line in lines:
                if line.startswith("Uid:"):
                    need(uid not in [int(x) for x in line.split()[1:]], "IDENTITY_HAS_PROCESSES")

    def unit(self):
        output = self.run("/usr/bin/systemctl", "show", UNIT_NAME,
                          "--property=LoadState,ActiveState,UnitFileState,FragmentPath,DropInPaths,RefuseManualStart")
        return dict(line.split("=", 1) for line in output.splitlines() if "=" in line)

    def create_user(self, tag):
        self.run("/usr/sbin/useradd", "--system", "--user-group", "--no-create-home",
                 "--home-dir", "/nonexistent", "--shell", "/usr/sbin/nologin",
                 "--no-log-init", "--password", "!", "--key", "CREATE_MAIL_SPOOL=no",
                 "--comment", tag, NAME)

    def remove_user(self):
        self.run("/usr/sbin/userdel", NAME)

    def remove_group(self):
        self.run("/usr/sbin/groupdel", NAME)

    def reload(self):
        self.run("/usr/bin/systemctl", "daemon-reload")

    def syntax(self):
        self.run("/usr/bin/systemd-analyze", "verify", UNIT_PATH)


class Package:
    def __init__(self, host):
        self.h = host

    def absent(self, path):
        return not os.path.lexists(self.h.path(path))

    def metadata(self, path, mode, gid=0, directory=False):
        s = self.h.path(path).lstat()
        kind = stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode)
        need(kind and s.st_uid == 0 and s.st_gid == gid
             and stat.S_IMODE(s.st_mode) == mode, "ARTIFACT_METADATA_DRIFT")
        if not directory:
            need(s.st_nlink == 1, "ARTIFACT_LINK_DRIFT")

    def parents(self):
        for path in PARENTS:
            s = self.h.path(path).lstat()
            need(stat.S_ISDIR(s.st_mode) and s.st_uid == 0 and not s.st_mode & 0o022,
                 "UNTRUSTED_PARENT")

    def fresh(self):
        self.h.platform()
        self.parents()
        need(self.h.user() is None and self.h.group() is None, "IDENTITY_ALREADY_EXISTS")
        for path in (*DIRS, UNIT_PATH, STATE):
            need(self.absent(path), "TARGET_ALREADY_EXISTS")
        unit = self.h.unit()
        need(unit.get("LoadState") == "not-found" and unit.get("ActiveState") == "inactive"
             and not unit.get("DropInPaths") and not unit.get("FragmentPath")
             and not unit.get("UnitFileState"), "UNIT_ALREADY_EXISTS")

    @contextmanager
    def lock(self):
        fd = os.open(self.h.path(STATE), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise Stop("ANOTHER_H2_OPERATION_ACTIVE") from None
            yield
        finally:
            os.close(fd)

    def write_new(self, path, data, mode, gid=0):
        fd = os.open(self.h.path(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
        with os.fdopen(fd, "wb") as stream:
            os.fchown(stream.fileno(), 0, gid)
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())

    def mkdir(self, path, mode, gid=0):
        self.h.path(path).mkdir(mode=mode)
        os.chown(self.h.path(path), 0, gid, follow_symlinks=False)
        os.chmod(self.h.path(path), mode)

    def save_receipt(self, receipt, first=False):
        data = (json.dumps(receipt, sort_keys=True) + "\n").encode()
        if first:
            self.write_new(RECEIPT, data, 0o600)
        else:
            self.write_new(RECEIPT + ".next", data, 0o600)
            os.replace(self.h.path(RECEIPT + ".next"), self.h.path(RECEIPT))
        fd = os.open(self.h.path(STATE), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def receipt(self):
        self.metadata(STATE, 0o700, directory=True)
        self.metadata(RECEIPT, 0o600)
        need({p.name for p in self.h.path(STATE).iterdir()} == {"receipt.json"}, "RECEIPT_PARTIAL_OR_DRIFT")
        need(self.h.path(RECEIPT).stat().st_size < 4096, "RECEIPT_INVALID")
        r = json.loads(self.h.path(RECEIPT).read_text())
        need(set(r) == {"schema", "id", "uid", "gid"} and r["schema"] == SCHEMA,
             "RECEIPT_INVALID")
        need(isinstance(r["id"], str) and re.fullmatch(r"[a-f0-9]{32}", r["id"]), "RECEIPT_INVALID")
        need((r["uid"] is None and r["gid"] is None) or
             (type(r["uid"]) is int and type(r["gid"]) is int and
              0 < r["uid"] < 1000 and 0 < r["gid"] < 1000), "RECEIPT_INVALID")
        return r

    def identity(self, r, partial=False):
        user, group = self.h.user(), self.h.group()
        if user is None:
            need(partial, "IDENTITY_MISSING")
            if group is not None:
                need(r["gid"] == group["gid"] and not group["members"]
                     and not group["other_primary"], "GROUP_OWNERSHIP_UNPROVEN")
            if r["uid"] is not None:
                self.h.no_processes(r["uid"])
            return r["gid"]
        need(user["tag"] == SCHEMA + "-" + r["id"] and user["locked"]
             and user["home"] == "/nonexistent" and user["shell"] == "/usr/sbin/nologin"
             and 0 < user["uid"] < 1000 and 0 < user["gid"] < 1000
             and set(user["groups"]) == {user["gid"]}, "IDENTITY_DRIFT")
        need(group is not None and group["gid"] == user["gid"] and not group["members"]
             and not group["other_primary"], "GROUP_DRIFT")
        need(r["uid"] in (None, user["uid"]) and r["gid"] in (None, user["gid"]), "IDENTITY_REPLACED")
        self.h.no_processes(user["uid"])
        return user["gid"]

    def files(self, gid, partial=False):
        for path, mode in DIRS.items():
            if partial and self.absent(path):
                continue
            owner_group = gid if path == "/etc/keirin-custody" else 0
            need(owner_group is not None, "ARTIFACT_OWNER_UNPROVEN")
            self.metadata(path, mode, owner_group, directory=True)
            expected = {"gates.json"} if path == "/etc/keirin-custody" else set()
            actual = {p.name for p in self.h.path(path).iterdir()}
            need(actual <= expected and (partial or actual == expected), "DIRECTORY_CONTENT_DRIFT")
        for path, (data, mode) in FILES.items():
            if partial and self.absent(path):
                continue
            owner_group = gid if path.endswith("/gates.json") else 0
            need(owner_group is not None, "ARTIFACT_OWNER_UNPROVEN")
            self.metadata(path, mode, owner_group)
            need(self.h.path(path).stat().st_size == len(data) and
                 self.h.path(path).read_bytes() == data, "ARTIFACT_CONTENT_DRIFT")

    def inactive(self, installed=False):
        unit = self.h.unit()
        need(unit.get("ActiveState") == "inactive" and not unit.get("DropInPaths"), "UNIT_STATE_DRIFT")
        if installed:
            need(unit.get("LoadState") == "loaded" and unit.get("UnitFileState") == "static"
                 and unit.get("FragmentPath") == UNIT_PATH
                 and unit.get("RefuseManualStart") == "yes", "UNIT_STATE_DRIFT")
        else:
            need(unit.get("LoadState") in ("loaded", "not-found")
                 and unit.get("UnitFileState", "") in ("", "static"), "UNIT_STATE_DRIFT")
            if unit.get("LoadState") == "loaded":
                need(unit.get("FragmentPath") == UNIT_PATH
                     and unit.get("RefuseManualStart") == "yes", "UNIT_STATE_DRIFT")

    def verify(self):
        self.h.platform()
        self.parents()
        r = self.receipt()
        need(r["uid"] is not None, "INSTALL_INCOMPLETE")
        gid = self.identity(r)
        self.files(gid)
        self.inactive(installed=True)
        return "INSTALLED_DISABLED_NOT_QUALIFIED"

    def apply(self, approve):
        need(approve == APPROVE, "LIVE_APPLY_APPROVAL_REQUIRED")
        self.fresh()
        r = {"schema": SCHEMA, "id": uuid.uuid4().hex, "uid": None, "gid": None}
        # Exclusive state-directory creation also prevents a second apply.
        self.mkdir(STATE, 0o700)
        with self.lock():
            return self.install(r)

    def install(self, r):
        self.save_receipt(r, first=True)
        self.h.create_user(SCHEMA + "-" + r["id"])
        self.identity(r)
        user = self.h.user()
        r.update(uid=user["uid"], gid=user["gid"])
        self.save_receipt(r)
        self.mkdir("/opt/keirin-custody", 0o755)
        self.mkdir("/etc/keirin-custody", 0o750, r["gid"])
        for path, (data, mode) in FILES.items():
            self.write_new(path, data, mode, r["gid"] if path.endswith("/gates.json") else 0)
        self.h.syntax()
        self.h.reload()
        return self.verify()

    def rollback(self, approve):
        need(approve == UNDO, "ROLLBACK_APPROVAL_REQUIRED")
        self.h.platform()
        self.parents()
        with self.lock():
            return self.remove_owned()

    def remove_owned(self):
        r = self.receipt()
        gid = self.identity(r, partial=True)
        self.files(gid, partial=True)
        self.inactive()
        # Validate everything first. No recursive deletion, process killing,
        # service stopping or adoption of existing data is permitted.
        for path in FILES:
            if not self.absent(path):
                self.h.path(path).unlink()
        for path in reversed(DIRS):
            if not self.absent(path):
                self.h.path(path).rmdir()
        self.h.reload()
        unit = self.h.unit()
        need(unit.get("LoadState") == "not-found", "UNIT_REMOVAL_UNCONFIRMED")
        if self.h.user() is not None:
            # Persist UID/GID if useradd completed before an interrupted receipt update.
            user = self.h.user()
            r.update(uid=user["uid"], gid=user["gid"])
            self.save_receipt(r)
            self.identity(r)
            self.h.remove_user()
        if self.h.group() is not None:
            self.identity(r, partial=True)
            self.h.remove_group()
        need(self.h.user() is None and self.h.group() is None, "IDENTITY_REMOVAL_UNCONFIRMED")
        self.h.path(RECEIPT).unlink()
        self.h.path(STATE).rmdir()
        return "ROLLED_BACK_NO_RUNTIME"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("inspect", "apply", "verify", "rollback"), nargs="?", default="inspect")
    parser.add_argument("--approve", default="")
    args = parser.parse_args(argv)
    package = Package(Host())
    try:
        if args.action == "inspect":
            package.fresh()
            result = "READY_FOR_SEPARATELY_APPROVED_H2A"
        elif args.action == "verify":
            result = package.verify()
        else:
            result = getattr(package, args.action)(args.approve)
        print("RESULT " + result)
        return 0
    except Stop as exc:
        print("STOP " + str(exc))
    except (OSError, ValueError, KeyError, TypeError):
        # Never render command diagnostics, account records or exception details.
        print("STOP HOST_STATE_UNREADABLE_OR_PARTIAL")
    print("RESULT NO_RUNTIME_AUTHORIZED_DO_NOT_RETRY_APPLY")
    return 1


if __name__ == "__main__":
    sys.exit(main())
