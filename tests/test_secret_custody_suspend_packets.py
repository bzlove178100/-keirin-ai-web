"""Observe the fixed kernel lease with real packets across actual guest S3.

Both possible measured suspend outcomes are reported; neither activates anything.
The awake control and all observation/isolation/cleanup requirements are mandatory.
"""
import gzip
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import sysconfig
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('vm', HERE / 'test_secret_custody_suspend_vm.py')
vm = importlib.util.module_from_spec(spec); spec.loader.exec_module(vm)
MODULES = ('ipv6', 'veth', 'nf_tables')


def guard():
    vm.guard()
    if os.environ.get('KC_SUSPEND_PACKET_CI') != '1':
        raise RuntimeError('GUEST_PACKET_CI_OPT_IN_REQUIRED')


def archive(files):
    """Fixed-builder files and guest devices, never host filesystem mounts."""
    entries = {'dev': (b'', stat.S_IFDIR | 0o755, 0, 0),
               'dev/console': (b'', stat.S_IFCHR | 0o600, 5, 1),
               'dev/null': (b'', stat.S_IFCHR | 0o666, 1, 3),
               'dev/urandom': (b'', stat.S_IFCHR | 0o444, 1, 9),
               'dev/stdin': (b'/proc/self/fd/0', stat.S_IFLNK | 0o777, 0, 0),
               'module-config': (b'', stat.S_IFDIR | 0o755, 0, 0)}
    for name, (content, mode) in files.items():
        path = Path(name)
        if path.is_absolute() or '..' in path.parts or name in entries or not name:
            raise ValueError('RELATIVE_REGULAR_GUEST_PATH_REQUIRED')
        for parent in path.parents:
            if str(parent) != '.': entries.setdefault(str(parent), (b'', stat.S_IFDIR | 0o755, 0, 0))
        entries[name] = (content, stat.S_IFREG | mode, 0, 0)
    result = bytearray()
    ordered = sorted(entries.items(), key=lambda item: (len(Path(item[0]).parts), item[0]))
    ordered.append(('TRAILER!!!', (b'', 0, 0, 0)))
    for inode, (name, (content, mode, major, minor)) in enumerate(ordered, 1):
        values = [inode, mode, 0, 0, 1, 0, len(content), 0, 0, major, minor, len(name) + 1, 0]
        result.extend(('070701' + ''.join(f'{v:08x}' for v in values)).encode())
        result.extend(name.encode() + b'\0'); result.extend(b'\0' * (-len(result) % 4))
        result.extend(content); result.extend(b'\0' * (-len(result) % 4))
    if len(result) > 160 * 1024 * 1024:
        raise RuntimeError('GUEST_IMAGE_SIZE_BOUND')
    return gzip.compress(bytes(result), mtime=0)


