"""Actual sealed inbound startup, immutable expiry and unmasked recovery matrix."""
import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('inbound_boot', HERE / 'test_secret_custody_inbound_boot.py')
h = importlib.util.module_from_spec(spec); spec.loader.exec_module(h)
b, p, vm = h.b, h.p, h.vm
guest = b.module('lease_guest', HERE / 'fixtures/secret_custody_inbound_lease_guest.py')


def command(path, mode):
    if mode not in ('awake', 'suspend'): raise ValueError('FIXED_INBOUND_LEASE_MODE_REQUIRED')
    args = h.command(path, 'closed')
    args[args.index('-append')+1] += ' kc_inbound_lease=1 kc_systemd_lease=' + mode + ' kc_boottime_guard=1 end=10'
    return args


def record(lines, event, mode, boot):
    diagnostic, deadline = [], time.monotonic() + 100
    while True:
        try: line = lines.line(deadline)
        except Exception:
            print('INBOUND_LEASE_DIAGNOSTIC ' + '\n'.join(diagnostic)[-8000:], flush=True); raise
        diagnostic.append(line[-2000:]); diagnostic = diagnostic[-40:]
        if line.startswith('INBOUND_BOOT_STAGE_ERROR') or 'Kernel panic' in line or 'Freezing execution' in line:
            raise RuntimeError('INBOUND_LEASE_GUEST_FAILED ' + '\n'.join(diagnostic)[-8000:])
        if not line.startswith('INBOUND_LEASE_RECORD '): continue
        row = json.loads(line[len('INBOUND_LEASE_RECORD '):])
        if (row.get('event') != event or row.get('mode') != mode or row.get('boot') != boot
                or row.get('marker') != 1 or type(row.get('marker')) is not int
                or any(type(row.get(k)) not in (int, float) or not math.isfinite(row[k]) or row[k] < 0
                       for k in ('monotonic', 'boottime'))):
            raise RuntimeError('ORDERED_INBOUND_LEASE_RECORD_REQUIRED')
        print(line, flush=True); return row


def expiry(mode, before, after, elapsed):
    if before.get('qualification') != [True]*4 or not 0 <= before['monotonic'] - before['lease_start']['monotonic'] < 3:
        raise RuntimeError('LIVE_INBOUND_QUALIFICATION_REQUIRED')
    p.ssh_evidence(after['ssh'])
    # These four management observations are actual authenticated existing/fresh
    # SSH results, not the outbound port-22 echo controls used by the old fixture.
    measured = dict(after, management=after['ssh']['established'] + after['ssh']['fresh'])
    return p.outcome(mode, before, measured, elapsed, boottime_guard=True)


def recovery(restored, recovered, completed, first):
    p.ssh_evidence(restored['ssh'])
    if (restored.get('guards_unchanged') is not True or restored.get('qualification') != [False]*4
            or recovered.get('guards_removed') is not True or recovered.get('policy_unchanged') is not True
            or completed.get('activation_allowed') is not False):
        raise RuntimeError('UNMASKED_RESTORATION_REQUIRED')
    # Reuse all 28 strict packet/counter and 16 active-loopback requirements.
    if set(recovered.get('checked', {})) != {'packets', 'loopback'}:
        raise RuntimeError('COMPLETE_RECOVERED_MATRIX_REQUIRED')
    checked = dict(first['checked'], **recovered['checked'])
    h.evidence(dict(first, checked=checked))
    states = completed['states']
    for name, dep in (('lease', 'check'), ('recover', 'lease')):
        if (any('kc-' + dep + '.service' not in states[name][k].split() for k in ('Requires', 'After'))
                or states[name]['ActiveState'] != 'active' or states[name]['ExecMainStatus'] != '0'
                or not 0 < int(states[dep]['ExecMainExitTimestampMonotonic']) <= int(states[name]['ExecMainStartTimestampMonotonic'])):
            raise RuntimeError('ACTUAL_RECOVERY_SERVICE_ORDER_REQUIRED')


def cycle(lines, qmp, mode, host_boot, *, before_check=None):
    matrix = h.record(lines, 'matrix', 'closed'); boot = matrix['boot']
    if boot == host_boot: raise RuntimeError('DISTINCT_INBOUND_LEASE_BOOT_REQUIRED')
    ready = record(lines, 'ssh_ready', mode, boot); p.ssh_evidence(ready['ssh'], initial=True)
    before = record(lines, 'before', mode, boot); started = time.monotonic()
    if before_check is not None: before_check(before)
    if mode == 'suspend':
        qmp.event('SUSPEND', time.monotonic()+20)
        if qmp.call('query-status').get('status') != 'suspended': raise RuntimeError('REAL_S3_REQUIRED')
        time.sleep(vm.SUSPEND_SECONDS)
        qmp.call('system_wakeup'); qmp.event('WAKEUP', time.monotonic()+10)
    after = record(lines, 'after', mode, boot); outcome = expiry(mode, before, after, time.monotonic()-started)
    restored = record(lines, 'restored', mode, boot)
    recovered = record(lines, 'recovered', mode, boot)
    completed = record(lines, 'completed', mode, boot)
    first = h.record(lines, 'observed', 'closed'); h.evidence(first); h.matrix_sequence(matrix, first)
    recovery(restored, recovered, completed, first)
    rows = (matrix, ready, before, after, restored, recovered, completed, first)
    if any(a['boot'] != z['boot'] or a['monotonic'] > z['monotonic'] for a,z in zip(rows, rows[1:])):
        raise RuntimeError('SAME_ORDERED_COMPOSITION_REQUIRED')
    return first, outcome


