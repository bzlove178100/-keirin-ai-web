from copy import deepcopy
import http.client
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch

from ml.held_review_workspace import ReviewWorkspace, ReviewStore
from ml.model_history import _canonical, _digest
from ml.synthetic_session import SessionStore, SessionSaveError, FILENAME, MAX_BYTES
from ml.synthetic_workbench import Workbench, make_server
from test_held_history_review import pair, evidence, decision
from test_synthetic_workbench_session import saved_session


def load(workspace, value):
    return workspace.load(value, workspace.state()['revision'])


def decide(workspace, record, normal=True):
    return workspace.review(_digest(record), evidence(record, normal=normal),
                            decision(normal=normal), workspace.state()['revision'])


class HeldReviewSessionTests(unittest.TestCase):
    def test_partial_then_complete_restore_seven_nine_and_all_statuses(self):
        for count in (7, 9):
            for status in ('dead_heat', 'withdrawn', 'cancelled'):
                for normal in (True, False):
                    with self.subTest(count=count, status=status, normal=normal), TemporaryDirectory() as tmp:
                        records = list(pair(count, status))
                        workspace = ReviewWorkspace(tmp)
                        self.assertFalse(workspace.state()['storage']['checkpoint_saved'])
                        load(workspace, records)
                        decide(workspace, records[0], normal)
                        pending = workspace.bundle()
                        workspace.close()
                        workspace = ReviewWorkspace(tmp)
                        try:
                            self.assertEqual(workspace.bundle(), pending)
                            self.assertTrue(workspace.state()['storage']['restored'])
                            self.assertEqual(workspace.report['released_races'], 0)
                            decide(workspace, records[1], normal)
                            final, report = workspace.bundle(), deepcopy(workspace.report)
                            self.assertEqual(report['released_races'], int(normal))
                            self.assertEqual(report['confirmed_excluded_races'], int(not normal))
                        finally:
                            workspace.close()
                        workspace = ReviewWorkspace(tmp)
                        try:
                            self.assertEqual(workspace.bundle(), final)
                            self.assertEqual(workspace.report, report)
                            self.assertFalse(workspace.state()['storage']['write_blocked'])
                            # Re-importing a partial old file never erases later decisions.
                            load(workspace, pending)
                            self.assertEqual(workspace.bundle(), final)
                        finally:
                            workspace.close()
                        self.assertEqual((Path(tmp)/ReviewStore.filename).stat().st_mode & 0o777, 0o600)

    def test_existing_prediction_checkpoint_and_review_are_independent(self):
        with TemporaryDirectory() as tmp:
            initial = saved_session()
            store = SessionStore(Path(tmp)); store.save(initial); store.close()
            original = (Path(tmp)/FILENAME).read_bytes()
            app = Workbench(tmp)
            try:
                with patch.object(app, '_train', side_effect=AssertionError('no training')):
                    load(app.held_review, list(pair(9, 'withdrawn')))
                bundle = app.held_review.bundle()
                self.assertEqual((Path(tmp)/FILENAME).read_bytes(), original)
                self.assertEqual(app.snapshots, initial['snapshots'])
                self.assertFalse(app.ready)
            finally:
                app.close()
            app = Workbench(tmp)
            try:
                self.assertEqual(app.held_review.bundle(), bundle)
                self.assertTrue(app.held_review.state()['storage']['restored'])
                self.assertEqual(app.snapshots, initial['snapshots'])
                self.assertFalse(app.ready)
                app.select('b'*32)
                self.assertEqual(app.held_review.bundle(), bundle)
            finally:
                app.close()

    def test_failed_write_preserves_confirmed_state_and_blocks_future_mutations(self):
        for operation in ('fsync', 'replace'):
            with self.subTest(operation=operation), TemporaryDirectory() as tmp:
                workspace = ReviewWorkspace(tmp)
                record = pair()[0]; load(workspace, record)
                before = workspace.bundle(); path = Path(tmp)/ReviewStore.filename
                disk = path.read_bytes()
                try:
                    with patch('ml.synthetic_session.os.'+operation, side_effect=OSError('synthetic ENOSPC')):
                        with self.assertRaisesRegex(SessionSaveError, 'save_failed'):
                            decide(workspace, record)
                    self.assertEqual(workspace.bundle(), before)
                    self.assertEqual(path.read_bytes(), disk)
                    self.assertTrue(workspace.state()['storage']['write_blocked'])
                    with self.assertRaisesRegex(SessionSaveError, 'restart_required'):
                        load(workspace, record)
                    self.assertEqual(list(Path(tmp).glob('*.partial')), [])
                finally:
                    workspace.close()
                restored = ReviewWorkspace(tmp)
                try:
                    self.assertEqual(restored.bundle(), before)
                    decide(restored, record)
                    self.assertEqual(len(restored.reviews), 1)
                finally:
                    restored.close()

    def test_directory_sync_failure_restores_valid_new_file_without_false_success(self):
        with TemporaryDirectory() as tmp:
            workspace = ReviewWorkspace(tmp); record = pair()[0]; load(workspace, record)
            before = workspace.bundle(); real_fsync = os.fsync; calls = []
            def fail_directory(fd):
                calls.append(fd)
                if len(calls) == 2:
                    raise OSError('synthetic directory sync failure')
                real_fsync(fd)
            try:
                with patch('ml.synthetic_session.os.fsync', side_effect=fail_directory):
                    with self.assertRaisesRegex(SessionSaveError, 'save_uncertain'):
                        decide(workspace, record)
                self.assertEqual(workspace.bundle(), before)
                self.assertTrue(workspace.state()['storage']['write_blocked'])
            finally:
                workspace.close()
            restored = ReviewWorkspace(tmp)
            try:
                self.assertEqual(len(restored.reviews), 1)
                self.assertEqual(restored.report['released_races'], 1)
            finally:
                restored.close()

    def test_corrupt_checkpoint_refuses_startup_and_never_resets_or_promotes_partial(self):
        source = ReviewWorkspace(); load(source, pair()[0]); valid = source.bundle()
        bad = deepcopy(valid); bad['payload']['held_records'][0]['db_write_enabled'] = True
        bad['sha256'] = _digest(bad['payload'])
        for data in (b'{', b'{}', _canonical({**valid, 'sha256': 'bad'}).encode(), _canonical(bad).encode()):
            with self.subTest(size=len(data)), TemporaryDirectory() as tmp:
                path = Path(tmp)/ReviewStore.filename; path.write_bytes(data)
                (Path(tmp)/'review-orphan.partial').write_text(_canonical(valid))
                with self.assertRaises(ValueError):
                    ReviewWorkspace(tmp)
                self.assertEqual(path.read_bytes(), data)
                # Failed construction releases the lock. Explicit repair is required.
                path.write_text(_canonical(valid))
                restored = ReviewWorkspace(tmp)
                try:
                    self.assertEqual(restored.bundle(), valid)
                finally:
                    restored.close()
        with TemporaryDirectory() as tmp:
            (Path(tmp)/'review-orphan.partial').write_text(_canonical(valid))
            restored = ReviewWorkspace(tmp)
            try:
                self.assertEqual(restored.holds, [])
                self.assertFalse(restored.restored)
            finally:
                restored.close()

    def test_unsafe_files_size_and_repository_paths_are_rejected(self):
        for kind in ('symlink', 'hardlink', 'fifo', 'oversized'):
            with self.subTest(kind=kind), TemporaryDirectory() as tmp:
                directory = Path(tmp)/'review'; directory.mkdir()
                path = directory/ReviewStore.filename; target = Path(tmp)/'target'
                target.write_bytes(b'unchanged')
                if kind == 'symlink': path.symlink_to(target)
                elif kind == 'hardlink': os.link(target, path)
                elif kind == 'fifo': os.mkfifo(path)
                else:
                    with path.open('wb') as handle: handle.truncate(MAX_BYTES+1)
                with self.assertRaises((OSError, ValueError)):
                    ReviewWorkspace(directory)
                self.assertEqual(target.read_bytes(), b'unchanged')
        with self.assertRaisesRegex(ValueError, 'outside_repository'):
            ReviewWorkspace(Path(__file__).resolve().parents[1]/'review-test-state')

    def test_other_process_and_external_edits_cannot_overwrite_checkpoint(self):
        with TemporaryDirectory() as tmp:
            workspace = ReviewWorkspace(tmp); record = pair()[0]; load(workspace, record)
            before = workspace.bundle(); path = Path(tmp)/ReviewStore.filename
            try:
                script = 'from ml.held_review_workspace import ReviewWorkspace;ReviewWorkspace('+repr(tmp)+')'
                result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, timeout=15)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('session_already_open', result.stderr)
                path.write_bytes(b'external change')
                with self.assertRaisesRegex(SessionSaveError, 'save_failed'):
                    decide(workspace, record)
                self.assertEqual(workspace.bundle(), before)
                self.assertEqual(path.read_bytes(), b'external change')
            finally:
                workspace.close()
            with self.assertRaises(ValueError):
                ReviewWorkspace(tmp)

    def test_sigkill_before_and_after_atomic_replace(self):
        for position in ('before', 'after'):
            with self.subTest(position=position), TemporaryDirectory() as tmp:
                workspace = ReviewWorkspace(tmp); records = list(pair())
                load(workspace, records); before = workspace.bundle(); workspace.close()
                script = '''
import os,signal,sys
sys.path.insert(0,'tests')
from unittest.mock import patch
from ml.held_review_workspace import ReviewWorkspace
from test_synthetic_workbench_held_review_session import decide
w=ReviewWorkspace(sys.argv[1]); original=os.replace
def interrupted(*args,**kwargs):
    if sys.argv[2]=='after': original(*args,**kwargs)
    print('at_replace',flush=True)
    signal.pause()
with patch('ml.synthetic_session.os.replace',side_effect=interrupted):
    decide(w,w.holds[0])
'''
                child = subprocess.Popen([sys.executable, '-c', script, tmp, position], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    with selectors.DefaultSelector() as selector:
                        selector.register(child.stdout, selectors.EVENT_READ)
                        self.assertTrue(selector.select(timeout=15), 'child did not reach rename boundary')
                    self.assertEqual(child.stdout.readline().strip(), 'at_replace')
                    child.kill(); child.communicate(timeout=10)
                finally:
                    if child.poll() is None: child.kill(); child.communicate(timeout=10)
                restored = ReviewWorkspace(tmp)
                try:
                    self.assertEqual(restored.holds, before['payload']['held_records'])
                    self.assertEqual(len(restored.reviews), int(position == 'after'))
                    self.assertEqual(restored.report['released_races'], 0)  # Still a second unreviewed hold.
                finally:
                    restored.close()

    def test_http_failure_returns_review_state_and_keeps_backup_available(self):
        with TemporaryDirectory() as tmp:
            app = Workbench(tmp); record = pair()[0]; load(app.held_review, record)
            before = app.held_review.bundle(); server = make_server(app)
            thread = Thread(target=server.serve_forever, daemon=True); thread.start()
            try:
                authority = f'127.0.0.1:{server.server_port}'
                connection = http.client.HTTPConnection(authority, timeout=10)
                body = {'source_sha256': _digest(record), 'evidence_json': json.dumps(evidence(record)),
                        'decision': decision(), 'revision': before['sha256']}
                with patch('ml.synthetic_session.os.replace', side_effect=OSError('synthetic write failure')):
                    connection.request('POST', '/api/held-review/decision', json.dumps(body),
                        {'Origin': 'http://'+authority, 'X-Keirin-Local': 'synthetic-only', 'Content-Type': 'application/json'})
                    response = connection.getresponse(); value = json.loads(response.read()); connection.close()
                self.assertEqual(response.status, 503)
                self.assertTrue(value['state']['storage']['write_blocked'])
                self.assertEqual(value['state']['revision'], before['sha256'])
                self.assertEqual(value['state']['report']['input_reviews'], 0)
                connection = http.client.HTTPConnection(authority, timeout=10)
                connection.request('GET', '/export/held-review'); response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read()), before); connection.close()
                self.assertFalse(app.ready)
                self.assertEqual(app.histories, {})
            finally:
                server.shutdown(); server.server_close(); thread.join(); app.close()


if __name__ == '__main__': unittest.main()
