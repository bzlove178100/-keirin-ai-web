"""Actual systemd startup, authenticated SSH and immutable expiry in one guest."""
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
spec = importlib.util.spec_from_file_location('boot', HERE / 'test_secret_custody_systemd_boot.py')
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
p, vm = b.p, b.vm


def command(path, boot_case, mode):
    if mode not in ('awake', 'suspend'): raise ValueError('FIXED_LEASE_MODE_REQUIRED')
    args = b.command(path, boot_case)
    args[args.index('-append') + 1] += ' kc_systemd_lease=' + mode + ' kc_ssh_probe=1 kc_boottime_guard=1 end=8'
    return args


def record(lines, event, mode, boot):
    deadline = time.monotonic() + 75
    diagnostic = []
    while True:
        try: line = lines.line(deadline)
        except Exception:
            print('SYSTEMD_LEASE_DIAGNOSTIC ' + '\n'.join(diagnostic)[-6000:], flush=True); raise
        diagnostic.append(line[-1500:]); diagnostic = diagnostic[-30:]
        if line.startswith(('SYSTEMD_LEASE_FAIL', 'SYSTEMD_BOOT_STAGE_ERROR')) or 'Kernel panic' in line:
            raise RuntimeError('COMPOSED_GUEST_FAILED ' + '\n'.join(diagnostic)[-6000:])
        if not line.startswith('SYSTEMD_LEASE_RECORD '): continue
        row = json.loads(line[len('SYSTEMD_LEASE_RECORD '):])
        if (row.get('event') != event or row.get('mode') != mode or row.get('boot') != boot
                or type(row.get('marker')) is not int or row['marker'] != 1
                or any(type(row.get(k)) not in (int, float) or not math.isfinite(row[k]) or row[k] < 0 for k in ('monotonic', 'boottime'))):
            raise RuntimeError('COMPOSED_RECORD_SEQUENCE_REQUIRED')
        print(line, flush=True); return row


def service_evidence(row, boot_case):
    if row.get('boot_case') != boot_case or row.get('activation_allowed') is not False: raise RuntimeError('MATCHED_SERVICE_COMPLETION_REQUIRED')
    states = row['states']
    for name, dependency in (('observe', 'link'), ('auth', 'observe'), ('lease', 'auth')):
        for prop in ('Requires', 'After'):
            if 'kc-' + dependency + '.service' not in states[name][prop].split(): raise RuntimeError('COMPOSED_DEPENDENCY_REQUIRED')
        if boot_case == 'closed':
            if (states[name]['ActiveState'] != 'active' or states[name]['ExecMainStatus'] != '0'
                    or not 0 < int(states[dependency]['ExecMainExitTimestampMonotonic']) <= int(states[name]['ExecMainStartTimestampMonotonic'])):
                raise RuntimeError('COMPOSED_SERVICE_ORDER_REQUIRED')
        elif int(states[name]['ExecMainStartTimestampMonotonic']) != 0 or states[name]['ActiveState'] != 'inactive':
            raise RuntimeError('FAILED_BOOT_MUST_PREVENT_COMPOSED_SERVICES')


def sequence_evidence(first, ready, refused, released, before):
    p.ssh_evidence(ready, initial=True)
    if (refused.get('new_connections') != [False, False, True, True] or refused.get('policy_unchanged') is not True
            or released.get('boottime_guard') != before.get('boottime_guard') or released.get('lease_start') != before.get('lease_start')
            or before.get('qualification') != [True]*4 or before.get('management') != [True]*4
            or not 0 <= before['monotonic'] - before['lease_start']['monotonic'] < 3):
        raise RuntimeError('CLOSED_AUTHENTICATED_LEASE_SEQUENCE_REQUIRED')
    rows = (first, ready, refused, released, before)
    for earlier, later in zip(rows, rows[1:]):
        if earlier['boot'] != later['boot'] or later['monotonic'] < earlier['monotonic']: raise RuntimeError('SAME_ORDERED_BOOT_REQUIRED')


