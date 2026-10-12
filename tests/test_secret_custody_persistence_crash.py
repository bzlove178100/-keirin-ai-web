"""Kill an owned QEMU between durable writes; reopen its unmodified private disk.

This is a process-crash experiment after an acknowledged fsync, not host power
loss, storage-controller failure, arbitrary torn-write or production validation.
"""
import hashlib
import errno
import importlib.util
import json
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
spec = importlib.util.spec_from_file_location('persistence', HERE / 'test_secret_custody_persistence.py')
s = importlib.util.module_from_spec(spec); spec.loader.exec_module(s)
b, c, p, vm = s.b, s.c, s.p, s.vm


def command(path, phase):
    if phase not in ('after-receipt', 'recover', 'enospc', 'erofs'): raise ValueError('FIXED_CRASH_PHASE_REQUIRED')
    args = s.command(path, 'invalid' if phase == 'recover' else 'closed', 'awake')
    flag = 'kc_persistence_fault=' if phase in ('enospc', 'erofs') else 'kc_persistence_crash='
    args[args.index('-append') + 1] += ' ' + flag + phase + ' end=11'
    return args


def barrier(lines, boot):
    deadline = time.monotonic() + 45
    while True:
        line = lines.line(deadline)
        if line.startswith(('SYSTEMD_RESTART_RECORD ', 'SYSTEMD_RESTART_FAIL', 'SYSTEMD_BOOT_STAGE_ERROR', 'SYSTEMD_PERSIST_STAGE_ERROR')) or 'Kernel panic' in line:
            raise RuntimeError('CRASH_BARRIER_NOT_REACHED ' + line[-1500:])
        if line.startswith('SYSTEMD_PERSIST_RECORD '):
            row = json.loads(line[len('SYSTEMD_PERSIST_RECORD '):])
            if (row.get('event') != 'crash-ready' or row.get('boot') != boot
                    or row.get('activation_allowed') is not False or row.get('saved_marker_present') is not False
                    or row.get('qualification') != [False, False] or row['crash_state']['receipt_boot'] != boot
                    or row['crash_state']['generation'] != 0):
                raise RuntimeError('CLOSED_PARTIAL_SAVE_BARRIER_REQUIRED')
            print(line, flush=True)
            return row


def recovery_evidence(row, ready, host_boot):
    if (row.get('event') != 'refused' or row.get('boot') in (ready['boot'], host_boot)
            or row.get('activation_allowed') is not False or row.get('link_up') is not False
            or row.get('recovery_refusal') != 'ORPHAN_RECEIPT_REFUSED'
            or row.get('crash_state') != ready['crash_state']):
        raise RuntimeError('EXACT_CRASH_STATE_REFUSED_ON_FRESH_BOOT_REQUIRED')


def fault_evidence(row, mode):
    info = row.get('filesystem_fault', {})
    expected = {'enospc': errno.ENOSPC, 'erofs': errno.EROFS}
    if mode not in expected or info.get('mode') != mode or info.get('errno') != expected[mode]:
        raise RuntimeError('EXACT_REAL_FILESYSTEM_ERROR_REQUIRED')
    required_mount = 'ro' if mode == 'erofs' else 'rw'
    if any(info.get(key, {}).get('mount_mode') != required_mount for key in ('prepared', 'after')):
        raise RuntimeError('ACTUAL_FAULT_MOUNT_MODE_REQUIRED')
    if mode == 'enospc':
        prepared = info['prepared']
        block = prepared.get('block_size', 0)
        reserved, free = prepared.get('reserved_clusters', -1), prepared.get('free_blocks', -1)
        if (block not in (1024, 2048, 4096) or not 0 <= free <= reserved <= s.SIZE // block
                or info.get('allocator_errno') != errno.ENOSPC
                or not 0 < info.get('allocated_bytes', 0) <= s.SIZE):
            raise RuntimeError('BOUNDED_GUEST_EXHAUSTION_REQUIRED')