def case(path, mode, host_boot):
    process = None
    try:
        with (path / 'stderr').open('wb') as err:
            process = subprocess.Popen(command(path, mode), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                       stderr=err, cwd=path, env={'PATH':'/usr/bin:/bin', 'LANG':'C'})
            with vm.connect(path / 'qmp', process) as monitor, vm.connect(path / 'serial', process) as serial:
                qmp, lines = vm.QMP(monitor), vm.Lines(serial)
                if qmp.call('query-block') != [] or qmp.call('query-current-machine').get('wakeup-suspend-support') is not True:
                    raise RuntimeError('DISKLESS_S3_MACHINE_REQUIRED')
                first, outcome = cycle(lines, qmp, mode, host_boot); boot = first['boot']
                serial.sendall(b'clean\n'); done = h.record(lines, 'done', 'closed')
                if done['boot'] != boot or done.get('interfaces') != ['lo'] or done.get('activation_allowed') is not False:
                    raise RuntimeError('INBOUND_LEASE_CLEANUP_REQUIRED')
                print('PASS INBOUND_STARTUP_EXPIRY_UNMASKED_RECOVERY ' + mode + ' ' + outcome, flush=True)
                return boot
    finally:
        if process is not None:
            process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
        for name in ('qmp', 'serial'): (path/name).unlink(missing_ok=True)


def run_vm():
    p.guard()
    if os.environ.get('KC_INBOUND_LEASE_CI') != '1': raise RuntimeError('INBOUND_LEASE_OPT_IN_REQUIRED')
    host_boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip(); host_ns = os.readlink('/proc/self/ns/net')
    with tempfile.TemporaryDirectory(prefix='kc-inbound-lease-') as value:
        path = Path(value)
        kernel = subprocess.run(['sudo','-n','/usr/bin/cat','/boot/vmlinuz-'+os.uname().release],check=True,capture_output=True,timeout=10).stdout
        if not 1024*1024 <= len(kernel) <= 64*1024*1024: raise RuntimeError('KERNEL_SIZE_BOUND')
        (path/'vmlinuz').write_bytes(kernel); b.payload(path, inbound=True, inbound_lease=True)
        boots = [case(path, mode, host_boot) for mode in ('awake','suspend')]
        if len(set(boots)) != 2: raise RuntimeError('FRESH_COMPOSITION_BOOTS_REQUIRED')
    if path.exists() or Path('/proc/sys/kernel/random/boot_id').read_text().strip() != host_boot or os.readlink('/proc/self/ns/net') != host_ns:
        raise RuntimeError('HOST_UNCHANGED_CLEANUP_REQUIRED')
    print('PASS INBOUND_LEASE_IMAGES_PROCESSES_CLEANED_HOST_UNCHANGED NO_LIVE_APPLY', flush=True)


class Tests(unittest.TestCase):
    def test_admission_rejects_missing_changed_expired_or_extended_guards(self):
        args = [['policy'], ['policy'], ['lease'], ['lease'], dict(loader_exits=True, deadline_ns=8_000_000_000), ['tc'], ['tc'], 1]
        guest.admission(*args)
        for index, value in ((0, []),(2, []),(4, None),(5, []),(7, 7),(7, -1),(7, float('nan'))):
            changed = copy.deepcopy(args); changed[index] = value
            with self.assertRaisesRegex(RuntimeError,'GUARDS'): guest.admission(*changed)

    def test_fixed_image_mode_host_refusal_and_original_units(self):
        with patch.object(p, 'guard'), patch.dict(os.environ, {'KC_INBOUND_LEASE_CI':'0'}), patch.object(subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError,'OPT_IN'): run_vm()
            run.assert_not_called()
        with self.assertRaises(ValueError): command(Path('/tmp/owned'),'live')
        with self.assertRaises(ValueError): b.payload(Path('/tmp/owned'),inbound_lease=True)
        self.assertNotIn('kc-lease.service',h.guest.units())
        units = h.guest.units(inbound_lease=True)
        for name, dep in (('lease','check'),('recover','lease')):
            self.assertIn('Requires=kc-'+dep+'.service\nAfter=kc-'+dep+'.service',units['kc-'+name+'.service'])
        args = command(Path('/tmp/owned'),'suspend')
        self.assertEqual(args[args.index('-nic')+1],'none'); self.assertNotIn('-drive',args)

    def test_expiry_requires_real_authenticated_management_and_original_deadline(self):
        proof = dict(deadline_ns=9_000_000_000,program_id=1,ifindex=2,tag='0123456789abcdef',loader_exits=True)
        before = dict(boot='same',marker=1,monotonic=2,boottime=2,lease_start=dict(monotonic=1,boottime=1),qualification=[True]*4,boottime_guard=proof)
        after = dict(boot='same',marker=1,monotonic=11,boottime=11,probe_finished_monotonic=12,qualification=[False]*4,
                     ssh=dict(established=[True]*2,fresh=[True]*2),rule_identity_unchanged=True,tc_identity_unchanged=True,
                     boottime_guard=proof,outcome='BOOTTIME_AWAKE_EXPIRY_CONFIRMED')
        expiry('awake',before,after,10)
        for change in ({'qualification':[True]*4},{'tc_identity_unchanged':False},{'ssh':dict(established=[False]*2,fresh=[True]*2)},
                       {'boottime_guard':dict(proof,deadline_ns=10_000_000_000)}):
            with self.assertRaises(RuntimeError): expiry('awake',before,dict(after,**change),10)
        after.update(monotonic=3,boottime=15,probe_finished_monotonic=4,outcome='BOOTTIME_SUSPEND_EXPIRY_OBSERVED')
        expiry('suspend',before,after,13)
        with self.assertRaises(RuntimeError): expiry('suspend',before,dict(after,marker=0),13)


if __name__ == '__main__':
    if sys.argv[1:] == ['--vm']: run_vm()
    else: unittest.main(verbosity=2)
