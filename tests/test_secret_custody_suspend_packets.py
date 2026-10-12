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


def archive(files, systemd=False):
    """Fixed-builder files and guest devices, never host filesystem mounts."""
    entries = {'dev': (b'', stat.S_IFDIR | 0o755, 0, 0),
               'dev/console': (b'', stat.S_IFCHR | 0o600, 5, 1),
               'dev/null': (b'', stat.S_IFCHR | 0o666, 1, 3),
               'dev/urandom': (b'', stat.S_IFCHR | 0o444, 1, 9),
               'dev/stdin': (b'/proc/self/fd/0', stat.S_IFLNK | 0o777, 0, 0),
               'module-config': (b'', stat.S_IFDIR | 0o755, 0, 0)}
    if systemd:
        entries.update({'dev/ttyS0': (b'', stat.S_IFCHR | 0o600, 4, 64),
                        'dev/zero': (b'', stat.S_IFCHR | 0o666, 1, 5),
                        'dev/random': (b'', stat.S_IFCHR | 0o444, 1, 8)})
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


def module_names(boottime_guard=False, storage=False, conntrack=False):
    return (MODULES + (('sch_ingress', 'cls_bpf') if boottime_guard else ())
            + (('virtio_pci', 'virtio_blk', 'ext4') if storage else ())
            + (('nft_ct',) if conntrack else ()))


def payload(path, boottime_guard=False, startup=False, authenticated=False, systemd=False, storage=False, conntrack=False):
    if storage and not systemd: raise ValueError("STORAGE_REQUIRES_SYSTEMD")
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
    add(HERE / 'fixtures/secret_custody_packet_guest.py', 'packets.py' if startup else 'probe.py')
    if startup:
        add(HERE / 'fixtures/secret_custody_startup_guest.py', 'probe.py')
    add(HERE.parent / 'review/secret_custody_closed_startup.py', 'startup_policy.py')
    add(HERE.parent / 'review/secret_custody_qualification_lease.py', 'lease.py')
    binaries = ['/usr/bin/python3', '/usr/sbin/ip', '/usr/sbin/nft', '/usr/sbin/modprobe']
    if storage: binaries += ['/usr/bin/mount', '/usr/bin/umount']
    if authenticated:
        add(HERE / 'fixtures/secret_custody_ssh_guest.py', 'ssh_probe.py')
        add(HERE / 'fixtures/secret_custody_ssh_echo.py', 'ssh_echo.py')
        # Download/extract only: never install/start an SSH service on CI's host.
        packages = path / 'ssh-packages'; packages.mkdir()
        extracted = path / 'ssh-extracted'; extracted.mkdir()
        subprocess.run(['apt-get', 'download', 'openssh-client', 'openssh-server'], cwd=packages,
                       check=True, capture_output=True, timeout=60)
        receipts = []
        for deb in sorted(packages.glob('*.deb')):
            receipts.append({'package': subprocess.run(['dpkg-deb', '-f', str(deb), 'Package', 'Version'],
                            check=True, capture_output=True, text=True).stdout.strip(),
                             'sha256': hashlib.sha256(deb.read_bytes()).hexdigest()})
            subprocess.run(['dpkg-deb', '-x', str(deb), str(extracted)], check=True, timeout=20)
        for target in ('usr/sbin/sshd', 'usr/bin/ssh', 'usr/bin/ssh-keygen'):
            source = extracted / target
            add(source, target); binaries.append(str(source))
        for name in ('sshd-session', 'sshd-auth'):
            source = extracted / 'usr/lib/openssh' / name
            if source.is_file():
                add(source, str(source.relative_to(extracted))); binaries.append(str(source))
        add('/bin/sh'); binaries.append('/bin/sh')
        for source in Path('/lib/x86_64-linux-gnu').glob('libnss_files.so*'): add(source)
        files['etc/passwd'] = (b'root:x:0:0:Synthetic root:/run/ssh-probe:/bin/sh\nsshd:x:74:74:Privilege separation:/run/sshd:/usr/sbin/nologin\n', 0o644)
        files['etc/group'] = (b'root:x:0:\nsshd:x:74:\n', 0o644)
        files['etc/shadow'] = (b'root:x:19000:0:99999:7:::\nsshd:!:19000:0:99999:7:::\n', 0o600)
        files['etc/nsswitch.conf'] = (b'passwd: files\ngroup: files\nshadow: files\nhosts: files\n', 0o644)
        print('SSH_PACKAGE_PROVENANCE', json.dumps(receipts), flush=True)
    if boottime_guard:
        subprocess.run(['/usr/bin/gcc', '-static', '-O2', '-Wall', '-Wextra', '-Werror',
                        *(['-DKC_SYSTEMD_LEASE_PROBE'] if systemd else []),
                        '-o', str(path / 'boot-guard'), str(HERE / 'fixtures/secret_custody_boottime_guard.c')],
                       check=True, timeout=30)
        denied = subprocess.run([str(path / 'boot-guard')], capture_output=True, timeout=5)
        if denied.returncode != 2 or b'BOOTTIME_GUEST_' not in denied.stderr:
            raise RuntimeError('BOOTTIME_LOADER_HOST_REFUSAL_REQUIRED')
        add(path / 'boot-guard', 'boot-guard')
        binaries.append('/usr/sbin/tc')
    for binary in binaries:
        if not authenticated or str(path / 'ssh-extracted') not in binary: add(binary)
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
    if 'not found' in output: raise RuntimeError('GUEST_SHARED_LIBRARY_MISSING')
    for library in set(re.findall(r'(/[^\s()]+)', output)):
        if Path(library).is_file(): add(library)
    version = os.uname().release
    root = Path('/lib/modules') / version
    empty = path / 'module-config'; empty.mkdir()
    manifest = []
    for module in module_names(boottime_guard, storage, conntrack):
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
    return files


