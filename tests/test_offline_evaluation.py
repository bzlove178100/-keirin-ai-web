from copy import deepcopy
from datetime import datetime, timedelta
from itertools import permutations
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ml_position_smoke import make_record
from ml.build_training_dataset import load_records
from ml.evaluate_offline import BASELINE, evaluate_records, prepare, score, split_records, timestamp
from ml.evaluation_protocol import prepare as protocol_prepare
from ml.evaluation_protocol import readiness as protocol_readiness
from ml.evaluation_protocol import split_records as protocol_split_records


def fixture(i):
    record = make_record(i)
    record['metadata']['result_timestamp'] = (
        datetime.fromisoformat(record['prediction_timestamp']) + timedelta(minutes=10)
    ).isoformat()
    record['metadata']['engine_version'] = BASELINE
    record['trifecta_scores'] = [
        {'combo_key': '-'.join(map(str, p)), 'estimated_probability': 1 / 210}
        for p in permutations(range(1, 8), 3)
    ]
    return record


class EvaluationTest(unittest.TestCase):
    def test_web_export_envelope(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'history.json'
            path.write_text(json.dumps({'mode': 'dry_run', 'payload': {'records': [fixture(0)]}}))
            self.assertEqual(len(load_records([path])), 1)

    def test_replay_synthetic_and_invalid_times_excluded(self):
        records = [fixture(i) for i in range(4)]
        records[1]['metadata']['evaluation_scope'] = 'replay_or_legacy'
        records[2]['metadata']['result_timestamp'] = records[2]['prediction_timestamp']
        records[3]['metadata']['result_timestamp'] = '2026-08-04T14:00:00'
        selected, report = prepare(records, synthetic=True)
        self.assertEqual(len(selected), 1)
        self.assertEqual(sum(report['excluded'].values()), 3)
        self.assertEqual(prepare([records[0]])[1]['excluded'], {'synthetic_excluded': 1})
        self.assertEqual(evaluate_records([])['status'], 'blocked_insufficient_eligible_data')

    def test_baseline_and_duplicate_validation(self):
        bad = fixture(0)
        bad['trifecta_scores'][0]['estimated_probability'] = float('nan')
        self.assertEqual(prepare([bad], synthetic=True)[0], [])
        bad = fixture(0)
        bad['trifecta_scores'][0]['combo_key'] = '1-1-2'
        self.assertEqual(prepare([bad], synthetic=True)[0], [])
        good = fixture(0)
        selected, report = prepare([good, deepcopy(good)], synthetic=True)
        self.assertEqual(len(selected), 1)
        self.assertEqual(report['duplicate_snapshots_removed'], 1)
        conflict = deepcopy(good)
        conflict['outcome_combo'] = '2-3-4'
        self.assertEqual(prepare([good, conflict], synthetic=True)[0], [])

    def test_chronological_evaluation_requires_at_least_five_distinct_prediction_times(self):
        four = evaluate_records([fixture(i) for i in range(4)], synthetic=True)
        self.assertEqual(four['status'], 'blocked_insufficient_eligible_data')
        self.assertEqual(four['blocked_reason'], 'need_at_least_five_distinct_prediction_times')

        five = [fixture(i) for i in range(5)]
        selected, _ = prepare(five, synthetic=True)
        train, valid, test, audit = split_records(selected)
        self.assertGreaterEqual(len(train), 2)
        self.assertGreaterEqual(len(valid), 1)
        self.assertGreaterEqual(len(test), 1)
        self.assertEqual(len({x['prediction_time'] for x in selected}), 5)
        self.assertEqual(audit['purged_unsettled_at_boundary'], 0)

    def test_readiness_protocol_matches_evaluator_preparation_and_split(self):
        records = [fixture(i) for i in range(10)]
        records[0]['metadata']['result_timestamp'] = records[8]['metadata']['result_timestamp']
        evaluator_selected, evaluator_quality = prepare(records, synthetic=True)
        protocol_selected, protocol_quality = protocol_prepare(records, synthetic=True)
        self.assertEqual(
            [x['race_id'] for x in protocol_selected],
            [x['race_id'] for x in evaluator_selected],
        )
        self.assertEqual(protocol_quality, evaluator_quality)

        e_train, e_valid, e_test, e_audit = split_records(evaluator_selected)
        p_train, p_valid, p_test, p_audit = protocol_split_records(protocol_selected)
        self.assertEqual([x['race_id'] for x in p_train], [x['race_id'] for x in e_train])
        self.assertEqual([x['race_id'] for x in p_valid], [x['race_id'] for x in e_valid])
        self.assertEqual([x['race_id'] for x in p_test], [x['race_id'] for x in e_test])
        self.assertEqual(p_audit, e_audit)
        self.assertTrue(protocol_readiness(records, synthetic=True)['chronological_partitions_ready'])

    def test_utc_order_and_boundary_purge(self):
        records = [fixture(i) for i in range(10)]
        # A training-period label unavailable at validation time must be purged.
        records[0]['metadata']['result_timestamp'] = records[8]['metadata']['result_timestamp']
        # A validation-period label unavailable at test time must be purged.
        records[6]['metadata']['result_timestamp'] = records[9]['metadata']['result_timestamp']
        selected, _ = prepare(records, synthetic=True)
        train, valid, test, audit = split_records(selected)
        self.assertEqual(audit['purged_unsettled_at_boundary'], 2)
        self.assertNotIn('SYN-000', audit['train_race_ids'])
        self.assertNotIn('SYN-006', audit['validation_race_ids'])
        self.assertLess(max(x['result_time'] for x in train), min(x['prediction_time'] for x in valid))
        self.assertLess(max(x['result_time'] for x in valid), min(x['prediction_time'] for x in test))
        self.assertEqual(timestamp('2026-08-01T12:00:00+09:00'), timestamp('2026-08-01T03:00:00Z'))
        self.assertFalse(set(audit['train_race_ids']) & set(audit['test_race_ids']))

    def test_metrics_known_values(self):
        result = score({'1-2-3': 0.75, '1-3-2': 0.25}, '1-3-2')
        self.assertEqual(result['rank'], 2)
        self.assertEqual(result['reciprocal_rank'], 0.5)
        self.assertEqual(result['brier_sum'], 1.125)
        self.assertEqual(result['top1'], 0)
        self.assertEqual(result['top3'], 1)

    def test_end_to_end_synthetic_holdout(self):
        report = evaluate_records([fixture(i) for i in range(16)], synthetic=True)
        self.assertEqual(report['status'], 'completed_offline_holdout')
        self.assertEqual(report['evidence_scope'], 'synthetic_test_only')
        self.assertFalse(report['promotion_eligible'])
        self.assertEqual(report['test_races'], 4)
        self.assertEqual(report['split']['test_race_ids'], ['SYN-012', 'SYN-013', 'SYN-014', 'SYN-015'])
        self.assertEqual(len(report['per_race']), 4)
        json.dumps(report, allow_nan=False)


if __name__ == '__main__':
    unittest.main()
