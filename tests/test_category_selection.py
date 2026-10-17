from copy import deepcopy
from itertools import permutations
import json
import os
from pathlib import Path
import random
import subprocess
import unittest

from ml.category_selection import CATEGORY_RULES, select_model_categories


def fixture(count=7, odds=None):
    combos = list(permutations(range(1, count + 1), 3))
    return [{'combo': list(combo), 'combo_key': '-'.join(map(str, combo)),
             'estimated_probability': 1 / len(combos), 'odds': (odds or {}).get(i),
             'monetary_expected_value': None} for i, combo in enumerate(combos)]


class CategorySelectionTests(unittest.TestCase):
    def test_no_odds_keeps_only_hit_priority(self):
        for count in (7, 9):
            rows = fixture(count)
            before = deepcopy(rows)
            result = select_model_categories(rows, count)
            self.assertEqual(rows, before)
            self.assertEqual(list(result['categories']), list(CATEGORY_RULES))
            self.assertEqual(result['total_picks'], 3)
            self.assertEqual(result['complete_category_count'], 1)
            for key in list(CATEGORY_RULES)[1:]:
                self.assertEqual(result['categories'][key]['status'], 'skipped')
                self.assertEqual(result['categories'][key]['picks'], [])
                self.assertIn('オッズ未取得', result['categories'][key]['category_note'])

    def test_boundaries_partial_and_global_deduplication(self):
        for count in (7, 9):
            odds = dict(enumerate([500, 20, 60, 19.999, 20, 59.999, 60, 99.999, 100, 499.999, 500, 1000]))
            result = select_model_categories(fixture(count, odds), count)
            categories = result['categories']
            self.assertEqual([p['odds'] for p in categories['hit_priority']['picks']], [500, 20, 60])
            for key, expected in [('balance', [20, 59.999]), ('middle', [60, 99.999]),
                                  ('longshot', [100, 499.999]), ('super_longshot', [500, 1000])]:
                self.assertEqual([p['odds'] for p in categories[key]['picks']], expected)
                self.assertEqual(categories[key]['status'], 'partial')
            picks = [p for c in categories.values() for p in c['picks']]
            self.assertEqual(len({p['combo_key'] for p in picks}), len(picks))
            self.assertEqual(result['total_picks'], 11)
            self.assertTrue(all(p['fallback'] is False and p['monetary_expected_value'] is None for p in picks))

    def test_original_typescript_policy_parity(self):
        # Load the actual private selector without editing/deploying Edge code.
        root = Path(__file__).resolve().parents[1]
        script = """
const fs = require('node:fs');
const {stripTypeScriptTypes} = require('node:module');
(async () => {
  const source = fs.readFileSync('supabase/functions/predict-engine-dev/engine_phase32.ts', 'utf8');
  const code = stripTypeScriptTypes(source + '\\nexport {select};');
  const original = await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'));
  const cases = JSON.parse(fs.readFileSync(0, 'utf8'));
  process.stdout.write(JSON.stringify({rules:original.CATEGORY_RULES, results:cases.map(rows=>original.select(rows))}));
})().catch(error => {console.error(error); process.exitCode=1;});
"""
        cases = []
        counts = []
        for count in (7, 9):
            for mode in ('none', 'bands', 'boundary', 'ranked', 'shuffled', 'zero'):
                rows = fixture(count)
                if mode != 'none':
                    for i, row in enumerate(rows):
                        row['odds'] = ([None, 20, 60, 100, 500][i % 5] if mode != 'boundary' else
                                       [19.999, 20, 59.999, 60, 99.999, 100, 499.999, 500][i % 8])
                if mode in ('ranked', 'zero'):
                    weights = [i % 13 if mode == 'zero' else 1 + i % 13 for i in range(len(rows))]
                    for row, weight in zip(rows, weights):
                        row['estimated_probability'] = weight / sum(weights)
                if mode == 'shuffled':
                    random.Random(42).shuffle(rows)
                cases.append(rows); counts.append(count)
        run = subprocess.run([os.environ.get('KEIRIN_NODE', 'node'), '-e', script], cwd=root,
                             input=json.dumps(cases), text=True, capture_output=True, check=True)
        reference = json.loads(run.stdout)
        self.assertEqual(reference['rules'], {key: {'name': name, 'target_min_odds': minimum,
                         'target_max_odds': maximum} for key, (name, minimum, maximum) in CATEGORY_RULES.items()})
        for rows, count, expected in zip(cases, counts, reference['results']):
            self.assertEqual(select_model_categories(rows, count), expected)

    def test_invalid_inputs_and_phase32_explanations_rejected(self):
        mutations = [lambda r:r.pop(), lambda r:r[0].update(combo_key='1-1-2'),
                     lambda r:r[0].update(combo=[True, 2, 3]),
                     lambda r:r[0].update(estimated_probability=float('nan')),
                     lambda r:r[0].update(odds=True), lambda r:r[0].update(odds=-1),
                     lambda r:r[0].update(reason='Phase32 feature explanation'),
                     lambda r:r[0].update(score=12), lambda r:r[0].update(monetary_expected_value=2)]
        for count in (7, 9):
            for mutate in mutations:
                rows = fixture(count); mutate(rows)
                with self.assertRaises(ValueError): select_model_categories(rows, count)


if __name__ == '__main__':
    unittest.main()
