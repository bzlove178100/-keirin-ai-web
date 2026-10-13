"""Fixed closed inbound profile on the sole synthetic ext4 volume.

No saved permission or key is restored. Crash mode pauses after receipt fsync;
only the host experiment kills its own QEMU, never the real host or cloud VM.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import time

PROFILE = 'inbound-maintenance-closed'
PHASES = ('normal', 'after-receipt', 'recover')


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


def context():
    persist = module('persist', '/persist_probe.py')
    b, g, durable = persist.context()  # Guest and fixed volume opt-in first.
    current = phase()
    flags = Path('/proc/cmdline').read_text().split()
    expected = 'invalid' if current == 'recover' else 'closed'
    if (flags.count('kc_inbound_boot=' + expected) != 1
            or flags.count('kc_inbound_restart=1') != 1 or flags.count('kc_inbound_lease=1') != 1
            or persist.crash_mode() is not None or persist.fault_mode() is not None
            or (current != 'normal' and b.composition() != 'awake') or not persist.mounted()):
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
        emit(b, 'refused', reason=str(exc), links=[False, False], **detail)
        raise RuntimeError('INVALID_DURABLE_INBOUND_POLICY') from exc
    if current == 'recover': raise RuntimeError('PARTIAL_CHECKPOINT_MUST_BE_REFUSED')
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
    if current == 'recover': raise RuntimeError('REFUSED_CHECKPOINT_CANNOT_BE_SAVED')
    h = module('inbound', '/inbound_boot.py'); _, i, _ = h.context()
    restart = module('restart', '/inbound_restart.py')
    restored, _ = restart.intact(b, h, g, i)
    config, _, _ = persist.load_state(durable, b.boot(), time.clock_gettime_ns(time.CLOCK_BOOTTIME))
    loaded = b.read('inbound-loaded')
    if (loaded['boot'] != b.boot() or loaded['generation'] != config['generation']
            or loaded['policy_sha256'] != hashlib.sha256(persist.read_bytes('policy.json')).hexdigest()
            or (current == 'after-receipt' and config != durable.policy())):
        raise RuntimeError('UNCHANGED_LOADED_INBOUND_CHECKPOINT_REQUIRED')
    generation = config['generation'] + 1
    candidate = durable.policy(generation, b.boot()); durable.decode(json.dumps(candidate).encode())
    receipt_sha = persist.atomic('receipt.json', dict(boot=b.boot(), deadline_ns=restored['proof']['deadline_ns']))
    if current == 'after-receipt': await_crash(persist, b, h, g, i, durable, receipt_sha)
    policy_sha = persist.atomic('policy.json', candidate)
    b.write('saved', dict(boot=b.boot(), generation=generation,
                         policy_sha256=policy_sha, receipt_sha256=receipt_sha))
    return b.read('saved')


def refused():
    persist, b, g, _, current = context()
    if current != 'recover': raise RuntimeError('CRASH_RECOVERY_ONLY')
    rows = [r for r in json.loads(g.run(g.NFT, '-j', 'list', 'ruleset'))['nftables'] if 'metainfo' not in r]
    states = {n: b.properties(g, 'kc-' + n) for n in ('link', 'check', 'lease', 'recover')}
    if rows or (b.STATE / 'saved').exists(): raise RuntimeError('NO_POLICY_OR_SAVED_MARKER_AFTER_REFUSAL')
    for value in states.values():
        if value['ActiveState'] != 'inactive' or int(value['ExecMainStartTimestampMonotonic']) != 0:
            raise RuntimeError('REFUSAL_MUST_PREVENT_ALL_EXECUTION')
    emit(b, 'blocked', ruleset_empty=True, saved_marker_present=False, states=states)
