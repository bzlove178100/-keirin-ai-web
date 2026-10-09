"""Synthetic rank/payout consistency checks; no real race or permission data."""
import copy
import itertools
import unittest

from tests.test_historical_official_detail import blocks, run


def tied_page(ranks, trifectas, exactas=None):
    header, payload = blocks(len(ranks))
    for row, rank in zip(payload['tyakujyunItemSubData'], ranks):
        row['tyaku'] = str(rank)
    if exactas is None:
        exactas = sorted({tuple(t[:2]) for t in trifectas})
    payouts = payload['haraiGakuSubData']
    for key, values in [('ST2HaraiGakuDispItemSubData', exactas),
                        ('RT3HaraiGakuDispItemSubData', trifectas)]:
        payouts[key] = [{'kumiBan': '-'.join(map(str, cars)),
                        'haraiGaku': str(1200 + 10 * i), 'kumiDispFlg': True}
                       for i, cars in enumerate(values)]
    return header, payload


class DeadHeatPayoutTests(unittest.TestCase):
    def test_first_second_third_and_lower_ties_preserve_all_observed_payouts(self):
        cases = [
            ([1, 1, 3, 4, 5], [(1, 2, 3), (2, 1, 3)]),
            ([1, 2, 2, 4, 5], [(1, 2, 3), (1, 3, 2)]),
            ([1, 2, 3, 3, 5], [(1, 2, 3), (1, 2, 4)]),
            ([1, 2, 3, 4, 4], [(1, 2, 3)]),
            ([1, 1, 1, 4, 5], list(itertools.permutations((1, 2, 3)))),
            ([1, 1, 3, 3, 5], [(1, 2, 3), (1, 2, 4), (2, 1, 3), (2, 1, 4)]),
        ]
        for ranks, outcomes in cases:
            with self.subTest(ranks=ranks):
                h, p = tied_page(ranks, outcomes)
                before = copy.deepcopy(p)
                result = run(h, p)
                self.assertEqual(result['issues'], [])
                self.assertEqual(result['raw_blocks']['PJ0326'], before)
                self.assertEqual(p, before)
                self.assertEqual([tuple(x['cars']) for x in result['summary']['trifecta']], outcomes)
                self.assertEqual([x['payout_yen'] for x in result['summary']['trifecta']],
                                 [1200 + 10*i for i in range(len(outcomes))])
                self.assertFalse(result['training_eligible'])

    def test_missing_tied_outcome_is_rejected_even_when_exacta_prefixes_agree(self):
        for ranks, outcomes in [([1, 1, 3, 4], [(1, 2, 3)]),
                                ([1, 2, 3, 3], [(1, 2, 3)])]:
            with self.subTest(ranks=ranks):
                h, p = tied_page(ranks, outcomes)
                result = run(h, p)
                self.assertIn('tied_finish_order_payout_disagree', result['issues'])
                self.assertEqual(result['raw_blocks']['PJ0326'], p)

    def test_extra_or_wrong_outcomes_do_not_pass_only_because_a_tie_exists(self):
        cases = [
            ([1, 1, 3, 4], [(1, 2, 3), (2, 1, 3), (1, 2, 4)]),
            ([1, 1, 3, 4], [(1, 2, 4), (2, 1, 4)]),
            ([1, 2, 3, 4, 4], [(2, 1, 3)]),
            ([1, 2, 2, 4], [(1, 2, 4), (1, 3, 4)]),
        ]
        for ranks, outcomes in cases:
            with self.subTest(ranks=ranks, outcomes=outcomes):
                self.assertIn('tied_finish_order_payout_disagree', run(*tied_page(ranks, outcomes))['issues'])

    def test_nonstandard_tied_ranks_are_retained_for_review(self):
        for ranks in ([1, 1, 2, 3], [1, 1, 4, 5], [2, 2, 4, 5]):
            with self.subTest(ranks=ranks):
                h, p = tied_page(ranks, [(1, 2, 3), (2, 1, 3)])
                result = run(h, p)
                self.assertIn('nonstandard_tied_finish_ranks', result['issues'])
                self.assertEqual(result['raw_blocks']['PJ0326'], p)

    def test_permuting_rows_or_payout_display_order_does_not_change_validation(self):
        h, p = tied_page([1, 1, 3, 4], [(1, 2, 3), (2, 1, 3)])
        p['tyakujyunItemSubData'].reverse()
        for key in ('ST2HaraiGakuDispItemSubData', 'RT3HaraiGakuDispItemSubData'):
            p['haraiGakuSubData'][key].reverse()
        self.assertEqual(run(h, p)['issues'], [])

    def test_withdrawals_and_retirements_do_not_create_ranked_combinations(self):
        h, p = tied_page([1, 1, 3, 4, 5], [(1, 2, 3), (2, 1, 3)])
        for row, state in zip(p['tyakujyunItemSubData'][-2:], ['欠場', '落車棄権']):
            row.update(tyaku='', kojinStateItemSubData=[{'kojinState': state}])
        result = run(h, p)
        self.assertEqual(result['issues'], [])
        self.assertEqual(result['summary']['confirmed_starter_count'], 4)
        self.assertEqual(result['summary']['withdrawn_cars'], [4])

    def test_nine_way_synthetic_tie_is_bounded_to_ordered_prefixes(self):
        outcomes = list(itertools.permutations(range(1, 10), 3))
        result = run(*tied_page([1]*9, outcomes))
        self.assertEqual(result['issues'], [])
        self.assertEqual(len(result['summary']['trifecta']), 504)
        self.assertEqual(len(result['summary']['exacta']), 72)


if __name__ == '__main__':
    unittest.main()
