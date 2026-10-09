"""Synthetic disqualification evidence: crossing order never becomes a label."""
import copy
import unittest
from tests.test_historical_official_detail import blocks, page, receipt, run
from tests.test_historical_official_json import inputs
from ml.historical_official_json import ingest_json_result
from ml.historical_official_records import join_json_result


def disqualify(h, p, crossing='7', extra=(), rank=''):
    p['tyakujyunItemSubData'][-1].update(tyaku=rank, inLineJyuni=crossing,
        kojinStateItemSubData=[{'kojinState':'失格','tyakuNote':'synthetic'}]+
                            [{'kojinState':s} for s in extra])


class DisqualificationTests(unittest.TestCase):
    def test_crossing_order_preserved_separately_from_finish_and_retirement(self):
        for n in range(4,10):
            h,p=blocks(n);disqualify(h,p,str(n));original=copy.deepcopy(p)
            r=run(h,p);row=r['summary']['rider_rows'][-1]
            self.assertEqual(r['issues'],[])
            self.assertEqual(r['summary']['confirmed_starter_count'],n)
            self.assertIsNone(row['finish_position'])
            self.assertFalse(row['withdrawn_as_observed'])
            self.assertFalse(row['started_but_did_not_finish_as_observed'])
            self.assertEqual(row['crossing_order_as_observed'],str(n))
            self.assertEqual(r['raw_blocks']['PJ0326'],original)

    def test_missing_malformed_out_of_roster_crossing_remains_quarantined(self):
        for value in (None,'','0','8','10','01',' 7','７',7,True,[],{}):
            for extra in ((),('落車棄権',)):
                with self.subTest(value=value,extra=extra):
                    h,p=blocks();disqualify(h,p,value,extra)
                    r=run(h,p)
                    self.assertIn('disqualified_start_evidence_requires_review',r['issues'])
                    self.assertIsNone(r['summary']['confirmed_starter_count'])

    def test_contradictory_rank_withdrawal_and_retirement_cannot_pass(self):
        for extra,rank,issue in (((),'7','contradictory_disqualification_and_finish'),
                ((),None,'contradictory_disqualification_and_finish'),
                (('欠場',),'','contradictory_withdrawal_and_disqualification'),
                (('落車棄権',),'','contradictory_retirement_and_crossing')):
            h,p=blocks();disqualify(h,p,'7',extra,rank);r=run(h,p)
            self.assertIn(issue,r['issues']);self.assertIsNone(r['summary']['confirmed_starter_count'])

    def test_unknown_status_with_crossing_is_not_promoted(self):
        h,p=blocks();disqualify(h,p)
        p['tyakujyunItemSubData'][-1]['kojinStateItemSubData']=[{'kojinState':'unknown'}]
        self.assertIsNone(run(h,p)['summary']['confirmed_starter_count'])

    def test_disqualified_rider_cannot_appear_in_ordered_payout(self):
        h,p=blocks();disqualify(h,p)
        p['haraiGakuSubData']['RT3HaraiGakuDispItemSubData'][0]['kumiBan']='1-2-7'
        self.assertIn('finish_order_payout_disagree',run(h,p)['issues'])

    def test_json_join_preserves_full_pre_population_without_approval(self):
        def edit(h,p):
            disqualify(h,p,'7')
            p['tyakujyunItemSubData'][-2].update(tyaku='',kojinStateItemSubData=[{'kojinState':'落車棄権'}])
        h,p=blocks(7,'pre');raw=page(h,p,'pre')
        r=join_json_result(raw,receipt(raw,'pre'),*inputs(edit=edit))
        self.assertEqual(r['actual_starters'],7)
        self.assertEqual(len(r['pre_race_features']),7)
        self.assertEqual(r['trifecta_outcomes'],[[1,2,3]])
        self.assertFalse(r['training_approved'])
        self.assertEqual(r['training_use_status'],'unconfirmed')
        for edit in (lambda h,p:disqualify(h,p,None),lambda h,p:disqualify(h,p,'7',('欠場',))):
            with self.assertRaisesRegex(ValueError,'capture_issues'):
                join_json_result(raw,receipt(raw,'pre'),*inputs(edit=edit))


if __name__=='__main__': unittest.main()
