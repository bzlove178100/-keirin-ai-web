from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ml.dataset import supervised_eligibility
from ml.held_history import build_held_history, partition_holds
from ml.held_history_review import EVIDENCE_SCHEMA, create_review, evaluate_reviews, validate_review
from ml.held_history_transfer import transfer_hold
from ml.model_history import _digest, evaluate_histories, settle_snapshot
from ml.probability_metrics import score
from ml.settle_snapshot import build_history_record
from test_held_history_transfer import event, rehash, snapshots


def pair(count=7, status='dead_heat'):
    phase, model = snapshots(count)
    held = build_held_history(phase, event(status, count))
    return held, transfer_hold(held, model, synthetic=True)['target_history']


def evidence(record, *, normal=True):
    phase32 = record['schema_version'] == 'phase32-held-history-v1'
    snapshot = record['snapshot']
    if phase32:
        race = snapshot['race_data']['race']
        count = len(snapshot['race_data']['players'])
    else:
        race = snapshot['prediction']['race']
        count = snapshot['prediction']['input_quality']['rider_count']
    result = ({'result_status': 'normal', 'outcome_combo': '1-2-3', 'settlement_odds': 40}
              if normal else {key: value for key, value in record['settlement'].items()
                              if key not in ('race_id', 'result_timestamp')})
    result['result_timestamp'] = '2026-10-17T02:20:00Z'
    return {
        'schema_version': EVIDENCE_SCHEMA, 'evidence_scope': 'synthetic_test_only',
        'fixture_id': 'generated-result-case',
        'race_identity': {key: race[key] for key in ('date', 'venue', 'race_number')},
        'scheduled_start': race['scheduled_start_jst'], 'car_numbers': list(range(1, count + 1)),
        'result': result,
    }


def decision(*, normal=True):
    return {'decision': 'correct_declaration' if normal else 'confirm_nonstandard',
            'reviewed_at': '2026-10-17T02:30:00Z', 'reviewer_id': 'synthetic-reviewer',
            'reason': 'Generated fixture declared incorrectly.' if normal else 'Generated nonstandard result confirmed.'}


def review(record, *, normal=True):
    return create_review(record, evidence(record, normal=normal), decision(normal=normal), synthetic=True)


