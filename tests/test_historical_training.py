import copy
import tempfile
import unittest
from pathlib import Path

from ml.historical_training import digest, prepare, train


def fixture(day, count=7):
    return {"race_id": "synthetic-" + str(day), "rider_count": count,
            "sources": ["synthetic"], "training_use_status": "confirmed",
            "pre_race_state_verified": True, "prospective": False, "dead_heat": False,
            "feature_as_of": f"2020-01-{day:02}T10:00:00+09:00",
            "listed_scheduled_start_jst": f"2020-01-{day:02}T10:10:00+09:00",
            "result_available_at": f"2020-01-{day:02}T10:20:00+09:00",
            "riders": [{"car_number": n} for n in range(1, count + 1)],
            "pre_race_features": [{"car_number": n, "style": "逃", "race_score": 80 + n}
                                  for n in range(1, count + 1)],
            "trifecta_outcomes": [[1, 2, 3]]}


def review(record):
    return {"race_id": record["race_id"], "record_sha256": digest(record),
            **{k: "synthetic test evidence" for k in
               ("reviewer", "source_use_evidence", "feature_time_evidence", "result_time_evidence")}}


def plan(records, reviews=None):
    return prepare(records, [review(r) for r in records] if reviews is None else reviews,
                   "2020-01-03T00:00:00+09:00", "2020-01-04T00:00:00+09:00")


class HistoricalTrainingTests(unittest.TestCase):
    def test_three_to_nine_riders_and_reviewed_form(self):
        for count in range(3, 10):
            r = fixture(1, count)
            r["pre_race_features"][0].update(recent_win_rate=25, recent_top2_rate=50,
                                              recent_top3_rate=75, recent_avg_finish=3)
            result = plan([r])
            self.assertEqual(len(result["partitions"]["train"][0]["rows"]), count)
            self.assertEqual(result["partitions"]["train"][0]["rows"][0]["recent_win_rate"], 25)

    def test_impossible_form_values_remain_excluded(self):
        for field, value in (("recent_win_rate", 101), ("recent_top2_rate", -1),
                             ("recent_avg_finish", 0), ("recent_avg_finish", True)):
            r = fixture(1)
            r["pre_race_features"][0][field] = value
            self.assertEqual(plan([r])["partition_counts"]["train"], 0)

    def test_seven_and_nine_grouped_and_labels_separate(self):
        result = plan([fixture(4), fixture(2, 9), fixture(3), fixture(1)])
        self.assertEqual(result["partition_counts"], {"train": 2, "validation": 1, "test": 1})
        self.assertEqual(len(result["partitions"]["train"][1]["rows"]), 9)
        row = result["partitions"]["train"][0]["rows"][0]
        self.assertEqual(row["target_first"], 1)
        self.assertIsNone(row["H"])
        self.assertNotIn("prediction_timestamp", row)
        self.assertFalse(result["prospective"])

    def test_flags_alone_cannot_supply_review(self):
        result = plan([fixture(1)], [])
        self.assertEqual(result["partition_counts"]["train"], 0)
        self.assertIn("review_missing_or_record_changed", result["excluded"][0]["reasons"])

    def test_review_is_bound_to_exact_record(self):
        r = fixture(1)
        approval = review(r)
        r["pre_race_features"][0]["race_score"] = 999
        self.assertEqual(plan([r], [approval])["partition_counts"]["train"], 0)

    def test_late_labels_purged_at_both_boundaries(self):
        a, b = fixture(1), fixture(3)
        a["result_available_at"] = "2020-01-03T00:00:00+09:00"
        b["result_available_at"] = "2020-01-04T00:00:00+09:00"
        result = plan([a, b])
        self.assertEqual(len(result["excluded"]), 2)
        self.assertTrue(all("label_unavailable_before_next_partition" in x["reasons"]
                            for x in result["excluded"]))

    def test_timezone_normalized_before_splitting(self):
        r = fixture(3)
        r.update(feature_as_of="2020-01-02T16:00:00Z",
                 listed_scheduled_start_jst="2020-01-02T16:10:00Z",
                 result_available_at="2020-01-02T16:20:00Z")
        self.assertEqual(plan([r])["partition_counts"]["validation"], 1)

    def test_missing_naive_or_post_start_feature_time_rejected(self):
        for value in (None, "2020-01-01T10:00:00", "2020-01-01T10:11:00+09:00"):
            r = fixture(1)
            r["feature_as_of"] = value
            self.assertEqual(plan([r])["partition_counts"]["train"], 0)

    def test_outcome_conflict_excludes_whole_race(self):
        a = fixture(1)
        b = copy.deepcopy(a)
        b["trifecta_outcomes"] = [[3, 2, 1]]
        self.assertEqual(plan([a, b], [review(a)])["partition_counts"]["train"], 0)

    def test_dead_heat_preserved_for_later_contract(self):
        r = fixture(1)
        r.update(dead_heat=True, trifecta_outcomes=[[1, 2, 3], [2, 1, 3]])
        self.assertEqual(plan([r])["partition_counts"]["train"], 0)

    def test_no_result_columns_or_duplicate_feature_riders(self):
        for change in (lambda r: r["pre_race_features"][0].update(finish_rank=1),
                       lambda r: r["pre_race_features"][0].update(car_number=2)):
            r = fixture(1)
            change(r)
            self.assertEqual(plan([r])["partition_counts"]["train"], 0)

    def test_missing_evidence_still_blocks(self):
        r = fixture(1)
        rev = review(r)
        rev["feature_time_evidence"] = ""
        self.assertEqual(plan([r], [rev])["partition_counts"]["train"], 0)

    def test_no_holdout_blocks_before_model_import(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "model"
            with self.assertRaisesRegex(ValueError, "insufficient_chronological_partitions"):
                train(plan([fixture(1)]), output)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
