"""Fixed closed inbound profile on the sole synthetic ext4 volume.

No saved permission or key is restored. Crash mode pauses after receipt fsync;
only the host experiment kills its own QEMU, never the real host or cloud VM.
"""
import hashlib
import errno
import importlib.util
import json
import os
from pathlib import Path
import time

PROFILE = 'inbound-maintenance-closed'
INVALID = {'missing': 'FileNotFoundError', 'corrupt': 'JSONDecodeError',
           'stale': 'CLOSED_POLICY_KEYS_REQUIRED', 'orphan': 'ORPHAN_RECEIPT_REFUSED',
           'mismatch': 'MATCHED_PREVIOUS_BOOT_RECEIPT_REQUIRED',
           'interrupted': 'INTERRUPTED_STATE_REFUSED', 'receipt-corrupt': 'JSONDecodeError'}
FAULTS = {'enospc': errno.ENOSPC, 'erofs': errno.EROFS}
PHASES = ('normal', 'live-refusal', 'after-receipt', 'recover') + tuple(INVALID) + tuple(FAULTS)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def phase():
    values = [x.split('=', 1)[1] for x in Path('/proc/cmdline').read_text().split()
              if x.startswith('kc_inbound_persistence=')]
    if len(values) != 1 or values[0] not in PHASES:
        raise RuntimeError('FIXED_INBOUND_PERSISTENCE_OPT_IN_REQUIRED')
    return values[0]


class ClosedProfile:
    def __init__(self, durable): self.d = durable
    def policy(self, generation=0, boot=None): return self.d.policy(generation, boot, profile=PROFILE)
    def decode(self, raw): return self.d.decode(raw, profile=PROFILE)
    def pair(self, *args): return self.d.pair(*args, profile=PROFILE)
    def object_bytes(self, raw): return self.d.object_bytes(raw)


def context(*, readonly=False):
    persist = module('persist', '/persist_probe.py')
    b, g, durable = persist.context()  # Guest and fixed volume opt-in first.
    current = phase()
    flags = Path('/proc/cmdline').read_text().split()
    expected = 'invalid' if current == 'recover' or current in INVALID else 'closed'
    mounted = persist.mounted('ro' if readonly and current == 'erofs' else 'rw')
    if (flags.count('kc_inbound_boot=' + expected) != 1
            or flags.count('kc_inbound_restart=1') != 1 or flags.count('kc_inbound_lease=1') != 1
            or persist.crash_mode() is not None or persist.fault_mode() is not None
            or (b.composition() not in ('awake', 'suspend')
                or current not in ('normal', *FAULTS) and b.composition() != 'awake') or not mounted):
        raise RuntimeError('FIXED_MOUNTED_INBOUND_COMPOSITION_REQUIRED')
    return persist, b, g, ClosedProfile(durable), current


def emit(b, event, **values):
    print('INBOUND_PERSIST_RECORD ' + json.dumps(dict(event=event, boot=b.boot(),
          monotonic=time.monotonic(), activation_allowed=False, **values)), flush=True)


def state(persist, durable):
    config_raw, receipt_raw = persist.read_bytes('policy.json'), persist.read_bytes('receipt.json')
    config, receipt = durable.decode(config_raw), durable.object_bytes(receipt_raw)
    if config != durable.policy() or set(receipt) != {'boot', 'deadline_ns'}:
        raise RuntimeError('SEED_AND_ORPHAN_INBOUND_STATE_REQUIRED')
    return dict(generation=0, receipt_boot=receipt['boot'],
                policy_sha256=hashlib.sha256(config_raw).hexdigest(),
                receipt_sha256=hashlib.sha256(receipt_raw).hexdigest())


def gate():
    persist, b, g, durable, current = context()
    h = module('inbound', '/inbound_boot.py'); _, i, _ = h.context()
    if any(h.up(i, n) for n in ('host0', 'host1')):
        raise RuntimeError('BOTH_LINKS_DOWN_BEFORE_DISK_READ_REQUIRED')
    try:
        config, receipt, reason = persist.load_state(durable, b.boot(), time.clock_gettime_ns(time.CLOCK_BOOTTIME))
    except (ValueError, OSError, RuntimeError) as exc:
        detail = dict(crash_state=state(persist, durable)) if current == 'recover' else {}
        if current in INVALID: detail = dict(disk_state=disk_state(persist), invalid_case=current,
                                             store_state=b.properties(g, 'kc-store'))
        reason = type(exc).__name__ if isinstance(exc, (FileNotFoundError, json.JSONDecodeError)) else str(exc)
        emit(b, 'refused', reason=reason, links=[False, False], **detail)
        raise RuntimeError('INVALID_DURABLE_INBOUND_POLICY') from exc
    if current == 'recover' or current in INVALID: raise RuntimeError('PARTIAL_CHECKPOINT_MUST_BE_REFUSED')
    value = dict(generation=config['generation'], writer_boot=config['writer_boot'],
                 policy_sha256=hashlib.sha256(persist.read_bytes('policy.json')).hexdigest(),
                 saved_receipt=receipt, replay_reason=reason, links=[False, False],
                 store_state=b.properties(g, 'kc-store'))
    b.write('inbound-loaded', dict(boot=b.boot(), **value))
    emit(b, 'loaded', **value)


