"""One bounded guest-owned ext4 image; never mount/format a host device."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('restart', HERE / 'test_secret_custody_systemd_restart.py')
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
c, b, p, vm = r.c, r.b, r.p, r.vm
d = b.module('durable', HERE.parent / 'review/secret_custody_durable_policy.py')
SIZE = 64 * 1024 * 1024


def disk(path, case):
    p.guard()
    if os.environ.get('KC_PERSISTENCE_CI') != '1': raise RuntimeError('PERSISTENCE_OPT_IN_REQUIRED')
    if case not in ('valid', 'missing', 'corrupt', 'stale'): raise ValueError('FIXED_DURABLE_CASE_REQUIRED')
    seed = path / 'seed'; seed.mkdir(mode=0o700)
    if case != 'missing':
        value = d.policy()
        if case == 'stale': value['lease'] = dict(boot='00000000-0000-4000-8000-000000000001', deadline_ns=10**15)
        (seed / 'policy.json').write_text('{broken' if case == 'corrupt' else json.dumps(value))
    target = path / 'state.raw'
    with target.open('xb') as f: f.truncate(SIZE)
    target.chmod(0o600)
    subprocess.run(['/usr/sbin/mkfs.ext4', '-F', '-q', '-L', 'KCSTATE', '-d', str(seed), str(target)],
                   check=True, capture_output=True, timeout=20)
    print('PERSIST_VOLUME_PROVENANCE ' + json.dumps(dict(case=case, bytes=SIZE,
          initial_sha256=hashlib.sha256(target.read_bytes()).hexdigest(), mkfs_sha256=hashlib.sha256(Path('/usr/sbin/mkfs.ext4').read_bytes()).hexdigest())), flush=True)


def command(path, boot_case, mode):
    target = path / 'state.raw'
    info = target.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size != SIZE or target.resolve().parent != path.resolve():
        raise RuntimeError('OWNED_REGULAR_VOLUME_REQUIRED')
    args = c.command(path, boot_case, mode)
    args[args.index('-append')+1] += ' kc_systemd_restart=1 kc_persistence=1 end=10'
    args += ['-drive', 'if=none,id=kc-state,format=raw,file=' + str(target) + ',cache=writeback',
             '-device', 'virtio-blk-pci,drive=kc-state,serial=KCSTATE']
    return args


def block_evidence(rows, path):
    if len(rows) != 1: raise RuntimeError('ONE_OWNED_BLOCK_REQUIRED')
    inserted = rows[0].get('inserted', {})
    image = inserted.get('image', {})
    if (inserted.get('file') != str(path / 'state.raw') or inserted.get('ro') is not False
            or image.get('format') != 'raw' or image.get('virtual-size') != SIZE
            or image.get('backing-filename') or inserted.get('backing_file')):
        raise RuntimeError('FIXED_PRIVATE_RAW_BLOCK_REQUIRED')


def record(lines, event, case):
    deadline = time.monotonic()+75
    diagnostic = []
    while True:
        try: line = lines.line(deadline)
        except Exception:
            print('PERSIST_DIAGNOSTIC ' + '\n'.join(diagnostic)[-6000:], flush=True); raise
        diagnostic.append(line[:1500]); diagnostic = diagnostic[-30:]
        if line.startswith('SYSTEMD_PERSIST_RECORD '):
            row = json.loads(line[len('SYSTEMD_PERSIST_RECORD '):])
            if row.get('event') != event or row.get('link_up') is not False or row.get('activation_allowed') is not False:
                raise RuntimeError('MATCHED_CLOSED_DURABLE_RECORD_REQUIRED')
            print(line, flush=True); return row
        if line.startswith(('SYSTEMD_PERSIST_STAGE_ERROR', 'SYSTEMD_LEASE_FAIL', 'SYSTEMD_RESTART_FAIL')) or 'Kernel panic' in line:
            raise RuntimeError('DURABLE_BOOT_FAILED ' + '\n'.join(diagnostic)[-6000:])


def loaded_evidence(row, first, previous):
    if row['boot'] != first['boot'] or row['monotonic'] >= first['linked']['up_ns']/1e9:
        raise RuntimeError('PERSISTENT_READ_BEFORE_LINK_REQUIRED')
    state = row['store_state']
    if state['ActiveState'] != 'active' or state['Result'] != 'success': raise RuntimeError('SUCCESSFUL_MOUNT_REQUIRED')
    if not 0 < int(first['states']['setup']['ExecMainExitTimestampMonotonic']) <= int(state['ExecMainStartTimestampMonotonic']) < int(state['ExecMainExitTimestampMonotonic']) <= int(first['states']['gate']['ExecMainStartTimestampMonotonic']):
        raise RuntimeError('ACTUAL_STORE_GATE_ORDER_REQUIRED')
    if previous is None:
        if row['generation'] != 0 or row['saved_receipt'] is not None or row['replay_reason'] != 'NO_SAVED_RECEIPT': raise RuntimeError('FRESH_SEED_REQUIRED')
    else:
        if (row['generation'] != previous['generation'] or row['writer_boot'] != previous['boot']
                or row['policy_sha256'] != previous['policy_sha256'] or row['replay_reason'] != 'PRIOR_BOOT_LEASE_REFUSED'
                or row['saved_receipt']['boot'] != previous['boot'] or row['boot'] == previous['boot']):
            raise RuntimeError('DURABLE_WRITE_AND_OLD_LEASE_REFUSAL_REQUIRED')
        data = (json.dumps(row['saved_receipt'], sort_keys=True) + '\n').encode()
        if hashlib.sha256(data).hexdigest() != previous['receipt_sha256']: raise RuntimeError('EXACT_SAVED_RECEIPT_REQUIRED')


def case(path, kind, host_boot):
    boot_case = {'valid':'closed', 'missing':'missing', 'corrupt':'invalid', 'stale':'invalid'}[kind]
    mode = 'suspend' if kind == 'valid' else 'awake'
    process = None
    try:
        with (path/'stderr').open('wb') as err:
            process = subprocess.Popen(command(path, boot_case, mode), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                       stderr=err, cwd=path, env={'PATH':'/usr/bin:/bin', 'LANG':'C'})
            with vm.connect(path/'qmp', process) as monitor, vm.connect(path/'serial', process) as serial:
                qmp, lines = vm.QMP(monitor), vm.Lines(serial)
                block_evidence(qmp.call('query-block'), path)
                if qmp.call('query-current-machine').get('wakeup-suspend-support') is not True: raise RuntimeError('S3_MACHINE_REQUIRED')
                previous, boots = None, {host_boot}
                if kind == 'valid':
                    for command_bytes, target, event in ((b'restart\n', 'reboot.target', 'RESET'), (b'halt\n', 'poweroff.target', 'SHUTDOWN')):
                        loaded = record(lines, 'loaded', kind)
                        first = c.cycle(lines, qmp, boot_case, mode, host_boot)
                        loaded_evidence(loaded, first, previous)
                        boot = first['boot']
                        if boot in boots: raise RuntimeError('FRESH_BOOT_REQUIRED')
                        boots.add(boot)
                        qmp.events = []
                        serial.sendall(command_bytes)
                        rows = [r.record(lines, e, boot, target) for e in ('requested', 'link_down', 'stopped')]
                        r.evidence(*rows)
                        previous = rows[0]['persistence']
                        stopped = rows[2]['persistence']
                        if stopped['unmounted'] is not True or stopped['saved'] != previous: raise RuntimeError('SAVED_THEN_UNMOUNTED_REQUIRED')
                        observed = qmp.event(event, time.monotonic()+30)
                        if observed.get('data', {}).get('guest') is not True: raise RuntimeError('GUEST_TRANSITION_REQUIRED')
                    if process.wait(timeout=10) != 0: raise RuntimeError('NORMAL_POWEROFF_REQUIRED')
                else:
                    denied = record(lines, 'refused', kind)
                    first = b.record(lines, 'observed', boot_case); b.evidence(first)
                    if first['boot'] in boots or first['boot'] != denied['boot']: raise RuntimeError('SAME_DISTINCT_BOOT_REQUIRED')
                    c.service_evidence(c.record(lines, 'completed', mode, first['boot']), boot_case)
                    serial.sendall(b'clean\n')
                    done = b.record(lines, 'done', boot_case)
                    if done['boot'] != first['boot'] or done.get('interfaces') != ['lo']: raise RuntimeError('NEGATIVE_CLEANUP_REQUIRED')
                print('PASS SYSTEMD_PERSISTENCE ' + kind, flush=True)
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
        for name in ('qmp','serial'): (path/name).unlink(missing_ok=True)


def run_vm():
    p.guard()
    if os.environ.get('KC_PERSISTENCE_CI') != '1': raise RuntimeError('PERSISTENCE_OPT_IN_REQUIRED')
    host_boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip(); netns = os.readlink('/proc/self/ns/net')
    with tempfile.TemporaryDirectory(prefix='kc-persist-') as value:
        path = Path(value)
        kernel = subprocess.run(['sudo','-n','/usr/bin/cat','/boot/vmlinuz-'+os.uname().release], check=True, capture_output=True, timeout=10).stdout
        if not 1024*1024 <= len(kernel) <= 64*1024*1024: raise RuntimeError('KERNEL_SIZE_BOUND')
        (path/'vmlinuz').write_bytes(kernel); b.payload(path, composed=True, restart=True, persistence=True)
        for kind in ('valid','missing','corrupt','stale'):
            child = path/kind; child.mkdir(mode=0o700)
            for name in ('vmlinuz','initramfs'): (child/name).symlink_to(path/name)
            disk(child, kind); case(child, kind, host_boot)
    if path.exists() or Path('/proc/sys/kernel/random/boot_id').read_text().strip() != host_boot or os.readlink('/proc/self/ns/net') != netns:
        raise RuntimeError('HOST_UNCHANGED_AND_OWNED_VOLUME_CLEANUP_REQUIRED')
    print('PASS PERSISTENCE_VOLUMES_IMAGES_PROCESSES_CLEANED_HOST_UNCHANGED NO_LIVE_APPLY', flush=True)


class Tests(unittest.TestCase):
    def test_closed_config_rejects_unknown_lease_open_duplicate_and_bad_bytes(self):
        self.assertEqual(d.decode(json.dumps(d.policy()).encode()), d.policy())
        for raw in (b'{broken', b'{}', b'[]', b'x'*4097,
                    json.dumps(dict(d.policy(), lease={})).encode(), json.dumps(dict(d.policy(), activation_allowed=True)).encode(),
                    json.dumps(dict(d.policy(), generation=True)).encode(), json.dumps(dict(d.policy(), profile='open')).encode(),
                    b'{"schema":1,"schema":2}'):
            with self.assertRaises(ValueError): d.decode(raw)

    def test_saved_receipt_never_authorizes_opening(self):
        self.assertEqual(d.replay_reason(dict(boot='old', deadline_ns=1000), 'new', 10), 'PRIOR_BOOT_LEASE_REFUSED')
        self.assertEqual(d.replay_reason(dict(boot='new', deadline_ns=10), 'new', 10), 'EXPIRED_LEASE_REFUSED')
        self.assertEqual(d.replay_reason(dict(boot='new', deadline_ns=1000), 'new', 10), 'RECEIPT_IS_NOT_AUTHORIZATION')
        self.assertEqual(d.replay_reason(dict(boot='new', deadline_ns=True), 'new', 10), 'INVALID_SAVED_LEASE')

    def test_volume_guard_precedes_creation_and_builder_requires_restart(self):
        with patch.object(p, 'guard'), patch.dict(os.environ, {'KC_PERSISTENCE_CI':'0'}), patch.object(subprocess,'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'OPT_IN'): disk(Path('/not-created'), 'valid')
            run.assert_not_called()
        with self.assertRaises(ValueError): b.u.units(persistence=True)
        guest = b.module('persist', HERE/'fixtures/secret_custody_persistence_guest.py')
        with patch.object(subprocess, 'run') as run:
            with self.assertRaises((FileNotFoundError, RuntimeError)): guest.main('mount')
            run.assert_not_called()

    def test_command_rejects_symlinks_and_block_readback_rejects_other_disk(self):
        with tempfile.TemporaryDirectory() as name:
            path=Path(name); (path/'other').write_bytes(b'')
            (path/'state.raw').symlink_to(path/'other')
            with self.assertRaisesRegex(RuntimeError, 'REGULAR_VOLUME'): command(path,'closed','awake')
            with self.assertRaises(RuntimeError): block_evidence([],path)
            row=dict(inserted=dict(file=str(path/'state.raw'), ro=False, image={'format':'raw','virtual-size':SIZE}))
            block_evidence([row],path)
            with self.assertRaises(RuntimeError): block_evidence([row,row],path)
            row['inserted']['image']['backing-filename']='/dev/sda'
            with self.assertRaises(RuntimeError): block_evidence([row],path)

    def test_mount_gates_startup_and_unmount_precedes_final_check(self):
        units=b.u.units(composed=True,restart=True,persistence=True)
        self.assertIn('Requires=kc-store.service\nAfter=kc-store.service',units['kc-gate.service'])
        self.assertIn('Before=shutdown.target umount.target',units['kc-store.service'])
        self.assertIn('After=shutdown.target umount.target',units['kc-shutdown-check.service'])
        self.assertNotIn('kc-store.service',b.u.units(composed=True,restart=True))


if __name__ == '__main__':
    if sys.argv[1:] == ['--vm']: run_vm()
    else: unittest.main(verbosity=2)
