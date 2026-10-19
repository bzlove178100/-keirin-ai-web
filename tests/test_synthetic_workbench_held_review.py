from copy import deepcopy
import http.client
import json
from threading import Thread
import unittest
from unittest.mock import patch

from ml.held_review_workspace import ReviewWorkspace, ReviewConflict
from ml.held_history_review import evaluate_reviews
from ml.model_history import _digest
from ml.synthetic_workbench import Workbench, make_server
from test_held_history_review import pair, evidence, decision, review


class ReviewWorkspaceTests(unittest.TestCase):
    def load(self, workspace, value):
        return workspace.load(value, workspace.state()['revision'])

    def test_roundtrip_both_engines_all_nonstandard_states(self):
        for count in (7, 9):
            for status in ('dead_heat', 'withdrawn', 'cancelled'):
                for normal in (False, True):
                    with self.subTest(count=count, status=status, normal=normal):
                        records = list(pair(count, status))
                        original = deepcopy(records)
                        workspace = ReviewWorkspace()
                        self.load(workspace, records)
                        for i, record in enumerate(records):
                            state = workspace.review(_digest(record), evidence(record, normal=normal),
                                                     decision(normal=normal), workspace.state()['revision'])
                            self.assertEqual(state['report']['released_races'], int(normal and i == 1))
                        report = state['report']
                        self.assertEqual(report['confirmed_excluded_races'], int(not normal))
                        bundle = json.loads(json.dumps(workspace.bundle()))
                        restored = ReviewWorkspace()
                        self.assertEqual(self.load(restored, bundle), state)
                        # CLI report is reusable only after strict recomputation.
                        from_report = ReviewWorkspace()
                        self.assertEqual(self.load(from_report, workspace.report), state)
                        self.assertEqual(records, original)
                        self.assertFalse(report['supervised_training_enabled'])
                        self.assertFalse(report['production_prediction_enabled'])

    def test_import_merges_never_removes_holds_or_conflicting_decisions(self):
        first, second = pair()
        workspace = ReviewWorkspace()
        partial = evaluate_reviews([first], [review(first)], synthetic=True)
        self.load(workspace, partial)
        self.assertEqual(workspace.report['released_races'], 1)
        self.load(workspace, second)
        self.assertEqual(workspace.report['released_races'], 0)
        self.load(workspace, partial)
        self.assertEqual(workspace.report['unresolved_races'], 1)
        self.assertEqual(len(workspace.holds), 2)
        other = evaluate_reviews([second], [review(second, normal=False)], synthetic=True)
        self.load(workspace, other)
        self.assertEqual(workspace.report['cases'][0]['reason'], 'conflicting_review_decisions')
        self.load(workspace, evaluate_reviews([second], [review(second)], synthetic=True))
        self.assertEqual(workspace.report['cases'][0]['reason'], 'conflicting_reviews')
        saved = workspace.bundle()
        for _ in range(2):
            self.load(workspace, saved)
        self.assertEqual(workspace.bundle(), saved)

    def test_invalid_file_is_atomic_even_with_valid_prefix_or_recomputed_hash(self):
        records = list(pair())
        workspace = ReviewWorkspace()
        self.load(workspace, records[0])
        before = workspace.bundle()
        tampered = deepcopy(records[1]); tampered['db_write_enabled'] = True
        valid_report = evaluate_reviews(records, [review(r) for r in records], synthetic=True)
        bad_report = deepcopy(valid_report); bad_report['released_races'] = 100
        bad_bundle = deepcopy(before); bad_bundle['payload']['held_records'].append(tampered)
        bad_bundle['sha256'] = _digest(bad_bundle['payload'])
        bad_digest = deepcopy(before); bad_digest['sha256'] = '0' * 64
        orphan = deepcopy(before); orphan['payload']['reviews'] = [review(records[1])]
        orphan['sha256'] = _digest(orphan['payload'])
        for value in ([records[1], tampered], bad_report, bad_bundle, bad_digest, orphan,
                      {'schema_version': 'ml-settled-history-v1'}, [records[0]] * 21):
            with self.assertRaises((ValueError, TypeError, KeyError)):
                self.load(workspace, value)
            self.assertEqual(workspace.bundle(), before)

    def test_limits_duplicate_imports_stale_revision_and_output_mutation(self):
        first, second = pair()
        workspace = ReviewWorkspace()
        stale = workspace.state()['revision']
        self.load(workspace, first)
        with self.assertRaises(ReviewConflict):
            workspace.load(second, stale)
        with self.assertRaises(ReviewConflict):
            workspace.review(_digest(first), evidence(first), decision(), stale)
        with patch('ml.held_review_workspace.MAX_HOLDS', 1):
            self.load(workspace, first)
            with self.assertRaises(ValueError):
                self.load(workspace, second)
        old = workspace.bundle()
        with patch('ml.held_review_workspace.MAX_BYTES', 1):
            with self.assertRaises(ValueError):
                workspace.review(_digest(first), evidence(first), decision(), old['sha256'])
        with patch('ml.held_review_workspace.MAX_REVIEWS', 0):
            with self.assertRaises(ValueError):
                workspace.review(_digest(first), evidence(first), decision(), old['sha256'])
        self.assertEqual(workspace.bundle(), old)
        workspace.state()['records'][0]['settlement']['result_status'] = 'normal'
        workspace.bundle()['payload']['held_records'].clear()
        self.assertEqual(workspace.bundle(), old)