def command(path, boottime_guard=False, integrated=False, authenticated=False):
    if integrated and not boottime_guard:
        raise ValueError('INTEGRATED_BOOTTIME_REQUIRED')
    args = vm.command(path)
    args[args.index('-m') + 1] = '512M'
    args[args.index('-append') + 1] += ' kc_packet_probe=1 end=2'
    if boottime_guard:
        args[args.index('-append') + 1] += ' kc_boottime_guard=1 end=3'
    if integrated:
        args[args.index('-append') + 1] += ' kc_integrated_probe=1 end=5'
    if authenticated:
        if not integrated: raise ValueError('SSH_INTEGRATED_REQUIRED')
        args[args.index('-append') + 1] += ' kc_ssh_probe=1 end=6'
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
        # Match the guest's integer-nanosecond construction exactly. Float
        # addition can round start+8 below deadline_ns/1e9 at exponent changes.
        start_ns = int(start['boottime'] * 1e9)
        if (not isinstance(proof, dict) or type(proof.get('deadline_ns')) is not int
                or type(proof.get('program_id')) is not int or proof['program_id'] <= 0
                or type(proof.get('ifindex')) is not int or proof['ifindex'] <= 0
                or not re.fullmatch('[0-9a-f]{16}', str(proof.get('tag')))
                or proof.get('loader_exits') is not True
                or proof != after.get('boottime_guard')
                or after.get('tc_identity_unchanged') is not True
                or not start_ns < proof['deadline_ns'] <= start_ns + 8000000000
                or int(after['boottime'] * 1e9) <= proof['deadline_ns']
                or packets != [False] * 4):
            raise RuntimeError('IMMUTABLE_BOOTTIME_PACKET_EXPIRY_REQUIRED')
        result = 'BOOTTIME_' + result
    if after.get('outcome') != result: raise RuntimeError('PACKET_OUTCOME_MISMATCH')
    return result


def ssh_evidence(row, initial=False):
    fields = ('established', 'wrong_keys_rejected', 'wrong_hosts_rejected') if initial else ('established', 'fresh')
    for key in fields:
        values = row.get(key)
        if values != [True, True] or any(type(value) is not bool for value in values):
            raise RuntimeError('AUTHENTICATED_SSH_EVIDENCE_REQUIRED')