def case(path, host_boot, fault=None):
    if fault not in (None, 'enospc', 'erofs'): raise ValueError('FIXED_FILESYSTEM_FAULT_REQUIRED')
    ready = None
    for phase in (fault or 'after-receipt', 'recover'):
        process = None
        try:
            with (path / ('stderr-' + phase)).open('wb') as err:
                process = subprocess.Popen(command(path, phase), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                           stderr=err, cwd=path, env={'PATH': '/usr/bin:/bin', 'LANG': 'C'})
                with vm.connect(path / 'qmp', process) as monitor, vm.connect(path / 'serial', process) as serial:
                    qmp, lines = vm.QMP(monitor), vm.Lines(serial)
                    s.block_evidence(qmp.call('query-block'), path)
                    if phase != 'recover':
                        loaded = s.record(lines, 'loaded', 'valid')
                        first = c.cycle(lines, qmp, 'closed', 'awake', host_boot)
                        s.loaded_evidence(loaded, first, None)
                        serial.sendall(b'restart\n')
                        ready = barrier(lines, first['boot'])
                        if fault is not None: fault_evidence(ready, fault)
                        process.kill()
                        if process.wait(timeout=10) != -signal.SIGKILL:
                            raise RuntimeError('OWNED_QEMU_SIGKILL_REQUIRED')
                        print('PERSIST_CRASH_KILLED ' + json.dumps(dict(boot=ready['boot'], signal='SIGKILL',
                              saved_marker_present=False, normal_shutdown=False,
                              disk_sha256=hashlib.sha256((path / 'state.raw').read_bytes()).hexdigest())), flush=True)
                    else:
                        denied = s.record(lines, 'refused', 'crash-recovery')
                        recovery_evidence(denied, ready, host_boot)
                        first = b.record(lines, 'observed', 'invalid'); b.evidence(first)
                        if first['boot'] != denied['boot']: raise RuntimeError('SAME_RECOVERY_BOOT_REQUIRED')
                        c.service_evidence(c.record(lines, 'completed', 'awake', first['boot']), 'invalid')
                        serial.sendall(b'clean\n')
                        done = b.record(lines, 'done', 'invalid')
                        if done['boot'] != first['boot'] or done.get('interfaces') != ['lo'] or done.get('activation_allowed') is not False:
                            raise RuntimeError('CRASH_RECOVERY_CLEANUP_REQUIRED')
                        print('PASS ACTUAL_QEMU_SIGKILL_SAME_DISK_ORPHAN_REFUSED NO_LIVE_APPLY', flush=True)
                        if fault is not None: print('PASS REAL_FILESYSTEM_FAULT_RECOVERY ' + fault, flush=True)
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
            for name in ('qmp', 'serial'): (path / name).unlink(missing_ok=True)


def run_vm(io_faults=False):
    p.guard()
    if os.environ.get('KC_PERSISTENCE_CRASH_CI') != '1' or os.environ.get('KC_PERSISTENCE_CI') != '1':
        raise RuntimeError('PERSISTENCE_CRASH_OPT_IN_REQUIRED')
    if io_faults and os.environ.get('KC_PERSISTENCE_IO_CI') != '1': raise RuntimeError('PERSISTENCE_IO_OPT_IN_REQUIRED')
    host_boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    netns = os.readlink('/proc/self/ns/net')
    with tempfile.TemporaryDirectory(prefix='kc-persist-crash-') as name:
        path = Path(name)
        kernel = subprocess.run(['sudo', '-n', '/usr/bin/cat', '/boot/vmlinuz-' + os.uname().release],
                                check=True, capture_output=True, timeout=10).stdout
        if not 1024*1024 <= len(kernel) <= 64*1024*1024: raise RuntimeError('KERNEL_SIZE_BOUND')
        (path / 'vmlinuz').write_bytes(kernel)
        b.payload(path, composed=True, restart=True, persistence=True)
        if io_faults:
            for fault in ('enospc', 'erofs'):
                child = path / fault; child.mkdir(mode=0o700)
                for name in ('vmlinuz', 'initramfs'): (child / name).symlink_to(path / name)
                s.disk(child, 'valid'); case(child, host_boot, fault)
        else:
            s.disk(path, 'valid')
            case(path, host_boot)  # No reseeding, repair, host mount or image replacement.
    if path.exists() or Path('/proc/sys/kernel/random/boot_id').read_text().strip() != host_boot or os.readlink('/proc/self/ns/net') != netns:
        raise RuntimeError('HOST_UNCHANGED_CRASH_CLEANUP_REQUIRED')
    print('PASS CRASH_VOLUME_IMAGES_PROCESSES_CLEANED_HOST_UNCHANGED NO_LIVE_APPLY', flush=True)


