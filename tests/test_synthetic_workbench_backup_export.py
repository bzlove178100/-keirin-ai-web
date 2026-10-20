"""Read-only migration-original inspection and exact, revision-bound downloads."""
from copy import deepcopy
import hashlib
import http.client
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch

from ml.model_history import _digest
from ml.synthetic_session import FILENAME, LEGACY_BACKUP_FILENAME, MAX_BYTES, SessionStore
from ml.synthetic_workbench import Workbench, make_server
from test_model_history import NOW
from test_synthetic_workbench_migration_backup import original_file
from test_synthetic_workbench_rollover import generated_at


def migrated(directory):
    old, raw = original_file(directory)
    app = Workbench(directory)
    with generated_at(app, NOW): app.predict(7)
    return app, old, raw


class BackupExportTests(unittest.TestCase):
    def test_missing_v1_completed_backup_and_migrated_records(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp); old, raw = original_file(directory)
            app = Workbench(directory)
            try:
                self.assertEqual(app.migration_backup(), ({'status': 'missing'}, None))
                (directory/LEGACY_BACKUP_FILENAME).write_bytes(raw)
                self.assertEqual(app.migration_backup()[1], raw)
                with generated_at(app, NOW): app.predict(7)
                app.hold('b'*32, 'cancelled')  # A later result is not part of the original.
                info, data = app.migration_backup()
                self.assertEqual(info, {'status': 'available', 'sha256': hashlib.sha256(raw).hexdigest(),
                                        'bytes': len(raw), 'snapshots': 2, 'histories': 1})
                self.assertEqual(data, raw)
                self.assertEqual(json.loads(data)['payload'], old)
                self.assertEqual(len(app.histories), 2)
            finally: app.close()

    def test_invalid_file_or_envelope_never_exposes_bytes_or_blocks_writes(self):
        for kind in ('symlink', 'hardlink', 'fifo', 'oversize', 'json', 'digest', 'schema', 'deep'):
            with self.subTest(kind=kind), TemporaryDirectory() as tmp:
                directory = Path(tmp); app, old, raw = migrated(directory)
                target = directory/LEGACY_BACKUP_FILENAME; target.unlink()
                other = directory/'other'; other.write_bytes(raw)
                if kind == 'symlink': target.symlink_to(other)
                elif kind == 'hardlink': os.link(other, target)
                elif kind == 'fifo': os.mkfifo(target)
                elif kind == 'oversize':
                    with target.open('wb') as handle: handle.truncate(MAX_BYTES+1)
                elif kind == 'json': target.write_bytes(b'{')
                elif kind == 'deep': target.write_bytes(b'['*2000+b']'*2000)
                else:
                    value = old if kind == 'digest' else app._payload()
                    target.write_text(json.dumps({'payload': value, 'sha256': '0'*64 if kind == 'digest' else _digest(value)}))
                before = (directory/FILENAME).read_bytes()
                try:
                    self.assertEqual(app.migration_backup(), ({'status': 'invalid'}, None))
                    self.assertFalse(app.store.failed)
                    self.assertEqual((directory/FILENAME).read_bytes(), before)
                    self.assertEqual(other.read_bytes(), raw)
                finally: app.close()

    def test_valid_unrelated_metadata_or_history_is_refused(self):
        for kind in ('legacy', 'history', 'v1_bytes'):
            with self.subTest(kind=kind), TemporaryDirectory() as tmp:
                directory = Path(tmp)
                if kind == 'v1_bytes':
                    _, raw = original_file(directory); app = Workbench(directory)
                    (directory/LEGACY_BACKUP_FILENAME).write_bytes(raw+b' ')
                else:
                    app, old, _ = migrated(directory)
                    if kind == 'legacy': old['series'] += 1
                    else:
                        # Another fully valid result for the same frozen snapshot.
                        from ml.model_history import settle_snapshot
                        from test_model_history import settlement
                        snap = old['snapshots']['a'*32]
                        result = settlement(snap); result['settlement_odds'] = 75.0
                        old['histories']['a'*32] = settle_snapshot(snap, result, synthetic=True)
                    (directory/LEGACY_BACKUP_FILENAME).write_text(json.dumps({'payload': old, 'sha256': _digest(old)}))
                try: self.assertEqual(app.migration_backup(), ({'status': 'unrelated'}, None))
                finally: app.close()

    def test_inspection_has_no_write_sync_or_training_side_effects(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp); app, _, raw = migrated(directory)
            files = {p: p.read_bytes() for p in directory.rglob('*') if p.is_file()}
            payload = deepcopy(app._payload()); expected = app.store.expected
            try:
                with patch('ml.synthetic_session.os.fsync', side_effect=AssertionError('read only')), \
                     patch('ml.synthetic_session.os.replace', side_effect=AssertionError('read only')), \
                     patch.object(app, '_train', side_effect=AssertionError('read only')):
                    for _ in range(2): self.assertEqual(app.migration_backup()[1], raw)
                self.assertEqual(app._payload(), payload)
                self.assertEqual(app.store.expected, expected)
                self.assertEqual({p: p.read_bytes() for p in directory.rglob('*') if p.is_file()}, files)
                self.assertFalse(app.store.failed)
            finally: app.close()

    def test_external_change_and_uncertain_save_are_not_claimed_current(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp); app, _, raw = migrated(directory)
            try:
                app.store.failed = True
                self.assertEqual(app.migration_backup()[1], raw)  # Failed write before replacement is still readable.
                (directory/FILENAME).write_bytes(app.store.expected+b' ')
                self.assertEqual(app.migration_backup(), ({'status': 'current_changed'}, None))
            finally: app.close()

    def test_http_exact_download_stale_revision_origin_and_fixed_path(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp); app, _, raw = migrated(directory)
            server = make_server(app); thread = Thread(target=server.serve_forever, daemon=True); thread.start()
            def get(path, headers=None):
                conn = http.client.HTTPConnection(*server.server_address)
                try:
                    conn.request('GET', path, headers=headers or {})
                    response = conn.getresponse(); return response.status, dict(response.getheaders()), response.read()
                finally: conn.close()
            try:
                status, _, body = get('/api/session-v1-backup'); self.assertEqual(status, 200)
                info = json.loads(body); url = '/export/session-v1/'+info['sha256']
                status, headers, body = get(url)
                self.assertEqual(status, 200); self.assertEqual(body, raw)
                self.assertEqual(headers['Content-Length'], str(len(raw)))
                self.assertEqual(headers['Cache-Control'], 'no-store')
                self.assertIn(LEGACY_BACKUP_FILENAME, headers['Content-Disposition'])
                # Same valid JSON, changed raw bytes: old displayed digest must fail.
                (directory/LEGACY_BACKUP_FILENAME).write_bytes(raw+b' ')
                self.assertEqual(get(url)[0], 409)
                new_info = json.loads(get('/api/session-v1-backup')[2])
                self.assertNotEqual(new_info['sha256'], info['sha256'])
                self.assertEqual(get('/export/session-v1/'+new_info['sha256'])[2], raw+b' ')
                for headers in ({'Origin': 'https://example.invalid'}, {'Sec-Fetch-Site': 'cross-site'}, {'Host': 'example.invalid'}):
                    self.assertEqual(get(url, headers)[0], 403)
                    self.assertEqual(get('/api/session-v1-backup', headers)[0], 403)
                for bad in ('../synthetic-session.json', 'a'*63, info['sha256']+'?path=other'):
                    self.assertEqual(get('/export/session-v1/'+bad)[0], 404)
                (directory/LEGACY_BACKUP_FILENAME).unlink()
                self.assertEqual(get(url)[0], 409)
                self.assertEqual(json.loads(get('/api/session-v1-backup')[2]), {'status': 'missing'})
            finally: server.shutdown(); server.server_close(); thread.join(); app.close()

    def test_temporary_and_new_session_never_invent_original(self):
        for persisted in (False, True):
            with TemporaryDirectory() as tmp:
                app = Workbench(Path(tmp) if persisted else None)
                try:
                    self.assertEqual(app.migration_backup(), ({'status': 'missing' if persisted else 'temporary'}, None))
                    self.assertFalse((Path(tmp)/LEGACY_BACKUP_FILENAME).exists())
                finally: app.close()


if __name__ == '__main__': unittest.main()
