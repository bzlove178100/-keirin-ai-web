from itertools import permutations
import unittest

from ml.offline_preview import render_preview, validate_preview
from ml.category_selection import select_model_categories


def fixture(count=7):
    combos = list(permutations(range(1, count+1), 3))
    return {
        'success':True, 'mode':'offline_inference_only',
        'model_version':'lightgbm-position-rankers-v1',
        'inference_version':'lightgbm-offline-inference-v1',
        'adapter_version':'position-probability-to-trifecta-v1',
        'production_prediction_enabled':False, 'db_write_enabled':False,
        'external_fetch_enabled':False, 'monetary_ev_enabled':False,
        'odds_used_as_model_feature':False, 'probability_calibration_status':'uncalibrated',
        'race':{'venue':'SYNTHETIC', 'race_number':1, 'date':'2099-01-01'},
        'model_artifact':{'evidence_scope':'synthetic_test_only'},
        'trifecta_scores':[{'combo_key':'-'.join(map(str,c)), 'estimated_probability':1/len(combos), 'odds':12.3 if i==0 else None, 'monetary_expected_value':None} for i,c in enumerate(combos)],
        'position_rankings':{p:[{'car_number':i, 'rank':i, 'estimated_probability':1/count} for i in range(1,count+1)] for p in ('first','second','third')},
        'input_quality':{'rider_count':count,'possible_trifecta_count':len(combos),'known_trifecta_odds_count':1},
    }


class OfflinePreviewTests(unittest.TestCase):
    def test_seven_and_nine_complete_tables_and_partial_odds(self):
        for count, possible in ((7,210),(9,504)):
            result=fixture(count)
            html=render_preview(result)
            self.assertIn(f'全{possible}通り',html)
            self.assertIn(f'1/{possible}',html)
            self.assertIn('未確認',html)
            self.assertIn('合成データでの動作検証',html)
            self.assertIn("connect-src 'none'",html)
            self.assertNotIn('<script',html)
            self.assertNotIn('<form',html)
            self.assertEqual(result,fixture(count))
            self.assertEqual(html.count('class="card category"'), 5)

    def test_selection_must_match_model_scores(self):
        for count in (7,9):
            result=fixture(count)
            result['selected_predictions']=select_model_categories(result['trifecta_scores'], count)
            self.assertIn('5カテゴリのモデル候補 · 3点',render_preview(result))
            result['selected_predictions']['categories']['hit_priority']['picks'][0]['odds']=999
            with self.assertRaises(ValueError):render_preview(result)
            result['selected_predictions']=select_model_categories(result['trifecta_scores'], count)
            result['selected_predictions']['monetary_ev_enabled']=0
            with self.assertRaises(ValueError):render_preview(result)

    def test_text_is_escaped_and_unknown_provenance_not_promoted(self):
        result=fixture()
        result['race']['venue']='</title><img src="https://bad.invalid/" onerror="alert(1)">'
        result.pop('model_artifact')
        html=render_preview(result)
        self.assertNotIn('<img',html)
        self.assertIn('&lt;img',html)
        self.assertIn('学習データの由来は未確認',html)
        self.assertNotIn('合成データでの動作検証',html)

    def test_safety_and_version_flags_fail_closed(self):
        for key in ('production_prediction_enabled','db_write_enabled','external_fetch_enabled','monetary_ev_enabled','odds_used_as_model_feature'):
            for value in (True, None, 0):
                with self.subTest(key=key,value=value):
                    bad=fixture();bad[key]=value
                    with self.assertRaises(ValueError):render_preview(bad)
        for key in ('model_version','inference_version','adapter_version','probability_calibration_status','mode'):
            bad=fixture();bad[key]='unexpected'
            with self.assertRaises(ValueError):render_preview(bad)

    def test_bad_probability_tables_and_metadata_rejected(self):
        mutations=[
            lambda r:r['trifecta_scores'].pop(),
            lambda r:r['trifecta_scores'][0].update(combo_key='10-2-3'),
            lambda r:r['trifecta_scores'][0].update(combo_key=r['trifecta_scores'][1]['combo_key']),
            lambda r:r['trifecta_scores'][0].update(estimated_probability=float('nan')),
            lambda r:r['trifecta_scores'][0].update(estimated_probability=-0.01),
            lambda r:r['trifecta_scores'][0].update(odds=True),
            lambda r:r['trifecta_scores'][0].update(monetary_expected_value=1),
            lambda r:r['input_quality'].update(known_trifecta_odds_count=2),
            lambda r:r['input_quality'].update(possible_trifecta_count=100),
            lambda r:r['position_rankings']['first'].pop(),
            lambda r:r['position_rankings']['first'][0].update(car_number=True),
            lambda r:r['position_rankings']['first'][0].update(rank=2),
        ]
        for count in (7,9):
            for index,mutate in enumerate(mutations):
                with self.subTest(count=count,index=index):
                    bad=fixture(count);mutate(bad)
                    with self.assertRaises(ValueError):validate_preview(bad)
        for count in (6,8,10):
            with self.assertRaises(ValueError):validate_preview(fixture(count))


if __name__=='__main__':unittest.main()
