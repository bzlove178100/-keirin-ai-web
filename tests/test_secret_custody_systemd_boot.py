"""Actual PID1 systemd ordering/reboot in diskless guests, never host services."""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


p = module('packets', HERE / 'test_secret_custody_suspend_packets.py')
vm = p.vm
u = module('units', HERE.parent / 'review/secret_custody_boot_units.py')
SYSTEMD_GUEST_MEMORY = '1024M'


def payload(path, composed=False, restart=False, persistence=False, inbound=False, inbound_lease=False, inbound_restart=False, inbound_persistence=False):
    if inbound_persistence and not inbound_restart: raise ValueError("INBOUND_PERSISTENCE_REQUIRES_RESTART")
    if inbound_restart and not inbound_lease: raise ValueError("INBOUND_RESTART_REQUIRES_LEASE")
    if inbound_lease and not inbound: raise ValueError("INBOUND_LEASE_REQUIRES_INBOUND")
    if inbound and (composed or restart or persistence): raise ValueError("SEPARATE_INBOUND_BOOT_REQUIRED")
    if persistence and not restart: raise ValueError("PERSISTENCE_REQUIRES_RESTART")
    if restart and not composed: raise ValueError("RESTART_REQUIRES_COMPOSITION")
    files = p.payload(path, boottime_guard=composed or inbound_lease, authenticated=composed or inbound, systemd=composed or inbound, storage=persistence or inbound_persistence, conntrack=inbound, inbound_lease=inbound_lease)
    def add(source, target=None):
        source = Path(source)
        files[(target or str(source)).lstrip('/')] = (source.read_bytes(), source.stat().st_mode & 0o777)
    subprocess.run(['/usr/bin/gcc', '-static', '-O2', '-Wall', '-Wextra', '-Werror', '-DKC_SYSTEMD_PROBE',
                    '-o', str(path / 'systemd-init'), str(HERE / 'fixtures/secret_custody_suspend_guest.c')], check=True, timeout=30)
    refused = subprocess.run([str(path / 'systemd-init')], capture_output=True, timeout=5)
    if refused.returncode != 2 or refused.stderr != b'VM_GUEST_PID1_REQUIRED\n': raise RuntimeError('HOST_REFUSAL_REQUIRED')
    add(path / 'systemd-init', 'init')
    add(HERE / 'fixtures/secret_custody_boot_guest.py', 'boot_probe.py')
    if composed: add(HERE / 'fixtures/secret_custody_composed_guest.py', 'composed.py')
    if inbound_lease: add(HERE / 'fixtures/secret_custody_inbound_lease_guest.py', 'inbound_lease.py')
    if inbound:
        add(HERE / 'fixtures/secret_custody_inbound_boot_guest.py', 'inbound_boot.py')
        for name in ('test_secret_custody_inbound.py', 'test_secret_custody_network_transition.py'):
            add(HERE / name, 'tests/' + name)
        add(HERE.parent / 'review/secret_custody_network_rehearsal.py', 'review/secret_custody_network_rehearsal.py')
    if inbound_restart: add(HERE / 'fixtures/secret_custody_inbound_restart_guest.py', 'inbound_restart.py')
    shutdown_units = ('reboot.target', 'systemd-reboot.service', 'poweroff.target', 'systemd-poweroff.service',
                      'shutdown.target', 'umount.target', 'final.target') if restart or inbound_restart else ()
    for name in shutdown_units: add('/usr/lib/systemd/system/' + name)
    if restart: add(HERE / 'fixtures/secret_custody_restart_guest.py', 'restart_probe.py')
    if inbound_persistence: add(HERE / 'fixtures/secret_custody_inbound_persistence_guest.py', 'inbound_persistence.py')
    if persistence or inbound_persistence:
        add(HERE / 'fixtures/secret_custody_persistence_guest.py', 'persist_probe.py')
        add(HERE / 'fixtures/secret_custody_persistence_fault_guest.py', 'persist_fault.py')
        add(HERE.parent / 'review/secret_custody_durable_policy.py', 'durable_policy.py')
    binaries = ['/usr/lib/systemd/systemd', '/usr/lib/systemd/systemd-executor',
                '/usr/lib/systemd/systemd-shutdown', '/usr/bin/systemctl']
    for binary in binaries: add(binary)
    dependencies = subprocess.run(['/usr/bin/ldd', *binaries], check=True, capture_output=True, text=True, timeout=10).stdout
    if 'not found' in dependencies: raise RuntimeError('SYSTEMD_LIBRARY_MISSING')
    for library in set(re.findall(r'(/[^\s()]+)', dependencies)):
        if Path(library).is_file(): add(library)
    files['etc/os-release'] = (b'ID=kc-guest\nPRETTY_NAME="Isolated systemd experiment"\n', 0o644)
    files['etc/machine-id'] = (b'', 0o644)
    if not composed and not inbound:
        files['etc/passwd'] = (b'root:x:0:0:Synthetic root:/root:/bin/false\n', 0o644)
        files['etc/group'] = (b'root:x:0:\n', 0o644)
    selected_units = module('inbound_boot', HERE / 'fixtures/secret_custody_inbound_boot_guest.py').units(inbound_lease=inbound_lease, inbound_restart=inbound_restart, inbound_persistence=inbound_persistence) if inbound else u.units(composed, restart, persistence)
    for name, content in selected_units.items(): files['etc/systemd/system/' + name] = (content.encode(), 0o644)
    image = p.archive(files, systemd=True)
    (path / 'initramfs').write_bytes(image)
    print('SYSTEMD_BOOT_PROVENANCE', json.dumps({'initramfs_sha256': hashlib.sha256(image).hexdigest(),
          'initramfs_compressed_bytes': len(image),
          'payload_file_bytes': sum(len(data) for data, _ in files.values()),
          'guest_memory': SYSTEMD_GUEST_MEMORY,
          'shutdown_units': {name: hashlib.sha256(Path('/usr/lib/systemd/system/' + name).read_bytes()).hexdigest() for name in shutdown_units},
          'binaries': {name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in binaries},
          'kernel_release': os.uname().release, 'kernel_sha256': hashlib.sha256((path / 'vmlinuz').read_bytes()).hexdigest(),
          'qemu_sha256': hashlib.sha256(Path(vm.QEMU).read_bytes()).hexdigest(),
          'version': subprocess.run([binaries[0], '--version'], check=True, capture_output=True, text=True).stdout.splitlines()[0]}), flush=True)