class Tests(unittest.TestCase):
    def test_opt_in_and_host_refusal_precede_disk_or_process_actions(self):
        with patch.object(p, 'guard'), patch.dict(os.environ, {'KC_PERSISTENCE_CRASH_CI': '0'}), patch.object(subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'OPT_IN'): run_vm()
            run.assert_not_called()
        guest = b.module('crash_host', HERE / 'fixtures/secret_custody_persistence_guest.py')
        fake = SimpleNamespace(guard=Mock(side_effect=RuntimeError('HOST_REFUSED')))
        with patch.object(guest, 'emit') as emit:
            with self.assertRaisesRegex(RuntimeError, 'HOST_REFUSED'): guest.await_crash(fake, None, s.d, 'unused')
            emit.assert_not_called()
        with self.assertRaisesRegex(ValueError, 'FIXED_CRASH'): command(Path('/not-created'), 'arbitrary')

    def test_flags_are_absent_by_default_and_reject_duplicates(self):
        guest = b.module('crash_flags', HERE / 'fixtures/secret_custody_persistence_guest.py')
        for raw, expected in (('quiet', None), ('kc_persistence_crash=after-receipt', 'after-receipt'),
                              ('kc_persistence_crash=recover', 'recover')):
            with patch.object(guest.Path, 'read_text', return_value=raw): self.assertEqual(guest.crash_mode(), expected)
        for raw in ('kc_persistence_crash=other', 'kc_persistence_crash=recover kc_persistence_crash=recover'):
            with patch.object(guest.Path, 'read_text', return_value=raw):
                with self.assertRaisesRegex(RuntimeError, 'FIXED_'): guest.crash_mode()

    def test_barrier_interruption_cannot_write_policy_or_success_marker(self):
        guest = b.module('crash_save', HERE / 'fixtures/secret_custody_persistence_guest.py')
        with tempfile.TemporaryDirectory() as name, patch.object(guest, 'ROOT', Path(name)):
            guest.atomic('policy.json', s.d.policy())
            fake = SimpleNamespace(boot=lambda: s.OLD_BOOT, read=lambda name: dict(boot=s.OLD_BOOT, deadline_ns=1), write=Mock())
            with patch.object(guest, 'context', return_value=(fake, None, s.d)), patch.object(guest, 'mounted', return_value=True), \
                    patch.object(guest, 'crash_mode', return_value='after-receipt'), \
                    patch.object(guest, 'await_crash', side_effect=RuntimeError('CRASH_STOP')):
                with self.assertRaisesRegex(RuntimeError, 'CRASH_STOP'): guest.save()
            fake.write.assert_not_called()
            self.assertEqual(s.d.decode(guest.read_bytes('policy.json')), s.d.policy())
            with self.assertRaisesRegex(ValueError, 'ORPHAN'): guest.load_state(s.d, s.NEW_BOOT, 10)

    def test_barrier_timeout_cannot_continue_and_open_packets_are_rejected(self):
        guest = b.module('crash_timeout', HERE / 'fixtures/secret_custody_persistence_guest.py')
        with tempfile.TemporaryDirectory() as name, patch.object(guest, 'ROOT', Path(name)):
            guest.atomic('policy.json', s.d.policy())
            receipt_sha = guest.atomic('receipt.json', dict(boot=s.OLD_BOOT, deadline_ns=1))
            fake = SimpleNamespace(guard=lambda: None, composition=lambda: 'awake', boot=lambda: s.OLD_BOOT,
                                   STATE=Path(name), link_up=lambda g: True)
            packets = SimpleNamespace(PEERS=('v4', 'v6'), reaches=lambda *args: False)
            with patch.object(guest, 'enabled', return_value=True), patch.object(guest, 'mounted', return_value=True), \
                    patch.object(guest, 'crash_mode', return_value='after-receipt'), patch.object(guest, 'emit') as emit, \
                    patch.object(guest.time, 'monotonic', side_effect=[0, 31]):
                with self.assertRaisesRegex(RuntimeError, 'TIMEOUT_NO_SAVE'): guest.await_crash(fake, packets, s.d, receipt_sha)
                self.assertEqual(emit.call_args.args[1], 'crash-ready')
            packets.reaches = lambda *args: True
            with patch.object(guest, 'enabled', return_value=True), patch.object(guest, 'mounted', return_value=True), \
                    patch.object(guest, 'crash_mode', return_value='after-receipt'), patch.object(guest, 'emit') as emit:
                with self.assertRaisesRegex(RuntimeError, 'CLOSED_UNPUBLISHED'): guest.await_crash(fake, packets, s.d, receipt_sha)
                emit.assert_not_called()

    def test_recovery_rejects_changed_state_same_boot_or_started_link(self):
        ready = dict(boot=s.OLD_BOOT, crash_state=dict(generation=0, receipt_boot=s.OLD_BOOT, policy_sha256='a'*64, receipt_sha256='b'*64))
        row = dict(event='refused', boot=s.NEW_BOOT, activation_allowed=False, link_up=False,
                   recovery_refusal='ORPHAN_RECEIPT_REFUSED', crash_state=ready['crash_state'])
        recovery_evidence(row, ready, 'host')
        for change in (dict(boot=s.OLD_BOOT), dict(boot='host'), dict(link_up=True), dict(activation_allowed=True),
                       dict(recovery_refusal='OTHER'), dict(crash_state=dict(ready['crash_state'], receipt_sha256='c'*64))):
            with self.assertRaisesRegex(RuntimeError, 'EXACT_CRASH_STATE'): recovery_evidence(dict(row, **change), ready, 'host')


if __name__ == '__main__':
    if sys.argv[1:] == ['--vm']: run_vm()
    elif sys.argv[1:] == ['--io-vm']: run_vm(io_faults=True)
    else: unittest.main(verbosity=2)
