from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from itertools import permutations
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from ml.dataset import build_rows
from ml.predict_position_models import load_models, predict_race, validate_race_data
from ml.offline_preview import render_preview
from ml.train_position_models import train


from ml.synthetic_demo import make_record


def check_declared_race_conditions():
    for count in (7,9):
        source=make_record(16,count)['training_input']
        for conditions in (None, {}, {'race_status':'unknown','withdrawn_car_numbers':[]},
                           {'race_status':'cancelled','withdrawn_car_numbers':[]},
                           {'race_status':'scheduled','withdrawn_car_numbers':[count]},
                           {'race_status':'scheduled','withdrawn_car_numbers':[], 'dead_heat':True}):
            bad=deepcopy(source);bad['race_conditions']=conditions
            with patch('ml.predict_position_models.load_models') as loader:
                try:
                    predict_race(bad,Path('/unused'))
                except ValueError:
                    pass
                else:
                    raise AssertionError('nonstandard declaration accepted')
                loader.assert_not_called()


def main() -> None:
    check_declared_race_conditions()
    records = [make_record(i, 7 if i % 2 == 0 else 9) for i in range(16)]
    rider_rows, summary = build_rows(records)
    assert summary['eligible_unique_races'] == 16
    assert len(rider_rows) == 128

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        csv_path = root / 'riders.csv'
        output_dir = root / 'models'
        with csv_path.open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(rider_rows[0].keys()))
            writer.writeheader()
            writer.writerows(rider_rows)

        metrics = train(csv_path, output_dir, min_races=5, validation_fraction=0.25)
        assert metrics['status'] == 'trained_offline_validation_only'
        assert metrics['production_enabled'] is False
        assert metrics['promotion_eligible'] is False
        assert metrics['probability_calibration_status'] == 'uncalibrated'
        assert metrics['odds_used_as_model_feature'] is False
        assert metrics['validation_races'] == 4
        assert (output_dir / 'first.txt').exists()
        assert (output_dir / 'second.txt').exists()
        assert (output_dir / 'third.txt').exists()
        assert (output_dir / 'feature_schema.json').exists()
        assert (output_dir / 'metrics.json').exists()

        # This marker is added only after training from the generated records above.
        metrics['evidence_scope'] = 'synthetic_test_only'
        (output_dir / 'metrics.json').write_text(json.dumps(metrics), encoding='utf-8')

        source = make_record(16)['training_input']
        race_data = {
            'race': source['race'],
            'players': source['players'],
            'odds': {
                'trifecta': {
                    '1-4-5': 12.3,
                    '2-6-3': 9999.9,
                    '1-2-3': 'NaN',
                    '1-2-4': 'Infinity',
                    '1-2-5': True,
                    '1-1-2': 12.0,
                    '1-2-9': 15.0,
                    'invalid': 20.0,
                }
            },
            'prediction_context': {'source': 'K-Dreams'},
        }
        prediction = predict_race(race_data, output_dir)
        scores = prediction['trifecta_scores']
        assert prediction['success'] is True
        assert prediction['mode'] == 'offline_inference_only'
        assert prediction['production_prediction_enabled'] is False
        assert prediction['db_write_enabled'] is False
        assert prediction['external_fetch_enabled'] is False
        assert prediction['probability_calibration_status'] == 'uncalibrated'
        assert prediction['monetary_ev_enabled'] is False
        assert prediction['odds_used_as_model_feature'] is False
        assert len(scores) == 210
        assert len({row['combo_key'] for row in scores}) == 210
        assert abs(sum(float(row['estimated_probability']) for row in scores) - 1.0) <= 1e-12
        assert prediction['odds_sanitization']['ignored_combos'] == ['2-6-3']
        assert prediction['input_quality']['known_trifecta_odds_count'] == 1
        assert next(row for row in scores if row['combo_key'] == '2-6-3')['odds'] is None
        assert next(row for row in scores if row['combo_key'] == '1-4-5')['odds'] == 12.3
        assert all(row['monetary_expected_value'] is None for row in scores)

        history_paths = []
        for count in (7, 9):
            generated = make_record(16, count)['training_input']
            scheduled = datetime.now(timezone.utc) + timedelta(hours=count)
            generated['race'].update(date=scheduled.astimezone(timezone(timedelta(hours=9))).date().isoformat(),
                                     race_number=1 if count==7 else 2, scheduled_start_jst=scheduled.isoformat())
            generated['odds'] = {'trifecta': {'1-2-3': 25.4, '2-3-4': 72.0}}
            if count == 9:
                generated['odds']['trifecta'] = {'-'.join(map(str, combo)): [25.4,72.0,200.0,600.0][i % 4]
                    for i, combo in enumerate(list(permutations(range(1, count + 1), 3))[:24])}
            race_path = root / f'race-{count}.json'
            json_path = root / f'prediction-{count}.json'
            html_path = root / f'prediction-{count}.html'
            race_path.write_text(json.dumps(generated), encoding='utf-8')
            # Exercise the real CLI, including model reload and both output files.
            subprocess.run([sys.executable, '-m', 'ml.predict_position_models', str(race_path),
                            '--model-dir', str(output_dir), '--output', str(json_path),
                            '--html-output', str(html_path)], check=True, stdout=subprocess.DEVNULL)
            result = json.loads(json_path.read_text(encoding='utf-8'))
            assert result['race_conditions'] == generated['race_conditions']
            html = html_path.read_text(encoding='utf-8')
            assert len(result['trifecta_scores']) == count*(count-1)*(count-2)
            assert html == render_preview(result)
            assert '合成データでの動作検証' in html
            assert f'{2 if count == 7 else 24}/{count*(count-1)*(count-2)}' in html
            selection = result['selected_predictions']
            assert len(selection['categories']) == 5
            assert selection['total_picks'] == selection['unique_picks']
            assert selection['monetary_ev_enabled'] is False
            assert all(len(c['picks']) <= 3 for c in selection['categories'].values())
            assert all('reason' not in p and 'score' not in p and p['fallback'] is False
                       for c in selection['categories'].values() for p in c['picks'])
            if count == 9:
                assert selection['complete_category_count'] == 5
                assert selection['total_picks'] == 15
            else:
                assert selection['complete_category_count'] == 1
            assert '5カテゴリのモデル候補' in html
            # Freeze the actual reloaded model's output, then settle/evaluate it
            # without retraining or substituting a Phase32 engine identity.
            snap_path=root/f'snapshot-{count}.json'
            settlement_path=root/f'settlement-{count}.json'
            history_path=root/f'history-{count}.json'
            command=[sys.executable,'-m','ml.model_history']
            subprocess.run(command+['capture',str(json_path),'--synthetic','--output',str(snap_path)],
                           check=True,stdout=subprocess.DEVNULL)
            snap=json.loads(snap_path.read_text())
            settlement_path.write_text(json.dumps({'race_id':snap['race_id'],
                'outcome_combo':'1-2-3' if count==7 else '9-8-7', 'settlement_odds':55.5,
                'result_timestamp':(scheduled+timedelta(minutes=10)).isoformat()}))
            subprocess.run(command+['settle',str(snap_path),str(settlement_path),'--synthetic','--output',str(history_path)],
                           check=True,stdout=subprocess.DEVNULL)
            history=json.loads(history_path.read_text())
            assert history['snapshot']['prediction']==result
            assert history['model_artifact_sha256']==result['model_artifact']['sha256']
            history_paths.append(history_path)
            for value in (True, '1', 1.5, 0, count+1):
                bad = deepcopy(generated); bad['players'][0]['car_number'] = value
                assert validate_race_data(bad)
            artifact_dir = os.environ.get('KEIRIN_SMOKE_ARTIFACT_DIR')
            if artifact_dir:
                destination = Path(artifact_dir); destination.mkdir(parents=True, exist_ok=True)
                (destination / html_path.name).write_text(html, encoding='utf-8')
                (destination / json_path.name).write_text(json.dumps(result), encoding='utf-8')

        report_path=root/'model-review.json'
        subprocess.run([sys.executable,'-m','ml.model_history','evaluate',*[str(p) for p in history_paths],
                        '--synthetic','--output',str(report_path)],check=True,stdout=subprocess.DEVNULL)
        report=json.loads(report_path.read_text())
        assert report['status']=='completed_synthetic_frozen_review'
        assert report['evaluated_races']==2
        assert report['promotion_eligible'] is False
        assert {r['rider_count'] for r in report['per_race']}=={7,9}
        assert len(report['model_artifacts'])==1

        for key, value in (('model_version', 'wrong-version'), ('feature_columns', []), ('production_enabled', True)):
            bad = {**metrics, key:value}
            (output_dir / 'metrics.json').write_text(json.dumps(bad), encoding='utf-8')
            try:
                load_models(output_dir)
            except ValueError:
                pass
            else:
                raise AssertionError(f'mismatched model artifact accepted: {key}')
        (output_dir / 'metrics.json').write_text(json.dumps(metrics), encoding='utf-8')


    print('LightGBM mixed 7/9 train → save → reload → inference → categories/HTML → frozen snapshot → settlement → review: PASS')


if __name__ == '__main__':
    main()