def command(path, mode):
    if mode not in ('closed', 'missing', 'invalid'): raise ValueError('FIXED_BOOT_MODE_REQUIRED')
    args = vm.command(path)
    # The kernel, compressed archive and unpacked Python/systemd payload coexist
    # during boot. 512M failed to unpack on the observed 7.0 CI kernel. Keep a
    # fixed 1 GiB fixture budget; never loosen image, deadline or policy guards.
    args[args.index('-m') + 1] = SYSTEMD_GUEST_MEMORY
    args[args.index('-append') + 1] += ' kc_systemd_probe=1 kc_boot_case=' + mode + ' systemd.show_status=false systemd.log_level=warning end=7'
    return args


def record(lines, event, mode):
    deadline = time.monotonic() + 75
    diagnostic = []
    while True:
        try: line = lines.line(deadline)
        except Exception:
            print('SYSTEMD_BOOT_DIAGNOSTIC ' + '\n'.join(diagnostic)[-6000:], flush=True); raise
        diagnostic.append(line[-1000:]); diagnostic = diagnostic[-40:]
        if line.startswith(('VM_FAIL', 'SYSTEMD_LEASE_FAIL')) or 'Kernel panic' in line or 'Freezing execution' in line:
            raise RuntimeError('SYSTEMD_BOOT_FATAL ' + '\n'.join(diagnostic)[-6000:])
        if not line.startswith('SYSTEMD_BOOT_RECORD '): continue
        row = json.loads(line[len('SYSTEMD_BOOT_RECORD '):])
        if row.get('event') != event or row.get('mode') != mode or row.get('pid1') != 'systemd': raise RuntimeError('BOOT_RECORD_SEQUENCE_REQUIRED')
        if str(vm.uuid.UUID(row['boot'])) != row['boot'] or not math.isfinite(row['monotonic']): raise RuntimeError('BOOT_ID_CLOCK_REQUIRED')
        print(line, flush=True); return row


