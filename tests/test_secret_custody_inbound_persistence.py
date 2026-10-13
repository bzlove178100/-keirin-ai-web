"""Closed inbound persistence: normal reboot and same-disk process-crash refusal.

Synthetic 64 MiB volume only, no external NIC, host mount, live credentials,
cloud actions, write repair, power-loss or general crash-consistency claim.
"""
import copy
import errno
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('restart', HERE / 'test_secret_custody_inbound_restart.py')
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
b, c, h, p, vm = r.b, r.c, r.h, r.p, r.vm
s = b.module('storage', HERE / 'test_secret_custody_persistence.py')
guest = b.module('inbound_store', HERE / 'fixtures/secret_custody_inbound_persistence_guest.py')
durable = guest.ClosedProfile(s.d)
persist = b.module('persist', HERE / 'fixtures/secret_custody_persistence_guest.py')
faults = b.module('storage_faults', HERE / 'test_secret_custody_persistence_crash.py')


def command(path, mode, phase):
    if phase not in guest.PHASES or (phase != 'normal' and mode != 'awake'):
        raise ValueError('FIXED_INBOUND_STORAGE_CASE_REQUIRED')
    args = r.command(path, mode)
    # Reuse the owned regular raw-image guard and exact block-device arguments.
    args += s.command(path, 'closed', mode)[-4:]
    index = args.index('-append') + 1
    if phase == 'recover' or phase in guest.INVALID: args[index] = args[index].replace('kc_inbound_boot=closed', 'kc_inbound_boot=invalid')
    args[index] += ' kc_persistence=1 kc_inbound_persistence=' + phase + ' end=12'
    return args


def record(lines, event, boot=None):
    diagnostic, deadline = [], time.monotonic() + 100
    while True:
        try: line = lines.line(deadline)
        except Exception:
            print('INBOUND_PERSIST_DIAGNOSTIC ' + '\n'.join(diagnostic)[-8000:], flush=True); raise
        diagnostic.append(line[-2000:]); diagnostic = diagnostic[-40:]
        if (line.startswith(('INBOUND_BOOT_STAGE_ERROR', 'INBOUND_RESTART_FAIL', 'SYSTEMD_PERSIST_STAGE_ERROR'))
                or 'Kernel panic' in line or 'Freezing execution' in line):
            raise RuntimeError('INBOUND_PERSIST_STAGE_FAILED ' + '\n'.join(diagnostic)[-8000:])
        if not line.startswith('INBOUND_PERSIST_RECORD '): continue
        row = json.loads(line[len('INBOUND_PERSIST_RECORD '):])
        if (row.get('event') != event or row.get('activation_allowed') is not False
                or str(vm.uuid.UUID(row['boot'])) != row['boot'] or boot is not None and row['boot'] != boot
                or type(row.get('monotonic')) not in (int, float)
                or not math.isfinite(row['monotonic']) or row['monotonic'] < 0):
            raise RuntimeError('MATCHED_FINITE_INBOUND_STORAGE_RECORD_REQUIRED')
        print(line, flush=True); return row


def startup(lines, excluded, recovering=False):
    case = 'invalid' if recovering else 'closed'
    rows = [h.record(lines, event, case) for event in ('setup_entered', 'setup_completed')]
    loaded = record(lines, 'refused' if recovering else 'loaded', rows[0]['boot'])
    rows.append(loaded)
    if not recovering:
        rows += [h.record(lines, event, case) for event in ('gate_completed', 'link_completed')]
    if (rows[0]['boot'] in excluded
            or any(x['boot'] != rows[0]['boot'] or x.get('activation_allowed') is not False
                   or type(x.get('monotonic')) not in (int, float)
                   or not math.isfinite(x['monotonic']) or x['monotonic'] < 0 for x in rows)
            or any(a['monotonic'] > z['monotonic'] for a, z in zip(rows, rows[1:]))):
        raise RuntimeError('FRESH_ORDERED_DURABLE_STARTUP_REQUIRED')
    return loaded


def loaded_evidence(loaded, first, previous):
    if loaded.get('links') != [False, False]: raise RuntimeError('TWO_CLOSED_LINKS_AT_LOAD_REQUIRED')
    s.loaded_evidence(loaded, first, previous)
    for prop in ('Requires', 'After'):
        if 'kc-store.service' not in first['states']['gate'][prop].split():
            raise RuntimeError('ACTUAL_STORE_GATE_DEPENDENCY_REQUIRED')


def saved_evidence(request, stopped, loaded):
    saved, shutdown = request['persistence'], stopped['persistence']
    if (saved.get('boot') != loaded['boot'] or type(saved.get('generation')) is not int
            or saved['generation'] != loaded['generation'] + 1
            or shutdown.get('unmounted') is not True or shutdown.get('saved') != saved):
        raise RuntimeError('SAVED_GENERATION_THEN_UNMOUNT_REQUIRED')
    for key in ('policy_sha256', 'receipt_sha256'):
        if not r.re.fullmatch('[0-9a-f]{64}', str(saved.get(key))): raise RuntimeError('EXACT_SAVED_HASH_REQUIRED')
    state = shutdown['store_state']
    if state.get('ActiveState') != 'inactive' or state.get('Result') != 'success':
        raise RuntimeError('ACTUAL_STORE_UNMOUNT_REQUIRED')
    return saved


