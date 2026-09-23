from pathlib import Path
from tempfile import TemporaryDirectory

from ml.build_trifecta_dataset import build_dataset, write_csv
from ml.train_lightgbm_ranker import train


def make_record(index:int):
    players=[]
    styles=['逃','追','両','追','逃','両','追']
    for car in range(1,8):
        players.append({
            'car_number':car,
            'name':f'P{car}',
            'style':styles[car-1],
            'race_score':90+car+(index%3)*0.1,
            'S':(car+index)%4,
            'H':(car*2+index)%8,
            'B':(car*3+index)%10,
            'line_id':f'L{1 if car<=3 else 2 if car<=5 else 3}',
            'line_position':1 if car in (1,4,6) else 2 if car in (2,5,7) else 3,
            'line_length':3 if car<=3 else 2,
        })
    outcome='7-6-5' if index%2==0 else '6-7-5'
    ts=f'2026-09-{10+index:02d}T10:00:00+09:00'
    return {
        'race_id':f'SYN-{index}',
        'prediction_timestamp':ts,
        'outcome_combo':outcome,
        'settlement_odds':50.0,
        'training_input':{
            'schema_version':'keirin-training-input-v1',
            'captured_at':ts,
            'race':{'date':f'2026-09-{10+index:02d}','venue':'SYN','race_number':1},
            'players':players,
            'odds':{'trifecta':{}},
            'prediction_context':{'source':'synthetic_ci_only'},
            'evaluation_scope':'prospective',
        },
        'metadata':{
            'evaluation_scope':'prospective',
            'temporal_order':'prediction_before_result',
            'training_eligibility':{
                'supervised_training':True,
                'reason':'eligible_prospective_pre_result_snapshot',
            },
        },
    }


def main():
    records=[make_record(i) for i in range(10)]
    rows,manifest=build_dataset(records)
    assert manifest['accepted_races']==10
    assert len(rows)==2100
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        dataset=root/'dataset.csv'
        model=root/'model.txt'
        metrics=root/'metrics.json'
        write_csv(rows,dataset)
        result=train(dataset,model,metrics,min_races=6,validation_fraction=0.2)
        assert result['status']=='trained_validation_only'
        assert result['production_enabled'] is False
        assert result['model_output']=='ranking_score_not_probability'
        assert result['prediction_time_odds_used_as_feature'] is False
        assert model.exists() and model.stat().st_size>0
        assert metrics.exists() and metrics.stat().st_size>0
    print('LightGBM smoke training: PASS')


if __name__=='__main__':
    main()
