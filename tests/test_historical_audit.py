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

    def test_conflicting_labels_quarantine_whole_race(self):
        a = example()
        b = copy.deepcopy(a)
        b["trifecta_outcomes"] = [[3, 2, 1]]
        result = audit([a, b])
        self.assertEqual(result["conflicting_races"], 1)
        self.assertIn("conflicting_duplicate_requires_review", result["records"][0]["reasons"])

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
