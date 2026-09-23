from __future__ import annotations

import csv
from pathlib import Path
from tempfile import TemporaryDirectory

from ml.dataset import build_rows
from ml.predict_position_models import predict_race
from ml.train_position_models import train


def make_record(index: int) -> dict:
    styles = ['逃', '逃', '両', '追', '追', '両', '追']
    players = []
    for car in range(1, 8):
        players.append({
            'car_number': car,
            'style': styles[car - 1],
            'race_score': 84 + car * 2 + (index % 4) * 0.2,
            'S': (car + index) % 5,
            'H': (car * 2 + index) % 9,
            'B': (car * 3 + index) % 11,
            'line_id': 'L1' if car <= 3 else 'L2' if car <= 5 else 'L3',
            'line_position': 1 if car in (1, 4, 6) else 2 if car in (2, 5, 7) else 3,
            'line_length': 3 if car <= 3 else 2,
            'recent_form': {
                'win_rate': 5 + car + index % 3,
                'top2_rate': 15 + car,
                'top3_rate': 25 + car,
                'avg_finish': 4.5 - car * 0.1,
            },
            'current_meet': {'results': [2 + (car + index) % 3, 1 + car % 4]},
            'condition': {'score': (car % 3) - 1},
            'bank_fit': {'score': (car + 1) % 3},
            'comments': {'parsed_factors': {
                'condition': 1 if car % 2 else 0,
                'training': 1 if car in (1, 4) else 0,
                'equipment': 0,
                'confidence': 1 if car in (2, 5) else 0,
                'motivation': 1,
                'fatigue': 0,
            }},
        })

    outcomes = ['1-4-5', '2-5-6', '3-6-7', '4-1-2']
    outcome = outcomes[index % len(outcomes)]
    day = 1 + index
    timestamp = f'2026-08-{day:02d}T12:00:00+09:00'
    return {
        'race_id': f'SYN-{index:03d}',
        'prediction_timestamp': timestamp,
        'outcome_combo': outcome,
        'settlement_odds': 10.0 + index,
        'training_input': {
            'schema_version': 'keirin-training-input-v1',
            'captured_at': timestamp,
            'race': {'date': f'2026-08-{day:02d}', 'venue': 'SYN', 'race_number': 1},
            'players': players,
            'odds': {'trifecta': {}},
            'prediction_context': {'source': 'synthetic_ci_only'},
            'evaluation_scope': 'prospective',
        },
        'metadata': {
            'evaluation_scope': 'prospective',
            'temporal_order': 'prediction_before_result',
            'training_eligibility': {
                'supervised_training': True,
                'reason': 'eligible_prospective_pre_result_snapshot',
            },
        },
    }


def main() -> None:
    records = [make_record(i) for i in range(16)]
    rider_rows, summary = build_rows(records)
    assert summary['eligible_unique_races'] == 16
    assert len(rider_rows) == 112

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

        source = records[-1]['training_input']
        race_data = {
            'race': source['race'],
            'players': source['players'],
            'odds': {
                'trifecta': {
                    '1-4-5': 12.3,
                    '2-6-3': 9999.9,
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

    print('LightGBM position-model train + offline inference smoke: PASS')


if __name__ == '__main__':
    main()