def await_crash(persist, b, h, g, i, durable, receipt_sha):
    b.guard()
    if phase() != 'after-receipt' or b.composition() != 'awake' or not persist.mounted():
        raise RuntimeError('FIXED_INBOUND_CRASH_BARRIER_REQUIRED')
    restart = module('restart', '/inbound_restart.py')
    _, blocked = restart.intact(b, h, g, i)
    snapshot = state(persist, durable)
    if (snapshot['receipt_boot'] != b.boot() or snapshot['receipt_sha256'] != receipt_sha
            or (b.STATE / 'saved').exists() or blocked != [False, False]):
        raise RuntimeError('CLOSED_UNPUBLISHED_INBOUND_SAVE_REQUIRED')
    emit(b, 'crash-ready', crash_state=snapshot, qualification=blocked,
         profile_unchanged=True, guards_absent=True, saved_marker_present=False)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline: time.sleep(.1)
    raise RuntimeError('INBOUND_CRASH_TIMEOUT_NO_SAVE_CONTINUATION')


def save():
    persist, b, g, durable, current = context()
    if current == 'recover' or current in INVALID: raise RuntimeError('REFUSED_CHECKPOINT_CANNOT_BE_SAVED')
    h = module('inbound', '/inbound_boot.py'); _, i, _ = h.context()
    restart = module('restart', '/inbound_restart.py')
    restored, _ = restart.intact(b, h, g, i)
    config, _, _ = persist.load_state(durable, b.boot(), time.clock_gettime_ns(time.CLOCK_BOOTTIME))
    loaded = b.read('inbound-loaded')
    if (loaded['boot'] != b.boot() or loaded['generation'] != config['generation']
            or loaded['policy_sha256'] != hashlib.sha256(persist.read_bytes('policy.json')).hexdigest()
            or (current in ('after-receipt', *FAULTS) and config != durable.policy())):
        raise RuntimeError('UNCHANGED_LOADED_INBOUND_CHECKPOINT_REQUIRED')
    generation = config['generation'] + 1
    candidate = durable.policy(generation, b.boot()); durable.decode(json.dumps(candidate).encode())
    receipt_sha = persist.atomic('receipt.json', dict(boot=b.boot(), deadline_ns=restored['proof']['deadline_ns']))
    if current == 'after-receipt': await_crash(persist, b, h, g, i, durable, receipt_sha)
    if current in FAULTS: prepare_fault(current)
    try:
        policy_sha = persist.atomic('policy.json', candidate)
    except OSError as exc:
        if current in FAULTS: observe_fault(current, exc)
        raise
    if current in FAULTS: raise RuntimeError('EXPECTED_REAL_INBOUND_WRITE_ERROR_NOT_OBSERVED')
    b.write('saved', dict(boot=b.boot(), generation=generation,
                         policy_sha256=policy_sha, receipt_sha256=receipt_sha))
    return b.read('saved')


def refused():
    persist, b, g, _, current = context()
    if current != 'recover' and current not in INVALID: raise RuntimeError('REFUSED_STARTUP_ONLY')
    rows = [r for r in json.loads(g.run(g.NFT, '-j', 'list', 'ruleset'))['nftables'] if 'metainfo' not in r]
    states = {n: b.properties(g, 'kc-' + n) for n in ('link', 'check', 'lease', 'recover')}
    if rows or (b.STATE / 'saved').exists(): raise RuntimeError('NO_POLICY_OR_SAVED_MARKER_AFTER_REFUSAL')
    for value in states.values():
        if value['ActiveState'] != 'inactive' or int(value['ExecMainStartTimestampMonotonic']) != 0:
            raise RuntimeError('REFUSAL_MUST_PREVENT_ALL_EXECUTION')
    detail = dict(disk_state=disk_state(persist), invalid_case=current) if current in INVALID else {}
    emit(b, 'blocked', ruleset_empty=True, saved_marker_present=False, states=states, **detail)


def disk_state(persist):
    return {name: hashlib.sha256(persist.read_bytes(name)).hexdigest() if os.path.lexists(persist.ROOT / name) else None
            for name in ('policy.json', 'receipt.json', 'policy.json.next', 'receipt.json.next')}


