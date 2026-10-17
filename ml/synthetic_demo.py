"""Deterministic generated records shared by the smoke and synthetic workbench."""

def make_record(index: int, rider_count: int = 7) -> dict:
    styles = ['逃', '逃', '両', '追', '追', '両', '追', '両', '追']
    players = []
    for car in range(1, rider_count + 1):
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
    if rider_count == 9:
        outcomes = ['1-8-9', '8-5-6', '3-9-7', '9-1-2']
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
            'race_conditions': {'race_status': 'scheduled', 'withdrawn_car_numbers': []},
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
