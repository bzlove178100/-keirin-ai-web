"""Fault-scope unit tests; actual ENOSPC/EROFS evidence is required separately in CI."""
import errno
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('crash', HERE / 'test_secret_custody_persistence_crash.py')
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
guest = c.b.module('io_guest', HERE / 'fixtures/secret_custody_persistence_fault_guest.py')
persist = c.b.module('persist_io', HERE / 'fixtures/secret_custody_persistence_guest.py')


class Tests(unittest.TestCase):
    def test_host_and_missing_optin_refused_before_mutation(self):
        with patch.object(guest.os, 'open') as opening:
            with self.assertRaises((FileNotFoundError, RuntimeError)): guest.prepare('enospc')
            opening.assert_not_called()
        with patch.object(c.p, 'guard'), patch.dict(os.environ, {'KC_PERSISTENCE_CRASH_CI':'1', 'KC_PERSISTENCE_CI':'1', 'KC_PERSISTENCE_IO_CI':'0'}), patch.object(c.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'IO_OPT_IN'): c.run_vm(io_faults=True)
            run.assert_not_called()

    def test_allocator_has_size_time_and_errno_bounds(self):
        calls = []
        def allocation(fd, offset, length):
            calls.append((offset, length))
            if offset >= 1024*1024: raise OSError(errno.ENOSPC, 'unit fault')
        with patch.object(guest.os, 'posix_fallocate', side_effect=allocation):
            self.assertEqual(guest.allocate_to_full(123, 4096), 1024*1024)
        self.assertEqual(calls, [(0, 1024*1024), (1024*1024, 1024*1024), (1024*1024, 4096)])
        with patch.object(guest.os, 'posix_fallocate', side_effect=OSError(errno.EIO, 'unit fault')):
            with self.assertRaises(OSError): guest.allocate_to_full(123, 4096)
        with patch.object(guest.os, 'posix_fallocate') as allocate:
            with self.assertRaisesRegex(RuntimeError, 'BOUNDED_REAL'): guest.allocate_to_full(123, 4096)
            self.assertEqual(allocate.call_count, 64)
        with patch.object(guest.time, 'monotonic', side_effect=[0, 21]), patch.object(guest.os, 'posix_fallocate') as allocate:
            with self.assertRaisesRegex(RuntimeError, 'BOUNDED_REAL'): guest.allocate_to_full(123, 4096)
            allocate.assert_not_called()

    def test_readonly_mount_is_never_accepted_as_default_writable(self):
        row='1 0 254:0 / /state ro,nodev,nosuid,noexec - ext4 /dev/vda ro\n'
        with patch.object(persist.Path, 'read_text', return_value=row):
            self.assertTrue(persist.mounted('ro'))
            with self.assertRaisesRegex(RuntimeError, 'PRIVATE_EXT4'): persist.mounted()
        with patch.object(persist.Path, 'read_text', return_value=row.replace('/dev/vda','/dev/sda')):
            with self.assertRaisesRegex(RuntimeError, 'PRIVATE_EXT4'): persist.mounted('ro')

    def test_real_error_propagates_and_cannot_publish_saved_marker(self):
        for mode, number in (('enospc', errno.ENOSPC), ('erofs', errno.EROFS)):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as name, patch.object(persist, 'ROOT', Path(name)):
                persist.atomic('policy.json', c.s.d.policy())
                fake = SimpleNamespace(boot=lambda:c.s.OLD_BOOT, read=lambda name:dict(boot=c.s.OLD_BOOT, deadline_ns=1), write=Mock())
                helper = SimpleNamespace(prepare=Mock(), observe=Mock())
                atomic = persist.atomic
                error = OSError(number, 'unit error; actual kernel errors required in CI')
                def write(leaf, value):
                    if leaf == 'policy.json': raise error
                    return atomic(leaf, value)
                with patch.object(persist, 'context', return_value=(fake, None, c.s.d)), patch.object(persist, 'mounted', return_value=True), \
                        patch.object(persist, 'crash_mode', return_value=None), patch.object(persist, 'fault_mode', return_value=mode), \
                        patch.object(persist, 'module', return_value=helper), patch.object(persist, 'atomic', side_effect=write):
                    with self.assertRaises(OSError) as caught: persist.save()
                    self.assertIs(caught.exception, error)
                helper.prepare.assert_called_once_with(mode)
                helper.observe.assert_called_once_with(mode, error)
                fake.write.assert_not_called()
                with self.assertRaisesRegex(ValueError, 'ORPHAN'): persist.load_state(c.s.d, c.s.NEW_BOOT, 10)

    def test_wrong_error_writable_readonly_claim_and_unbounded_fill_rejected(self):
        for mode, number, mount in (('enospc', errno.ENOSPC, 'rw'), ('erofs', errno.EROFS, 'ro')):
            info=dict(mode=mode, errno=number, allocated_bytes=4096, allocator_errno=errno.ENOSPC,
                      prepared=dict(mount_mode=mount, free_blocks=0, reserved_clusters=0, block_size=4096),
                      after=dict(mount_mode=mount))
            c.fault_evidence(dict(filesystem_fault=info), mode)
            for change in (dict(errno=errno.EIO), dict(mode='other'), dict(after=dict(mount_mode='wrong'))):
                with self.assertRaises(RuntimeError): c.fault_evidence(dict(filesystem_fault=dict(info, **change)), mode)
            if mode == 'enospc':
                c.fault_evidence(dict(filesystem_fault=dict(info, prepared=dict(info['prepared'],
                    free_blocks=327, reserved_clusters=327))), mode)
                for change in (dict(allocated_bytes=c.s.SIZE+1), dict(allocator_errno=errno.EIO),
                               dict(prepared=dict(info['prepared'], free_blocks=1)),
                               dict(prepared=dict(info['prepared'], reserved_clusters=c.s.SIZE)),
                               dict(prepared=dict(info['prepared'], block_size=0))):
                    with self.assertRaises(RuntimeError): c.fault_evidence(dict(filesystem_fault=dict(info, **change)), mode)

    def test_fault_flags_reject_duplicates_unknown_and_mixed_crash(self):
        for mode in ('enospc','erofs'):
            with patch.object(persist.Path, 'read_text', return_value='kc_persistence_fault='+mode):
                self.assertEqual(persist.fault_mode(),mode)
        for raw in ('kc_persistence_fault=other', 'kc_persistence_fault=enospc kc_persistence_fault=erofs'):
            with patch.object(persist.Path, 'read_text', return_value=raw):
                with self.assertRaisesRegex(RuntimeError,'FIXED_'): persist.fault_mode()
        with patch.object(persist, 'context', return_value=(None,None,None)), \
                patch.object(persist, 'crash_mode', return_value='after-receipt'), patch.object(persist,'fault_mode',return_value='enospc'), \
                patch.object(persist, 'atomic') as atomic:
            with self.assertRaisesRegex(RuntimeError,'ONE_STORAGE'): persist.save()
            atomic.assert_not_called()


if __name__ == '__main__': unittest.main(verbosity=2)
