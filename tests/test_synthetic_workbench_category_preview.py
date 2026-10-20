from copy import deepcopy
from datetime import timedelta
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

from ml.product_category_preview import (GRANT_SCHEMA, SCENARIOS, category_view,
                                         fixture_view, render_category_preview)
from ml.model_web_response import model_web_response
from ml.settle_snapshot import CATEGORIES
from ml.synthetic_session import FILENAME, SessionStore
from ml.synthetic_workbench import Workbench, make_server
from test_model_history import NOW, snapshot
from test_synthetic_workbench_session import saved_session

KEY = 'a'*32


def grant(categories=None):
    return {'schema_version': GRANT_SCHEMA, 'synthetic_only': True, 'snapshot_id': KEY,
            'categories': list(CATEGORIES) if categories is None else categories,
            'starts_at': (NOW-timedelta(minutes=1)).isoformat(),
            'ends_at': (NOW+timedelta(minutes=1)).isoformat()}


class CategoryPreviewTests(unittest.TestCase):
    def test_seven_nine_filtered_response_keeps_only_exact_allowed_fields(self):
        for count in (7, 9):
            original = snapshot(count); frozen = deepcopy(original)
            full = model_web_response(original, KEY)
            for allowed in ([], ['hit_priority'], ['balance', 'hit_priority'], ['super_longshot'], list(CATEGORIES)):
                with self.subTest(count=count, allowed=allowed):
                    result = category_view(original, KEY, grant(allowed), now=NOW)
                    self.assertEqual(set(result['categories']), set(allowed))
                    self.assertEqual(result['locked_categories'], [k for k in CATEGORIES if k not in allowed])
                    self.assertEqual(result['total_picks'], sum(len(full['categories'][k]['picks']) for k in allowed))
                    for key in allowed: self.assertEqual(result['categories'][key], full['categories'][key])
                    self.assertNotIn('prediction', result)
                    self.assertNotIn('snapshot_sha256', result)
                    self.assertNotIn('full_scores', json.dumps(result))
                    self.assertFalse(result['billing_enabled']); self.assertFalse(result['monetary_ev_enabled'])
                    self.assertEqual(result['authentication_status'], 'not_asserted')
                    self.assertEqual(result['entitlement_status'], 'not_asserted')
                    self.assertEqual(original, frozen)

    def test_closed_default_target_and_exact_time_boundaries_before_projection(self):
        cases = [(None, 'no_categories'), (grant([]), 'no_categories'),
                 ({**grant(), 'snapshot_id': 'b'*32}, 'different_snapshot'),
                 ({**grant(), 'starts_at': (NOW+timedelta(seconds=1)).isoformat()}, 'not_started'),
                 ({**grant(), 'ends_at': NOW.isoformat()}, 'expired')]
        with patch('ml.product_category_preview.model_web_response', side_effect=AssertionError('closed cases must not project')):
            for value, reason in cases:
                result = category_view(None, KEY, value, now=NOW)
                self.assertEqual(result['status'], 'locked'); self.assertEqual(result['reason'], reason)
                self.assertEqual(result['categories'], {}); self.assertEqual(result['total_picks'], 0)
                for field in ('race', 'snapshot_id', 'rider_count', 'captured_at'): self.assertNotIn(field, result)
        value = grant(['hit_priority']); value['starts_at'] = NOW.isoformat()
        result = category_view(snapshot(7), KEY, value, now=NOW)
        self.assertEqual(result['status'], 'visible')
        # Alternate timezone spelling of the exact same expiration is expired.
        value['ends_at'] = (NOW+timedelta(seconds=1)).isoformat()
        self.assertEqual(category_view(None, KEY, value, now=NOW+timedelta(seconds=1))['reason'], 'expired')

    def test_malformed_or_real_access_claims_never_fall_back_to_all_categories(self):
        bad = [False, [], {}, {**grant(), 'role': 'owner'}, {**grant(), 'synthetic_only': False},
               {**grant(), 'schema_version': 'member-grant-v1'}, {**grant(), 'snapshot_id': '../file'},
               {**grant(), 'starts_at': '2026-10-17T00:00:00'},
               {**grant(), 'ends_at': grant()['starts_at']}]
        bad += [{**grant(), 'categories': value} for value in (None, {}, 'all', ['hit_priority']*2, ['FINAL5'], ['DREAM_TICKET'], [True], [[]], list(CATEGORIES)+['owner'])]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError): category_view(None, KEY, value, now=NOW)
        with self.assertRaises(ValueError): category_view(None, KEY, None, now=NOW.replace(tzinfo=None))
        with self.assertRaises(ValueError): fixture_view(None, KEY, 'owner', now=NOW)

    def test_visible_prediction_must_pass_existing_snapshot_validation(self):
        original = snapshot(7)
        for broken in (None, {}, {**original, 'snapshot_sha256': '0'*64}):
            with self.subTest(broken=type(broken)), self.assertRaises((ValueError, TypeError, KeyError)):
                category_view(broken, KEY, grant(), now=NOW)

    def test_http_fixture_matrix_origin_unknown_fields_and_no_writes_or_training(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp); store = SessionStore(directory); store.save(saved_session()); store.close()
            app = Workbench(directory); before = (directory/FILENAME).read_bytes()
            server = make_server(app); thread = Thread(target=server.serve_forever, daemon=True); thread.start()
            def get(path, headers=None):
                conn = http.client.HTTPConnection(*server.server_address)
                try:
                    conn.request('GET', path, headers=headers or {})
                    response = conn.getresponse(); return response.status, dict(response.getheaders()), response.read()
                finally: conn.close()
            try:
                with patch.object(app, '_train', side_effect=AssertionError('read only')):
                    for key in ('a'*32, 'b'*32):
                        for scenario in SCENARIOS:
                            status, headers, body = get('/api/category-view/'+key+'/'+scenario)
                            self.assertEqual(status, 200); self.assertEqual(headers['Cache-Control'], 'no-store')
                            view = json.loads(body)
                            self.assertEqual(len(view['categories']), {'hit': 1, 'two': 2, 'three': 3, 'all': 5}.get(scenario, 0))
                        self.assertEqual(get('/category-view/'+key)[0], 200)
                    for path in ('/api/category-view/'+KEY+'/all', '/category-view/'+KEY):
                        for headers in ({'Origin': 'https://example.invalid'}, {'Sec-Fetch-Site': 'cross-site'}, {'Host': 'example.invalid'}):
                            self.assertEqual(get(path, headers)[0], 403)
                    for path in ('/api/category-view/'+'c'*32+'/all', '/api/category-view/'+KEY+'/all?plan=owner'):
                        self.assertEqual(get(path)[0], 404)
                    status, _, body = get('/api/category-view/'+KEY+'/owner')
                    self.assertEqual(status, 409); self.assertNotIn('categories', json.loads(body))
                self.assertEqual((directory/FILENAME).read_bytes(), before)
                self.assertFalse(app.ready)
                self.assertEqual(app.held_review.holds, []); self.assertEqual(app.held_review.reviews, [])
            finally: server.shutdown(); server.server_close(); thread.join(); app.close()

    def test_preview_script_hash_and_snapshot_path_are_bound(self):
        html, digest = render_category_preview(KEY)
        script = re.search(r'<script>(.*?)</script>', html, re.S).group(1)
        self.assertEqual(digest, base64.b64encode(hashlib.sha256(script.encode()).digest()).decode())
        self.assertIn(json.dumps(KEY), script)
        with self.assertRaises(ValueError): render_category_preview('</script>')


if __name__ == '__main__': unittest.main()