class ReviewApiTests(unittest.TestCase):
    def setUp(self):
        self.app = Workbench()
        self.server = make_server(self.app)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.authority = f'127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.app.close()

    def request(self, path, body=None, headers=None):
        connection = http.client.HTTPConnection(self.authority, timeout=10)
        defaults = {'Origin': 'http://' + self.authority, 'X-Keirin-Local': 'synthetic-only',
                    'Content-Type': 'application/json'}
        defaults.update(headers or {})
        connection.request('GET' if body is None else 'POST', path,
                           body=None if body is None else json.dumps(body), headers=defaults)
        response = connection.getresponse(); raw = response.read(); status = response.status
        response_headers = dict(response.getheaders()); connection.close()
        return status, raw, response_headers

    def test_http_decision_save_reload_and_stale_tab_without_training(self):
        records = list(pair(9, 'withdrawn'))
        state = self.app.held_review.state()
        code, raw, _ = self.request('/api/held-review/import', {'value': records, 'revision': state['revision']})
        self.assertEqual(code, 200, raw)
        state = json.loads(raw)
        for record in records:
            body = {'source_sha256': _digest(record), 'evidence': evidence(record),
                    'decision': decision(), 'revision': state['revision']}
            code, raw, _ = self.request('/api/held-review/decision', body)
            self.assertEqual(code, 200, raw); state = json.loads(raw)
        code, raw, _ = self.request('/api/held-review/decision', body)
        self.assertEqual(code, 409)
        self.assertEqual(json.loads(raw)['state'], state)
        code, raw, headers = self.request('/export/held-review')
        self.assertEqual(code, 200)
        self.assertIn('attachment', headers['Content-Disposition'])
        bundle = json.loads(raw)
        self.app.held_review = ReviewWorkspace()  # A new server process starts empty.
        code, raw, _ = self.request('/api/held-review/import',
                                   {'value': bundle, 'revision': self.app.held_review.state()['revision']})
        self.assertEqual(code, 200, raw)
        self.assertEqual(json.loads(raw), state)
        exported = json.loads(self.request('/export/held-review-report')[1])
        self.assertEqual(exported, evaluate_reviews(bundle['payload']['held_records'], bundle['payload']['reviews'], synthetic=True))
        self.assertFalse(self.app.ready)
        self.assertEqual(self.app.histories, {})

    def test_same_origin_csp_body_limits_and_atomic_rejection(self):
        code, html, headers = self.request('/held-review')
        self.assertEqual(code, 200)
        self.assertIn('合成データの保留確認', html.decode())
        self.assertIn("script-src 'sha256-", headers['Content-Security-Policy'])
        self.assertIn("connect-src 'self'", headers['Content-Security-Policy'])
        self.assertIn('/held-review', self.request('/')[1].decode())
        body = {'value': list(pair()), 'revision': self.app.held_review.state()['revision']}
        for headers in ({'Host': 'untrusted.invalid'}, {'Origin': 'https://untrusted.invalid'},
                        {'X-Keirin-Local': ''}, {'Sec-Fetch-Site': 'cross-site'}):
            self.assertEqual(self.request('/api/held-review/import', body, headers)[0], 403)
        self.assertEqual(self.request('/api/held-review/import', body, {'Content-Length': str(33*1024*1024)})[0], 400)
        self.assertEqual(self.request('/api/held-review/decision', body, {'Content-Length': '5000'})[0], 400)
        self.assertEqual(self.request('/api/held-review/import', {**body, 'replace': True})[0], 400)
        self.assertEqual(self.app.held_review.state()['records'], [])
        self.assertEqual(self.request('/api/held-review/import', body)[0], 200)
        before = self.app.held_review.bundle()
        self.assertEqual(self.request('/api/held-review/decision', {'source_sha256': _digest(body['value'][0]),
            'evidence': {}, 'decision': {}, 'revision': before['sha256']})[0], 400)
        self.assertEqual(self.app.held_review.bundle(), before)


if __name__ == '__main__':
    unittest.main()
