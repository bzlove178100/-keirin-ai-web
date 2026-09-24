from datetime import datetime, timedelta, timezone
import unittest

from ml.collection_status import MIN_DISTINCT_PREDICTION_TIMES, collection_status


def record(i: int, *, race_id: str | None = None, odds_count: int = 72):
    predicted = datetime(2026, 9, 24, 1, 0, tzinfo=timezone.utc) + timedelta(hours=i)
    players = [
        {"car_number": car, "style": "逃" if car in {1, 7} else "追"}
        for car in range(1, 8)
    ]
    return {
        "race_id": race_id or f"RACE-{i}",
        "prediction_timestamp": predicted.isoformat(),
        "outcome_combo": "1-2-3",
        "metadata": {
            "evaluation_scope": "prospective",
            "temporal_order": "prediction_before_result",
            "training_eligibility": {"supervised_training": True},
        },
        "training_input": {
            "schema_version": "keirin-training-input-v1",
            "evaluation_scope": "prospective",
            "captured_at": predicted.isoformat(),
            "players": players,
            "odds": {"trifecta": {f"1-2-{car}": float(car) for car in range(3, 3 + odds_count)}},
        },
    }


class CollectionStatusTest(unittest.TestCase):
    def test_below_minimum_reports_remaining_without_rejecting_partial_odds(self):
        report = collection_status([record(i) for i in range(4)])
        self.assertEqual(report["eligible_unique_races"], 4)
        self.assertEqual(report["distinct_prediction_times"], 4)
        self.assertEqual(report["remaining_distinct_prediction_times"], 1)
        self.assertFalse(report["collection_threshold_met"])
        self.assertEqual(report["known_trifecta_odds_count"]["min"], 72)

    def test_five_distinct_times_meet_only_the_technical_collection_threshold(self):
        report = collection_status([record(i) for i in range(MIN_DISTINCT_PREDICTION_TIMES)])
        self.assertTrue(report["collection_threshold_met"])
        self.assertTrue(report["chronological_evaluation_may_run"])
        self.assertEqual(report["remaining_distinct_prediction_times"], 0)
        self.assertIn("not evidence of statistical sufficiency", report["note"])

    def test_latest_eligible_snapshot_per_race_is_used(self):
        older = record(0, race_id="SAME")
        newer = record(1, race_id="SAME")
        report = collection_status([older, newer, record(2)])
        self.assertEqual(report["eligible_unique_races"], 2)
        self.assertEqual(report["distinct_prediction_times"], 2)
        self.assertEqual(report["eligible_race_ids"], ["RACE-2", "SAME"])

    def test_timezone_naive_prediction_timestamp_is_not_counted(self):
        bad = record(0)
        bad["prediction_timestamp"] = "2026-09-24T10:00:00"
        report = collection_status([bad])
        self.assertEqual(report["eligible_unique_races"], 0)
        self.assertEqual(report["invalid_prediction_times"], 1)


if __name__ == "__main__":
    unittest.main()
