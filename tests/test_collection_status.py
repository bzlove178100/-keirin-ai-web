from copy import deepcopy
from datetime import datetime, timedelta, timezone
from itertools import permutations
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

from collection_status import MIN_DISTINCT_PREDICTION_TIMES, collection_status  # noqa: E402


def record(i: int, *, race_id: str | None = None, odds_count: int = 72):
    predicted = datetime(2026, 9, 24, 1, 0, tzinfo=timezone.utc) + timedelta(hours=i)
    settled = predicted + timedelta(minutes=10)
    players = [
        {
            "car_number": car,
            "style": "逃" if car in {1, 7} else "追",
            "race_score": 80 + car,
            "S": car,
            "H": car if car in {1, 7} else 0,
            "B": car if car in {1, 7} else 0,
            "line_id": f"L{car}",
            "line_position": 1,
            "line_length": 1,
        }
        for car in range(1, 8)
    ]
    combos = ["-".join(map(str, p)) for p in permutations(range(1, 8), 3)]
    return {
        "race_id": race_id or f"RACE-{i}",
        "prediction_timestamp": predicted.isoformat(),
        "outcome_combo": "1-2-3",
        "settlement_odds": 12.3,
        "trifecta_scores": [
            {"combo_key": combo, "estimated_probability": 1 / 210}
            for combo in combos
        ],
        "metadata": {
            "evaluation_scope": "prospective",
            "temporal_order": "prediction_before_result",
            "result_timestamp": settled.isoformat(),
            "engine_version": "phase32-hit-priority-all210-v1",
            "training_eligibility": {"supervised_training": True},
        },
        "training_input": {
            "schema_version": "keirin-training-input-v1",
            "evaluation_scope": "prospective",
            "captured_at": predicted.isoformat(),
            "race": {"date": "2026-09-24", "venue": "TEST", "race_number": i + 1},
            "players": players,
            "prediction_context": {"source": "WINTICKET"},
            "odds": {"trifecta": {combo: float(n + 10) for n, combo in enumerate(combos[:odds_count])}},
        },
    }


class CollectionStatusTest(unittest.TestCase):
    def test_below_minimum_reports_remaining_without_rejecting_partial_odds(self):
        report = collection_status([record(i) for i in range(4)])
        self.assertEqual(report["eligible_unique_races"], 4)
        self.assertEqual(report["distinct_prediction_times"], 4)
        self.assertEqual(report["remaining_distinct_prediction_times"], 1)
        self.assertFalse(report["collection_threshold_met"])
        self.assertFalse(report["chronological_evaluation_may_run"])
        self.assertEqual(report["blocked_reason"], "need_at_least_five_distinct_prediction_times")
        self.assertEqual(report["known_trifecta_odds_count"]["min"], 72)

    def test_five_distinct_times_form_chronological_partitions(self):
        report = collection_status([record(i) for i in range(MIN_DISTINCT_PREDICTION_TIMES)])
        self.assertTrue(report["collection_threshold_met"])
        self.assertTrue(report["chronological_evaluation_may_run"])
        self.assertEqual(report["remaining_distinct_prediction_times"], 0)
        self.assertIsNone(report["blocked_reason"])
        self.assertEqual(report["split"]["train_races"], 3)
        self.assertEqual(report["split"]["validation_races"], 1)
        self.assertEqual(report["split"]["test_races"], 1)
        self.assertIn("not evidence", report["note"])

    def test_boundary_purge_can_block_even_after_five_time_minimum(self):
        records = [record(i) for i in range(5)]
        # Make two early labels unavailable until after their partition boundaries.
        records[0]["metadata"]["result_timestamp"] = records[4]["metadata"]["result_timestamp"]
        records[3]["metadata"]["result_timestamp"] = records[4]["metadata"]["result_timestamp"]
        report = collection_status(records)
        self.assertTrue(report["collection_threshold_met"])
        self.assertFalse(report["chronological_evaluation_may_run"])
        self.assertEqual(report["blocked_reason"], "insufficient_non_overlapping_partitions")

    def test_latest_eligible_snapshot_per_race_is_used(self):
        older = record(0, race_id="SAME")
        newer = record(1, race_id="SAME")
        report = collection_status([older, newer, record(2)])
        self.assertEqual(report["eligible_unique_races"], 2)
        self.assertEqual(report["distinct_prediction_times"], 2)
        self.assertEqual(report["eligible_race_ids"], ["SAME", "RACE-2"])
        self.assertEqual(report["duplicate_snapshots_removed"], 1)

    def test_evaluator_contract_failures_are_excluded(self):
        bad_time = record(0)
        bad_time["prediction_timestamp"] = "2026-09-24T10:00:00"
        bad_engine = record(1)
        bad_engine["metadata"]["engine_version"] = "other-engine"
        bad_table = record(2)
        bad_table["trifecta_scores"].pop()
        report = collection_status([bad_time, bad_engine, bad_table])
        self.assertEqual(report["eligible_unique_races"], 0)
        self.assertEqual(report["excluded"].get("timestamp_timezone_missing"), 1)
        self.assertEqual(report["excluded"].get("baseline_version_mismatch"), 1)
        self.assertEqual(report["excluded"].get("baseline_incomplete"), 1)


if __name__ == "__main__":
    unittest.main()
