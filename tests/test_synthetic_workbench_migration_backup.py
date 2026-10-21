"""Preserve the exact v1 source before committing a v2 synthetic session."""
from copy import deepcopy
import http.client
import json
import os
from pathlib import Path
import select
import signal
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch

from ml.model_history import _digest
from ml.synthetic_session import (FILENAME, LEGACY_BACKUP_FILENAME, SCHEMA, LEGACY_SCHEMA,
                                  MAX_BYTES, SessionSaveError, SessionStore)
from ml.synthetic_workbench import Workbench, make_server
from test_model_history import NOW
from test_synthetic_workbench_rollover import generated_at
from test_synthetic_workbench_session import saved_session


def original_file(directory):
    payload = saved_session()
    # Non-canonical formatting proves that the source bytes, not just JSON
    # meaning, survive the migration backup.
    raw = (json.dumps({'sha256': _digest(payload), 'payload': payload}, indent=2)+'\n\n').encode()
    (directory/FILENAME).write_bytes(raw)
    return payload, raw


class MigrationBackupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = Workbench()
        try:
            app._apply(saved_session())
            with generated_at(app, NOW): app.predict(7)
            cls.candidate = deepcopy(app._payload())
        finally: app.close()

    def test_exact_original_only_at_migration_and_never_overwritten_afterward(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp); old, raw = original_file(directory)
            backup = directory/LEGACY_BACKUP_FILENAME; store = SessionStore(directory)
            try:
                self.assertFalse(backup.exists())
                self.assertEqual((directory/FILENAME).read_bytes(), raw)
                store.save(self.candidate)
                self.assertEqual(backup.read_bytes(), raw)
                self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
                self.assertEqual(backup.stat().st_nlink, 1)
                store.save({**self.candidate, 'current': 'b'*32})
                self.assertEqual(backup.read_bytes(), raw)
            finally: store.close()
            # Original v1 can be opened separately, without discarding the v2
            # session or rolling back the independently saved review workspace.
            restored_dir = directory/'original'; restored_dir.mkdir()
            (restored_dir/FILENAME).write_bytes(backup.read_bytes())
            original = Workbench(restored_dir)
            try:
                self.assertEqual(original._payload(), old)
                self.assertFalse(original.ready)
            finally: original.close()

    def test_existing_different_unsafe_and_oversized_backups_stop_before_replace(self):
        for kind in ('different', 'symlink', 'hardlink', 'fifo', 'oversized'):
            with self.subTest(kind=kind), TemporaryDirectory() as tmp:
                directory = Path(tmp); _, raw = original_file(directory)
                backup = directory/LEGACY_BACKUP_FILENAME; target = directory/'target'
                target.write_bytes(raw)
                if kind == 'different': backup.write_bytes(raw+b' ')
                elif kind == 'symlink': backup.symlink_to(target)
                elif kind == 'hardlink': os.link(target, backup)
                elif kind == 'fifo': os.mkfifo(backup)
                else:
                    with backup.open('wb') as handle: handle.truncate(MAX_BYTES+1)
                before = backup.lstat(); store = SessionStore(directory)
                try:
                    with self.assertRaisesRegex(SessionSaveError, 'migration_backup_failed'):
                        store.save(self.candidate)
                    self.assertEqual((directory/FILENAME).read_bytes(), raw)
                    self.assertEqual(target.read_bytes(), raw)
                    self.assertTrue(store.failed)
                    after = backup.lstat()
                    for field in ('st_ino', 'st_mode', 'st_size', 'st_mtime_ns', 'st_nlink'):
                        self.assertEqual(getattr(after, field), getattr(before, field))
                    with self.assertRaisesRegex(SessionSaveError, 'restart_required'): store.save(self.candidate)
                finally: store.close()

    def test_backup_io_failure_keeps_v1_and_completed_backup_can_be_reused(self):
        for failure in ('file_sync', 'directory_sync', 'link', 'main_replace'):
            with self.subTest(failure=failure), TemporaryDirectory() as tmp:
                directory = Path(tmp); _, raw = original_file(directory); store = SessionStore(directory)
                real_sync = os.fsync
                def sync(fd):
                    is_directory = stat.S_ISDIR(os.fstat(fd).st_mode)
                    if is_directory == (failure == 'directory_sync'):
                        raise OSError('injected backup sync failure')
                    real_sync(fd)
                target = 'os.link' if failure == 'link' else 'os.replace' if failure == 'main_replace' else 'os.fsync'
                effect = sync if failure.endswith('sync') else OSError('injected publication failure')
                try:
                    with patch('ml.synthetic_session.'+target, side_effect=effect):
                        with self.assertRaises(SessionSaveError): store.save(self.candidate)
                    self.assertEqual((directory/FILENAME).read_bytes(), raw)
                    self.assertTrue(store.failed)
                    self.assertEqual(list(directory.glob('*.partial')), [])
                finally: store.close()
                backup = directory/LEGACY_BACKUP_FILENAME
                if backup.exists(): self.assertEqual(backup.read_bytes(), raw)
                store = SessionStore(directory)
                try: store.save(self.candidate)
                finally: store.close()
                self.assertEqual(backup.read_bytes(), raw)
                self.assertEqual(json.loads((directory/FILENAME).read_bytes())['payload'], self.candidate)

    def test_backup_appearing_during_publication_is_never_overwritten(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp); _, raw = original_file(directory); store = SessionStore(directory)
            backup = directory/LEGACY_BACKUP_FILENAME; real_link = os.link
            def collision(*args, **kwargs):
                backup.write_bytes(b'other backup appeared')
                return real_link(*args, **kwargs)
            try:
                with patch('ml.synthetic_session.os.link', side_effect=collision):
                    with self.assertRaisesRegex(SessionSaveError, 'migration_backup_failed'): store.save(self.candidate)
                self.assertEqual(backup.read_bytes(), b'other backup appeared')
                self.assertEqual((directory/FILENAME).read_bytes(), raw)
                self.assertEqual(list(directory.glob('*.partial')), [])
            finally: store.close()

    def test_sigkill_before_and_after_main_replace_preserves_both_versions(self):
        script = '''
import json, os, signal, sys
from pathlib import Path
from ml.synthetic_session import SessionStore
directory, phase = sys.argv[1:]
payload = json.load(sys.stdin)
store = SessionStore(Path(directory))
real_replace, real_link = os.replace, os.link
def stop():
    print('checkpoint', flush=True)
    signal.pause()
def replace(*args, **kwargs):
    if phase == 'before': stop()
    real_replace(*args, **kwargs)
    if phase == 'after': stop()
def link(*args, **kwargs):
    real_link(*args, **kwargs)
    if phase == 'linked': stop()
os.replace, os.link = replace, link
store.save(payload)
'''
        for phase in ('before', 'after', 'linked'):
            with self.subTest(phase=phase), TemporaryDirectory() as tmp:
                directory = Path(tmp); _, raw = original_file(directory)
                child = subprocess.Popen([sys.executable, '-c', script, tmp, phase],
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    child.stdin.write(json.dumps(self.candidate).encode()); child.stdin.close()
                    ready, _, _ = select.select([child.stdout], [], [], 10)
                    self.assertTrue(ready, 'child did not reach migration checkpoint')
                    self.assertEqual(child.stdout.readline(), b'checkpoint\n')
                    child.send_signal(signal.SIGKILL); child.wait(timeout=10)
                    self.assertEqual(child.returncode, -signal.SIGKILL)
                finally:
                    if child.poll() is None: child.kill(); child.wait(timeout=10)
                    child.stdout.close(); child.stderr.close()
                backup = directory/LEGACY_BACKUP_FILENAME
                self.assertEqual(backup.read_bytes(), raw)
                store = SessionStore(directory)
                try:
                    self.assertEqual(store.loaded['schema_version'], SCHEMA if phase == 'after' else LEGACY_SCHEMA)
                    if phase == 'linked':
                        # A kill between link and unlink leaves two links. Keep
                        # the v1 source and refuse automatic cleanup/promotion.
                        self.assertEqual(backup.stat().st_nlink, 2)
                        with self.assertRaisesRegex(SessionSaveError, 'migration_backup_failed'): store.save(self.candidate)
                        self.assertEqual((directory/FILENAME).read_bytes(), raw)
                    else:
                        store.save(self.candidate)
                        self.assertEqual(backup.read_bytes(), raw)
                finally: store.close()

    def test_http_backup_failure_reports_503_and_preserves_old_memory(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp); old, raw = original_file(directory)
            (directory/LEGACY_BACKUP_FILENAME).write_bytes(b'conflicting backup')
            app = Workbench(directory); server = make_server(app)
            thread = Thread(target=server.serve_forever, daemon=True); thread.start()
            try:
                authority = f'127.0.0.1:{server.server_port}'
                connection = http.client.HTTPConnection(authority, timeout=10)
                with generated_at(app, NOW):
                    connection.request('POST', '/api/predict', json.dumps({'rider_count': 7}),
                                       {'Origin': 'http://'+authority, 'Content-Type': 'application/json',
                                        'X-Keirin-Local': 'synthetic-only'})
                    response = connection.getresponse(); body = json.loads(response.read()); connection.close()
                self.assertEqual(response.status, 503)
                self.assertEqual(body['error'], 'session_migration_backup_failed_restart_required')
                self.assertTrue(body['state']['storage']['write_blocked'])
                self.assertEqual(app._payload(), old)
                self.assertEqual((directory/FILENAME).read_bytes(), raw)
            finally: server.shutdown(); server.server_close(); thread.join(); app.close()

    def test_fresh_v2_and_old_v1_operations_do_not_create_backup(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp); old, _ = original_file(directory); store = SessionStore(directory)
            try: store.save({**old, 'current': 'b'*32})
            finally: store.close()
            self.assertFalse((directory/LEGACY_BACKUP_FILENAME).exists())
        with TemporaryDirectory() as tmp:
            directory = Path(tmp); store = SessionStore(directory)
            try:
                store.save({**self.candidate, 'legacy': None, 'snapshots': {}, 'histories': {}, 'current': None})
            finally: store.close()
            self.assertFalse((directory/LEGACY_BACKUP_FILENAME).exists())


if __name__ == '__main__': unittest.main()