def integrated_evidence(sealed, closed, refused, released, before):
    rows = (sealed, closed, refused, released, before)
    if (sealed.get('link_up') is not False or sealed.get('closed_policy') is not True
            or refused.get('policy_unchanged') is not True
            or any(row.get('new_connections') != [False, False, True, True]
                   or any(type(v) is not bool for v in row['new_connections']) for row in (closed, refused))
            or not isinstance(released.get('boottime_guard'), dict)
            or released['boottime_guard'] != before.get('boottime_guard')
            or released.get('lease_start') != before.get('lease_start')):
        raise RuntimeError('INTEGRATED_CLOSED_TO_LEASE_EVIDENCE_REQUIRED')
    for earlier, later in zip(rows, rows[1:]):
        if (earlier['boot'] != later['boot'] or earlier['mode'] != later['mode']
                or any(later[key] < earlier[key] for key in ('monotonic', 'boottime'))):
            raise RuntimeError('INTEGRATED_EVIDENCE_ORDER_REQUIRED')


def case(path, mode, host_boot, boottime_guard=False, integrated=False, authenticated=False):
    if mode not in ('awake', 'suspend'): raise ValueError('FIXED_PACKET_CASE_REQUIRED')
    process = None
    try:
        with (path / 'stderr').open('wb') as errors:
            process = subprocess.Popen(command(path, boottime_guard, integrated, authenticated), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=errors,
                                       cwd=path, env={'PATH': '/usr/bin:/bin', 'LANG': 'C'})
            with vm.connect(path / 'qmp', process) as monitor, vm.connect(path / 'serial', process) as serial:
                qmp, lines = vm.QMP(monitor), vm.Lines(serial)
                if qmp.call('query-block') != [] or qmp.call('query-current-machine').get('wakeup-suspend-support') is not True:
                    raise RuntimeError('DISKLESS_S3_MACHINE_REQUIRED')
                boot = vm.record(lines, 'boot')['boot']
                if boot == host_boot: raise RuntimeError('DISTINCT_GUEST_BOOT_REQUIRED')
                serial.sendall((mode + '\n').encode())
                if integrated:
                    sealed = record(lines, 'startup_sealed', mode, boot)
                    closed = record(lines, 'startup_closed', mode, boot)
                    refused = record(lines, 'startup_release_refused', mode, boot)
                    if authenticated:
                        ssh_ready = record(lines, 'ssh_ready', mode, boot)
                        ssh_evidence(ssh_ready, initial=True)
                    released = record(lines, 'startup_released', mode, boot)
                    before = record(lines, 'before', mode, boot)
                    integrated_evidence(sealed, closed, refused, released, before)
                    print('PASS CLOSED_STARTUP_REFUSED_UNGUARDED_RELEASE_THEN_LEASED', mode, flush=True)
                else:
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
                if authenticated:
                    ssh_after = record(lines, 'ssh_after', mode, boot)
                    ssh_evidence(ssh_after)
                    print('PASS AUTHENTICATED_SSH_EXISTING_AND_FRESH_AFTER_EXPIRY', mode, flush=True)
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


def run_vm(boottime_guard=False, integrated=False, authenticated=False):
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
        payload(path, boottime_guard, authenticated=authenticated)
        print('PACKET_VM_PROVENANCE', json.dumps({'kernel_release': os.uname().release,
              'kernel_sha256': hashlib.sha256(kernel).hexdigest(), 'qemu_sha256': hashlib.sha256(Path(vm.QEMU).read_bytes()).hexdigest()}), flush=True)
        awake_boot, _ = case(path, 'awake', host_boot, boottime_guard, integrated, authenticated)
        suspend_boot, measured = case(path, 'suspend', host_boot, boottime_guard, integrated, authenticated)
        if awake_boot == suspend_boot: raise RuntimeError('FRESH_VM_PER_PACKET_CASE_REQUIRED')
    if path.exists() or Path('/proc/sys/kernel/random/boot_id').read_text().strip() != host_boot or os.readlink('/proc/self/ns/net') != host_netns:
        raise RuntimeError('PACKET_VM_CLEANUP_HOST_CONTEXT_REQUIRED')
    print('PASS PACKET_VM_IMAGES_CHANNELS_PROCESSES_CLEANED_HOST_UNCHANGED', flush=True)
    print('RESULT', measured, 'NO_LIVE_APPLY_ACTIVATION_FALSE', flush=True)


