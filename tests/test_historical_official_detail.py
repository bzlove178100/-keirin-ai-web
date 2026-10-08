"""Synthetic saved pages only: no real rider or race data in this repository."""
import copy
import hashlib
import json
import unittest

from ml.historical_official_detail import ingest
from ml.historical_training import digest


def blocks(n=7, mode="result"):
    header = {"resultCd": 0, "C0201data": {
        "selKaisai": "20260102", "selKjyoCd": "35", "selRaceNo": 1,
        "flgRaceCancel": False, "flgSectionCancel": False,
        "C0201racedtl": {"bfrStartTime": "10:00", "aftStartTime": "10:00",
                         "C0201sensyu": [{"carNum": c, "numPlayer": f"{c:06}"} for c in range(1,n+1)]}}}
    rows = [{"syaban": str(c), "sensyuRegistNo": f"{c:06}", "sensyuName": f"Synthetic {c}"} for c in range(1,n+1)]
    if mode == "pre":
        for r in rows: r.update(kyakusitu="追", heikinTokuten="85.1", stTori="2", homeTori="0", backCnt="0", futureSourceField={"preserve": True})
        payload = {"resultCd": 0, "syusouInfoExistFlg": "1", "sensyuTypeInfo": rows, "lastUpdateTime": "old label"}
    else:
        for r in rows: r.update(tyaku=r["syaban"], kojinStateItemSubData=[])
        payload = {"resultCd": 0, "tyakujyunDispFlg": True, "haraiGakuDispFlg": True,
                   "tyakujyunItemSubData": rows, "tenki": "晴", "husoku": "1.0",
                   "haraiGakuSubData": {"APartReturnDispFlg": False,
                       "ST2HaraiGakuDispItemSubData": [{"kumiBan": "1-2", "haraiGaku": "420", "kumiDispFlg": True}],
                       "RT3HaraiGakuDispItemSubData": [{"kumiBan": "1-2-3", "haraiGaku": "1,230", "kumiDispFlg": True}]}}
    return header, payload


def page(h, p, mode="result"):
    key = "PJ0315" if mode == "pre" else "PJ0326"
    return ('<script>\njsonData["PC0201"] = '+json.dumps(h)+';\njsonData["'+key+'"] = '+json.dumps(p)+';\n</script>').encode()


def receipt(raw, mode="result"):
    url = "https://keirin.jp/pc/racelive"
    when = "02:00" if mode == "result" else "00:00"
    return {"url": url, "final_url": url, "status": 200, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
            "request_started_at": "2026-01-02T"+when+":00Z", "download_completed_at": "2026-01-02T"+when+":01Z"}


def run(h=None, p=None, mode="result", raw=None, rec=None, **scope):
    if h is None: h,p=blocks(mode=mode)
    raw=page(h,p,mode) if raw is None else raw
    return ingest(raw,receipt(raw,mode) if rec is None else rec,scope.get('date','2026-01-02'),scope.get('venue','35'),scope.get('race',1),mode)