def evidence(row):
    states = row['states']
    if row.get('fresh') is not True or row.get('qualification') != [False, False]: raise RuntimeError('FRESH_CLOSED_BOOT_REQUIRED')
    if states['setup']['ActiveState'] != 'active' or states['setup']['ExecMainStatus'] != '0': raise RuntimeError('SETUP_SUCCESS_REQUIRED')
    for name, dependency in (('gate', 'setup'), ('link', 'gate')):
        for prop in ('Requires', 'After'):
            if 'kc-' + dependency + '.service' not in states[name][prop].split(): raise RuntimeError('ACTUAL_MANAGER_DEPENDENCY_REQUIRED')
    if row['mode'] == 'closed':
        if (row.get('link_up') is not True or row.get('link_entered') is not True
                or row.get('management') != [True, True] or row.get('policy_unchanged') is not True
                or row['sealed']['boot'] != row['boot'] or row['linked']['boot'] != row['boot']
                or row['sealed']['link_up'] is not False or row['sealed']['sealed_ns'] >= row['linked']['up_ns']):
            raise RuntimeError('ORDERED_CLOSED_LINK_REQUIRED')
        for n in ('gate', 'link'):
            if states[n]['ActiveState'] != 'active' or states[n]['ExecMainStatus'] != '0': raise RuntimeError('UNIT_SUCCESS_REQUIRED')
        times = [int(states[n][prop]) for n, prop in (
            ('setup', 'ExecMainExitTimestampMonotonic'), ('gate', 'ExecMainStartTimestampMonotonic'),
            ('gate', 'ExecMainExitTimestampMonotonic'), ('link', 'ExecMainStartTimestampMonotonic'))]
        if not all(t > 0 for t in times) or times != sorted(times): raise RuntimeError('REAL_SERVICE_ORDER_REQUIRED')
    elif row['mode'] in ('missing', 'invalid'):
        if (row.get('link_up') is not False or row.get('link_entered') is not False
                or row.get('management') != [False, False] or row.get('ruleset_empty') is not True
                or states['gate']['ActiveState'] != 'failed' or states['gate']['Result'] != 'exit-code'
                or states['gate']['ExecMainStatus'] == '0'
                or int(states['link']['ExecMainStartTimestampMonotonic']) != 0):
            raise RuntimeError('FAILED_GATE_MUST_PREVENT_LINK_SERVICE')
    else: raise RuntimeError('FIXED_BOOT_MODE_REQUIRED')


def case(path, mode, host_boot):
    process = None
    try:
        with (path / 'stderr').open('wb') as err:
            process = subprocess.Popen(command(path, mode), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                       stderr=err, cwd=path, env={'PATH': '/usr/bin:/bin', 'LANG': 'C'})
            with vm.connect(path / 'qmp', process) as monitor, vm.connect(path / 'serial', process) as serial:
                qmp, lines = vm.QMP(monitor), vm.Lines(serial)
                if qmp.call('query-block') != []: raise RuntimeError('DISKLESS_GUEST_REQUIRED')
                first = record(lines, 'observed', mode); evidence(first)
                if first['boot'] == host_boot: raise RuntimeError('DISTINCT_GUEST_REQUIRED')
                if mode == 'closed':
                    qmp.events = [e for e in qmp.events if e.get('event') != 'RESET']
                    serial.sendall(b'reboot\n')
                    request = record(lines, 'reboot_requested', mode)
                    if request['boot'] != first['boot']: raise RuntimeError('SAME_REBOOT_SOURCE_REQUIRED')
                    reset = qmp.event('RESET', time.monotonic() + 30)
                    if reset.get('data', {}).get('guest') is not True: raise RuntimeError('GUEST_INITIATED_REBOOT_REQUIRED')
                    second = record(lines, 'observed', mode); evidence(second)
                    if second['boot'] in (first['boot'], host_boot): raise RuntimeError('FRESH_REBOOT_REQUIRED')
                    print('PASS REAL_SYSTEMD_REBOOT_RESEALED_BEFORE_LINK', flush=True)
                serial.sendall(b'clean\n')
                done = record(lines, 'done', mode)
                if done.get('interfaces') != ['lo'] or done.get('activation_allowed') is not False: raise RuntimeError('GUEST_CLEANUP_REQUIRED')
                print('PASS SYSTEMD_BOOT_CASE ' + mode, flush=True)
    finally:
        if process is not None:
            process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
        for name in ('qmp', 'serial'): (path / name).unlink(missing_ok=True)