class Tests(unittest.TestCase):
    def test_ssh_rejection_requires_auth_failure_exit_and_no_command_output(self):
        spec = importlib.util.spec_from_file_location('ssh_guest', HERE / 'fixtures/secret_custody_ssh_guest.py')
        ssh = importlib.util.module_from_spec(spec); spec.loader.exec_module(ssh)
        for reason in (b'Permission denied (publickey)', b'Too many authentication failures'):
            self.assertEqual(ssh.rejection(subprocess.CompletedProcess([], 255, b'', reason), 'client_key'), reason.decode())
        for rc, output, error in ((0, b'', b'Too many authentication failures'),
                                  (255, b'ssh-synthetic-1\n', b'Permission denied (publickey)'),
                                  (255, b'', b'Connection reset by peer'),
                                  (255, b'', b'Host key verification failed')):
            with self.assertRaisesRegex(RuntimeError, 'SSH_NEGATIVE_CONTROL_FAILED'):
                ssh.rejection(subprocess.CompletedProcess([], rc, output, error), 'client_key')

    def test_ssh_evidence_requires_real_boolean_authentication_and_negative_controls(self):
        good = {'established': [True]*2, 'fresh': [True]*2,
                'wrong_keys_rejected': [True]*2, 'wrong_hosts_rejected': [True]*2}
        ssh_evidence(good, initial=True); ssh_evidence(good)
        for key in good:
            for value in (None, [True, False], [1, 1]):
                with self.subTest(key=key, value=value), self.assertRaises(RuntimeError):
                    ssh_evidence(dict(good, **{key: value}), initial=key != 'fresh')

    def test_ssh_is_guest_only_and_clients_require_pinned_host_key(self):
        spec = importlib.util.spec_from_file_location('ssh_guest', HERE / 'fixtures/secret_custody_ssh_guest.py')
        ssh = importlib.util.module_from_spec(spec); spec.loader.exec_module(ssh)
        with patch.object(ssh.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'FIXED_SSH_GUEST_REQUIRED'): ssh.prepare()
            run.assert_not_called()
        args = ssh.client_args('192.0.2.1')
        for option in ('StrictHostKeyChecking=yes', 'IdentitiesOnly=yes', 'IdentityAgent=none',
                       'GlobalKnownHostsFile=/dev/null', 'PasswordAuthentication=no'):
            self.assertIn(option, args)
        self.assertIn('PermitRootLogin forced-commands-only', ssh.configuration())
        self.assertIn('DisableForwarding yes', ssh.configuration())
        with self.assertRaises(ValueError): ssh.client_args('example.com')
        with self.assertRaises(ValueError): command(Path('/tmp/owned'), authenticated=True)

    def test_startup_release_never_deletes_gate_with_missing_changed_or_expired_guards(self):
        spec = importlib.util.spec_from_file_location('packet_guest', HERE / 'fixtures/secret_custody_packet_guest.py')
        guest = importlib.util.module_from_spec(spec); spec.loader.exec_module(guest)
        policy, lease = Mock(TABLE='kc_startup_guard'), Mock()
        policy.seal.return_value = 'closed'
        lease.snapshot.return_value = 'lease'
        proof = dict(deadline_ns=108000000000, loader_exits=True)
        for fault in ('missing', 'closed_changed', 'lease_changed', 'tc_changed', 'expired', 'valid'):
            policy.seal.return_value = 'wrong' if fault == 'closed_changed' else 'closed'
            lease.snapshot.return_value = 'wrong' if fault == 'lease_changed' else 'lease'
            with self.subTest(fault=fault), patch.object(guest, 'run', return_value=b'{}') as run, \
                    patch.object(guest, 'reports', return_value=[]), \
                    patch.object(guest, 'tc_identity', return_value='wrong' if fault == 'tc_changed' else 'tc'), \
                    patch.object(guest, 'clocks', return_value={'boottime': 109 if fault == 'expired' else 101}):
                args = (policy, 'closed', lease, 'lease', None if fault == 'missing' else proof, 'tc', 108000000000)
                if fault == 'valid':
                    guest.release_startup(*args)
                    self.assertEqual(run.call_args.args, (guest.NFT, 'delete', 'table', 'inet', 'kc_startup_guard'))
                else:
                    with self.assertRaisesRegex(RuntimeError, 'STARTUP_RELEASE_GUARDS_REQUIRED'):
                        guest.release_startup(*args)
                    self.assertFalse(any('delete' in call.args for call in run.call_args_list))

    def test_integrated_evidence_rejects_open_startup_or_different_deadline(self):
        sealed = dict(boot='a', mode='suspend', monotonic=1., boottime=1., link_up=False, closed_policy=True)
        closed = dict(sealed, new_connections=[False, False, True, True])
        refused = dict(closed, policy_unchanged=True)
        released = dict(sealed, boottime_guard={'deadline_ns': 9}, lease_start={'boottime': 1})
        before = dict(released)
        integrated_evidence(sealed, closed, refused, released, before)
        for change in ({'new_connections': [True]*4}, {'new_connections': [0, 0, 1, 1]}, {'boot': 'b'}):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                integrated_evidence(sealed, dict(closed, **change), refused, released, before)
        with self.assertRaises(RuntimeError):
            integrated_evidence(sealed, closed, refused, released, dict(before, boottime_guard={'deadline_ns': 10}))
        with self.assertRaises(ValueError): command(Path('/tmp/owned'), integrated=True)

    def test_actual_iproute2_nested_program_identity_is_required(self):
        spec = importlib.util.spec_from_file_location('packet_guest', HERE / 'fixtures/secret_custody_packet_guest.py')
        guest = importlib.util.module_from_spec(spec); spec.loader.exec_module(guest)
        proof = {'program_id': 1, 'tag': '67a57c06ba353954'}
        # Shape from failed guest job 113730362212, not a guessed flat schema.
        header = {'protocol': 'all', 'pref': 1, 'kind': 'bpf', 'chain': 0}
        options = {'handle': '0x1', 'bpf_name': 'kc_boot_guard', 'direct-action': True,
                   'not_in_hw': True, 'prog': {'id': 1, 'name': 'kc_boot_guard',
                                              'tag': proof['tag'], 'jited': 1}}
        report = [header, dict(header, options=options)]
        with patch.object(guest, 'run', return_value=json.dumps(report).encode()):
            self.assertEqual(guest.tc_identity(proof), [report, report])
        for replacement in ({}, dict(options, prog={'id': 2, 'tag': proof['tag']}),
                            dict(options, prog={'id': 1, 'tag': '0' * 16}),
                            dict(options, **{'direct-action': False}),
                            dict(options, prog=None, id=1, tag=proof['tag'])):
            with self.subTest(options=replacement), patch.object(guest, 'run',
                    return_value=json.dumps([header, dict(header, options=replacement)]).encode()), self.assertRaises(RuntimeError):
                guest.tc_identity(proof)

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

    def test_deadline_uses_exact_nanoseconds_without_tolerance_or_extension(self):
        before, after = self.sample([False] * 4)
        before['lease_start'] = {'monotonic': 25.540520284, 'boottime': 25.540526456}
        proof = {'deadline_ns': 33540526456, 'program_id': 1, 'ifindex': 3,
                 'tag': 'a4e3f9e7631a3501', 'loader_exits': True}
        before['boottime_guard'] = proof
        after.update(monotonic=36.462182233, boottime=36.462204986,
                     probe_finished_monotonic=37.474899962, boottime_guard=proof,
                     tc_identity_unchanged=True, outcome='BOOTTIME_AWAKE_EXPIRY_CONFIRMED')
        self.assertEqual(outcome('awake', before, after, 12, True), 'BOOTTIME_AWAKE_EXPIRY_CONFIRMED')
        for deadline in (33540526457, int(before['lease_start']['boottime'] * 1e9)):
            wrong = dict(proof, deadline_ns=deadline)
            with self.assertRaisesRegex(RuntimeError, 'IMMUTABLE_BOOTTIME_PACKET_EXPIRY_REQUIRED'):
                outcome('awake', dict(before, boottime_guard=wrong), dict(after, boottime_guard=wrong), 12, True)

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
    elif sys.argv[1:] == ['--integrated-vm']: run_vm(boottime_guard=True, integrated=True)
    elif sys.argv[1:] == ['--ssh-vm']: run_vm(boottime_guard=True, integrated=True, authenticated=True)
    else: unittest.main(verbosity=2)
