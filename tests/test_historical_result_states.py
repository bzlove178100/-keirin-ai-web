"""Synthetic contradictions must not become finish labels or starter counts."""
import copy
import unittest

from ml.historical_official_records import convert
from tests.test_historical_official_detail import blocks, run
from tests.test_historical_official_records import pair


class ResultStateTests(unittest.TestCase):
    def test_ranked_retirement_is_flagged_and_not_converted(self):
        for state in ('落車棄権', '事故棄権', '故障棄権'):
            for index in (0, 6):
                with self.subTest(state=state, index=index):
                    def edit(h, p):
                        p['tyakujyunItemSubData'][index]['kojinStateItemSubData'] = [{'kojinState': state}]
                    h, p = blocks()
                    edit(h, p)
                    original = copy.deepcopy(p)
                    result = run(h, p)
                    self.assertIn('contradictory_retirement_and_finish', result['issues'])
                    self.assertIsNone(result['summary']['confirmed_starter_count'])
                    self.assertEqual(result['raw_blocks']['PJ0326'], original)
                    report = convert([pair(edit_result=edit)])
                    self.assertEqual(report['summary']['converted_records'], 0)
                    self.assertEqual(report['quarantined_records'][0]['reason'], 'capture_issues_require_review')

    def test_withdrawal_and_retirement_are_mutually_inconsistent(self):
        for states in ([{'kojinState': '欠場'}, {'kojinState': '落車棄権'}],
                       [{'kojinState': '故障棄権'}, {'kojinState': '欠場'}]):
            with self.subTest(states=states):
                h, p = blocks()
                p['tyakujyunItemSubData'][-1].update(tyaku='', kojinStateItemSubData=states)
                result = run(h, p)
                self.assertIn('contradictory_withdrawal_and_retirement', result['issues'])
                self.assertIsNone(result['summary']['confirmed_starter_count'])

    def test_blank_status_placeholders_do_not_classify_missing_rank(self):
        for states in ([], [{}], [{'kojinState': ''}], [{'kojinState': '  '}],
                       [{'kojinState': '', 'tyakuNote': 'retain this note'}]):
            with self.subTest(states=states):
                h, p = blocks()
                p['tyakujyunItemSubData'][-1].update(tyaku='', kojinStateItemSubData=states)
                result = run(h, p)
                self.assertIn('unclassified_result_row', result['issues'])
                self.assertIsNone(result['summary']['confirmed_starter_count'])
                self.assertEqual(result['raw_blocks']['PJ0326'], p)

    def test_nonblank_unknown_status_is_preserved_without_claiming_a_start(self):
        h, p = blocks()
        p['tyakujyunItemSubData'][-1].update(tyaku='', kojinStateItemSubData=[{'kojinState': '未定義'}])
        result = run(h, p)
        self.assertIsNone(result['summary']['confirmed_starter_count'])
        self.assertEqual(result['raw_blocks']['PJ0326'], p)

    def test_ranked_blank_placeholders_remain_valid(self):
        h, p = blocks()
        p['tyakujyunItemSubData'][0]['kojinStateItemSubData'] = [{'kojinState': '', 'tyakuNote': ''}]
        result = run(h, p)
        self.assertEqual(result['issues'], [])
        self.assertEqual(result['summary']['confirmed_starter_count'], 7)

    def test_separate_unranked_withdrawal_and_retirement_remain_valid(self):
        h, p = blocks()
        p['tyakujyunItemSubData'][-2].update(tyaku='', kojinStateItemSubData=[{'kojinState': '欠場'}])
        p['tyakujyunItemSubData'][-1].update(tyaku='', kojinStateItemSubData=[{'kojinState': '事故棄権'}])
        result = run(h, p)
        self.assertEqual(result['issues'], [])
        self.assertEqual(result['summary']['confirmed_starter_count'], 6)
        self.assertEqual(result['summary']['ranked_rider_count'], 5)


if __name__ == '__main__':
    unittest.main()
