from copy import deepcopy
from datetime import datetime, timedelta
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
from ml.final_five_review import evaluate_final_five, render_final_five_review
from ml.model_history import _digest, evaluate_histories, race_key, settle_snapshot
from ml.synthetic_session import SCHEMA, FILENAME, SessionStore
from ml.synthetic_workbench import Workbench, make_server
from test_synthetic_workbench_final_five import baseline_snapshot


def digest(snapshot):
    snapshot['snapshot_sha256'] = _digest({k: v for k, v in snapshot.items() if k != 'snapshot_sha256'})
    return snapshot


def dated_snapshot(count=7, day=0, size=5):
    snap = baseline_snapshot(count, partial=size < 5)
    prediction = snap['prediction']; race = prediction['race']; delta = timedelta(days=day)
    for key in ('captured_at', 'scheduled_start'): snap[key] = (datetime.fromisoformat(snap[key])+delta).isoformat()
    prediction['generated_at'] = (datetime.fromisoformat(prediction['generated_at'])+delta).isoformat()
    race['scheduled_start_jst'] = (datetime.fromisoformat(race['scheduled_start_jst'])+delta).isoformat()
    race['date'] = datetime.fromisoformat(race['scheduled_start_jst']).date().isoformat()
    if size == 4:
        prediction['trifecta_scores'][6]['odds'] = 30
        prediction['input_quality']['known_trifecta_odds_count'] = 1
        prediction['selected_predictions'] = select_model_categories(prediction['trifecta_scores'], count)
    snap['race_id'] = race_key(race)
    return digest(snap)


def result(snap, index=0, status='normal', odds=40):
    event = {'race_id': snap['race_id'],
             'result_timestamp': (datetime.fromisoformat(snap['scheduled_start'])+timedelta(minutes=10)).isoformat()}
    if status == 'normal': event.update(outcome_combo=snap['prediction']['trifecta_scores'][index]['combo_key'], settlement_odds=odds)
    else:
        event['result_status'] = status
        if status == 'withdrawn': event['withdrawn_car_numbers'] = [snap['prediction']['input_quality']['rider_count']]
    return settle_snapshot(snap, event, synthetic=True)


def review_session():
    snapshots, histories = {}, {}
    for count in (7, 9):
        for day, size, outcome in ((0, 5, 6), (1, 5, 8), (2, 5, 3), (3, 3, 0), (4, 4, 6), (5, 5, 'withdrawn'), (6, 5, None)):
            key = f'{len(snapshots)+1:032x}'; snap = dated_snapshot(count, day, size); snapshots[key] = snap
            if outcome is not None: histories[key] = result(snap, status=outcome) if isinstance(outcome, str) else result(snap, outcome)
    return {'schema_version': SCHEMA, 'synthetic_only': True, 'legacy': None,
            'scheduled': snapshots[key]['scheduled_start'], 'current': next(iter(snapshots)),
            'snapshots': snapshots, 'histories': histories}


