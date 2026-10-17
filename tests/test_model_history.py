from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ml.category_selection import select_model_categories
from ml.dataset import supervised_eligibility
from ml.model_history import capture_prediction, settle_snapshot, evaluate_histories, validate_snapshot, _digest
from ml.probability_metrics import score
from ml.settle_snapshot import validate_snapshot as validate_phase32
from test_offline_preview import fixture as prediction_fixture

NOW = datetime(2026, 10, 17, 1, 0, tzinfo=timezone.utc)


def prediction(count=7):
    result = prediction_fixture(count)
    result['race'] = {'date': '2026-10-17', 'venue': 'SYNTHETIC', 'race_number': count,
                      'scheduled_start_jst': '2026-10-17T11:00:00+09:00'}
    result['generated_at'] = '2026-10-17T09:59:00+09:00'
    result['model_artifact'].update(sha256='a'*64, trained_at='2026-10-17T00:30:00Z')
    result['selected_predictions'] = select_model_categories(result['trifecta_scores'], count)
    return result


def snapshot(count=7, now=NOW):
    with patch('ml.model_history.datetime', wraps=datetime) as clock:
        clock.now.return_value = now
        return capture_prediction(prediction(count), synthetic=True)


def settlement(snap, outcome='1-2-3'):
    return {'race_id': snap['race_id'], 'outcome_combo': outcome, 'settlement_odds': 40.0,
            'result_timestamp': '2026-10-17T02:10:00Z'}