def crash_evidence(ready, boot):
    if (ready.get('boot') != boot or ready.get('activation_allowed') is not False
            or ready.get('qualification') != [False, False] or ready.get('profile_unchanged') is not True
            or ready.get('guards_absent') is not True or ready.get('saved_marker_present') is not False
            or ready['crash_state'].get('generation') != 0 or ready['crash_state'].get('receipt_boot') != boot):
        raise RuntimeError('CLOSED_UNPUBLISHED_INBOUND_BARRIER_REQUIRED')
    for key in ('policy_sha256', 'receipt_sha256'):
        if not r.re.fullmatch('[0-9a-f]{64}', str(ready['crash_state'].get(key))):
            raise RuntimeError('EXACT_CRASH_HASH_REQUIRED')


def refused_evidence(denied, ready, first, blocked):
    h.evidence(first)
    if (denied.get('reason') != 'ORPHAN_RECEIPT_REFUSED' or denied.get('links') != [False, False]
            or denied['boot'] == ready['boot'] or denied['boot'] != first['boot'] or blocked['boot'] != first['boot']
            or denied.get('crash_state') != ready['crash_state'] or blocked.get('ruleset_empty') is not True
            or blocked.get('saved_marker_present') is not False or blocked.get('activation_allowed') is not False
            or not denied['monotonic'] <= first['monotonic'] <= blocked['monotonic']):
        raise RuntimeError('EXACT_PARTIAL_STATE_REFUSED_BEFORE_LINK_REQUIRED')
    if set(blocked['states']) != {'link', 'check', 'lease', 'recover'}:
        raise RuntimeError('COMPLETE_REFUSED_SERVICES_REQUIRED')
    for value in blocked['states'].values():
        if value['ActiveState'] != 'inactive' or int(value['ExecMainStartTimestampMonotonic']) != 0:
            raise RuntimeError('NO_AUTH_OR_LEASE_AFTER_REFUSAL_REQUIRED')


def stop(process, path):
    if process is not None and process.poll() is None:
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
    for name in ('qmp', 'serial'): (path / name).unlink(missing_ok=True)


def normal(path, host_boot):
    process = None
    try:
        with (path / 'stderr').open('wb') as err:
            process = subprocess.Popen(command(path, 'suspend', 'normal'), stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=err, cwd=path, env={'PATH': '/usr/bin:/bin', 'LANG': 'C'})
            with vm.connect(path / 'qmp', process) as monitor, vm.connect(path / 'serial', process) as serial:
                qmp, lines = vm.QMP(monitor), vm.Lines(serial)
                s.block_evidence(qmp.call('query-block'), path)
                if qmp.call('query-current-machine').get('wakeup-suspend-support') is not True:
                    raise RuntimeError('ACTUAL_S3_CAPABILITY_REQUIRED')
                previous, boots, requests = None, {host_boot}, []
                for instruction, target, event in ((b'restart\n', 'reboot.target', 'RESET'), (b'halt\n', 'poweroff.target', 'SHUTDOWN')):
                    loaded = startup(lines, boots)
                    first, outcome = c.cycle(lines, qmp, 'suspend', host_boot)
                    loaded_evidence(loaded, first, previous); boots.add(first['boot'])
                    qmp.events = []
                    serial.sendall(instruction)
                    rows = [r.record(lines, e, first['boot'], target) for e in ('requested', 'link_down', 'stopped')]
                    r.evidence(*rows); previous = saved_evidence(rows[0], rows[2], loaded); requests.append(rows[0])
                    transition = qmp.event(event, time.monotonic() + 30)
                    if transition.get('data', {}).get('guest') is not True: raise RuntimeError('NORMAL_GUEST_TRANSITION_REQUIRED')
                    print('PASS INBOUND_DURABLE_CYCLE ' + target + ' ' + first['boot'] + ' ' + outcome, flush=True)
                r.fresh(*requests)
                if process.wait(timeout=10) != 0: raise RuntimeError('NORMAL_INBOUND_DURABLE_POWEROFF_REQUIRED')
                print('PASS INBOUND_DURABLE_REBOOT_EXACT_CHECKPOINT_OLD_LEASE_REFUSED_FRESH_AUTH', flush=True)
    finally: stop(process, path)


