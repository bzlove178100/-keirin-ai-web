"""Direct transfer preserves the exact frozen session and append-only reviews."""
from copy import deepcopy
import http.client
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch

from ml.model_history import _digest, capture_prediction
from ml.synthetic_session import SessionStore, FILENAME
from ml.synthetic_workbench import Workbench, make_server
from test_model_history import snapshot, prediction
from test_held_history_review import pair, evidence, decision


def seed(app):
    seven, nine = snapshot(7), snapshot(9)
    app._commit(app._payload(scheduled=seven['scheduled_start'], current='a'*32,
                            snapshots={'a'*32: seven, 'b'*32: nine}))


def transfer(app):
    return app.import_review_session(app.review_session_source()['source_revision'],
                                     app.held_review.state()['revision'])


class SessionTransferTests(unittest.TestCase):
    def test_all_states_seven_nine_exact_copy_no_training_and_no_decisions(self):
        for status in ('dead_heat', 'withdrawn', 'cancelled'):
            app = Workbench()
            try:
                seed(app)
                for key, count in [('a'*32, 7), ('b'*32, 9)]:
                    app.hold(key, status, [count] if status == 'withdrawn' else None)
                frozen = deepcopy(app._payload())
                with patch.object(app, '_train', side_effect=AssertionError('no training')):
                    source = app.review_session_source()
                    self.assertEqual((source['held_count'], source['already_added']), (2, 0))
                    self.assertEqual(app.held_review.holds, [])  # GET is read-only.
                    state = transfer(app)
                self.assertEqual({_digest(r) for r in app.held_review.holds},
                                 {_digest(r) for r in app.histories.values()})
                self.assertEqual(state['report']['unresolved_races'], 2)
                self.assertEqual(state['report']['released_races'], 0)
                self.assertEqual(app.held_review.reviews, [])
                self.assertEqual(transfer(app), state)
                self.assertEqual(app.review_session_source()['already_added'], 2)
                self.assertEqual(app._payload(), frozen)
                self.assertFalse(app.ready)
            finally:
                app.close()

    def test_normal_history_omitted_existing_other_engine_and_decisions_preserved(self):
        app = Workbench()
        try:
            seed(app); app.settle('a'*32, '1-2-3', 40.0); app.hold('b'*32, 'withdrawn', [9])
            phase = pair(9, 'withdrawn')[0]
            w = app.held_review
            w.load(phase, w.state()['revision'])
            w.review(_digest(phase), evidence(phase), decision(), w.state()['revision'])
            before = deepcopy(w.reviews)
            self.assertEqual(app.review_session_source()['held_count'], 1)
            transfer(app)
            self.assertEqual(len(w.holds), 2)
            self.assertEqual(w.reviews, before)
            self.assertEqual(w.report['released_races'], 0)
            self.assertTrue(all(r['schema_version'].endswith('held-history-v1') for r in w.holds))
        finally:
            app.close()

    def test_atomic_limit_invalid_source_and_legacy_race_number_rejection(self):
        app = Workbench()
        try:
            seed(app); app.hold('a'*32, 'cancelled'); app.hold('b'*32, 'cancelled')
            before = app.held_review.bundle()
            with patch('ml.held_review_workspace.MAX_HOLDS', 1):
                with self.assertRaises(ValueError): transfer(app)
            self.assertEqual(app.held_review.bundle(), before)
            original = deepcopy(app.histories['b'*32])
            app.histories['b'*32]['snapshot']['snapshot_sha256'] = '0'*64
            with self.assertRaises(ValueError): transfer(app)
            self.assertEqual(app.held_review.bundle(), before)
            app.histories['b'*32] = original
        finally:
            app.close()
        app = Workbench()
        try:
            from datetime import datetime
            p = prediction(7); p['race']['race_number'] = 17
            with patch('ml.model_history.datetime', wraps=datetime) as clock:
                clock.now.return_value = datetime.fromisoformat('2026-10-17T01:00:00+00:00')
                snap = capture_prediction(p, synthetic=True)
            app._commit(app._payload(series=1, scheduled=snap['scheduled_start'],
                                     snapshots={'a'*32: snap}, current='a'*32))
            app.hold('a'*32, 'cancelled')
            frozen = deepcopy(app._payload())
            with self.assertRaisesRegex(ValueError, 'race_number_invalid'): transfer(app)
            self.assertEqual(app._payload(), frozen)
            self.assertEqual(app.held_review.holds, [])
        finally:
            app.close()

    def test_saved_copy_restores_and_failed_save_keeps_both_sources(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)/'session'; app = Workbench(directory)
            try:
                seed(app); app.hold('a'*32, 'cancelled')
                prediction_bytes = (directory/FILENAME).read_bytes()
                result = transfer(app)
                self.assertEqual((directory/FILENAME).read_bytes(), prediction_bytes)
                self.assertTrue(result['storage']['checkpoint_saved'])
            finally:
                app.close()
            app = Workbench(directory)
            try:
                self.assertEqual(app.held_review.state()['revision'], result['revision'])
                self.assertEqual(app.review_session_source()['already_added'], 1)
                self.assertFalse(app.ready)
                app.hold('b'*32, 'withdrawn', [9])
                frozen = deepcopy(app._payload()); before = app.held_review.bundle()
                review_path = directory/'held-review'/'held-review.json'
                saved = review_path.read_bytes()
                with patch('ml.synthetic_session.os.replace', side_effect=OSError('injected')):
                    from ml.synthetic_session import SessionSaveError
                    with self.assertRaises(SessionSaveError): transfer(app)
                self.assertEqual(app._payload(), frozen)
                self.assertEqual(app.held_review.bundle(), before)
                self.assertEqual(review_path.read_bytes(), saved)
                self.assertTrue(app.held_review.state()['storage']['write_blocked'])
                app.store.failed = True
                with self.assertRaisesRegex(ValueError, 'prediction_session_restart_required'):
                    app.review_session_source()
            finally:
                app.close()

    def test_http_stale_source_stale_target_origin_and_fields(self):
        temporary = TemporaryDirectory(); directory = Path(temporary.name)/'state'
        app = Workbench(directory); seed(app); app.hold('a'*32, 'cancelled')
        server = make_server(app); thread = Thread(target=server.serve_forever, daemon=True); thread.start()
        authority = f'127.0.0.1:{server.server_port}'
        def request(path, body=None, headers=None):
            connection = http.client.HTTPConnection(authority, timeout=10)
            h = {'Origin': 'http://'+authority, 'X-Keirin-Local': 'synthetic-only', 'Content-Type': 'application/json'}
            h.update(headers or {})
            connection.request('GET' if body is None else 'POST', path, None if body is None else json.dumps(body), h)
            response = connection.getresponse(); data = json.loads(response.read()); connection.close()
            return response.status, data
        path = '/api/held-review/import-session'
        source_path = '/api/held-review/session-source'
        try:
            source = request(source_path)[1]
            body = {'source_revision': source['source_revision'], 'revision': app.held_review.state()['revision']}
            for headers in ({'Origin':'https://wrong.invalid'}, {'Host':'wrong.invalid'}, {'X-Keirin-Local':''}):
                self.assertEqual(request(path, body, headers)[0], 403)
            self.assertEqual(request(path, {**body, 'replace': True})[0], 400)
            app.hold('b'*32, 'cancelled')
            self.assertEqual(request(path, body)[0], 409)
            self.assertEqual(app.held_review.holds, [])
            body['source_revision'] = request(source_path)[1]['source_revision']
            code, state = request(path, body); self.assertEqual(code, 200, state)
            self.assertEqual(len(state['records']), 2)
            self.assertEqual(request(path, body)[0], 409)
            body['revision'] = state['revision']
            self.assertEqual(request(path, body), (200, state))
            self.assertEqual(request(source_path, headers={'Origin':'https://wrong.invalid'})[0], 403)
            # This route must report a real checkpoint conflict as 503, too.
            before = app.held_review.bundle(); frozen = deepcopy(app._payload())
            checkpoint = directory/'held-review'/'held-review.json'
            checkpoint.write_text('external synthetic edit')
            code, failed = request(path, body)
            self.assertEqual(code, 503)
            self.assertTrue(failed['state']['storage']['write_blocked'])
            self.assertEqual(app.held_review.bundle(), before)
            self.assertEqual(app._payload(), frozen)
            self.assertEqual(checkpoint.read_text(), 'external synthetic edit')
        finally:
            server.shutdown(); server.server_close(); thread.join(); app.close()
            temporary.cleanup()

    def test_empty_source_does_not_create_checkpoint(self):
        with TemporaryDirectory() as tmp:
            app = Workbench(Path(tmp)/'state')
            try:
                self.assertEqual(app.review_session_source()['held_count'], 0)
                with self.assertRaisesRegex(ValueError, 'has_no_holds'): transfer(app)
                self.assertFalse(app.held_review.state()['storage']['checkpoint_saved'])
            finally:
                app.close()


if __name__ == '__main__':
    unittest.main()
