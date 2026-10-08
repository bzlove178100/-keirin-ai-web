"""Synthetic contracts; no private race or source page is checked into git."""
import copy
import hashlib
import json
import unittest

from ml.historical_official_results import parse_result_list, reconcile
from ml.historical_training import digest, prepare


DATE = "2026-01-02"
HEADER = ('<tr><td rowspan="2">R</td><td colspan="2">2車単</td><td colspan="2">3連単</td></tr>'
          '<tr><td>組番</td><td>払戻金</td><td>組番</td><td>払戻金</td></tr>')


def row(n=1, exacta=("1-2",), trifecta=("1-2-3",), money=("1,230円",), pending=False):
    def cell(items, cls):
        return '<td>' + ''.join(f'<div class="{cls}">{s}</div>' for s in items) + '</td>'
    body = '<td></td>'*4 if pending else cell(exacta,'b')+cell(("420円",)*len(exacta),'pb')+cell(trifecta,'b')+cell(money,'pb')
    return f'<tr><td><input data-name="20260102" data-race="{n}" value="{n}R"></td>{body}</tr>'


def page(rows=None, mobile=True):
    rows = row()+row(2,pending=True) if rows is None else rows
    html = '<table class="pc-only">'+HEADER+rows+'</table>'
    if mobile:
        html += '<table class="sp-only">'+HEADER+rows+'</table>'
    return html.encode()


def snapshot():
    races=[]
    for n in (1,2):
        race={'race_id':f'20260102_hiratsuka{n}', 'race_date':DATE,'race_number':n,
              'venue_key':'hiratsuka','rider_count_as_printed':7,
              'source_observed_at_jst':'2026-01-02T09:00:00+09:00',
              'listed_scheduled_start_jst':f'2026-01-02T10:{n*10}:00+09:00',
              'riders':[{'car_number':c,'name_as_printed':f'Synthetic rider {c}',
                         'score_as_printed':str(80+c)} for c in range(1,8)]}
        race['record_sha256_without_hash_field']=digest(race)
        races.append(race)
    return {'schema_version':'keirin-official-pre-race-source-observation-v1',
            'capture':{'pdf':{'download_completed_at':'2026-01-02T00:00:00Z',
                              'url':'https://example.invalid/synthetic-card.pdf'}},'races':races}


def receipt(raw):
    url='https://www.shonanbank.com/race-result-list/?race_start=20260102'
    return {'url':url,'final_url':url,'status':200,'bytes':len(raw),
            'sha256':hashlib.sha256(raw).hexdigest(),
            'request_started_at':'2026-01-02T01:25:00Z',
            'download_completed_at':'2026-01-02T01:25:01Z'}


def run(snapshot_value=None, raw=None, receipt_value=None):
    raw=page() if raw is None else raw
    data=json.dumps(snapshot() if snapshot_value is None else snapshot_value,ensure_ascii=False).encode()
    return reconcile(data,raw,receipt(raw) if receipt_value is None else receipt_value,hashlib.sha256(data).hexdigest())


def rehash(race):
    race.pop('record_sha256_without_hash_field',None)
    race['record_sha256_without_hash_field']=digest(race)