def crash(path, host_boot, fault=None):
    if fault is not None and fault not in guest.FAULTS: raise ValueError('FIXED_INBOUND_IO_FAULT_REQUIRED')
    ready, disk_sha = None, None
    for phase in (fault or 'after-receipt', 'recover'):
        process = None
        try:
            if phase == 'recover' and hashlib.sha256((path / 'state.raw').read_bytes()).hexdigest() != disk_sha:
                raise RuntimeError('UNMODIFIED_SAME_CRASH_DISK_REQUIRED')
            with (path / ('stderr-' + phase)).open('wb') as err:
                process = subprocess.Popen(command(path, 'awake', phase), stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=err, cwd=path, env={'PATH': '/usr/bin:/bin', 'LANG': 'C'})
                with vm.connect(path / 'qmp', process) as monitor, vm.connect(path / 'serial', process) as serial:
                    qmp, lines = vm.QMP(monitor), vm.Lines(serial)
                    s.block_evidence(qmp.call('query-block'), path)
                    loaded = startup(lines, {host_boot} | ({ready['boot']} if ready else set()), recovering=phase == 'recover')
                    if phase != 'recover':
                        first, _ = c.cycle(lines, qmp, 'awake', host_boot)
                        loaded_evidence(loaded, first, None)
                        serial.sendall(b'restart\n')
                        ready = record(lines, 'crash-ready', first['boot']); crash_evidence(ready, first['boot'])
                        if fault is not None: faults.fault_evidence(ready, fault)
                        process.kill()
                        if process.wait(timeout=10) != -signal.SIGKILL: raise RuntimeError('ACTUAL_OWNED_QEMU_SIGKILL_REQUIRED')
                        disk_sha = hashlib.sha256((path / 'state.raw').read_bytes()).hexdigest()
                        print('INBOUND_PERSIST_KILLED ' + json.dumps(dict(boot=ready['boot'], signal='SIGKILL',
                              normal_shutdown=False, disk_sha256=disk_sha)), flush=True)
                    else:
                        first = h.record(lines, 'observed', 'invalid')
                        blocked = record(lines, 'blocked', first['boot'])
                        refused_evidence(loaded, ready, first, blocked)
                        serial.sendall(b'clean\n'); done = h.record(lines, 'done', 'invalid')
                        if (done['boot'] != first['boot'] or done.get('interfaces') != ['lo']
                                or done.get('activation_allowed') is not False
                                or done['store_state']['ActiveState'] != 'inactive' or done['store_state']['Result'] != 'success'):
                            raise RuntimeError('REFUSED_GUEST_UNMOUNT_CLEANUP_REQUIRED')
                        print('PASS INBOUND_ACTUAL_SIGKILL_SAME_DISK_PARTIAL_SAVE_REFUSED_NO_AUTH_NO_LEASE', flush=True)
                        if fault is not None: print('PASS INBOUND_REAL_FILESYSTEM_ERROR_SAME_DISK_RECOVERY ' + fault, flush=True)
        finally: stop(process, path)


def invalid_evidence(denied, first, blocked, bad, expected):
    h.evidence(first)
    if (bad not in guest.INVALID or denied.get('reason') != guest.INVALID[bad]
            or denied.get('invalid_case') != bad or blocked.get('invalid_case') != bad
            or denied.get('disk_state') != expected or blocked.get('disk_state') != expected
            or denied['boot'] != first['boot'] or blocked['boot'] != first['boot']
            or denied.get('links') != [False, False] or blocked.get('ruleset_empty') is not True
            or blocked.get('saved_marker_present') is not False or blocked.get('activation_allowed') is not False
            or not denied['monotonic'] <= first['monotonic'] <= blocked['monotonic']):
        raise RuntimeError('EXACT_INVALID_DISK_REFUSAL_WITHOUT_REPAIR_REQUIRED')
    state = denied['store_state']
    gate = first['states']['gate']
    if (state['ActiveState'] != 'active' or state['Result'] != 'success'
            or any('kc-store.service' not in gate[k].split() for k in ('Requires', 'After'))
            or not 0 < int(first['states']['setup']['ExecMainExitTimestampMonotonic'])
                   <= int(state['ExecMainStartTimestampMonotonic']) < int(state['ExecMainExitTimestampMonotonic'])
                   <= int(gate['ExecMainStartTimestampMonotonic'])):
        raise RuntimeError('ACTUAL_INVALID_STORE_GATE_ORDER_REQUIRED')
    if set(blocked['states']) != {'link', 'check', 'lease', 'recover'}:
        raise RuntimeError('COMPLETE_INVALID_REFUSAL_SERVICES_REQUIRED')
    for value in blocked['states'].values():
        if value['ActiveState'] != 'inactive' or int(value['ExecMainStartTimestampMonotonic']) != 0:
            raise RuntimeError('INVALID_DISK_CANNOT_START_AUTH_OR_LEASE')