def payload(path, boottime_guard=False):
    files = {}
    def add(source, target=None):
        source = Path(source)
        if not source.is_file(): raise RuntimeError('FIXED_GUEST_INPUT_REQUIRED ' + str(source))
        data = source.read_bytes()
        if len(data) > 32 * 1024 * 1024: raise RuntimeError('GUEST_FILE_SIZE_BOUND')
        files[(target or str(source)).lstrip('/')] = (data, source.stat().st_mode & 0o777)
    subprocess.run(['/usr/bin/gcc', '-static', '-O2', '-Wall', '-Wextra', '-Werror', '-DKC_PACKET_PROBE',
                    '-o', str(path / 'init'), str(HERE / 'fixtures/secret_custody_suspend_guest.c')], check=True, timeout=30)
    denied = subprocess.run([str(path / 'init')], capture_output=True, timeout=5)
    if denied.returncode != 2 or denied.stderr != b'VM_GUEST_PID1_REQUIRED\n':
        raise RuntimeError('PACKET_GUEST_HOST_REFUSAL_REQUIRED')
    add(path / 'init', 'init')
    add(HERE / 'fixtures/secret_custody_packet_guest.py', 'probe.py')
    add(HERE.parent / 'review/secret_custody_qualification_lease.py', 'lease.py')
    binaries = ['/usr/bin/python3', '/usr/sbin/ip', '/usr/sbin/nft', '/usr/sbin/modprobe']
    if boottime_guard:
        subprocess.run(['/usr/bin/gcc', '-static', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-o', str(path / 'boot-guard'), str(HERE / 'fixtures/secret_custody_boottime_guard.c')],
                       check=True, timeout=30)
        denied = subprocess.run([str(path / 'boot-guard')], capture_output=True, timeout=5)
        if denied.returncode != 2 or b'BOOTTIME_GUEST_' not in denied.stderr:
            raise RuntimeError('BOOTTIME_LOADER_HOST_REFUSAL_REQUIRED')
        add(path / 'boot-guard', 'boot-guard')
        binaries.append('/usr/sbin/tc')
    for binary in binaries: add(binary)
    add('/usr/sbin/modprobe', '/sbin/modprobe')
    stdlib = Path(sysconfig.get_path('stdlib'))
    if not re.fullmatch(r'/usr/lib/python3\.\d+', str(stdlib)):
        raise RuntimeError('SYSTEM_PYTHON_STDLIB_REQUIRED')
    extensions = []
    for file in stdlib.rglob('*'):
        if any(part in ('site-packages', 'dist-packages', '__pycache__', 'test', 'tests', 'ensurepip') for part in file.relative_to(stdlib).parts): continue
        if file.is_file() and file.suffix in ('.py', '.so'):
            add(file)
            if file.suffix == '.so': extensions.append(str(file))
    # Inspect trusted packaged binaries/extensions, then copy only their named
    # runtime libraries. No environment, credentials or host /etc is included.
    output = subprocess.run(['/usr/bin/ldd', *binaries, *extensions], check=True, capture_output=True, text=True, timeout=30).stdout
    for library in set(re.findall(r'(/[^\s()]+)', output)):
        if Path(library).is_file(): add(library)
    version = os.uname().release
    root = Path('/lib/modules') / version
    empty = path / 'module-config'; empty.mkdir()
    manifest = []
    for module in MODULES + (('sch_ingress', 'cls_bpf') if boottime_guard else ()):
        dependency = subprocess.run(['/usr/sbin/modprobe', '-C', str(empty), '--show-depends', module],
                                    capture_output=True, text=True, timeout=5)
        if dependency.returncode:
            raise RuntimeError('MODULE_DISCOVERY_FAILED ' + module + ' ' + dependency.stderr[-2000:])
        output = dependency.stdout
        for line in output.splitlines():
            if line.startswith('builtin '): continue
            parts = line.split()
            if len(parts) != 2 or parts[0] != 'insmod': raise RuntimeError('MODULE_COPY_ONLY_REQUIRED')
            source = Path(parts[1])
            if root.resolve() not in source.resolve().parents: raise RuntimeError('MATCHED_KERNEL_MODULE_REQUIRED')
            add(source)
            manifest.append({'name': source.name, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
    for metadata in root.glob('modules.*'):
        if metadata.is_file() and metadata.suffix != '.ko': add(metadata)
    image = archive(files)
    (path / 'initramfs').write_bytes(image)
    print('PACKET_PAYLOAD', json.dumps({'initramfs_sha256': hashlib.sha256(image).hexdigest(),
          'file_count': len(files), 'modules': manifest}), flush=True)


def command(path, boottime_guard=False):
    args = vm.command(path)
    args[args.index('-m') + 1] = '512M'
    args[args.index('-append') + 1] += ' kc_packet_probe=1 end=2'
    if boottime_guard:
        args[args.index('-append') + 1] += ' kc_boottime_guard=1 end=3'
    return args


def record(lines, event, mode, boot, timeout=30):
    deadline = time.monotonic() + timeout
    diagnostic = []
    while True:
        try:
            text = lines.line(deadline)
        except Exception:
            print('PACKET_GUEST_DIAGNOSTIC ' + '\n'.join(diagnostic)[-4000:], flush=True)
            raise
        diagnostic.append(text[-512:]); diagnostic = diagnostic[-32:]
        if text.startswith(('PACKET_FAIL', 'VM_FAIL')) or 'Kernel panic' in text:
            print('PACKET_GUEST_DIAGNOSTIC ' + '\n'.join(diagnostic)[-4000:], flush=True)
            raise RuntimeError(text)
        if not text.startswith('PACKET_RECORD '): continue
        row = json.loads(text[len('PACKET_RECORD '):])
        if row.get('event') != event or row.get('mode') != mode or row.get('boot') != boot:
            raise RuntimeError('PACKET_EVIDENCE_SEQUENCE_REQUIRED')
        expected = ['lo'] if event == 'done' else ['host0', 'lo']
        if row.get('interfaces') != expected or type(row.get('marker')) is not int or row['marker'] != 1: raise RuntimeError('GUEST_INTERNAL_INTERFACES_REQUIRED')
        for key in ('monotonic', 'boottime'):
            if type(row.get(key)) not in (int, float) or not math.isfinite(row[key]) or row[key] < 0:
                raise RuntimeError('FINITE_PACKET_CLOCK_REQUIRED')
        print(text, flush=True)
        return row


def outcome(mode, before, after, host_elapsed, boottime_guard=False):
    if after.get('management') != [True] * 4 or after.get('rule_identity_unchanged') is not True:
        raise RuntimeError('PACKET_MANAGEMENT_AND_IDENTITY_REQUIRED')
    packets = after.get('qualification')
    if not isinstance(packets, list) or len(packets) != 4 or any(type(p) is not bool for p in packets):
        raise RuntimeError('FOUR_REAL_PACKET_OBSERVATIONS_REQUIRED')
    start = before['lease_start']
    for value in (*start.values(), after.get('probe_finished_monotonic'), host_elapsed):
        if type(value) not in (int, float) or not math.isfinite(value): raise RuntimeError('FINITE_PACKET_INTERVAL_REQUIRED')
    if mode == 'awake':
        if after['monotonic'] - start['monotonic'] < 8 or packets != [False] * 4:
            raise RuntimeError('AWAKE_EXPIRY_CONTROL_REQUIRED')
        result = 'AWAKE_EXPIRY_CONFIRMED'
    elif mode == 'suspend':
        vm.suspend_delta(before, after, host_elapsed)
        if not 0 <= after['probe_finished_monotonic'] - start['monotonic'] < 7 or after['boottime'] - start['boottime'] < 10:
            raise RuntimeError('ORIGINAL_SUSPEND_PROBE_WINDOW_REQUIRED')
        if packets == [True] * 4: result = 'BLOCKED_SUSPEND_EXPIRY_GAP'
        elif packets == [False] * 4: result = 'SUSPEND_EXPIRY_OBSERVED'
        else: raise RuntimeError('MIXED_SUSPEND_PACKET_EVIDENCE')
    else:
        raise ValueError('FIXED_PACKET_CASE_REQUIRED')
    if boottime_guard:
        proof = before.get('boottime_guard')
        if (not isinstance(proof, dict) or type(proof.get('deadline_ns')) is not int
                or type(proof.get('program_id')) is not int or proof['program_id'] <= 0
                or type(proof.get('ifindex')) is not int or proof['ifindex'] <= 0
                or not re.fullmatch('[0-9a-f]{16}', str(proof.get('tag')))
                or proof.get('loader_exits') is not True
                or proof != after.get('boottime_guard')
                or after.get('tc_identity_unchanged') is not True
                or not start['boottime'] < proof['deadline_ns'] / 1e9 <= start['boottime'] + 8
                or after['boottime'] <= proof['deadline_ns'] / 1e9
                or packets != [False] * 4):
            raise RuntimeError('IMMUTABLE_BOOTTIME_PACKET_EXPIRY_REQUIRED')
        result = 'BOOTTIME_' + result
    if after.get('outcome') != result: raise RuntimeError('PACKET_OUTCOME_MISMATCH')
    return result


def case(path, mode, host_boot, boottime_guard=False):
    if mode not in ('awake', 'suspend'): raise ValueError('FIXED_PACKET_CASE_REQUIRED')
    process = None
    try:
        with (path / 'stderr').open('wb') as errors:
            process = subprocess.Popen(command(path, boottime_guard), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=errors,
                                       cwd=path, env={'PATH': '/usr/bin:/bin', 'LANG': 'C'})
            with vm.connect(path / 'qmp', process) as monitor, vm.connect(path / 'serial', process) as serial:
                qmp, lines = vm.QMP(monitor), vm.Lines(serial)
                if qmp.call('query-block') != [] or qmp.call('query-current-machine').get('wakeup-suspend-support') is not True:
                    raise RuntimeError('DISKLESS_S3_MACHINE_REQUIRED')
                boot = vm.record(lines, 'boot')['boot']
                if boot == host_boot: raise RuntimeError('DISTINCT_GUEST_BOOT_REQUIRED')
                serial.sendall((mode + '\n').encode())
                startup = record(lines, 'startup_unprotected', mode, boot)
                if startup.get('new_connections') != [True] * 4: raise RuntimeError('OPEN_STARTUP_NEGATIVE_CONTROL_REQUIRED')
                print('PASS PACKET_UNPROTECTED_BOOT_DETECTED', mode, flush=True)
                before = record(lines, 'before', mode, boot)
                started = time.monotonic()
                if mode == 'suspend':
                    qmp.event('SUSPEND', time.monotonic() + 20)
                    if qmp.call('query-status').get('status') != 'suspended': raise RuntimeError('REAL_S3_STATE_REQUIRED')
                    time.sleep(vm.SUSPEND_SECONDS)
                    qmp.call('system_wakeup'); qmp.event('WAKEUP', time.monotonic() + 10)
                after = record(lines, 'after', mode, boot)
                result = outcome(mode, before, after, time.monotonic() - started, boottime_guard)
                print('PASS PACKET_FIRST_OBSERVATION_CLASSIFIED', mode, result, flush=True)
                late = record(lines, 'awake_expired', mode, boot)
                if late.get('qualification') != [False] * 4 or late.get('management') != [True] * 4:
                    raise RuntimeError('ORIGINAL_AWAKE_EXPIRY_REQUIRED')
                print('PASS PACKET_ORIGINAL_GUARD_EVENTUALLY_EXPIRES_ADMIN_SURVIVES', mode, flush=True)
                done = record(lines, 'done', mode, boot)
                if done.get('activation_allowed') is not False or done.get('outcome') != result:
                    raise RuntimeError('NO_ACTIVATION_AND_MATCHED_OUTCOME_REQUIRED')
                print('PASS PACKET_GUEST_RULES_PEER_AND_LINK_CLEANED', mode, flush=True)
                return boot, result
    except Exception:
        print((path / 'stderr').read_text(errors='replace')[-4000:], flush=True)
        raise
    finally:
        if process is not None:
            process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=5)
            if Path(f'/proc/{process.pid}').exists(): raise RuntimeError('OWNED_PACKET_VM_REAP_REQUIRED')
        for name in ('serial', 'qmp'):
            (path / name).unlink(missing_ok=True)


def run_vm(boottime_guard=False):
    guard()
    host_boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    host_netns = os.readlink('/proc/self/ns/net')
    with tempfile.TemporaryDirectory(prefix='kc-packet-vm-') as value:
        path = Path(value)
        source = Path('/boot') / ('vmlinuz-' + os.uname().release)
        if not source.is_file(): raise RuntimeError('INSTALLED_CI_KERNEL_REQUIRED')
        kernel = subprocess.run(['sudo', '-n', '/usr/bin/cat', str(source)], check=True, capture_output=True, timeout=10).stdout
        if not 1024 * 1024 <= len(kernel) <= 64 * 1024 * 1024: raise RuntimeError('KERNEL_SIZE_BOUND')
        (path / 'vmlinuz').write_bytes(kernel)
        payload(path, boottime_guard)
        print('PACKET_VM_PROVENANCE', json.dumps({'kernel_release': os.uname().release,
              'kernel_sha256': hashlib.sha256(kernel).hexdigest(), 'qemu_sha256': hashlib.sha256(Path(vm.QEMU).read_bytes()).hexdigest()}), flush=True)
        awake_boot, _ = case(path, 'awake', host_boot, boottime_guard)
        suspend_boot, measured = case(path, 'suspend', host_boot, boottime_guard)
        if awake_boot == suspend_boot: raise RuntimeError('FRESH_VM_PER_PACKET_CASE_REQUIRED')
    if path.exists() or Path('/proc/sys/kernel/random/boot_id').read_text().strip() != host_boot or os.readlink('/proc/self/ns/net') != host_netns:
        raise RuntimeError('PACKET_VM_CLEANUP_HOST_CONTEXT_REQUIRED')
    print('PASS PACKET_VM_IMAGES_CHANNELS_PROCESSES_CLEANED_HOST_UNCHANGED', flush=True)
    print('RESULT', measured, 'NO_LIVE_APPLY_ACTIVATION_FALSE', flush=True)


class Tests(unittest.TestCase):
    def test_archive_supplies_guest_random_and_null_device_nodes(self):
        data, offset, devices, links = gzip.decompress(archive({})), 0, {}, {}
        while True:
            header = data[offset:offset + 110]
            self.assertEqual(header[:6], b'070701')
            fields = [int(header[i:i + 8], 16) for i in range(6, 110, 8)]
            offset += 110
            name = data[offset:offset + fields[11] - 1].decode()
            offset = (offset + fields[11] + 3) & ~3
            if name == 'TRAILER!!!': break
            if stat.S_ISCHR(fields[1]): devices[name] = (fields[9], fields[10])
            if stat.S_ISLNK(fields[1]): links[name] = data[offset:offset + fields[6]]
            offset = (offset + fields[6] + 3) & ~3
        self.assertEqual(devices, {'dev/console': (5, 1), 'dev/null': (1, 3), 'dev/urandom': (1, 9)})
        self.assertEqual(links, {'dev/stdin': b'/proc/self/fd/0'})

    def test_guest_startup_failure_preserves_bounded_preceding_diagnostics(self):
        lines = Mock()
        lines.line.side_effect = ['old' * 3000, 'ImportError: missing packaged library', 'Kernel panic: init exited']
        with patch('builtins.print') as printed, self.assertRaisesRegex(RuntimeError, 'Kernel panic'):
            record(lines, 'startup_unprotected', 'awake', 'boot')
        message = printed.call_args.args[0]
        self.assertIn('ImportError: missing packaged library', message)
        self.assertLessEqual(len(message), 4024)

    def sample(self, packets):
        before = {'boot': 'a', 'marker': 1, 'monotonic': 101., 'boottime': 101., 'lease_start': {'monotonic': 100., 'boottime': 100.}}
        after = {'boot': 'a', 'marker': 1, 'monotonic': 101.1, 'boottime': 113.1, 'probe_finished_monotonic': 102.,
                 'management': [True] * 4, 'qualification': packets, 'rule_identity_unchanged': True,
                 'outcome': 'BLOCKED_SUSPEND_EXPIRY_GAP' if all(packets) else 'SUSPEND_EXPIRY_OBSERVED'}
        return before, after

    def test_live_resume_allowance_is_reported_as_blocking_gap(self):
        before, after = self.sample([True] * 4)
        self.assertEqual(outcome('suspend', before, after, 13), 'BLOCKED_SUSPEND_EXPIRY_GAP')
        before, after = self.sample([False] * 4)
        self.assertEqual(outcome('suspend', before, after, 13), 'SUSPEND_EXPIRY_OBSERVED')

    def test_mixed_late_changed_or_nonfinite_observations_cannot_qualify(self):
        before, after = self.sample([True] * 4)
        for changed in ({'qualification': [True, False, True, False]}, {'probe_finished_monotonic': 108.},
                        {'boottime': 102.}, {'boot': 'other'}, {'management': [False] * 4},
                        {'rule_identity_unchanged': False}, {'probe_finished_monotonic': float('nan')},
                        {'qualification': [1] * 4}, {'outcome': 'SUSPEND_EXPIRY_OBSERVED'}):
            with self.subTest(change=changed), self.assertRaises(RuntimeError):
                outcome('suspend', before, dict(after, **changed), 13)

    def test_awake_expiry_must_be_actual_denial(self):
        before, after = self.sample([False] * 4)
        after.update(monotonic=111., boottime=111., outcome='AWAKE_EXPIRY_CONFIRMED')
        self.assertEqual(outcome('awake', before, after, 10), 'AWAKE_EXPIRY_CONFIRMED')
        with self.assertRaises(RuntimeError): outcome('awake', before, dict(after, qualification=[True] * 4), 10)

    def test_boottime_candidate_cannot_pass_with_old_gap_or_missing_identity(self):
        before, after = self.sample([False] * 4)
        proof = {'deadline_ns': 108000000000, 'program_id': 1, 'ifindex': 2,
                 'tag': 'a' * 16, 'loader_exits': True}
        before['boottime_guard'] = proof
        after.update(boottime_guard=proof, tc_identity_unchanged=True,
                     outcome='BOOTTIME_SUSPEND_EXPIRY_OBSERVED')
        self.assertEqual(outcome('suspend', before, after, 13, True), 'BOOTTIME_SUSPEND_EXPIRY_OBSERVED')
        for change in ({'qualification': [True] * 4}, {'tc_identity_unchanged': False},
                       {'boottime_guard': None}, {'boottime_guard': dict(proof, program_id=2)},
                       {'outcome': 'SUSPEND_EXPIRY_OBSERVED'}):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                outcome('suspend', before, dict(after, **change), 13, True)
        for change in ({'deadline_ns': 109000000000}, {'program_id': 0}, {'loader_exits': False}):
            wrong = dict(proof, **change)
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                outcome('suspend', dict(before, boottime_guard=wrong), dict(after, boottime_guard=wrong), 13, True)

    def test_packet_gate_precedes_any_build_or_launch(self):
        with patch.object(vm, 'guard'), patch.dict(os.environ, {'KC_SUSPEND_PACKET_CI': '0'}), patch.object(subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'OPT_IN'): run_vm()
            run.assert_not_called()

    def test_archive_rejects_escape_and_fixed_vm_has_no_host_network_or_disk(self):
        for name in ('/etc/shadow', '../private', 'dev/console'):
            with self.assertRaises(ValueError): archive({name: (b'x', 0o600)})
        args = command(Path('/tmp/owned'))
        for forbidden in ('-netdev', '-drive', '-blockdev', '-virtfs', '-fsdev', '-enable-kvm'):
            self.assertNotIn(forbidden, args)
        self.assertEqual(args[args.index('-nic') + 1], 'none')
        self.assertEqual(args[args.index('-machine') + 1], 'pc,accel=tcg')


if __name__ == '__main__':
    if sys.argv[1:] == ['--vm']: run_vm()
    elif sys.argv[1:] == ['--boottime-vm']: run_vm(boottime_guard=True)
    else: unittest.main(verbosity=2)
