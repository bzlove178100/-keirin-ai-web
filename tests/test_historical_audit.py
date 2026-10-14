import copy
import unittest

from ml.historical_audit import audit


def example(count=7):
    # Synthetic fixture only. Real observations never enter the public repository.
    return {"race_id": "synthetic-race", "rider_count": count,
            "sources": ["synthetic"], "training_use_status": "unconfirmed",
            "pre_race_state_verified": False,
            "riders": [{"car_number": n} for n in range(1, count + 1)],
            "trifecta_outcomes": [[1, 2, 3]], "dead_heat": False}


class HistoricalAuditTests(unittest.TestCase):
    def test_seven_and_nine_are_preserved_but_not_promoted(self):
        for count in [7, 9]:
            result = audit([example(count)])
            self.assertEqual(result["rider_count_distribution"], {str(count): 1})
            self.assertEqual(result["training_eligible_races"], 0)
            self.assertFalse(result["records"][0]["prospective"])

    def test_cross_source_duplicate_is_one_race(self):
        a = example()
        b = copy.deepcopy(a)
        b["sources"] = ["another-synthetic-source"]
        result = audit([a, b])
        self.assertEqual(result["unique_races"], 1)
        self.assertEqual(result["identical_duplicates"], 1)
        self.assertEqual(result["source_variant_races"], 1)
        self.assertIn("source_variants_require_review", result["records"][0]["reasons"])

    def test_source_variants_are_counted_once_even_alongside_label_conflicts(self):
        a = example()
        b, c = copy.deepcopy(a), copy.deepcopy(a)
        b["sources"] = ["second-synthetic-source"]
        c.update(sources=["third-synthetic-source"], trifecta_outcomes=[[3, 2, 1]])
        result = audit([a, b, c, a])
        self.assertEqual(result["unique_races"], 1)
        self.assertEqual(result["source_variant_races"], 1)
        self.assertEqual(result["conflicting_races"], 1)
        self.assertIn("source_variants_require_review", result["records"][0]["reasons"])
        self.assertIn("conflicting_duplicate_requires_review", result["records"][0]["reasons"])

    def test_conflicting_labels_quarantine_whole_race(self):
        a = example()
        b = copy.deepcopy(a)
        b["trifecta_outcomes"] = [[3, 2, 1]]
        result = audit([a, b])
        self.assertEqual(result["conflicting_races"], 1)
        self.assertIn("conflicting_duplicate_requires_review", result["records"][0]["reasons"])

    def test_scalar_types_in_duplicate_content_cannot_be_collapsed(self):
        changes = (lambda r: r.update(rider_count=7.0),
                   lambda r: r.update(dead_heat=0),
                   lambda r: r["riders"][0].update(car_number=True),
                   lambda r: r.update(trifecta_outcomes=[[1.0, 2, 3]]))
        for change in changes:
            a = example()
            b = copy.deepcopy(a)
            change(b)
            for rows in ([a, b], [b, a]):
                before = copy.deepcopy(rows)
                result = audit(rows)
                self.assertEqual(result["conflicting_races"], 1)
                self.assertEqual(result["identical_duplicates"], 0)
                self.assertEqual(result["source_variant_races"], 0)
                self.assertIn("conflicting_duplicate_requires_review", result["records"][0]["reasons"])
                self.assertEqual(result["training_eligible_races"], 0)
                self.assertEqual(rows, before)

    def test_reordered_content_object_keys_remain_identical(self):
        a = example()
        a["metadata"] = {"version": 1, "nested": {"a": 1, "b": False}}
        b = dict(reversed(list(copy.deepcopy(a).items())))
        b["metadata"] = {"nested": {"b": False, "a": 1}, "version": 1}
        result = audit([a, b])
        self.assertEqual(result["conflicting_races"], 0)
        self.assertEqual(result["identical_duplicates"], 1)

    def test_non_json_duplicate_content_is_not_certified_identical(self):
        for value in (float("nan"), float("inf"), float("-inf"), object()):
            a = example()
            a["metadata"] = {"value": value}
            result = audit([a, a])
            self.assertEqual(result["conflicting_races"], 1)
            self.assertEqual(result["identical_duplicates"], 0)

    def test_dead_heat_not_forced_to_one_winner(self):
        a = example()
        a.update(dead_heat=True, trifecta_outcomes=[[1, 2, 3], [2, 1, 3]])
        self.assertIn("dead_heat_requires_multilabel_contract", audit([a])["records"][0]["reasons"])

    def test_complete_metadata_does_not_bypass_dedicated_review(self):
        a = example()
        a.update(training_use_status="confirmed", pre_race_state_verified=True)
        result = audit([a])
        self.assertEqual(result["training_eligible_races"], 0)
        self.assertIn("dedicated_historical_review_required", result["records"][0]["reasons"])

    def test_missing_roster_and_unverified_time_remain_explicit(self):
        a = example()
        a["riders"] = []
        reasons = audit([a])["records"][0]["reasons"]
        self.assertIn("roster_incomplete_or_invalid", reasons)
        self.assertIn("historical_feature_time_unverified", reasons)

    def test_invalid_rows_do_not_silently_count_as_races(self):
        result = audit([None, {}, example()])
        self.assertEqual(result["unique_races"], 1)
        self.assertEqual(len(result["invalid_records"]), 2)

    def test_outcome_outside_roster(self):
        a = example()
        a["trifecta_outcomes"] = [[1, 2, 9]]
        self.assertIn("outcome_not_in_roster", audit([a])["records"][0]["reasons"])


if __name__ == "__main__":
    unittest.main()