class OfficialDetailTests(unittest.TestCase):
    def test_three_to_nine_rosters_and_comma_payout(self):
        for n in range(3,10):
            with self.subTest(n=n):
                r=run(*blocks(n));self.assertEqual(r['issues'],[])
                self.assertEqual(r['summary']['confirmed_starter_count'],n)
                self.assertEqual(r['summary']['trifecta'][0]['payout_yen'],1230)

    def test_lossless_pre_fields_and_unchanged_input(self):
        h,p=blocks(mode='pre');old=copy.deepcopy(p);r=run(h,p,mode='pre')
        self.assertEqual(r['raw_blocks']['PJ0315'],p);self.assertEqual(p,old)
        self.assertTrue(r['summary']['captured_before_both_listed_starts'])
        self.assertEqual(r['observed_at'],'2026-01-02T00:00:01Z')

    def test_withdrawal_partial_refund_and_actual_six_starters(self):
        h,p=blocks();p['tyakujyunItemSubData'][6].update(tyaku='',kojinStateItemSubData=[{'kojinState':'欠場'}])
        p['haraiGakuSubData'].update(APartReturnDispFlg=True,APartReturn='一部返還')
        r=run(h,p);self.assertEqual(r['summary']['listed_rider_count'],7)
        self.assertEqual(r['summary']['confirmed_starter_count'],6);self.assertEqual(r['summary']['withdrawn_cars'],[7])
        self.assertTrue(r['summary']['partial_refund_as_observed']);self.assertEqual(r['issues'],[])

    def test_fall_retirement_is_not_a_withdrawal_or_seventh_place(self):
        h,p=blocks();p['tyakujyunItemSubData'][6].update(tyaku='',kojinStateItemSubData=[{'kojinState':'落車棄権'}])
        r=run(h,p);row=r['summary']['rider_rows'][6]
        self.assertIsNone(row['finish_position']);self.assertFalse(row['withdrawn_as_observed'])
        self.assertEqual(r['summary']['confirmed_starter_count'],7)

    def test_unknown_status_retained_without_invented_start_count(self):
        h,p=blocks();p['tyakujyunItemSubData'][6].update(tyaku='',kojinStateItemSubData=[{'kojinState':'未知状態'}])
        r=run(h,p);self.assertIsNone(r['summary']['confirmed_starter_count'])
        self.assertEqual(r['raw_blocks']['PJ0326'],p)

    def test_pre_roster_change_requires_review(self):
        h,p=blocks(mode='pre');p['sensyuTypeInfo'][0]['ketujyouTuikaHojyu']='(欠場)'
        r=run(h,p,mode='pre');self.assertIn('pre_race_roster_note_requires_review',r['issues'])

    def test_hash_status_source_and_chronology(self):
        raw=page(*blocks())
        for edits in [{'sha256':'0'*64},{'bytes':0},{'status':500},{'final_url':'https://other.invalid/pc/racelive'},
                      {'request_started_at':'2026-01-03T00:00:00Z'},{'download_completed_at':'2026-01-02T02:00:01'}]:
            rec=receipt(raw);rec.update(edits)
            with self.subTest(edits=edits),self.assertRaises(ValueError):run(raw=raw,rec=rec)

    def test_changed_date_venue_race_rejected(self):
        for scope in [{'date':'2026-01-03'},{'venue':'34'},{'race':2},{'race':True}]:
            with self.subTest(scope=scope),self.assertRaises(ValueError):run(**scope)

    def test_post_start_features_never_backdated(self):
        h,p=blocks(mode='pre');raw=page(h,p,'pre');rec=receipt(raw,'result')
        with self.assertRaisesRegex(ValueError,'not_before'):run(h,p,mode='pre',rec=rec)
        h['C0201data']['C0201racedtl']['bfrStartTime']='08:30'
        with self.assertRaisesRegex(ValueError,'not_before'):run(h,p,mode='pre')

    def test_result_before_start_rejected(self):
        raw=page(*blocks())
        with self.assertRaisesRegex(ValueError,'result_before'):run(raw=raw,rec=receipt(raw,'pre'))

    def test_duplicate_blocks_json_keys_and_nonfinite_rejected(self):
        raw=page(*blocks())
        for bad in [raw+raw,raw.replace(b'"resultCd": 0',b'"resultCd": 0, "resultCd": 0',1),raw.replace(b'"resultCd": 0',b'"resultCd": NaN',1)]:
            with self.subTest(bad=bad[:30]),self.assertRaises(ValueError):run(raw=bad)

    def test_roster_duplicate_missing_and_id_mismatch_rejected(self):
        for change in ('duplicate','missing','id'):
            h,p=blocks();rows=p['tyakujyunItemSubData']
            if change=='duplicate':rows.append(copy.deepcopy(rows[0]))
            elif change=='missing':rows.pop()
            else:rows[0]['sensyuRegistNo']='999999'
            with self.subTest(change=change),self.assertRaises(ValueError):run(h,p)

    def test_refund_and_changed_payout_quarantined_with_original_retained(self):
        for edits in [{'kumiBan':'全返還'},{'haraiGaku':'1,23'},{'kumiBan':'1-2-4'},{'kumiBan':'1-2-2'}]:
            h,p=blocks();p['haraiGakuSubData']['RT3HaraiGakuDispItemSubData'][0].update(edits)
            r=run(h,p);self.assertTrue(r['issues']);self.assertEqual(r['raw_blocks']['PJ0326'],p)

    def test_missing_classification_and_contradictory_withdrawal_flagged(self):
        h,p=blocks();p['tyakujyunItemSubData'][6]['tyaku']=''
        self.assertIn('unclassified_result_row',run(h,p)['issues'])
        p['tyakujyunItemSubData'][0]['kojinStateItemSubData']=[{'kojinState':'欠場'}]
        self.assertIn('contradictory_withdrawal_and_finish',run(h,p)['issues'])

    def test_no_training_approval_and_content_hash(self):
        r=run();sha=r.pop('record_sha256_without_hash_field')
        self.assertEqual(sha,digest(r));self.assertFalse(r['training_eligible'])
        self.assertEqual(r['training_runs'],0);self.assertFalse(r['automatic_collection_enabled'])


if __name__ == '__main__':
    unittest.main()