def run_vm():
    p.guard()
    if os.environ.get('KC_SYSTEMD_BOOT_CI') != '1': raise RuntimeError('SYSTEMD_BOOT_OPT_IN_REQUIRED')
    host_boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    host_netns = os.readlink('/proc/self/ns/net')
    with tempfile.TemporaryDirectory(prefix='kc-systemd-boot-') as value:
        path = Path(value)
        kernel = subprocess.run(['sudo', '-n', '/usr/bin/cat', '/boot/vmlinuz-' + os.uname().release], check=True, capture_output=True, timeout=10).stdout
        if not 1024*1024 <= len(kernel) <= 64*1024*1024: raise RuntimeError('KERNEL_SIZE_BOUND')
        (path / 'vmlinuz').write_bytes(kernel); payload(path)
        for mode in ('closed', 'missing', 'invalid'): case(path, mode, host_boot)
    if path.exists() or Path('/proc/sys/kernel/random/boot_id').read_text().strip() != host_boot or os.readlink('/proc/self/ns/net') != host_netns:
        raise RuntimeError('HOST_UNCHANGED_CLEANUP_REQUIRED')
    print('PASS SYSTEMD_BOOT_IMAGES_PROCESSES_CLEANED_HOST_UNCHANGED NO_LIVE_APPLY', flush=True)


class Tests(unittest.TestCase):
    def test_ready_marker_is_absent_while_json_is_partial(self):
        guest = module('bootguest', HERE / 'fixtures/secret_custody_boot_guest.py')
        original = Path.write_text
        with tempfile.TemporaryDirectory() as value, patch.object(guest, 'STATE', Path(value)):
            def partial_write(path, data, *args, **kwargs):
                original(path, data[:1], *args, **kwargs)
                self.assertFalse((guest.STATE / 'peer-isolated').exists())
                return original(path, data, *args, **kwargs)
            with patch.object(Path, 'write_text', partial_write):
                guest.write('peer-isolated', {'pid': 123})
            self.assertEqual(guest.read('peer-isolated'), {'pid': 123})
            self.assertEqual([p.name for p in guest.STATE.iterdir()], ['peer-isolated'])

    def test_failed_publication_keeps_previous_complete_marker(self):
        guest = module('bootguest', HERE / 'fixtures/secret_custody_boot_guest.py')
        with tempfile.TemporaryDirectory() as value, patch.object(guest, 'STATE', Path(value)):
            guest.write('state', {'version': 1})
            with patch.object(guest.os, 'replace', side_effect=OSError('synthetic replacement fault')):
                with self.assertRaises(OSError): guest.write('state', {'version': 2})
            self.assertEqual(guest.read('state'), {'version': 1})
            self.assertEqual([p.name for p in guest.STATE.iterdir()], ['state'])

    def test_fixed_units_require_success_and_order(self):
        units = u.units()
        self.assertIn('Requires=kc-gate.service\nAfter=kc-gate.service', units['kc-link.service'])
        self.assertIn('Wants=kc-link.service\nAfter=kc-link.service', units['kc-report.service'])
        self.assertNotIn('ExecStop=', ''.join(units.values()))

    def test_host_refusal_and_fixed_vm(self):
        guest = module('bootguest', HERE / 'fixtures/secret_custody_boot_guest.py')
        with self.assertRaisesRegex(RuntimeError, 'ISOLATED_SYSTEMD_GUEST_REQUIRED'): guest.guard()
        with self.assertRaises(ValueError): command(Path('/tmp/owned'), 'arbitrary')
        args = command(Path('/tmp/owned'), 'closed')
        self.assertEqual(args[args.index('-nic')+1], 'none')
        self.assertNotIn('-drive', args)
        with patch.object(p, 'guard'), patch.dict(os.environ, {'KC_SYSTEMD_BOOT_CI': '0'}), patch.object(subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'OPT_IN'): run_vm()
            run.assert_not_called()

    def test_failed_gate_cannot_pass_if_link_ran_or_policy_is_partial(self):
        states = {'setup': {'ActiveState': 'active', 'ExecMainStatus': '0'},
                  'gate': {'ActiveState': 'failed', 'ExecMainStatus': '1', 'Result': 'exit-code', 'Requires': 'kc-setup.service', 'After': 'kc-setup.service'},
                  'link': {'Requires': 'kc-gate.service', 'After': 'kc-gate.service', 'ExecMainStartTimestampMonotonic': '0'}}
        row = dict(mode='invalid', states=states, fresh=True, qualification=[False]*2, management=[False]*2,
                   link_up=False, link_entered=False, ruleset_empty=True)
        evidence(row)
        for change in ({'link_up':True},{'link_entered':True},{'ruleset_empty':False},{'management':[True]*2}):
            with self.assertRaises(RuntimeError): evidence(dict(row, **change))


if __name__ == '__main__':
    if sys.argv[1:] == ['--vm']: run_vm()
    else: unittest.main(verbosity=2)