class OfficialResultsTests(unittest.TestCase):
    def test_join_pending_mobile_duplicates_and_unchanged_baseline(self):
        base=snapshot();before=copy.deepcopy(base)
        result=run(base)
        self.assertEqual(base,before)
        self.assertEqual(result['counts'],{'joined_ordered_payouts':1,'pending':1})
        self.assertEqual(result['observations'][0]['trifecta'],[{'cars':[1,2,3],'payout_yen':1230}])
        self.assertEqual(result['review_candidates'][0]['pre_race_features'][0]['race_score'],81)
        self.assertIsNone(result['review_candidates'][0]['dead_heat'])

    def test_result_bytes_and_snapshot_hashes_are_pinned(self):
        data=json.dumps(snapshot()).encode();raw=page()
        with self.assertRaisesRegex(ValueError,'snapshot_hash'):
            reconcile(data,raw,receipt(raw),'0'*64)
        with self.assertRaisesRegex(ValueError,'receipt_hash'):
            reconcile(data,raw+b' ',receipt(raw),hashlib.sha256(data).hexdigest())
        changed=snapshot();changed['races'][0]['riders'][0]['score_as_printed']='99'
        with self.assertRaisesRegex(ValueError,'record_hash'):
            run(changed)

    def test_changed_headers_and_missing_scope_fail(self):
        with self.assertRaisesRegex(ValueError,'header_changed'):
            parse_result_list(page().replace('2車単'.encode(),'2車複'.encode()),DATE)
        with self.assertRaisesRegex(ValueError,'no_matching'):
            parse_result_list(page(), '2026-01-03')
        with self.assertRaisesRegex(ValueError,'race_set_mismatch'):
            run(raw=page(row()))

    def test_duplicate_desktop_race_fails(self):
        with self.assertRaisesRegex(ValueError,'duplicate_desktop'):
            parse_result_list(page(row()+row()),DATE)

    def test_missing_or_partial_columns_quarantine(self):
        raw=page(row().replace('<div class="pb">1,230円</div>','')+row(2,pending=True))
        r=run(raw=raw)
        self.assertEqual(r['counts'],{'quarantined':1,'pending':1})
        self.assertFalse(r['review_candidates'])

    def test_refund_is_retained_without_invented_outcome(self):
        raw=page(row(trifecta=('全返還',))+row(2,pending=True))
        r=run(raw=raw)
        self.assertEqual(r['observations'][0]['status'],'quarantined')
        self.assertIn('全返還',r['observations'][0]['raw_cells'])

    def test_multiple_ordered_outcomes_are_preserved_not_single_label(self):
        raw=page(row(trifecta=('1-2-3','1-2-4'),money=('1,230円','2,300円'))+row(2,pending=True))
        r=run(raw=raw)
        self.assertEqual(r['review_candidates'][0]['trifecta_outcomes'],[[1,2,3],[1,2,4]])
        plan=prepare(r['review_candidates'],[],'2026-01-03T00:00:00Z','2026-01-04T00:00:00Z')
        self.assertEqual(plan['partition_counts'],{'train':0,'validation':0,'test':0})
        self.assertIn('dead_heat_requires_multilabel_contract',plan['excluded'][0]['reasons'])

    def test_exacta_trifecta_disagreement_quarantines(self):
        r=run(raw=page(row(exacta=('2-1',))+row(2,pending=True)))
        self.assertIn('exacta_trifecta_disagree',r['observations'][0]['issues'])

    def test_duplicate_invalid_cars_or_amounts_quarantine(self):
        for raw in [page(row(trifecta=('1-2-2',))+row(2,pending=True)),
                    page(row(money=('1,23円',))+row(2,pending=True)),
                    page(row(trifecta=('1-2-3','1-2-3'),money=('120円','120円'))+row(2,pending=True)),
                    page(row(trifecta=('1-2-9',))+row(2,pending=True))]:
            with self.subTest(raw=raw):
                self.assertEqual(run(raw=raw)['observations'][0]['status'],'quarantined')

    def test_result_before_start_and_late_feature_capture_quarantine(self):
        raw=page();rec=receipt(raw)
        rec.update(request_started_at='2026-01-02T00:05:00Z',download_completed_at='2026-01-02T00:05:01Z')
        self.assertEqual(run(receipt_value=rec)['observations'][0]['status'],'quarantined')
        base=snapshot();base['races'][0]['source_observed_at_jst']='2026-01-02T10:15:00+09:00';rehash(base['races'][0])
        self.assertEqual(run(base)['observations'][0]['status'],'quarantined')

    def test_source_identity_and_capture_receipt_are_checked(self):
        for edits in [{'final_url':'https://example.invalid/?race_start=20260102'},
                      {'status':500},{'request_started_at':'2026-01-02T03:00:00Z'},
                      {'download_completed_at':'2026-01-02T11:00:00'}]:
            rec=receipt(page());rec.update(edits)
            with self.subTest(edits=edits),self.assertRaises(ValueError):run(receipt_value=rec)

    def test_no_automatic_approval_or_fabricated_missing_features(self):
        r=run();candidate=r['review_candidates'][0]
        self.assertFalse(candidate['pre_race_state_verified'])
        self.assertEqual(candidate['training_use_status'],'unconfirmed')
        self.assertIsNone(candidate['pre_race_features'][0]['style'])
        plan=prepare(r['review_candidates'],[],'2026-01-03T00:00:00Z','2026-01-04T00:00:00Z')
        self.assertEqual(plan['partition_counts'],{'train':0,'validation':0,'test':0})
        self.assertEqual(r['training_runs'],0)


if __name__ == '__main__':
    unittest.main()