class ModelHistoryTests(unittest.TestCase):
    def test_seven_nine_snapshot_settlement_and_frozen_metrics(self):
        records=[]
        for count in (7,9):
            snap=snapshot(count); before=deepcopy(snap)
            outcome='1-2-3' if count==7 else '9-8-7'
            record=settle_snapshot(snap,settlement(snap,outcome),synthetic=True)
            self.assertEqual(snap,before)
            self.assertEqual(record['snapshot']['prediction']['trifecta_scores'],before['prediction']['trifecta_scores'])
            self.assertIsNone(record['snapshot']['prediction']['trifecta_scores'][-1]['odds'])
            self.assertNotIn('outcome_combo',json.dumps(record['snapshot']))
            self.assertFalse(supervised_eligibility(record)[0])
            with self.assertRaisesRegex(ValueError,'schema_mismatch'):validate_phase32(snap)
            records.append(record)
        report=evaluate_histories(records,synthetic=True)
        self.assertEqual(report['status'],'completed_synthetic_frozen_review')
        self.assertEqual(report['evaluated_races'],2)
        by_count={r['rider_count']:r for r in report['per_race']}
        self.assertEqual({count:r['metrics']['rank'] for count,r in by_count.items()},{7:1,9:504})
        self.assertEqual(report['metrics']['top1'],0.5)
        self.assertEqual(by_count[7]['categories']['hit_priority'],{'selected_count':3,'hit':True})
        for key in ('promotion_eligible','monetary_ev_enabled','supervised_training_enabled','production_prediction_enabled'):
            self.assertIs(report[key],False)
        self.assertEqual(score({'a':0.75,'b':0.25},'b')['brier_sum'],1.125)

    def test_explicit_synthetic_gate_and_model_provenance(self):
        snap=snapshot()
        for call in (lambda:capture_prediction(prediction()),
                     lambda:settle_snapshot(snap,settlement(snap)),lambda:evaluate_histories([])):
            with self.assertRaisesRegex(ValueError,'synthetic_mode_required'):call()
        for field,value in [('evidence_scope','not_verified'),('sha256','bad'),('trained_at',None),
                            ('trained_at','2026-10-17T02:00:00Z')]:
            bad=deepcopy(snap);bad['prediction']['model_artifact'][field]=value
            bad['snapshot_sha256']=_digest({k:v for k,v in bad.items() if k!='snapshot_sha256'})
            with self.assertRaises(ValueError):validate_snapshot(bad,synthetic=True)

    def test_identity_time_and_immutable_snapshot_checks(self):
        snap=snapshot()
        bad=deepcopy(snap);bad['prediction']['trifecta_scores'][0]['odds']=400
        with self.assertRaisesRegex(ValueError,'digest_mismatch'):validate_snapshot(bad,synthetic=True)
        mutations=[lambda s:s.update(captured_at='2026-10-17T02:00:00Z'),
                   lambda s:s.update(captured_at='2026-10-17T00:00:00Z'),
                   lambda s:s.update(scheduled_start='2026-10-17T02:01:00Z'),
                   lambda s:s.update(race_id='other'),
                   lambda s:s.update(db_write_enabled=0),
                   lambda s:s.update(clock_source='independently_verified'),
                   lambda s:s['prediction']['race'].update(date='2026-10-16'),
                   lambda s:s['prediction']['model_artifact'].update(trained_at='2026-10-17T00:00:00')]
        for mutate in mutations:
            bad=deepcopy(snap);mutate(bad)
            bad['snapshot_sha256']=_digest({k:v for k,v in bad.items() if k!='snapshot_sha256'})
            with self.assertRaises(ValueError):validate_snapshot(bad,synthetic=True)
        for field,value in [('race_id','other'),('outcome_combo','9-8-7'),('outcome_combo','1-1-2'),
                            ('settlement_odds',True),('settlement_odds',float('nan')),
                            ('result_timestamp','2026-10-17T01:59:59Z')]:
            bad=settlement(snap);bad[field]=value
            with self.assertRaises(ValueError):settle_snapshot(snap,bad,synthetic=True)

    def test_duplicates_conflicts_and_malformed_records(self):
        snap=snapshot(); old=settle_snapshot(snap,settlement(snap),synthetic=True)
        newer=snapshot(now=NOW+timedelta(minutes=1))
        new=settle_snapshot(newer,settlement(newer),synthetic=True)
        report=evaluate_histories([old,new,deepcopy(new),None],synthetic=True)
        self.assertEqual(report['evaluated_races'],1)
        self.assertEqual(report['duplicate_snapshots_removed'],2)
        self.assertEqual(report['per_race'][0]['prediction_timestamp'],newer['captured_at'])
        conflict=settle_snapshot(snap,settlement(snap,'1-2-4'),synthetic=True)
        report=evaluate_histories([old,conflict],synthetic=True)
        self.assertEqual(report['excluded'],{'conflicting_settlements':2})
        self.assertEqual(report['status'],'blocked_no_valid_histories')
        tied=deepcopy(snap);tied['prediction']['model_artifact']['sha256']='b'*64
        tied['snapshot_sha256']=_digest({k:v for k,v in tied.items() if k!='snapshot_sha256'})
        conflict=settle_snapshot(tied,settlement(tied),synthetic=True)
        report=evaluate_histories([old,conflict],synthetic=True)
        self.assertEqual(report['excluded'],{'conflicting_latest_snapshots':2})
        bad=deepcopy(old);bad['model_artifact_sha256']='b'*64
        self.assertEqual(evaluate_histories([bad],synthetic=True)['evaluated_races'],0)

    def test_cli_requires_synthetic_and_refuses_overwrite(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp);source=path/'prediction.json';output=path/'snapshot.json'
            value=prediction();value['race'].update(date='2099-01-01',scheduled_start_jst='2099-01-01T11:00:00+09:00')
            source.write_text(json.dumps(value))
            args=[sys.executable,'-m','ml.model_history','capture',str(source),'--output',str(output)]
            run=subprocess.run(args,capture_output=True,text=True)
            self.assertNotEqual(run.returncode,0);self.assertFalse(output.exists())
            subprocess.run(args+['--synthetic'],check=True,capture_output=True)
            before=output.read_bytes()
            run=subprocess.run(args+['--synthetic'],capture_output=True,text=True)
            self.assertNotEqual(run.returncode,0);self.assertEqual(output.read_bytes(),before)


if __name__=='__main__':unittest.main()