def refuse_live_save(deadline):
    """Exercise the real save entrypoint before expiry; never create live receipts."""
    persist, b, _, _, current = context()
    if current != 'live-refusal' or b.composition() != 'awake':
        raise RuntimeError('FIXED_LIVE_SAVE_REFUSAL_REQUIRED')
    forbidden = ('inbound-lease', 'inbound-recovery', 'saved', 'inbound-shutdown-request')
    def unpublished():
        return not any(os.path.lexists(b.STATE / (name + suffix))
                       for name in forbidden for suffix in ('', '.next'))
    started = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
    if type(deadline) is not int or not 0 < started < deadline or not unpublished():
        raise RuntimeError('LIVE_UNPUBLISHED_REQUESTS_REQUIRED')
    snapshot = disk_state(persist)
    try: save()
    except RuntimeError as exc:
        if str(exc) != 'COMPLETED_INBOUND_RECOVERY_REQUIRED': raise
        refusals = {'save': str(exc)}
    else: raise RuntimeError('LIVE_SAVE_MUST_BE_REFUSED')
    if disk_state(persist) != snapshot or not unpublished():
        raise RuntimeError('LIVE_REFUSAL_MUST_NOT_WRITE_OR_PUBLISH')
    finished = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
    if not started <= finished < deadline: raise RuntimeError('REFUSALS_BEFORE_ORIGINAL_EXPIRY_REQUIRED')
    return dict(refusals=refusals, disk_before=snapshot, disk_after=disk_state(persist),
                started_ns=started, finished_ns=finished, deadline_ns=deadline,
                saved_marker_present=False, shutdown_request_present=False)


def fault_context(mode, *, observing=False):
    persist, b, g, durable, current = context(readonly=observing)
    if (mode not in FAULTS or current != mode or persist.ROOT != Path('/state')
            or Path('/sys/block/vda/size').read_text().strip() != '131072'):
        raise RuntimeError('FIXED_INBOUND_GUEST_VOLUME_FAULT_REQUIRED')
    return persist, b, g, durable, module('fault', '/persist_fault.py')


def prepare_fault(mode):
    persist, b, g, durable, helper = fault_context(mode)
    if not persist.mounted(): raise RuntimeError('WRITABLE_INBOUND_FAULT_VOLUME_REQUIRED')
    snapshot = state(persist, durable)
    if snapshot['receipt_boot'] != b.boot() or (b.STATE / 'saved').exists():
        raise RuntimeError('UNPUBLISHED_INBOUND_FAULT_RECEIPT_REQUIRED')
    before = helper.filesystem(persist.ROOT, 'rw'); allocated = 0
    if mode == 'enospc':
        fd = os.open(persist.ROOT / 'capacity.bin', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            allocated = helper.allocate_to_full(fd, before['block_size']); os.fsync(fd)
        finally: os.close(fd)
        directory = os.open(persist.ROOT, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)
        prepared = helper.filesystem(persist.ROOT, 'rw')
        if not 0 <= prepared['free_blocks'] <= prepared['reserved_clusters'] or not 0 < allocated <= helper.SIZE:
            raise RuntimeError('ACTUAL_INBOUND_VOLUME_EXHAUSTION_REQUIRED')
    else:
        g.run('/usr/bin/mount', '-n', '-i', '-o', 'remount,ro,nodev,nosuid,noexec', '/dev/vda', '/state')
        if not persist.mounted('ro'): raise RuntimeError('ACTUAL_INBOUND_READONLY_REMOUNT_REQUIRED')
        prepared = helper.filesystem(persist.ROOT, 'ro')
    b.write('inbound-io-fault', dict(mode=mode, boot=b.boot(), crash_state=snapshot,
        prepared=prepared, allocated_bytes=allocated, allocator_errno=errno.ENOSPC if mode == 'enospc' else None))


def observe_fault(mode, exc):
    persist, b, g, durable, helper = fault_context(mode, observing=True)
    prepared, snapshot = b.read('inbound-io-fault'), state(persist, durable)
    mount_mode = 'ro' if mode == 'erofs' else 'rw'
    h = module('inbound', '/inbound_boot.py'); _, i, _ = h.context()
    _, blocked = module('restart', '/inbound_restart.py').intact(b, h, g, i)
    if (exc.errno != FAULTS[mode] or prepared['mode'] != mode or prepared['boot'] != b.boot()
            or snapshot != prepared['crash_state'] or (b.STATE / 'saved').exists()
            or (b.STATE / 'inbound-shutdown-request').exists()
            or not persist.mounted(mount_mode) or blocked != [False, False]
            or any(os.path.lexists(persist.ROOT / (name + '.next')) for name in ('policy.json', 'receipt.json'))):
        raise RuntimeError('EXACT_INBOUND_WRITE_ERROR_WITHOUT_SUCCESS_REQUIRED')
    info = dict(mode=mode, errno=exc.errno, prepared=prepared['prepared'],
                allocated_bytes=prepared['allocated_bytes'], allocator_errno=prepared['allocator_errno'],
                after=helper.filesystem(persist.ROOT, mount_mode))
    emit(b, 'crash-ready', crash_state=snapshot, qualification=blocked, profile_unchanged=True,
         guards_absent=True, saved_marker_present=False, filesystem_fault=info,
         composition=b.composition(), shutdown_request_present=False)
