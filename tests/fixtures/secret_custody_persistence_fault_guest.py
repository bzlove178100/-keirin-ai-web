"""Actual ENOSPC/EROFS on the sole bounded synthetic guest disk, never host mounts."""
import errno
import importlib.util
import json
import os
from pathlib import Path
import stat
import time

SIZE = 64 * 1024 * 1024
ERRORS = {'enospc': errno.ENOSPC, 'erofs': errno.EROFS}


def context(mode):
    spec = importlib.util.spec_from_file_location('persist', '/persist_probe.py')
    persist = importlib.util.module_from_spec(spec); spec.loader.exec_module(persist)
    b, g, durable = persist.context()  # Real guest guard precedes every mutation.
    if (mode not in ERRORS or persist.fault_mode() != mode or persist.crash_mode() is not None
            or b.composition() != 'awake' or persist.ROOT != Path('/state')
            or Path('/sys/block/vda/size').read_text().strip() != '131072'):
        raise RuntimeError('FIXED_ISOLATED_FILESYSTEM_FAULT_REQUIRED')
    return persist, b, g, durable


def filesystem(root, mode):
    value = os.statvfs(root)
    if (value.f_frsize not in (1024, 2048, 4096) or not 0 < value.f_blocks * value.f_frsize <= SIZE
            or bool(value.f_flag & os.ST_RDONLY) != (mode == 'ro')):
        raise RuntimeError('BOUNDED_FILESYSTEM_MODE_REQUIRED')
    reserved = int(Path('/sys/fs/ext4/vda/reserved_clusters').read_text().strip())
    if not 0 <= reserved <= SIZE // value.f_frsize:
        raise RuntimeError('BOUNDED_EXT4_RESERVATION_REQUIRED')
    return dict(mount_mode=mode, block_size=value.f_frsize, free_blocks=value.f_bfree,
                available_blocks=value.f_bavail, reserved_clusters=reserved)


def allocate_to_full(fd, block_size):
    allocated, step = 0, 1024 * 1024
    deadline = time.monotonic() + 20
    while allocated + step <= SIZE and time.monotonic() < deadline:
        try:
            os.posix_fallocate(fd, allocated, step)
            allocated += step
        except OSError as exc:
            if exc.errno != errno.ENOSPC: raise
            if step == block_size: return allocated
            step = block_size
    raise RuntimeError('BOUNDED_REAL_ENOSPC_REQUIRED')


def prepare(mode):
    persist, b, g, durable = context(mode)
    if not persist.mounted(): raise RuntimeError('WRITABLE_GUEST_DISK_REQUIRED')
    state = persist.crash_state(durable)
    if state['receipt_boot'] != b.boot() or (b.STATE / 'saved').exists():
        raise RuntimeError('UNPUBLISHED_SAME_BOOT_RECEIPT_REQUIRED')
    before = filesystem(persist.ROOT, 'rw')
    allocated = 0
    if mode == 'enospc':
        fd = os.open(persist.ROOT / 'capacity.bin', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode): raise RuntimeError('OWNED_FILLER_FILE_REQUIRED')
            allocated = allocate_to_full(fd, before['block_size'])
            os.fsync(fd)
        finally: os.close(fd)
        directory = os.open(persist.ROOT, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)
        prepared = filesystem(persist.ROOT, 'rw')
        # ext4 keeps an internal reserved cluster pool even for uid 0.
        # A cluster is at least one block; this bound is conservative.
        # The actual policy write must independently fail with ENOSPC.
        if not 0 <= prepared['free_blocks'] <= prepared['reserved_clusters'] or not 0 < allocated <= SIZE:
            raise RuntimeError('ACTUALLY_EXHAUSTED_GUEST_BLOCKS_REQUIRED ' + json.dumps(
                dict(prepared=prepared, allocated_bytes=allocated), sort_keys=True))
    else:
        g.run('/usr/bin/mount', '-n', '-i', '-o', 'remount,ro,nodev,nosuid,noexec', '/dev/vda', '/state')
        if not persist.mounted('ro'): raise RuntimeError('ACTUAL_READONLY_REMOUNT_REQUIRED')
        prepared = filesystem(persist.ROOT, 'ro')
    b.write('io-fault', dict(mode=mode, boot=b.boot(), crash_state=state,
                           prepared=prepared, allocated_bytes=allocated,
                           allocator_errno=errno.ENOSPC if mode == 'enospc' else None))


def observe(mode, exc):
    persist, b, g, durable = context(mode)
    mount_mode = 'ro' if mode == 'erofs' else 'rw'
    if not persist.mounted(mount_mode): raise RuntimeError('FAULTED_MOUNT_REQUIRED')
    prepared, state = b.read('io-fault'), persist.crash_state(durable)
    blocked = [g.reaches(address, 443) for address in g.PEERS]
    if (exc.errno != ERRORS[mode] or prepared['mode'] != mode or prepared['boot'] != b.boot()
            or state != prepared['crash_state'] or blocked != [False, False]
            or (b.STATE / 'saved').exists()
            or any(os.path.lexists(persist.ROOT / (name + '.next')) for name in ('policy.json', 'receipt.json'))):
        raise RuntimeError('EXACT_REAL_WRITE_FAILURE_WITHOUT_SAVED_MARKER_REQUIRED')
    info = dict(mode=mode, errno=exc.errno, allocated_bytes=prepared['allocated_bytes'],
                allocator_errno=prepared['allocator_errno'],
                prepared=prepared['prepared'], after=filesystem(persist.ROOT, mount_mode))
    persist.emit(b, 'crash-ready', crash_state=state, qualification=blocked,
                 saved_marker_present=False, link_up=b.link_up(g), filesystem_fault=info)
    # Caller re-raises the real OSError. No saved marker or normal shutdown.