def case(path, boot_case, mode, host_boot):
    process = None
    try:
        with (path / 'stderr').open('wb') as err:
            process = subprocess.Popen(command(path, boot_case, mode), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                       stderr=err, cwd=path, env={'PATH': '/usr/bin:/bin', 'LANG': 'C'})
            with vm.connect(path / 'qmp', process) as monitor, vm.connect(path / 'serial', process) as serial:
                qmp, lines = vm.QMP(monitor), vm.Lines(serial)
                if qmp.call('query-block') != [] or qmp.call('query-current-machine').get('wakeup-suspend-support') is not True: raise RuntimeError('DISKLESS_S3_MACHINE_REQUIRED')
                first = b.record(lines, 'observed', boot_case); b.evidence(first); boot = first['boot']
                if boot == host_boot: raise RuntimeError('DISTINCT_GUEST_REQUIRED')
                if boot_case == 'closed':
                    ready = record(lines, 'ssh_ready', mode, boot)
                    refused = record(lines, 'release_refused', mode, boot)
                    released = record(lines, 'released', mode, boot)
                    before = record(lines, 'before', mode, boot)
                    sequence_evidence(first, ready, refused, released, before)
                    started = time.monotonic()
                    if mode == 'suspend':
                        qmp.event('SUSPEND', time.monotonic() + 20)
                        if qmp.call('query-status').get('status') != 'suspended': raise RuntimeError('REAL_S3_REQUIRED')
                        time.sleep(vm.SUSPEND_SECONDS)
                        qmp.call('system_wakeup'); qmp.event('WAKEUP', time.monotonic() + 10)
                    after = record(lines, 'after', mode, boot)
                    result = p.outcome(mode, before, after, time.monotonic() - started, boottime_guard=True)
                    p.ssh_evidence(record(lines, 'ssh_after', mode, boot))
                    late = record(lines, 'awake_expired', mode, boot)
                    if late.get('qualification') != [False]*4 or late.get('management') != [True]*4: raise RuntimeError('LATE_CLOSED_REQUIRED')
                    print('PASS SYSTEMD_AUTHENTICATED_IMMUTABLE_LEASE ' + mode + ' ' + result, flush=True)
                service_evidence(record(lines, 'completed', mode, boot), boot_case)
                serial.sendall(b'clean\n')
                done = b.record(lines, 'done', boot_case)
                if done['boot'] != boot or done.get('interfaces') != ['lo'] or done.get('activation_allowed') is not False: raise RuntimeError('COMPOSED_CLEANUP_REQUIRED')
                print('PASS SYSTEMD_LEASE_CASE ' + boot_case + ' ' + mode, flush=True)
    finally:
        if process is not None:
            process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
        for name in ('qmp', 'serial'): (path / name).unlink(missing_ok=True)


def run_vm():
    p.guard()
    if os.environ.get('KC_SYSTEMD_LEASE_CI') != '1': raise RuntimeError('SYSTEMD_LEASE_OPT_IN_REQUIRED')
    host_boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip(); host_netns = os.readlink('/proc/self/ns/net')
    with tempfile.TemporaryDirectory(prefix='kc-systemd-lease-') as value:
        path = Path(value)
        kernel = subprocess.run(['sudo', '-n', '/usr/bin/cat', '/boot/vmlinuz-' + os.uname().release], check=True, capture_output=True, timeout=10).stdout
        if not 1024*1024 <= len(kernel) <= 64*1024*1024: raise RuntimeError('KERNEL_SIZE_BOUND')
        (path / 'vmlinuz').write_bytes(kernel); b.payload(path, composed=True)
        for boot_case, mode in (('closed', 'awake'), ('closed', 'suspend'), ('missing', 'awake'), ('invalid', 'awake')): case(path, boot_case, mode, host_boot)
    if path.exists() or Path('/proc/sys/kernel/random/boot_id').read_text().strip() != host_boot or os.readlink('/proc/self/ns/net') != host_netns: raise RuntimeError('HOST_UNCHANGED_CLEANUP_REQUIRED')
    print('PASS SYSTEMD_LEASE_IMAGES_PROCESSES_CLEANED_HOST_UNCHANGED NO_LIVE_APPLY', flush=True)


