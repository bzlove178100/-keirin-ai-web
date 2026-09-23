from ml.build_trifecta_dataset import build_dataset, record_to_rows


def make_record(scope='prospective', supervised=True, race_id='R1'):
    players=[]
    styles=['逃','追','両','追','逃','両','追']
    for car in range(1,8):
        players.append({
            'car_number':car,
            'name':f'P{car}',
            'style':styles[car-1],
            'race_score':90+car,
            'S':car%3,
            'H':car%4,
            'B':car%5,
            'line_id':f'L{1 if car<=3 else 2 if car<=5 else 3}',
            'line_position':1 if car in (1,4,6) else 2 if car in (2,5,7) else 3,
            'line_length':3 if car<=3 else 2,
        })
    return {
        'race_id':race_id,
        'prediction_timestamp':'2026-09-23T10:00:00+09:00',
        'outcome_combo':'7-6-5',
        'settlement_odds':50.0,
        'training_input':{
            'schema_version':'keirin-training-input-v1',
            'captured_at':'2026-09-23T10:00:00+09:00',
            'race':{'date':'2026-09-23','venue':'TEST','race_number':1},
            'players':players,
            'odds':{'trifecta':{'7-6-5':45.0}},
            'prediction_context':{'source':'test'},
            'evaluation_scope':scope,
        },
        'metadata':{
            'evaluation_scope':scope,
            'temporal_order':'prediction_before_result',
            'training_eligibility':{
                'supervised_training':supervised,
                'reason':'eligible_prospective_pre_result_snapshot' if supervised else 'replay_or_legacy_excluded',
            },
        },
    }


def test_prospective_record_expands_to_210_rows():
    rows=record_to_rows(make_record())
    assert len(rows)==210
    assert sum(r['label'] for r in rows)==1
    assert next(r for r in rows if r['label']==1)['combo_key']=='7-6-5'


def test_prediction_odds_are_metadata_not_features():
    rows,manifest=build_dataset([make_record()])
    assert len(rows)==210
    assert manifest['uses_prediction_time_odds_as_feature'] is False
    assert 'prediction_odds' not in manifest['feature_columns']
    assert next(r for r in rows if r['combo_key']=='7-6-5')['prediction_odds']==45.0


def test_replay_and_noneligible_records_are_excluded():
    replay=make_record(scope='replay_or_legacy',supervised=False,race_id='R2')
    bad=make_record(scope='prospective',supervised=False,race_id='R3')
    rows,manifest=build_dataset([replay,bad])
    assert rows==[]
    assert manifest['eligible_records']==0
    assert manifest['accepted_races']==0


if __name__=='__main__':
    test_prospective_record_expands_to_210_rows()
    test_prediction_odds_are_metadata_not_features()
    test_replay_and_noneligible_records_are_excluded()
    print('ml dataset checks: PASS')
