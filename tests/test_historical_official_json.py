"""Synthetic paired-JSON transport evidence and existing review boundaries."""
import copy
import hashlib
import json
import unittest

from ml.historical_official_json import ingest_json_result
from ml.historical_official_records import join_json_result
from ml.historical_training import digest
from tests.test_historical_official_detail import blocks, page, receipt


def capture(data, kind):
    raw = json.dumps(data, ensure_ascii=False).encode()
    rec = receipt(raw)
    rec.update(method='GET', url=f'https://keirin.jp/pc/json?encp=synthetic-selection&type={kind}',
               final_url=f'https://keirin.jp/pc/json?type={kind}&encp=synthetic-selection')
    return raw, rec


def inputs(count=7, edit=None):
    h, p = blocks(count)
    h['C0201data']['encSelParaR'] = 'synthetic-selection'
    if edit:
        edit(h, p)
    hb, hr = capture(h, 'JSJ001'); rb, rr = capture(p, 'JSJ012')
    return [hb, hr, rb, rr, '2026-01-02', '35', 1]


class OfficialJsonTests(unittest.TestCase):
    def test_three_to_nine_rows_keep_both_blocks_hashes_and_receipts(self):
        for n in range(3, 10):
            args = inputs(n); before = copy.deepcopy(args)
            result = ingest_json_result(*args)
            self.assertEqual(args, before)
            self.assertEqual(result['issues'], [])
            self.assertEqual(result['summary']['listed_rider_count'], n)
            self.assertEqual(result['raw_blocks'], {'PC0201': json.loads(args[0]), 'PJ0326': json.loads(args[2])})
            self.assertEqual(result['source_capture_sha256'], {'PC0201': args[1]['sha256'], 'PJ0326': args[3]['sha256']})
            self.assertEqual(result['source_sha256'], digest(result['source_capture_sha256']))
            self.assertEqual(result['record_sha256_without_hash_field'], digest({k:v for k,v in result.items() if k!='record_sha256_without_hash_field'}))
            self.assertFalse(result['training_eligible'])

    def test_each_response_requires_matching_bytes_and_receipt(self):
        for idx in (1, 3):
            for field, value in (('sha256', '0'*64), ('bytes', 0), ('status', 500), ('method', 'POST')):
                with self.subTest(idx=idx, field=field):
                    args=inputs();args[idx][field]=value
                    with self.assertRaisesRegex(ValueError,'receipt_mismatch'):ingest_json_result(*args)

    def test_each_url_type_host_and_parameters_are_closed(self):
        for index in (1,3):
            for field in ('url','final_url'):
                for replacement in ('https://example.com/pc/json?encp=x&type=JSJ012',
                        'https://keirin.jp/pc/json?encp=x&type=JSJ999',
                        'https://keirin.jp/pc/json?encp=x&encp=y&type=JSJ012',
                        'https://keirin.jp/pc/json?encp=&type=JSJ012'):
                    args=inputs();args[index][field]=replacement
                    with self.assertRaises(ValueError):ingest_json_result(*args)

    def test_redirect_and_cross_capture_selection_changes_are_rejected(self):
        args=inputs();args[3]['final_url']=args[3]['final_url'].replace('synthetic-selection','different')
        with self.assertRaisesRegex(ValueError,'redirect_parameters'):ingest_json_result(*args)
        args[3]['url']=args[3]['url'].replace('synthetic-selection','different')
        with self.assertRaisesRegex(ValueError,'capture_selection_mismatch'):ingest_json_result(*args)

    def test_header_selection_and_expected_race_are_checked(self):
        args=inputs(edit=lambda h,p:h['C0201data'].update(encSelParaR='other'))
        with self.assertRaisesRegex(ValueError,'header_selection_mismatch'):ingest_json_result(*args)
        for index,value in ((4,'2026-01-03'),(5,'21'),(6,2)):
            args=inputs();args[index]=value
            with self.assertRaisesRegex(ValueError,'race_identity_mismatch'):ingest_json_result(*args)

    def test_unpublished_results_are_not_empty_training_records(self):
        for key in ('tyakujyunDispFlg','haraiGakuDispFlg'):
            for value in (False,None,1,'true'):
                args=inputs(edit=lambda h,p:p.update({key:value}))
                with self.assertRaisesRegex(ValueError,'result_not_published'):ingest_json_result(*args)

    def test_duplicate_json_keys_and_nonfinite_values_rejected(self):
        for raw in (b'{"resultCd":0,"resultCd":0}', b'{"resultCd":0,"x":NaN}'):
            args=inputs();args[2]=raw;args[3].update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            with self.assertRaises(ValueError):ingest_json_result(*args)

    def test_both_capture_times_must_follow_start_and_latest_is_observed(self):
        args=inputs();args[1]['download_completed_at']='2026-01-02T22:00:00+09:00'
        result=ingest_json_result(*args)
        self.assertEqual(result['observed_at'],args[1]['download_completed_at'])
        for index in (1,3):
            args=inputs();args[index].update(request_started_at='2026-01-02T08:00:00+09:00',download_completed_at='2026-01-02T08:01:00+09:00')
            with self.assertRaisesRegex(ValueError,'before_listed_start'):ingest_json_result(*args)

    def test_existing_retirement_and_payout_checks_apply(self):
        def edit(h,p):p['tyakujyunItemSubData'][0]['kojinStateItemSubData']=[{'kojinState':'落車棄権'}]
        self.assertIn('contradictory_retirement_and_finish',ingest_json_result(*inputs(edit=edit))['issues'])
        def payout(h,p):p['haraiGakuSubData']['RT3HaraiGakuDispItemSubData'][0]['kumiBan']='1-2-4'
        self.assertIn('finish_order_payout_disagree',ingest_json_result(*inputs(edit=payout))['issues'])

    def test_original_pre_capture_joins_without_granting_approval(self):
        h,p=blocks(7,'pre');pre=page(h,p,'pre');args=inputs()
        record=join_json_result(pre,receipt(pre,'pre'),*args)
        self.assertEqual(record['rider_count'],7)
        self.assertEqual(record['source_observations']['result']['capture_format'],'paired_official_json')
        self.assertFalse(record['training_approved'])
        self.assertEqual(record['training_use_status'],'unconfirmed')
        late=receipt(pre,'result')
        with self.assertRaisesRegex(ValueError,'capture_not_before'):join_json_result(pre,late,*args)

    def test_tied_json_result_still_requires_multilabel_review(self):
        def edit(h,p):
            p['tyakujyunItemSubData'][1]['tyaku']='1'
            payouts=p['haraiGakuSubData']
            payouts['ST2HaraiGakuDispItemSubData'].append({'kumiBan':'2-1','haraiGaku':'410','kumiDispFlg':True})
            payouts['RT3HaraiGakuDispItemSubData'].append({'kumiBan':'2-1-3','haraiGaku':'1200','kumiDispFlg':True})
        args=inputs(edit=edit)
        self.assertEqual(ingest_json_result(*args)['issues'],[])
        h,p=blocks(7,'pre');pre=page(h,p,'pre')
        with self.assertRaisesRegex(ValueError,'dead_heat_requires_multilabel_contract'):
            join_json_result(pre,receipt(pre,'pre'),*args)


if __name__=='__main__':unittest.main()
