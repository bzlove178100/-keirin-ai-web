"""Fixed synthetic policy volume; all mount/write operations guarded in guest."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import time

ROOT = Path('/state')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def enabled():
    values = [x for x in Path('/proc/cmdline').read_text().split() if x.startswith('kc_persistence=')]
    if not values: return False
    if values != ['kc_persistence=1']: raise RuntimeError('FIXED_PERSISTENCE_OPT_IN_REQUIRED')
    return True


def context():
    b = module('boot', '/boot_probe.py'); b.guard()
    if not enabled() or not b.composition(): raise RuntimeError('ISOLATED_PERSISTENCE_REQUIRED')
    return b, module('packets', '/probe.py'), module('durable', '/durable_policy.py')


def mounted():
    rows = [line.split() for line in Path('/proc/self/mountinfo').read_text().splitlines() if line.split()[4] == str(ROOT)]
    if not rows: return False
    if len(rows) != 1: raise RuntimeError('SINGLE_STATE_MOUNT_REQUIRED')
    row = rows[0]; split = row.index('-')
    if row[split+1:split+3] != ['ext4', '/dev/vda'] or not {'rw', 'nodev', 'nosuid', 'noexec'} <= set(row[5].split(',')):
        raise RuntimeError('PRIVATE_EXT4_MOUNT_REQUIRED')
    return True


def read_bytes(name):
    fd = os.open(ROOT / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 4096: raise RuntimeError('BOUNDED_REGULAR_STATE_REQUIRED')
        return os.read(fd, 4097)
    finally: os.close(fd)


def atomic(name, value):
    data = (json.dumps(value, sort_keys=True) + '\n').encode()
    if len(data) > 4096: raise RuntimeError('STATE_WRITE_BOUND')
    temporary = ROOT / (name + '.next')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, ROOT / name)
        directory = os.open(ROOT, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally: temporary.unlink(missing_ok=True)
    if read_bytes(name) != data: raise RuntimeError('SAVED_STATE_READBACK_REQUIRED')
    return hashlib.sha256(data).hexdigest()


def emit(b, event, **values):
    print('SYSTEMD_PERSIST_RECORD ' + json.dumps(dict(event=event, boot=b.boot(),
          monotonic=time.monotonic(), activation_allowed=False, **values)), flush=True)


def save():
    b, g, durable = context()
    if not mounted(): raise RuntimeError('MOUNTED_STATE_REQUIRED')
    config = durable.decode(read_bytes('policy.json'))
    lease = b.read('lease')
    if lease['boot'] != b.boot() or time.clock_gettime_ns(time.CLOCK_BOOTTIME) <= lease['deadline_ns']:
        raise RuntimeError('ONLY_COMPLETED_EXPIRED_RECEIPT_CAN_BE_SAVED')
    generation = config['generation'] + 1
    candidate = durable.policy(generation, b.boot()); durable.decode(json.dumps(candidate).encode())
    receipt = dict(boot=b.boot(), deadline_ns=lease['deadline_ns'])
    receipt_sha = atomic('receipt.json', receipt)
    policy_sha = atomic('policy.json', candidate)
    b.write('saved', dict(boot=b.boot(), generation=generation, policy_sha256=policy_sha, receipt_sha256=receipt_sha))
    return b.read('saved')


def unmounted_store():
    b, g, _ = context()
    state = b.properties(g, 'kc-store')
    if mounted() or state['ActiveState'] != 'inactive' or state['Result'] != 'success':
        raise RuntimeError('STATE_UNMOUNTED_BEFORE_FINAL_REQUIRED')
    return state


def shutdown_check():
    b, _, _ = context()
    state = unmounted_store()
    saved = b.read('saved')
    if saved['boot'] != b.boot(): raise RuntimeError('SAME_BOOT_SAVED_RECORD_REQUIRED')
    return dict(unmounted=True, store_state=state, saved=saved)


def main(action):
    b, g, durable = context()
    if action == 'mount':
        if mounted(): raise RuntimeError('FRESH_STATE_MOUNT_REQUIRED')
        g.run('/sbin/modprobe', '-C', '/module-config', '-a', 'virtio_pci', 'virtio_blk', 'ext4')
        deadline = time.monotonic() + 5
        while not Path('/sys/block/vda/serial').exists() and time.monotonic() < deadline: time.sleep(.02)
        devices = [x.name for x in Path('/sys/block').iterdir() if '/virtual/' not in str(x.resolve())]
        if (devices != ['vda'] or Path('/sys/block/vda/serial').read_text().strip() != 'KCSTATE'
                or Path('/sys/block/vda/size').read_text().strip() != '131072'):
            raise RuntimeError('SINGLE_OWNED_64M_VOLUME_REQUIRED')
        major, minor = map(int, Path('/sys/block/vda/dev').read_text().split(':'))
        device = Path('/dev/vda')
        if not device.exists(): os.mknod(device, stat.S_IFBLK | 0o600, os.makedev(major, minor))
        info = device.stat()
        if not stat.S_ISBLK(info.st_mode) or info.st_rdev != os.makedev(major, minor): raise RuntimeError('MATCHED_GUEST_DEVICE_REQUIRED')
        ROOT.mkdir(mode=0o700)
        g.run('/usr/bin/mount', '-n', '-i', '-t', 'ext4', '-o', 'rw,nodev,nosuid,noexec', '/dev/vda', str(ROOT))
        if not mounted(): raise RuntimeError('ACTUAL_EXT4_MOUNT_REQUIRED')
    elif action == 'unmount':
        if mounted(): g.run('/usr/bin/umount', '-n', '-i', str(ROOT))
        if mounted(): raise RuntimeError('STATE_UNMOUNT_REQUIRED')
    elif action == 'gate':
        if not mounted() or b.link_up(g): raise RuntimeError('CLOSED_MOUNTED_GATE_REQUIRED')
        try: config = durable.decode(read_bytes('policy.json'))
        except (FileNotFoundError, ValueError, OSError) as exc:
            emit(b, 'refused', reason=type(exc).__name__, link_up=False)
            raise RuntimeError('INVALID_DURABLE_CLOSED_POLICY') from exc
        receipt, reason = None, 'NO_SAVED_RECEIPT'
        if (ROOT / 'receipt.json').exists():
            receipt = json.loads(read_bytes('receipt.json'))
            reason = durable.replay_reason(receipt, b.boot(), time.clock_gettime_ns(time.CLOCK_BOOTTIME))
        if config['generation'] and (not receipt or config['writer_boot'] != receipt['boot'] or reason != 'PRIOR_BOOT_LEASE_REFUSED'):
            raise RuntimeError('MATCHED_PREVIOUS_BOOT_RECEIPT_REQUIRED')
        policy = module('policy', '/startup_policy.py')
        g.run(g.NFT, '-f', '-', input=policy.install().encode())
        seal = policy.seal(json.loads(g.run(g.NFT, '-j', 'list', 'table', 'inet', policy.TABLE)))
        b.write('gate', dict(boot=b.boot(), seal=seal, sealed_ns=time.monotonic_ns(), link_up=b.link_up(g)))
        emit(b, 'loaded', generation=config['generation'], writer_boot=config['writer_boot'],
             policy_sha256=hashlib.sha256(read_bytes('policy.json')).hexdigest(), saved_receipt=receipt,
             replay_reason=reason, link_up=False, store_state=b.properties(g, 'kc-store'))
    else: raise RuntimeError('FIXED_PERSISTENCE_ACTION_REQUIRED')


if __name__ == '__main__':
    try: main(sys.argv[1] if len(sys.argv) == 2 else '')
    except Exception as exc:
        print('SYSTEMD_PERSIST_STAGE_ERROR ' + repr(exc), flush=True)
        raise