def invalid(path, bad, boots, expected):
    if bad not in guest.INVALID: raise ValueError('FIXED_INVALID_INBOUND_DISK_REQUIRED')
    process = None
    try:
        with (path / 'stderr').open('wb') as err:
            process = subprocess.Popen(command(path, 'awake', bad), stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=err, cwd=path, env={'PATH': '/usr/bin:/bin', 'LANG': 'C'})
            with vm.connect(path / 'qmp', process) as monitor, vm.connect(path / 'serial', process) as serial:
                qmp, lines = vm.QMP(monitor), vm.Lines(serial)
                s.block_evidence(qmp.call('query-block'), path)
                denied = startup(lines, boots, recovering=True)
                first = h.record(lines, 'observed', 'invalid')
                blocked = record(lines, 'blocked', first['boot'])
                invalid_evidence(denied, first, blocked, bad, expected)
                serial.sendall(b'clean\n'); done = h.record(lines, 'done', 'invalid')
                if (done['boot'] != first['boot'] or done.get('interfaces') != ['lo']
                        or done.get('activation_allowed') is not False
                        or done['store_state']['ActiveState'] != 'inactive' or done['store_state']['Result'] != 'success'):
                    raise RuntimeError('INVALID_DISK_UNMOUNT_CLEANUP_REQUIRED')
                print('PASS INBOUND_INVALID_DISK_REFUSED_UNCHANGED ' + bad + ' ' + first['boot'], flush=True)
                return first['boot']
    finally: stop(process, path)


def run_vm(kind):
    p.guard()
    if (os.environ.get('KC_INBOUND_PERSISTENCE_CI') != '1' or os.environ.get('KC_PERSISTENCE_CI') != '1'
            or kind not in ('normal', 'crash', 'invalid', *guest.FAULTS)):
        raise RuntimeError('FIXED_INBOUND_PERSISTENCE_CI_OPT_IN_REQUIRED')
    host_boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip(); host_ns = os.readlink('/proc/self/ns/net')
    with tempfile.TemporaryDirectory(prefix='kc-inbound-persist-') as value:
        path = Path(value)
        kernel = subprocess.run(['sudo', '-n', '/usr/bin/cat', '/boot/vmlinuz-' + os.uname().release],
                                check=True, capture_output=True, timeout=10).stdout
        if not 1024*1024 <= len(kernel) <= 64*1024*1024: raise RuntimeError('KERNEL_SIZE_BOUND')
        (path / 'vmlinuz').write_bytes(kernel)
        b.payload(path, inbound=True, inbound_lease=True, inbound_restart=True, inbound_persistence=True)
        if kind == 'invalid':
            boots = {host_boot}
            for bad in guest.INVALID:
                child = path / bad; child.mkdir(mode=0o700)
                for name in ('vmlinuz', 'initramfs'): (child / name).symlink_to(path / name)
                s.disk(child, bad, profile=guest.PROFILE)
                expected = guest.disk_state(SimpleNamespace(ROOT=child / 'seed', read_bytes=lambda name: (child / 'seed' / name).read_bytes()))
                boot = invalid(child, bad, boots, expected); boots.add(boot)
        else:
            s.disk(path, 'valid', profile=guest.PROFILE)
            if kind == 'normal': normal(path, host_boot)
            else: crash(path, host_boot, kind if kind in guest.FAULTS else None)
    if path.exists() or Path('/proc/sys/kernel/random/boot_id').read_text().strip() != host_boot or os.readlink('/proc/self/ns/net') != host_ns:
        raise RuntimeError('INBOUND_STORAGE_HOST_UNCHANGED_REQUIRED')
    print('PASS INBOUND_STORAGE_IMAGES_DISK_PROCESSES_CLEANED_HOST_UNCHANGED NO_LIVE_APPLY', flush=True)


