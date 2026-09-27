"""Linux-only bounded, digest-pinned CA snapshot; no mutable path reaches libpq."""
import fcntl
from hashlib import sha256
import os
from pathlib import PurePosixPath
import re
import stat
import sys

_MAX_CA_BYTES = 131072
# Linux UAPI values from linux/fcntl.h. Some Linux Python builds omit the names;
# the actual kernel operations below must still succeed and are never skipped.
_ADD_SEALS = getattr(fcntl, "F_ADD_SEALS", 1033)
_GET_SEALS = getattr(fcntl, "F_GET_SEALS", 1034)
_SEALS = 0x0008 | 0x0004 | 0x0002 | 0x0001


class HostTrustError(RuntimeError):
    pass


class SealedTrustSnapshot:
    def __init__(self, fd):
        self._fd = fd

    @property
    def path(self):
        if self._fd is None:
            raise HostTrustError("host_trust_closed")
        return f"/proc/self/fd/{self._fd}"

    def close(self):
        if self._fd is not None:
            fd, self._fd = self._fd, None
            os.close(fd)

    def __repr__(self):
        return "SealedTrustSnapshot(<redacted>)"


def snapshot_trust(path, expected_sha256):
    """Pin must come from reviewed host configuration, not the candidate file.

    Walk directory FDs without following symlinks, bound reads, verify ownership/
    permissions and content hash, then copy to an immutable sealed memfd. A root-owned
    sticky ancestor such as /tmp is allowed; the immediate parent must be protected.
    Root/host account and kernel remain trusted. No claim of protecting compromised
    process code or erasing every memory copy is made.
    """
    descriptors = []
    sealed = None
    failed = False
    interrupted = None
    try:
        if sys.platform != "linux":
            raise ValueError()
        if (type(path) is not str or not path.startswith("/") or len(path) > 2048
                or str(PurePosixPath(path)) != path or ".." in path.split("/")
                or type(expected_sha256) is not str or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None):
            raise ValueError()
        parts = PurePosixPath(path).parts[1:]
        if not parts:
            raise ValueError()
        directory = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        descriptors.append(directory)
        for index, part in enumerate(parts[:-1]):
            directory = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)
            descriptors.append(directory)
            info = os.fstat(directory)
            sticky_ancestor = (index < len(parts) - 2 and info.st_uid == 0 and info.st_mode & stat.S_ISVTX)
            if info.st_uid not in {0, os.geteuid()} or (info.st_mode & 0o022 and not sticky_ancestor):
                raise ValueError()
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=directory)
        descriptors.append(fd)
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid not in {0, os.geteuid()}
                or before.st_mode & 0o022 or before.st_nlink != 1
                or not 0 < before.st_size <= _MAX_CA_BYTES):
            raise ValueError()
        chunks = []
        remaining = _MAX_CA_BYTES + 1
        while remaining:
            chunk = os.read(fd, min(16384, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        content = b"".join(chunks)
        after = os.fstat(fd)
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_uid", "st_mode", "st_nlink")
        if (len(content) != before.st_size or any(getattr(before, field) != getattr(after, field) for field in fields)
                or sha256(content).hexdigest() != expected_sha256):
            raise ValueError()
        sealed = os.memfd_create("agent-host-trust", os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
        offset = 0
        while offset < len(content):
            written = os.write(sealed, content[offset:])
            if written <= 0:
                raise ValueError()
            offset += written
        os.lseek(sealed, 0, os.SEEK_SET)
        fcntl.fcntl(sealed, _ADD_SEALS, _SEALS)
        if fcntl.fcntl(sealed, _GET_SEALS) & _SEALS != _SEALS:
            raise ValueError()
    except BaseException as error:
        failed = True
        if isinstance(error, KeyboardInterrupt):
            interrupted = KeyboardInterrupt
        elif isinstance(error, SystemExit):
            interrupted = SystemExit
    finally:
        for fd in reversed(descriptors):
            try:
                os.close(fd)
            except OSError:
                failed = True
    if failed:
        if sealed is not None:
            os.close(sealed)
        if interrupted:
            raise interrupted("host_trust_interrupted")
        raise HostTrustError("host_trust_invalid")
    return SealedTrustSnapshot(sealed)