class Tests(unittest.TestCase):
    def test_suspend_marker_requires_preserved_same_boot_file(self):
        guest = b.module('composed', HERE / 'fixtures/secret_custody_composed_guest.py')
        with tempfile.TemporaryDirectory() as directory:
            marker, boot = Path(directory) / 'marker', Path(directory) / 'boot'
            boot.write_text('boot-one\n')
            self.assertEqual(guest.marker(marker, boot), 0)
            marker.write_text('boot-one'); self.assertEqual(guest.marker(marker, boot), 1)
            boot.write_text('boot-two\n'); self.assertEqual(guest.marker(marker, boot), 0)
            marker.unlink(); self.assertEqual(guest.marker(marker, boot), 0)

    def test_original_units_unchanged_and_composition_requires_link_auth(self):
        self.assertNotIn('kc-lease.service', b.u.units())
        units = b.u.units(composed=True)
        self.assertIn('Requires=kc-auth.service\nAfter=kc-auth.service', units['kc-lease.service'])
        self.assertIn('Requires=kc-observe.service\nAfter=kc-observe.service', units['kc-auth.service'])
        self.assertIn('Wants=kc-lease.service', units['kc-report.service'])

    def test_host_refusal_before_actions(self):
        ssh = b.module('ssh', HERE / 'fixtures/secret_custody_ssh_guest.py')
        with patch.object(subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'FIXED_SSH_GUEST_REQUIRED'): ssh.prepare(systemd=True)
            run.assert_not_called()
        with patch.object(p, 'guard'), patch.dict(os.environ, {'KC_SYSTEMD_LEASE_CI': '0'}), patch.object(subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'OPT_IN'): run_vm()
            run.assert_not_called()
        with self.assertRaises(ValueError): command(Path('/tmp/owned'), 'closed', 'arbitrary')

    def test_failed_startup_cannot_claim_downstream_execution(self):
        states = {'link': {}}
        for name, dep in (('observe', 'link'), ('auth', 'observe'), ('lease', 'auth')):
            states[name] = dict(Requires='kc-' + dep + '.service', After='kc-' + dep + '.service', ActiveState='inactive', ExecMainStartTimestampMonotonic='0')
        row = dict(boot_case='missing', activation_allowed=False, states=states)
        service_evidence(row, 'missing')
        states['lease']['ExecMainStartTimestampMonotonic'] = '1'
        with self.assertRaisesRegex(RuntimeError, 'FAILED_BOOT'): service_evidence(row, 'missing')

    def test_success_requires_actual_service_time_order(self):
        states = {'link': {'ExecMainExitTimestampMonotonic': '1'}}
        for index, (name, dep) in enumerate((('observe', 'link'), ('auth', 'observe'), ('lease', 'auth')), 1):
            states[name] = dict(Requires='kc-' + dep + '.service', After='kc-' + dep + '.service', ActiveState='active', ExecMainStatus='0', ExecMainStartTimestampMonotonic=str(index*2), ExecMainExitTimestampMonotonic=str(index*2+1))
        row = dict(boot_case='closed', activation_allowed=False, states=states)
        service_evidence(row, 'closed')
        states['lease']['ExecMainStartTimestampMonotonic'] = '4'
        with self.assertRaisesRegex(RuntimeError, 'ORDER'): service_evidence(row, 'closed')


if __name__ == '__main__':
    if sys.argv[1:] == ['--vm']: run_vm()
    else: unittest.main(verbosity=2)