class Tests(unittest.TestCase):
    def test_all_invalid_disk_fixtures_reject_the_intended_reason_without_repair(self):
        for bad, reason in guest.INVALID.items():
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as value, patch.object(persist, 'ROOT', Path(value)):
                files = s.seed_files(bad, profile=guest.PROFILE)
                for name, data in files.items(): (Path(value) / name).write_text(data)
                before = guest.disk_state(persist)
                try: persist.load_state(durable, '11111111-1111-4111-8111-111111111111', 10)
                except (ValueError, OSError) as exc:
                    actual = type(exc).__name__ if isinstance(exc, (FileNotFoundError, json.JSONDecodeError)) else str(exc)
                    self.assertEqual(actual, reason)
                else: self.fail('invalid fixture admitted')
                self.assertEqual(guest.disk_state(persist), before)
                for name, data in files.items(): self.assertEqual((Path(value) / name).read_text(), data)
        # In particular, mismatch/receipt-corrupt must not accidentally test
        # cross-profile rejection before reaching their intended bad receipt.
        for bad in ('mismatch', 'receipt-corrupt'):
            self.assertEqual(json.loads(s.seed_files(bad, profile=guest.PROFILE)['policy.json'])['profile'], guest.PROFILE)
            self.assertEqual(json.loads(s.seed_files(bad)['policy.json'])['profile'], 'tcp443-closed')

    def test_real_fault_paths_cannot_mutate_before_guard(self):
        for mode in guest.FAULTS:
            with patch.object(guest, 'fault_context', side_effect=RuntimeError('GUEST_REFUSED')), patch.object(guest.os, 'open') as opened:
                with self.assertRaisesRegex(RuntimeError, 'GUEST_REFUSED'): guest.prepare_fault(mode)
                opened.assert_not_called()
        with patch.object(subprocess, 'run') as run:
            with self.assertRaises((FileNotFoundError, RuntimeError)): guest.prepare_fault('enospc')
            run.assert_not_called()

    def test_fault_context_requires_exact_volume_mode_and_size(self):
        fake = SimpleNamespace(ROOT=Path('/state'))
        for current, root, size in (('normal', '/state', '131072'), ('enospc', '/tmp', '131072'), ('enospc', '/state', '1')):
            fake.ROOT = Path(root)
            with patch.object(guest, 'context', return_value=(fake, None, None, None, current)), \
                    patch.object(guest.Path, 'read_text', return_value=size), patch.object(guest, 'module') as module:
                with self.assertRaisesRegex(RuntimeError, 'FIXED_INBOUND_GUEST'): guest.fault_context('enospc')
                module.assert_not_called()

    def test_mount_mode_is_explicit_for_readonly_error_observation(self):
        fakeb = SimpleNamespace(composition=lambda: 'awake')
        fakep = SimpleNamespace(context=lambda: (fakeb, None, None), mounted=Mock(return_value=True),
                                crash_mode=lambda: None, fault_mode=lambda: None)
        flags = 'kc_inbound_boot=closed kc_inbound_restart=1 kc_inbound_lease=1'
        with patch.object(guest, 'module', return_value=fakep), patch.object(guest, 'phase', return_value='erofs'), \
                patch.object(guest.Path, 'read_text', return_value=flags):
            guest.context(); fakep.mounted.assert_called_with('rw')
            guest.context(readonly=True); fakep.mounted.assert_called_with('ro')

    def test_error_observation_rejects_wrong_errno_or_changed_state(self):
        for mode, expected_errno in guest.FAULTS.items():
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as value, patch.object(persist, 'ROOT', Path(value)):
                persist.atomic('policy.json', durable.policy())
                persist.atomic('receipt.json', dict(boot=s.OLD_BOOT, deadline_ns=1))
                snapshot = guest.state(persist, durable)
                prepared = dict(mode=mode, boot=s.OLD_BOOT, crash_state=snapshot, prepared={}, allocated_bytes=1, allocator_errno=None)
                fakeb = SimpleNamespace(STATE=Path(value), boot=lambda: s.OLD_BOOT, read=lambda name: prepared)
                helper = SimpleNamespace(filesystem=lambda *args: {})
                hfake = SimpleNamespace(context=lambda: (None, None, None))
                restart = SimpleNamespace(intact=lambda *args: ({}, [False, False]))
                with patch.object(guest, 'fault_context', return_value=(persist, fakeb, None, durable, helper)), \
                        patch.object(persist, 'mounted', return_value=True), \
                        patch.object(guest, 'module', side_effect=lambda name, path: hfake if name == 'inbound' else restart), \
                        patch.object(guest, 'emit') as emit:
                    with self.assertRaisesRegex(RuntimeError, 'EXACT_INBOUND_WRITE_ERROR'): guest.observe_fault(mode, OSError(errno.EIO, 'wrong error'))
                    emit.assert_not_called()
                    guest.observe_fault(mode, OSError(expected_errno, 'expected error'))
                    self.assertEqual(emit.call_args.kwargs['filesystem_fault']['errno'], expected_errno)
                    emit.reset_mock(); prepared['crash_state'] = dict(snapshot, receipt_sha256='changed')
                    with self.assertRaises(RuntimeError): guest.observe_fault(mode, OSError(expected_errno, 'expected error'))
                    emit.assert_not_called()

    def test_failed_fault_write_propagates_original_error_without_success_marker(self):
        with tempfile.TemporaryDirectory() as value, patch.object(persist, 'ROOT', Path(value)):
            persist.atomic('policy.json', durable.policy())
            loaded = dict(boot=s.OLD_BOOT, generation=0, policy_sha256=hashlib.sha256(persist.read_bytes('policy.json')).hexdigest())
            fake = SimpleNamespace(boot=lambda: s.OLD_BOOT, read=lambda name: loaded, write=Mock())
            hfake = SimpleNamespace(context=lambda: (None, None, None))
            restart = SimpleNamespace(intact=lambda *args: (dict(proof=dict(deadline_ns=1)), [False, False]))
            original = OSError(errno.ENOSPC, 'synthetic no space'); atomic = persist.atomic
            def write(name, data):
                if name == 'policy.json': raise original
                return atomic(name, data)
            with patch.object(guest, 'context', return_value=(persist, fake, None, durable, 'enospc')), \
                    patch.object(guest, 'module', side_effect=[hfake, restart]), patch.object(persist, 'atomic', side_effect=write), \
                    patch.object(guest, 'prepare_fault') as prepare, patch.object(guest, 'observe_fault') as observe:
                with self.assertRaises(OSError) as exc: guest.save()
                self.assertIs(exc.exception, original)
                prepare.assert_called_once_with('enospc'); observe.assert_called_once_with('enospc', original)
            fake.write.assert_not_called()
            with self.assertRaisesRegex(ValueError, 'ORPHAN'): persist.load_state(durable, s.NEW_BOOT, 2)

    def test_explicit_profile_binding_refuses_cross_profile_open_and_duplicate(self):
        raw = lambda x: json.dumps(x).encode()
        config = raw(durable.policy(1, s.OLD_BOOT)); receipt = raw(dict(boot=s.OLD_BOOT, deadline_ns=100))
        self.assertEqual(durable.pair(config, receipt, s.NEW_BOOT, 1)[2], 'PRIOR_BOOT_LEASE_REFUSED')
        for fn, data in ((durable.decode, raw(s.d.policy())), (s.d.decode, raw(durable.policy())),
                         (durable.decode, raw(dict(durable.policy(), activation_allowed=True))),
                         (durable.decode, raw(dict(durable.policy(), profile='open'))),
                         (durable.decode, config[:-1] + b',"generation":1}')):
            with self.assertRaises(ValueError): fn(data)
        for saved, boot in ((None, s.NEW_BOOT), (receipt, s.OLD_BOOT), (raw(dict(boot=s.NEW_BOOT, deadline_ns=1)), s.NEW_BOOT)):
            with self.assertRaises(ValueError): durable.pair(config, saved, boot, 1)
        with self.assertRaises(ValueError): s.d.policy(profile='open')

    def test_host_guards_and_fixed_cases_precede_mutations(self):
        with patch.object(subprocess, 'run') as run:
            with self.assertRaises((FileNotFoundError, RuntimeError)): guest.gate()
            run.assert_not_called()
        with patch.object(p, 'guard'), patch.dict(os.environ, {'KC_INBOUND_PERSISTENCE_CI': '0'}), patch.object(subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'OPT_IN'): run_vm('crash')
            run.assert_not_called()
        for flags in ('', 'kc_inbound_persistence=live', 'kc_inbound_persistence=normal kc_inbound_persistence=normal'):
            with patch.object(guest.Path, 'read_text', return_value=flags):
                with self.assertRaisesRegex(RuntimeError, 'OPT_IN'): guest.phase()
        with self.assertRaises(ValueError): command(Path('/not-created'), 'suspend', 'after-receipt')
        with self.assertRaises(ValueError): b.payload(Path('/not-created'), inbound_persistence=True)

    def test_both_profile_pairs_and_leftover_temporary_files_fail_closed(self):
        with tempfile.TemporaryDirectory() as value, patch.object(persist, 'ROOT', Path(value)):
            persist.atomic('policy.json', durable.policy())
            persist.atomic('receipt.json', dict(boot=s.OLD_BOOT, deadline_ns=1))
            with self.assertRaisesRegex(ValueError, 'ORPHAN'): persist.load_state(durable, s.NEW_BOOT, 2)
            persist.atomic('policy.json', durable.policy(1, s.OLD_BOOT))
            self.assertEqual(persist.load_state(durable, s.NEW_BOOT, 2)[2], 'PRIOR_BOOT_LEASE_REFUSED')
            (Path(value) / 'policy.json.next').write_bytes(b'{partial')
            with self.assertRaisesRegex(ValueError, 'INTERRUPTED'): persist.load_state(durable, s.NEW_BOOT, 2)

    def test_actual_mount_dependency_and_shutdown_keep_legacy_units_unchanged(self):
        with self.assertRaises(ValueError): h.guest.units(inbound_persistence=True)
        old = h.guest.units(inbound_lease=True, inbound_restart=True)
        self.assertNotIn('kc-store.service', old)
        new = h.guest.units(inbound_lease=True, inbound_restart=True, inbound_persistence=True)
        self.assertIn('Requires=kc-store.service\nAfter=kc-store.service', new['kc-gate.service'])
        self.assertIn('/persist_probe.py unmount', new['kc-store.service'])
        self.assertIn('After=shutdown.target umount.target', new['kc-shutdown-check.service'])

    def test_save_interruption_never_writes_policy_or_publishes_success(self):
        for fail in ('barrier', 'policy'):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as value, patch.object(persist, 'ROOT', Path(value)):
                persist.atomic('policy.json', durable.policy())
                loaded = dict(boot=s.OLD_BOOT, generation=0, policy_sha256=hashlib.sha256(persist.read_bytes('policy.json')).hexdigest())
                fake = SimpleNamespace(boot=lambda: s.OLD_BOOT, read=lambda name: loaded, write=Mock())
                hfake = SimpleNamespace(context=lambda: (None, None, None))
                restart = SimpleNamespace(intact=lambda *args: (dict(proof=dict(deadline_ns=1)), [False, False]))
                mode = 'after-receipt' if fail == 'barrier' else 'normal'
                atomic = persist.atomic
                def write(name, data):
                    if fail == 'policy' and name == 'policy.json': raise OSError('synthetic write failure')
                    return atomic(name, data)
                with patch.object(guest, 'context', return_value=(persist, fake, None, durable, mode)), \
                        patch.object(guest, 'module', side_effect=[hfake, restart]), \
                        patch.object(guest, 'await_crash', side_effect=RuntimeError('CRASH_STOP')), patch.object(persist, 'atomic', side_effect=write):
                    with self.assertRaises((RuntimeError, OSError)): guest.save()
                fake.write.assert_not_called()
                self.assertEqual(durable.decode(persist.read_bytes('policy.json')), durable.policy())
                with self.assertRaisesRegex(ValueError, 'ORPHAN'): persist.load_state(durable, s.NEW_BOOT, 2)

    def test_crash_barrier_rejects_open_masked_published_or_wrong_boot(self):
        row = dict(boot=s.OLD_BOOT, activation_allowed=False, qualification=[False]*2, profile_unchanged=True,
                   guards_absent=True, saved_marker_present=False,
                   crash_state=dict(generation=0, receipt_boot=s.OLD_BOOT, policy_sha256='a'*64, receipt_sha256='b'*64))
        crash_evidence(row, s.OLD_BOOT)
        for changed in (dict(qualification=[True, False]), dict(profile_unchanged=False), dict(guards_absent=False),
                        dict(saved_marker_present=True), dict(boot=s.NEW_BOOT), dict(activation_allowed=True),
                        dict(crash_state=dict(row['crash_state'], receipt_sha256='bad'))):
            with self.assertRaises(RuntimeError): crash_evidence(dict(row, **changed), s.OLD_BOOT)

    def test_recovery_rejects_changed_bytes_same_boot_or_started_services(self):
        states = dict(setup=dict(ActiveState='active', ExecMainStatus='0'))
        for name, dep in (('gate', 'setup'), ('link', 'gate'), ('check', 'link')):
            states[name] = dict(Requires='kc-' + dep + '.service', After='kc-' + dep + '.service',
                                ActiveState='inactive', ExecMainStartTimestampMonotonic='0')
        states['gate'].update(ActiveState='failed', Result='exit-code', ExecMainStatus='1')
        first = dict(case='invalid', boot=s.NEW_BOOT, monotonic=2, states=states, links=[False]*2,
                     link_entered=False, sealed=None, linked=None, checked=None, activation_allowed=False)
        ready = dict(boot=s.OLD_BOOT, crash_state=dict(policy_sha256='a'*64, receipt_sha256='b'*64))
        denied = dict(boot=s.NEW_BOOT, monotonic=1, reason='ORPHAN_RECEIPT_REFUSED', links=[False]*2,
                      crash_state=ready['crash_state'])
        blocked = dict(boot=s.NEW_BOOT, monotonic=3, ruleset_empty=True, saved_marker_present=False,
                       activation_allowed=False, states={n: dict(ActiveState='inactive', ExecMainStartTimestampMonotonic='0')
                           for n in ('link', 'check', 'lease', 'recover')})
        refused_evidence(denied, ready, first, blocked)
        for change in (dict(boot=s.OLD_BOOT), dict(reason='other'), dict(links=[True, False]),
                       dict(crash_state=dict(ready['crash_state'], receipt_sha256='c'*64))):
            with self.assertRaises(RuntimeError): refused_evidence(dict(denied, **change), ready, first, blocked)
        for change in (dict(ruleset_empty=False), dict(saved_marker_present=True), dict(states={}), dict(monotonic=0)):
            with self.assertRaises(RuntimeError): refused_evidence(denied, ready, first, dict(blocked, **change))
        altered = copy.deepcopy(blocked); altered['states']['lease']['ExecMainStartTimestampMonotonic'] = '1'
        with self.assertRaises(RuntimeError): refused_evidence(denied, ready, first, altered)

    def test_invalid_evidence_rejects_repair_wrong_reason_or_started_services(self):
        states = dict(setup=dict(ActiveState='active', ExecMainStatus='0', ExecMainExitTimestampMonotonic='1'))
        for name, dep in (('gate', 'setup'), ('link', 'gate'), ('check', 'link')):
            states[name] = dict(Requires='kc-' + dep + '.service', After='kc-' + dep + '.service',
                                ActiveState='inactive', ExecMainStartTimestampMonotonic='0')
        states['gate'].update(ActiveState='failed', Result='exit-code', ExecMainStatus='1',
                             Requires='kc-setup.service kc-store.service', After='kc-setup.service kc-store.service',
                             ExecMainStartTimestampMonotonic='4')
        first = dict(case='invalid', boot=s.NEW_BOOT, monotonic=2, states=states, links=[False]*2,
                     link_entered=False, sealed=None, linked=None, checked=None, activation_allowed=False)
        expected = dict.fromkeys(('policy.json', 'receipt.json', 'policy.json.next', 'receipt.json.next'))
        denied = dict(boot=s.NEW_BOOT, monotonic=1, reason='FileNotFoundError', links=[False]*2,
                      invalid_case='missing', disk_state=expected,
                      store_state=dict(ActiveState='active', Result='success',
                          ExecMainStartTimestampMonotonic='2', ExecMainExitTimestampMonotonic='3'))
        blocked = dict(boot=s.NEW_BOOT, monotonic=3, ruleset_empty=True, saved_marker_present=False,
                       invalid_case='missing', disk_state=expected, activation_allowed=False,
                       states={n: dict(ActiveState='inactive', ExecMainStartTimestampMonotonic='0')
                               for n in ('link', 'check', 'lease', 'recover')})
        invalid_evidence(denied, first, blocked, 'missing', expected)
        for change in (dict(reason='other'), dict(disk_state={}), dict(invalid_case='corrupt'), dict(links=[True, False])):
            with self.assertRaises(RuntimeError): invalid_evidence(dict(denied, **change), first, blocked, 'missing', expected)
        for change in (dict(disk_state={}), dict(states={}), dict(saved_marker_present=True), dict(ruleset_empty=False)):
            with self.assertRaises(RuntimeError): invalid_evidence(denied, first, dict(blocked, **change), 'missing', expected)
        altered = copy.deepcopy(blocked); altered['states']['lease']['ExecMainStartTimestampMonotonic'] = '1'
        with self.assertRaises(RuntimeError): invalid_evidence(denied, first, altered, 'missing', expected)
        altered = copy.deepcopy(first); altered['states']['gate']['ExecMainStartTimestampMonotonic'] = '1'
        with self.assertRaises(RuntimeError): invalid_evidence(denied, altered, blocked, 'missing', expected)

    def test_crash_timeout_never_returns_to_writer(self):
        with tempfile.TemporaryDirectory() as value, patch.object(persist, 'ROOT', Path(value)):
            persist.atomic('policy.json', durable.policy())
            sha = persist.atomic('receipt.json', dict(boot=s.OLD_BOOT, deadline_ns=1))
            fake = SimpleNamespace(guard=Mock(), composition=lambda: 'awake', boot=lambda: s.OLD_BOOT, STATE=Path(value))
            restart = SimpleNamespace(intact=lambda *args: ({}, [False, False]))
            with patch.object(guest, 'phase', return_value='after-receipt'), patch.object(persist, 'mounted', return_value=True), \
                    patch.object(guest, 'module', return_value=restart), patch.object(guest, 'emit') as emit, \
                    patch.object(guest.time, 'monotonic', side_effect=[0, 31]):
                with self.assertRaisesRegex(RuntimeError, 'TIMEOUT_NO_SAVE'):
                    guest.await_crash(persist, fake, None, None, None, durable, sha)
                fake.guard.assert_called_once(); self.assertEqual(emit.call_args.args[1], 'crash-ready')
            self.assertEqual(durable.decode(persist.read_bytes('policy.json')), durable.policy())

    def test_command_has_one_owned_disk_and_no_external_nic(self):
        with tempfile.TemporaryDirectory() as value:
            path = Path(value)
            with (path / 'state.raw').open('xb') as stream: stream.truncate(s.SIZE)
            for phase in guest.PHASES:
                args = command(path, 'awake', phase)
                self.assertEqual(args[args.index('-nic') + 1], 'none')
                self.assertEqual(args.count('-drive'), 1)
                flags = args[args.index('-append') + 1]
                self.assertIn('kc_inbound_persistence=' + phase, flags)
                self.assertIn('kc_inbound_boot=' + ('invalid' if phase == 'recover' or phase in guest.INVALID else 'closed'), flags)
                self.assertNotIn('kc_systemd_restart=', flags)

    def test_durable_startup_rejects_mixed_boot_and_reversed_clock(self):
        first = dict(boot=s.NEW_BOOT, monotonic=1, activation_allowed=False)
        rows = [dict(first, monotonic=x) for x in (1, 2, 4, 5)]
        loaded = dict(first, monotonic=3)
        with patch.object(h, 'record', side_effect=rows), patch(__name__ + '.record', return_value=loaded):
            self.assertEqual(startup(None, {s.OLD_BOOT}), loaded)
        for change in (dict(boot=s.OLD_BOOT), dict(monotonic=float('nan')), dict(monotonic=1), dict(activation_allowed=True)):
            with patch.object(h, 'record', side_effect=rows), patch(__name__ + '.record', return_value=dict(loaded, **change)):
                with self.assertRaises(RuntimeError): startup(None, {s.OLD_BOOT})


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--vm': run_vm(sys.argv[2])
    else: unittest.main(verbosity=2)
