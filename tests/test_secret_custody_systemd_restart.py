"""Composed expiry -> normal shutdown -> fresh sealed boot -> normal poweroff."""
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
spec = importlib.util.spec_from_file_location('composed', HERE / 'test_secret_custody_systemd_lease.py')
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
b, p, vm = c.b, c.p, c.vm


def record(lines, event, boot, target):
    deadline = time.monotonic() + 75
    diagnostic = []
    while True:
        try: line = lines.line(deadline)
        except Exception:
            print('SYSTEMD_RESTART_DIAGNOSTIC ' + '\n'.join(diagnostic)[-6000:], flush=True); raise
        diagnostic.append(line[-1500:]); diagnostic = diagnostic[-30:]
        if line.startswith(('SYSTEMD_RESTART_FAIL', 'SYSTEMD_BOOT_STAGE_ERROR', 'SYSTEMD_LEASE_FAIL')) or 'Kernel panic' in line:
            raise RuntimeError('NORMAL_SHUTDOWN_FAILED ' + '\n'.join(diagnostic)[-6000:])
        if not line.startswith('SYSTEMD_RESTART_RECORD '): continue
        row = json.loads(line[len('SYSTEMD_RESTART_RECORD '):])
        if (row.get('event') != event or row.get('boot') != boot or row.get('target') != target
                or row.get('activation_allowed') is not False or not math.isfinite(row['monotonic'])):
            raise RuntimeError('MATCHED_RESTART_SEQUENCE_REQUIRED')
        print(line, flush=True); return row


def evidence(request, down, stopped):
    if not request['monotonic'] <= down['monotonic'] <= stopped['monotonic']:
        raise RuntimeError('ORDERED_SHUTDOWN_REQUIRED')
    for row in (request, down):
        if row.get('qualification') != [False, False] or row.get('guards_unchanged') is not True:
            raise RuntimeError('CLOSED_UNCHANGED_SHUTDOWN_REQUIRED')
    if (down.get('link_up') is not False or stopped.get('inet_guard_unchanged') is not True
            or stopped.get('peer_stopped') is not True or stopped.get('ssh_stopped') is not True
            or not request['monotonic'] <= stopped['link_stopped_at'] <= down['monotonic']
            or any(v['ActiveState'] != 'inactive' or v['Result'] != 'success' for v in stopped['states'].values())
            or set(stopped['states']) != {'report', 'lease', 'auth', 'observe', 'link', 'gate', 'setup'}):
        raise RuntimeError('RETAINED_GUARD_AND_SERVICE_STOP_REQUIRED')


def case(path, mode, host_boot):
    process = None
    try:
        args = c.command(path, 'closed', mode)
        args[args.index('-append') + 1] += ' kc_systemd_restart=1 end=9'
        with (path / 'stderr').open('wb') as err:
            process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                       stderr=err, cwd=path, env={'PATH': '/usr/bin:/bin', 'LANG': 'C'})
            with vm.connect(path / 'qmp', process) as monitor, vm.connect(path / 'serial', process) as serial:
                qmp, lines = vm.QMP(monitor), vm.Lines(serial)
                if qmp.call('query-block') != [] or qmp.call('query-current-machine').get('wakeup-suspend-support') is not True:
                    raise RuntimeError('DISKLESS_S3_MACHINE_REQUIRED')
                boots = {host_boot}
                for command, target, event in ((b'restart\n', 'reboot.target', 'RESET'), (b'halt\n', 'poweroff.target', 'SHUTDOWN')):
                    first = c.cycle(lines, qmp, 'closed', mode, host_boot)
                    boot = first['boot']
                    if boot in boots: raise RuntimeError('FRESH_REBOOT_REQUIRED')
                    boots.add(boot)
                    qmp.events = [e for e in qmp.events if e.get('event') in ('SUSPEND', 'WAKEUP')]
                    serial.sendall(command)
                    rows = [record(lines, name, boot, target) for name in ('requested', 'link_down', 'stopped')]
                    evidence(*rows)
                    observed = qmp.event(event, time.monotonic() + 30)
                    if observed.get('data', {}).get('guest') is not True: raise RuntimeError('GUEST_ORIGIN_TRANSITION_REQUIRED')
                    print('PASS NORMAL_SYSTEMD_TRANSITION ' + mode + ' ' + target + ' ' + boot, flush=True)
                if process.wait(timeout=10) != 0: raise RuntimeError('NORMAL_POWEROFF_EXIT_REQUIRED')
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
        for name in ('qmp', 'serial'): (path / name).unlink(missing_ok=True)