class HeldHistoryReviewTests(unittest.TestCase):
    def test_correction_preserves_predictions_and_scores_both_engines_seven_nine(self):
        for count in (7, 9):
            for status in ('dead_heat', 'withdrawn', 'cancelled'):
                with self.subTest(count=count, status=status):
                    records = list(pair(count, status))
                    original = deepcopy(records)
                    with patch('socket.socket', side_effect=AssertionError('network forbidden')):
                        receipts = [review(record) for record in records]
                        report = evaluate_reviews(records, receipts, synthetic=True)
                    self.assertEqual(records, original)
                    self.assertEqual(report['source_histories'], original)
                    self.assertEqual(report['reviews'], receipts)
                    self.assertEqual(report['released_races'], 1)
                    self.assertEqual(report['unresolved_races'], 0)
                    self.assertEqual(len(report['predictions']), 2)
                    self.assertTrue(report['cases'][0]['hold_released'])
                    for engine, record in zip(('phase32', 'ml'), records):
                        prediction = (record['snapshot']['engine_response']['prediction'] if engine == 'phase32'
                                      else record['snapshot']['prediction'])
                        table = {row['combo_key']: row['estimated_probability'] for row in prediction['trifecta_scores']}
                        expected = score(table, '1-2-3')
                        actual = next(row for row in report['predictions'] if row['engine'] == engine)
                        self.assertEqual(actual['metrics'], expected)
                        self.assertEqual(report['metrics_by_engine'][engine]['evaluated_races'], 1)
                        for name, value in report['metrics_by_engine'][engine]['metrics'].items():
                            self.assertEqual(value, expected[name])
                        self.assertEqual(actual['prediction_timestamp'], record['prediction_timestamp'])
                    self.assertNotEqual(report['metrics_by_engine']['phase32']['metrics']['log_loss'],
                                        report['metrics_by_engine']['ml']['metrics']['log_loss'])
                    for receipt in receipts:
                        validate_review(receipt, synthetic=True)
                        self.assertIs(receipt['hold_released'], False)
                        self.assertIs(receipt['release_requested'], True)
                        self.assertFalse(supervised_eligibility(receipt)[0])
                    self.assertFalse(supervised_eligibility(report)[0])
                    for key in ('production_prediction_enabled', 'db_write_enabled', 'external_fetch_enabled',
                                'monetary_ev_enabled', 'promotion_eligible', 'supervised_training_enabled',
                                'supervised_training_eligible', 'provenance_independently_verified'):
                        self.assertIs(report[key], False)
                    self.assertNotIn('training_input', json.dumps(report))
                    report['source_histories'][0]['snapshot']['captured_at'] = 'changed'
                    self.assertEqual(records, original)

    def test_confirmed_nonstandard_is_closed_but_never_scored(self):
        for count in (7, 9):
            for status in ('dead_heat', 'withdrawn', 'cancelled'):
                records = list(pair(count, status))
                receipts = [review(record, normal=False) for record in records]
                report = evaluate_reviews(records, receipts, synthetic=True)
                self.assertEqual(report['confirmed_excluded_races'], 1)
                self.assertEqual(report['unresolved_races'], 0)
                self.assertEqual(report['released_races'], 0)
                self.assertFalse(report['cases'][0]['hold_released'])
                self.assertEqual(report['predictions'], [])
                self.assertIsNone(report['metrics_by_engine']['ml']['metrics'])
                self.assertIsNone(report['metrics_by_engine']['phase32']['metrics'])
                self.assertTrue(all(not item['release_requested'] for item in receipts))

    def test_missing_reviews_and_new_holds_block_existing_correction(self):
        phase, model = pair()
        corrected = review(phase)
        for records in ([phase, model], [model, phase], [phase, phase, model]):
            report = evaluate_reviews(records, [corrected], synthetic=True)
            self.assertEqual(report['released_races'], 0)
            self.assertEqual(report['cases'][0]['reason'], 'unreviewed_held_history')
            self.assertEqual(report['predictions'], [])
        self.assertEqual(evaluate_reviews([phase], [corrected], synthetic=True)['released_races'], 1)
        additional = build_held_history(phase['snapshot'], event('cancelled'))
        report = evaluate_reviews([phase, additional], [corrected], synthetic=True)
        self.assertEqual(report['released_races'], 0)
        self.assertEqual(report['unresolved_races'], 1)

    def test_duplicate_order_independence_and_conflicting_reviews(self):
        records = list(pair())
        receipts = [review(record) for record in records]
        reference = evaluate_reviews(records, receipts, synthetic=True)
        repeated = evaluate_reviews([records[1], records[0], records[0]],
                                    [receipts[1], receipts[0], receipts[0]], synthetic=True)
        self.assertEqual(repeated['cases'], reference['cases'])
        self.assertEqual(repeated['predictions'], reference['predictions'])
        self.assertEqual(repeated['metrics_by_engine'], reference['metrics_by_engine'])
        self.assertEqual(repeated['duplicate_held_records'], 1)
        self.assertEqual(repeated['unique_reviews'], 2)
        changed_decision = decision()
        changed_decision.update(reviewed_at='2026-10-17T02:31:00Z', reason='Different review.')
        conflicting = create_review(records[0], evidence(records[0]), changed_decision, synthetic=True)
        report = evaluate_reviews(records, [*receipts, conflicting], synthetic=True)
        self.assertEqual(report['cases'][0]['reason'], 'conflicting_reviews')
        self.assertEqual(report['released_races'], 0)
        # Even a later receipt cannot silently overwrite an earlier decision.
        self.assertEqual(evaluate_reviews(records, [conflicting, *receipts], synthetic=True)['cases'], report['cases'])

    def test_cross_engine_result_and_decision_conflicts_block_whole_race(self):
        phase, model = pair()
        for field, value in (('outcome_combo', '1-2-4'), ('settlement_odds', 41),
                             ('result_timestamp', '2026-10-17T02:21:00Z')):
            changed = evidence(model)
            changed['result'][field] = value
            report = evaluate_reviews([phase, model], [review(phase),
                                      create_review(model, changed, decision(), synthetic=True)], synthetic=True)
            self.assertEqual(report['cases'][0]['reason'], 'conflicting_corrected_results')
            self.assertEqual(report['predictions'], [])
        mixed = evaluate_reviews([phase, model], [review(phase), review(model, normal=False)], synthetic=True)
        self.assertEqual(mixed['cases'][0]['reason'], 'conflicting_review_decisions')
        equivalent = evidence(model)
        equivalent['result'].update(result_timestamp='2026-10-17T11:20:00+09:00', settlement_odds=40.0)
        report = evaluate_reviews([phase, model], [review(phase),
                                  create_review(model, equivalent, decision(), synthetic=True)], synthetic=True)
        self.assertEqual(report['released_races'], 1)

    def test_context_conflicts_and_unrelated_race_metrics(self):
        phase, model = pair()
        other_phase, other_model = pair(9)
        reference = evaluate_reviews([other_phase, other_model], [review(other_phase), review(other_model)], synthetic=True)
        model_snapshot = deepcopy(model['snapshot'])
        model_snapshot['scheduled_start'] = '2026-10-17T02:01:00Z'
        model_snapshot['prediction']['race']['scheduled_start_jst'] = model_snapshot['scheduled_start']
        rehash(model_snapshot)
        changed = settle_snapshot(model_snapshot, {**event(), 'race_id': model_snapshot['race_id']}, synthetic=True)
        records = [phase, changed, other_phase, other_model]
        report = evaluate_reviews(records, [review(record) for record in records], synthetic=True)
        self.assertEqual(report['released_races'], 1)
        self.assertEqual(report['unresolved_races'], 1)
        self.assertIn('conflicting_race_context', [case['reason'] for case in report['cases']])
        self.assertEqual(report['metrics_by_engine'], reference['metrics_by_engine'])
        self.assertEqual(report['predictions'], reference['predictions'])
        # Same date/venue/number but a different car count cannot be treated as another race.
        other_phase['snapshot']['race_data']['race']['race_number'] = 7
        other_phase = build_held_history(other_phase['snapshot'], event(count=9))
        report = evaluate_reviews([phase, other_phase], [review(phase), review(other_phase)], synthetic=True)
        self.assertEqual(report['cases'][0]['reason'], 'conflicting_race_context')

    def test_latest_prediction_ties_are_not_resolved_by_input_order(self):
        _, old = pair()
        newer_snapshot = deepcopy(old['snapshot'])
        newer_snapshot['captured_at'] = '2026-10-17T01:05:00Z'
        rehash(newer_snapshot)
        newer = settle_snapshot(newer_snapshot, old['settlement'], synthetic=True)
        report = evaluate_reviews([old, newer], [review(old), review(newer)], synthetic=True)
        self.assertEqual(len(report['predictions']), 1)
        self.assertEqual(report['predictions'][0]['prediction_timestamp'], newer_snapshot['captured_at'])
        tied_snapshot = deepcopy(newer_snapshot)
        tied_snapshot['prediction']['model_artifact']['sha256'] = 'b' * 64
        rehash(tied_snapshot)
        tied = settle_snapshot(tied_snapshot, old['settlement'], synthetic=True)
        report = evaluate_reviews([old, newer, tied], [review(old), review(newer), review(tied)], synthetic=True)
        self.assertEqual(report['cases'][0]['reason'], 'conflicting_latest_snapshots')
        self.assertEqual(report['predictions'], [])

    def test_evidence_schema_identity_result_and_timing_fail_closed(self):
        records = pair(status='withdrawn')
        for record in records:
            mutations = [lambda e: e.update(evidence_scope='real'), lambda e: e.update(fixture_id='official-proof'),
                         lambda e: e.update(override=True), lambda e: e['race_identity'].update(venue='OTHER'),
                         lambda e: e.update(scheduled_start='2026-10-17T02:01:00Z'),
                         lambda e: e.update(car_numbers=[True, 2, 3, 4, 5, 6, 7]),
                         lambda e: e['result'].update(result_timestamp='2026-10-17T02:09:00Z'),
                         lambda e: e['result'].update(result_timestamp='2026-10-17T02:31:00Z'),
                         lambda e: e['result'].update(result_timestamp='2026-10-17T02:20:00'),
                         lambda e: e['result'].update(result_status='dead_heat'),
                         lambda e: e['result'].update(outcome_combo='9-8-7'),
                         lambda e: e['result'].update(settlement_odds=True),
                         lambda e: e['result'].update(settlement_odds=float('nan')),
                         lambda e: e['result'].update(withdrawn_car_numbers=[])]
            for mutate in mutations:
                bad = evidence(record)
                mutate(bad)
                with self.assertRaises(ValueError):
                    create_review(record, bad, decision(), synthetic=True)
            for field, value in (('decision', 'override'), ('reviewer_id', 'owner'), ('reason', ''),
                                 ('reviewed_at', '2026-10-17T02:19:00Z'), ('unknown', True)):
                with self.assertRaises(ValueError):
                    create_review(record, evidence(record), {**decision(), field: value}, synthetic=True)
            for cars in ([], [7], [7, 1, 1], [True, 7], ['1', 7]):
                bad = evidence(record, normal=False)
                bad['result']['withdrawn_car_numbers'] = cars
                with self.assertRaises(ValueError):
                    create_review(record, bad, decision(normal=False), synthetic=True)
        early = build_held_history(records[0]['snapshot'], event('cancelled', timestamp='2026-10-17T01:30:00Z'))
        bad = evidence(early)
        bad['result']['result_timestamp'] = '2026-10-17T01:50:00Z'
        with self.assertRaisesRegex(ValueError, 'before_scheduled_start'):
            create_review(early, bad, decision(), synthetic=True)

    def test_tampering_or_orphan_receipt_rejects_entire_batch(self):
        records = list(pair())
        valid = [review(record) for record in records]
        for mutate in (lambda r: r.update(hold_released=True), lambda r: r.update(db_write_enabled=0),
                       lambda r: r.update(override=True), lambda r: r.update(source_history_sha256='b' * 64),
                       lambda r: r['source_history'].update(race_id='OTHER'),
                       lambda r: r['evidence']['result'].update(outcome_combo='1-2-4')):
            bad = deepcopy(valid[0])
            mutate(bad)
            with self.assertRaises(ValueError):
                validate_review(bad, synthetic=True)
            with self.assertRaises(ValueError):
                evaluate_reviews(records, [*valid, bad], synthetic=True)
        with self.assertRaisesRegex(ValueError, 'source_not_in_batch'):
            evaluate_reviews([records[0]], valid, synthetic=True)
        for bad in (None, {}, {**records[0], 'db_write_enabled': True}, {**records[1], 'model_artifact_sha256': 'b' * 64}):
            with self.assertRaises(ValueError):
                evaluate_reviews([*records, bad], valid, synthetic=True)

    def test_existing_history_guards_still_hold_and_no_training_record_is_exported(self):
        phase, model = pair()
        normal_phase = build_history_record(phase['snapshot'], outcome_combo='1-2-3', settlement_odds=40,
                                           result_timestamp='2026-10-17T02:20:00Z')
        normal_model = settle_snapshot(model['snapshot'], {**evidence(model)['result'], 'race_id': model['race_id']}, synthetic=True)
        receipts = [review(phase), review(model)]
        report = evaluate_reviews([phase, model], receipts, synthetic=True)
        self.assertEqual(report['released_races'], 1)
        self.assertEqual(partition_holds([phase, normal_phase])[0], [])
        self.assertEqual(evaluate_histories([model, normal_model], synthetic=True)['evaluated_races'], 0)
        self.assertFalse(supervised_eligibility(report)[0])
        for record in (normal_phase, normal_model, report):
            with self.assertRaisesRegex(ValueError, 'held_history_required'):
                evaluate_reviews([record], [], synthetic=True)

    def test_synthetic_gate_empty_batch_and_cli_audit_round_trip(self):
        phase, _ = pair()
        receipt = review(phase)
        for enabled in (False, None, 1, 'true'):
            for operation, args in ((create_review, (phase, evidence(phase), decision())),
                                    (validate_review, (receipt,)), (evaluate_reviews, ([phase], [receipt]))):
                with self.assertRaisesRegex(ValueError, 'explicit_synthetic'):
                    operation(*args, synthetic=enabled)
        empty = evaluate_reviews([], [], synthetic=True)
        self.assertEqual(empty['released_races'], 0)
        self.assertIsNone(empty['metrics_by_engine']['ml']['metrics'])
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = [root / name for name in ('held.json', 'evidence.json', 'decision.json')]
            for path, value in zip(paths, (phase, evidence(phase), decision())):
                path.write_text(json.dumps(value), encoding='utf-8')
            output = root / 'review.json'
            prefix = [sys.executable, '-m', 'ml.held_history_review']
            args = [*prefix, 'create-review', *map(str, paths), '--output', str(output)]
            self.assertNotEqual(subprocess.run(args, capture_output=True).returncode, 0)
            self.assertFalse(output.exists())
            subprocess.run([*args, '--synthetic'], capture_output=True, check=True)
            validate_review(json.loads(output.read_text(encoding='utf-8')), synthetic=True)
            before = output.read_bytes()
            self.assertNotEqual(subprocess.run([*args, '--synthetic'], capture_output=True).returncode, 0)
            self.assertEqual(output.read_bytes(), before)
            batch = root / 'batch.json'
            batch.write_text(json.dumps({'held_records': [phase], 'reviews': [receipt]}), encoding='utf-8')
            report_path = root / 'report.json'
            command = [*prefix, 'evaluate', str(batch), '--synthetic', '--output', str(report_path)]
            subprocess.run(command, check=True, capture_output=True)
            report = json.loads(report_path.read_text(encoding='utf-8'))
            self.assertEqual(report['released_races'], 1)
            self.assertEqual(report['source_histories'], [phase])
            invalid = root / 'invalid.json'
            invalid.write_text(json.dumps({'held_records': [phase], 'reviews': [{**receipt, 'hold_released': True}]}), encoding='utf-8')
            absent = root / 'absent.json'
            self.assertNotEqual(subprocess.run([*prefix, 'evaluate', str(invalid), '--synthetic', '--output', str(absent)], capture_output=True).returncode, 0)
            self.assertFalse(absent.exists())
            unresolved = root / 'unresolved.json'
            unresolved.write_text(json.dumps({'held_records': [phase], 'reviews': []}), encoding='utf-8')
            blocked = root / 'blocked-report.json'
            self.assertEqual(subprocess.run([*prefix, 'evaluate', str(unresolved), '--synthetic', '--output', str(blocked)], capture_output=True).returncode, 2)
            self.assertEqual(json.loads(blocked.read_text(encoding='utf-8'))['unresolved_races'], 1)


if __name__ == '__main__':
    unittest.main()