class FinalFiveReviewTests(unittest.TestCase):
    def test_seven_nine_outcomes_budgets_and_exact_denominators_without_mutation(self):
        records = list(review_session()['histories'].values()); frozen = deepcopy(records)
        report = evaluate_final_five(records, synthetic=True)
        self.assertEqual(report['summary'], {'races': 10, 'selected_hits': 6, 'candidate_pool_hits': 8, 'removed_by_five': 2, 'outside_pool': 2})
        self.assertEqual((report['evaluated_races'], report['held_races']), (10, 2))
        self.assertEqual(len(report['strata']), 6)
        for group in report['strata']:
            self.assertEqual((group['races'], group['selected_hits'], group['selected_hit_rate']), (3, 1, 1/3) if group['selected_count'] == 5 else (1, 1, 1))
        self.assertEqual(records, frozen)
        self.assertNotIn('hit_rate', report['summary'])
        for row in report['per_race']:
            self.assertEqual(row['selected_hit'], row['outcome_combo'] in row['selected_combos'])
            self.assertEqual(row['selected_count'], len(row['selected_combos']))
            self.assertNotIn('settlement_odds', row); self.assertNotIn('trifecta_scores', row)
        for key in ('monetary_ev_enabled', 'production_prediction_enabled', 'db_write_enabled', 'supervised_training_enabled', 'second_stage_ai_enabled', 'promotion_eligible'):
            self.assertIs(report[key], False)

    def test_outcome_and_settlement_odds_never_change_the_selected_combos(self):
        snap = dated_snapshot(); rows = [evaluate_final_five([result(snap, i)], synthetic=True)['per_race'][0] for i in (6, 8, 3)]
        self.assertEqual([r['diagnostic'] for r in rows], ['selected_hit', 'removed_by_five', 'outside_pool'])
        self.assertTrue(all(r['selected_combos'] == rows[0]['selected_combos'] for r in rows))
        self.assertEqual(evaluate_final_five([result(snap, 6, odds=40)], synthetic=True), evaluate_final_five([result(snap, 6, odds=999)], synthetic=True))

    def test_latest_duplicate_normal_alias_and_order_match_existing_review(self):
        old = dated_snapshot(); newer = deepcopy(old)
        newer['captured_at'] = (datetime.fromisoformat(newer['captured_at'])+timedelta(minutes=1)).isoformat(); digest(newer)
        recent = result(newer); explicit = settle_snapshot(newer, {**recent['settlement'], 'result_status': 'normal'}, synthetic=True)
        records = [result(old), recent, explicit, deepcopy(recent)]
        report = evaluate_final_five(records, synthetic=True)
        self.assertEqual((report['evaluated_races'], report['duplicate_snapshots_removed']), (1, 3))
        self.assertEqual(report['per_race'][0]['snapshot_sha256'], newer['snapshot_sha256'])
        self.assertEqual(report, evaluate_final_five(list(reversed(records)), synthetic=True))
        original = evaluate_histories(records, synthetic=True)
        for key in ('evaluated_races', 'held_races', 'excluded', 'duplicate_snapshots_removed'):
            self.assertEqual(report[key], original[key])

    def test_holds_conflicts_and_malformed_records_do_not_contribute(self):
        for count in (7, 9):
            snap = dated_snapshot(count)
            for status in ('dead_heat', 'withdrawn', 'cancelled'):
                report = evaluate_final_five([result(snap), result(snap, status=status)], synthetic=True)
                self.assertEqual((report['evaluated_races'], report['held_races']), (0, 1))
                self.assertTrue(all(s['selected_hit_rate'] is None for s in report['strata']))
            other = deepcopy(snap); other['prediction']['model_artifact']['sha256'] = 'b'*64; digest(other)
            corrupt = result(snap); corrupt['snapshot']['snapshot_sha256'] = '0'*64
            for records, reason in (([result(snap), result(snap, 8)], 'conflicting_settlements'),
                                    ([result(snap), result(other)], 'conflicting_latest_snapshots'),
                                    ([corrupt], 'snapshot_digest_mismatch'), ([None], 'ml_history_schema_mismatch')):
                report = evaluate_final_five(records, synthetic=True)
                self.assertEqual(report['evaluated_races'], 0); self.assertIn(reason, report['excluded'])
                valid = result(dated_snapshot(count, day=1), 6)
                with_valid = evaluate_final_five(records+[valid], synthetic=True)
                self.assertEqual(with_valid['per_race'], evaluate_final_five([valid], synthetic=True)['per_race'])

    def test_empty_and_explicit_synthetic_requirement(self):
        report = evaluate_final_five([], synthetic=True)
        self.assertEqual(report['status'], 'blocked_no_valid_histories'); self.assertEqual(report['summary']['races'], 0)
        self.assertTrue(all(s['selected_hit_rate'] is None for s in report['strata']))
        for value in (False, None, 1):
            with self.assertRaises(ValueError): evaluate_final_five([], synthetic=value)
        for value in (None, {}, '[]'):
            with self.assertRaises(ValueError): evaluate_final_five(value, synthetic=True)

    def test_http_export_origin_restore_and_read_only_failed_storage_state(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp); initial = review_session()
            store = SessionStore(directory); store.save(initial); store.close()
            original = (directory/FILENAME).read_bytes(); app = Workbench(directory)
            server = make_server(app); thread = Thread(target=server.serve_forever, daemon=True); thread.start()
            def get(path, headers=None):
                connection = http.client.HTTPConnection(*server.server_address)
                try:
                    connection.request('GET', path, headers=headers or {}); response = connection.getresponse()
                    return response.status, dict(response.getheaders()), response.read()
                finally: connection.close()
            try:
                with patch.object(app, '_train', side_effect=AssertionError('no training')), patch.object(app.store, 'save', side_effect=AssertionError('no writes')):
                    status, headers, raw = get('/api/final-five-review'); report = json.loads(raw)
                    self.assertEqual(status, 200); self.assertEqual(headers['Cache-Control'], 'no-store')
                    self.assertEqual((report['evaluated_races'], report['pending_snapshots'], report['held_races']), (10, 2, 2))
                    status, headers, raw = get('/export/final-five-review')
                    self.assertEqual(json.loads(raw), report); self.assertIn('attachment', headers['Content-Disposition'])
                    self.assertEqual(get('/final-five-review')[0], 200)
                    for path in ('/api/final-five-review', '/final-five-review', '/export/final-five-review'):
                        self.assertEqual(get(path+'?all=true')[0], 404)
                        for headers in ({'Origin': 'https://example.invalid'}, {'Host': 'example.invalid'}, {'Sec-Fetch-Site': 'cross-site'}):
                            self.assertEqual(get(path, headers)[0], 403)
                    app.store.failed = True
                    blocked = json.loads(get('/api/final-five-review')[2])
                    self.assertTrue(blocked['storage']['write_blocked']); self.assertEqual(blocked['per_race'], report['per_race'])
                self.assertEqual((directory/FILENAME).read_bytes(), original); self.assertEqual(app.snapshots, initial['snapshots'])
                self.assertEqual(app.histories, initial['histories']); self.assertFalse(app.ready)
                self.assertEqual(app.held_review.holds, []); self.assertEqual(app.held_review.reviews, [])
            finally: server.shutdown(); server.server_close(); thread.join(); app.close()
            app = Workbench(directory)
            try: self.assertEqual(app.final_five_report(), report)
            finally: app.close()

    def test_static_review_script_matches_csp(self):
        html, expected = render_final_five_review(); script = re.search(r'<script>(.*?)</script>', html, re.S).group(1)
        self.assertEqual(expected, base64.b64encode(hashlib.sha256(script.encode()).digest()).decode())


if __name__ == '__main__': unittest.main()
