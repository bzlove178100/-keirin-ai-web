from copy import deepcopy
from datetime import datetime
import base64
import hashlib
import http.client
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch

from ml.category_selection import select_model_categories
from ml.final_five_preview import final_five_view, render_final_five_preview
from ml.model_history import capture_prediction, _digest
from ml.synthetic_session import FILENAME, SessionStore
from ml.synthetic_workbench import Workbench, make_server
from test_model_history import NOW, prediction
from test_synthetic_workbench_session import saved_session

KEY = 'a'*32


def baseline_snapshot(count=7, *, partial=False, tied=False):
    value = prediction(count)
    rows = value['trifecta_scores']; size = len(rows)
    for i, row in enumerate(rows):
        row['estimated_probability'] = 1/size if tied else (size-i)/(size*(size+1)/2)
        # High-probability rows 3..5 have no odds and are outside the 15 picks.
        row['odds'] = (30, 80, 150, 600)[(i-6)//3] if not partial and 6 <= i < 18 else None
    value['input_quality']['known_trifecta_odds_count'] = sum(r['odds'] is not None for r in rows)
    value['selected_predictions'] = select_model_categories(rows, count)
    with patch('ml.model_history.datetime', wraps=datetime) as clock:
        clock.now.return_value = NOW
        return capture_prediction(value, synthetic=True)


class FinalFiveTests(unittest.TestCase):
    def test_only_original_category_pool_crosses_categories_without_quota_or_mutation(self):
        for count in (7, 9):
            snap = baseline_snapshot(count); before = deepcopy(snap)
            result = final_five_view(snap, KEY)
            expected = [snap['prediction']['trifecta_scores'][i] for i in (0, 1, 2, 6, 7)]
            self.assertEqual([p['combo_key'] for p in result['picks']], [p['combo_key'] for p in expected])
            self.assertEqual([p['estimated_probability'] for p in result['picks']], [p['estimated_probability'] for p in expected])
            self.assertEqual([p['odds'] for p in result['picks']], [None, None, None, 30, 30])
            self.assertEqual([p['source_category'] for p in result['picks']], ['hit_priority']*3+['balance']*2)
            self.assertEqual([p['source_rank'] for p in result['picks']], [1, 2, 3, 1, 2])
            self.assertEqual([p['rank'] for p in result['picks']], [1, 2, 3, 4, 5])
            self.assertEqual((result['candidate_count'], result['selected_count'], result['shortfall'], result['status']), (15, 5, 0, 'ready'))
            for field in ('prediction', 'categories', 'trifecta_scores', 'snapshot_sha256', 'model_artifact_sha256', 'settlement'):
                self.assertNotIn(field, result)
            for field in ('production_prediction_enabled', 'db_write_enabled', 'external_fetch_enabled', 'supervised_training_enabled', 'billing_enabled', 'monetary_ev_enabled', 'second_stage_ai_enabled'):
                self.assertIs(result[field], False)
            self.assertEqual(result['entitlement_status'], 'not_asserted')
            self.assertEqual(result['authentication_status'], 'not_asserted')
            self.assertEqual(snap, before)

    def test_shortage_keeps_unknown_odds_and_never_fills_from_full_table(self):
        for count in (7, 9):
            result = final_five_view(baseline_snapshot(count, partial=True), KEY)
            self.assertEqual((result['candidate_count'], result['selected_count'], result['shortfall'], result['status']), (3, 3, 2, 'partial'))
            self.assertTrue(all(p['odds'] is None for p in result['picks']))
            self.assertEqual(len({p['combo_key'] for p in result['picks']}), 3)
            self.assertLess(sum(p['estimated_probability'] for p in result['picks']), 1)

    def test_ties_use_numeric_combo_order_not_category_mapping_order(self):
        for count in (7, 9):
            snap = baseline_snapshot(count, tied=True)
            expected = final_five_view(snap, KEY)
            categories = snap['prediction']['selected_predictions']['categories']
            pool = [p['combo_key'] for c in categories.values() for p in c['picks']]
            self.assertEqual([p['combo_key'] for p in expected['picks']], sorted(pool, key=lambda k: tuple(map(int, k.split('-'))))[:5])
            snap['prediction']['selected_predictions']['categories'] = dict(reversed(list(categories.items())))
            self.assertEqual(final_five_view(snap, KEY), expected)

    def test_existing_snapshot_validation_rejects_forged_selection_and_provenance(self):
        for mutate in (
            lambda s: s.update(snapshot_sha256='0'*64),
            lambda s: s['prediction']['selected_predictions']['categories']['balance']['picks'][0].update(combo_key='9-9-9'),
            lambda s: s['prediction']['selected_predictions']['categories']['balance']['picks'][0].update(estimated_probability=0.99),
            lambda s: s['prediction']['model_artifact'].update(evidence_scope='real_data'),
            lambda s: s.update(production_prediction_enabled=True),
        ):
            snap = baseline_snapshot(); mutate(snap)
            if snap['snapshot_sha256'] != '0'*64:
                snap['snapshot_sha256'] = _digest({k: v for k, v in snap.items() if k != 'snapshot_sha256'})
            with self.assertRaises(ValueError): final_five_view(snap, KEY)
        with self.assertRaises(ValueError): final_five_view(baseline_snapshot(), '../file')

    def test_http_read_only_restore_boundaries_and_invalid_snapshot_are_fail_closed(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp); value = saved_session()
            value['snapshots'] = {'a'*32: baseline_snapshot(7), 'b'*32: baseline_snapshot(9, partial=True)}
            value['histories'] = {}
            store = SessionStore(directory); store.save(value); store.close()
            before = (directory/FILENAME).read_bytes(); app = Workbench(directory)
            server = make_server(app); thread = Thread(target=server.serve_forever, daemon=True); thread.start()
            def get(path, headers=None):
                conn = http.client.HTTPConnection(*server.server_address)
                try:
                    conn.request('GET', path, headers=headers or {})
                    response = conn.getresponse(); return response.status, dict(response.getheaders()), response.read()
                finally: conn.close()
            try:
                with patch.object(app, '_train', side_effect=AssertionError('read only')):
                    for key, count in (('a'*32, 5), ('b'*32, 3)):
                        status, headers, body = get('/api/final-five-view/'+key)
                        self.assertEqual(status, 200); self.assertEqual(json.loads(body)['selected_count'], count)
                        self.assertEqual(headers['Cache-Control'], 'no-store')
                        self.assertEqual(get('/final-five-view/'+key)[0], 200)
                    for path in ('/api/final-five-view/'+KEY, '/final-five-view/'+KEY):
                        for headers in ({'Origin': 'https://example.invalid'}, {'Host': 'example.invalid'}, {'Sec-Fetch-Site': 'cross-site'}):
                            self.assertEqual(get(path, headers)[0], 403)
                        self.assertEqual(get(path+'?plan=top')[0], 404)
                    self.assertEqual(get('/api/final-five-view/'+'c'*32)[0], 404)
                    app.snapshots[KEY]['snapshot_sha256'] = '0'*64
                    status, _, body = get('/api/final-five-view/'+KEY)
                    self.assertEqual(status, 409); self.assertNotIn('picks', json.loads(body))
                self.assertEqual((directory/FILENAME).read_bytes(), before)
                self.assertFalse(app.ready); self.assertEqual(app.held_review.holds, []); self.assertEqual(app.held_review.reviews, [])
            finally: server.shutdown(); server.server_close(); thread.join(); app.close()
            restored = Workbench(directory)
            try: self.assertEqual(final_five_view(restored.snapshots[KEY], KEY)['selected_count'], 5)
            finally: restored.close()

    def test_rendered_script_csp_is_exact_and_path_input_cannot_inject(self):
        html, digest = render_final_five_preview(KEY)
        script = re.search(r'<script>(.*?)</script>', html, re.S).group(1)
        self.assertEqual(digest, base64.b64encode(hashlib.sha256(script.encode()).digest()).decode())
        self.assertIn(json.dumps(KEY), script)
        with self.assertRaises(ValueError): render_final_five_preview('</script>')


if __name__ == '__main__': unittest.main()