def run_vm():
    p.guard()
    if os.environ.get('KC_SYSTEMD_RESTART_CI') != '1': raise RuntimeError('SYSTEMD_RESTART_OPT_IN_REQUIRED')
    host_boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip(); host_netns = os.readlink('/proc/self/ns/net')
    with tempfile.TemporaryDirectory(prefix='kc-systemd-restart-') as value:
        path = Path(value)
        kernel = subprocess.run(['sudo', '-n', '/usr/bin/cat', '/boot/vmlinuz-' + os.uname().release], check=True, capture_output=True, timeout=10).stdout
        if not 1024*1024 <= len(kernel) <= 64*1024*1024: raise RuntimeError('KERNEL_SIZE_BOUND')
        (path / 'vmlinuz').write_bytes(kernel); b.payload(path, composed=True, restart=True)
        for mode in ('awake', 'suspend'): case(path, mode, host_boot)
    if path.exists() or Path('/proc/sys/kernel/random/boot_id').read_text().strip() != host_boot or os.readlink('/proc/self/ns/net') != host_netns:
        raise RuntimeError('HOST_UNCHANGED_CLEANUP_REQUIRED')
    print('PASS SYSTEMD_RESTART_IMAGES_PROCESSES_CLEANED_HOST_UNCHANGED NO_LIVE_APPLY', flush=True)


class Tests(unittest.TestCase):
    def test_shutdown_requires_composition_and_reversed_service_order(self):
        with self.assertRaises(ValueError): b.u.units(restart=True)
        self.assertNotIn('shutdown.target', ''.join(b.u.units(composed=True).values()))
        units = b.u.units(composed=True, restart=True)
        for name in ('report', 'lease', 'auth', 'observe', 'link', 'gate', 'setup'):
            self.assertIn('Conflicts=shutdown.target\nBefore=shutdown.target', units['kc-' + name + '.service'])
        self.assertIn('ExecStop=', units['kc-link.service'])
        self.assertIn('Requires=shutdown.target\nAfter=shutdown.target\nBefore=final.target', units['kc-shutdown-check.service'])
        self.assertEqual(units['final.target.d/kc-check.conf'], '[Unit]\nRequires=kc-shutdown-check.service\nAfter=kc-shutdown-check.service\n')

    def test_host_refusal_precedes_power_actions(self):
        guest = b.module('restart', HERE / 'fixtures/secret_custody_restart_guest.py')
        # No boot_probe exists on the supervisor, and no subprocess can run.
        with patch.object(subprocess, 'run') as run:
            with self.assertRaises((FileNotFoundError, RuntimeError)): guest.main('restart')
            run.assert_not_called()
        with patch.object(p, 'guard'), patch.dict(os.environ, {'KC_SYSTEMD_RESTART_CI': '0'}), patch.object(subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'OPT_IN'): run_vm()
            run.assert_not_called()

    def test_missing_stale_or_unexpired_proof_rejected(self):
        guest = b.module('restart', HERE / 'fixtures/secret_custody_restart_guest.py')
        state = dict(boot='one', deadline_ns=10, boottime_guard=dict(deadline_ns=10))
        guest.expired(state, 'one', 11)
        for change, boot, now in (({}, 'two', 11), ({}, 'one', 10), ({'boottime_guard': {}}, 'one', 11), ({'deadline_ns': True}, 'one', 11)):
            with self.assertRaisesRegex(RuntimeError, 'EXPIRED'): guest.expired(dict(state, **change), boot, now)

    def test_stopped_claim_rejected_with_open_packets_or_live_service(self):
        request = dict(monotonic=1, qualification=[False]*2, guards_unchanged=True)
        down = dict(request, monotonic=2, link_up=False)
        stopped = dict(monotonic=3, link_stopped_at=1.9, inet_guard_unchanged=True, peer_stopped=True, ssh_stopped=True,
                       states={n: dict(ActiveState='inactive', Result='success') for n in ('report','lease','auth','observe','link','gate','setup')})
        evidence(request, down, stopped)
        with self.assertRaises(RuntimeError): evidence(dict(request, qualification=[True]*2), down, stopped)
        with self.assertRaises(RuntimeError): evidence(request, down, dict(stopped, inet_guard_unchanged=False))
        stopped['states']['auth']['ActiveState'] = 'active'
        with self.assertRaises(RuntimeError): evidence(request, down, stopped)


if __name__ == '__main__':
    if sys.argv[1:] == ['--vm']: run_vm()
    else: unittest.main(verbosity=2)
