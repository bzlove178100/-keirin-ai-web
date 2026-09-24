from datetime import datetime, timedelta, timezone
from itertools import permutations
import json
import unittest

from ml.collection_status import collection_status
from ml.evaluate_offline import evaluate_records
from ml.settle_snapshot import build_history_record


COMBOS = ["-".join(map(str, p)) for p in permutations(range(1, 8), 3)]


def snapshot(i: int):
    captured = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc) + timedelta(hours=i)
    players = [
        {
            "car_number": car,
            "style": "逃" if car in {1, 7} else ("両" if car == 2 else "追"),
            "race_score": 75 + car + (i % 5) * 0.2,
            "S": (car + i) % 8,
            "H": (car + i) % 5 if car in {1, 7} else 0,
            "B": (car + 2 * i) % 6 if car in {1, 7} else 0,
            "line_id": f"L{1 + ((car + i) % 3)}",
            "line_position": 1 if car in {1, 2, 7} else 2,
            "line_length": 2,
        }
        for car in range(1, 8)
    ]
    categories = {
        key: {"picks": [{"combo_key": COMBOS[index]}]}
        for index, key in enumerate(
            ("hit_priority", "balance", "middle", "longshot", "super_longshot")
        )
    }
    known = {combo: float(10 + index) for index, combo in enumerate(COMBOS[:72])}
    return {
        "schema_version": "prediction-snapshot-v1",
        "captured_at": captured.isoformat(),
        "validation_mode": "prospective-only",
        "snapshot_eligibility": {
            "prospective": True,
            "reason": "before_scheduled_start",
            "scheduled_start": (captured + timedelta(minutes=30)).isoformat(),
            "prestart_confirmed": True,
            "clock_source": "client_unverified",
        },
        "race_data": {
            "race": {
                "date": captured.date().isoformat(),
                "venue": "SYNTHETIC-E2E",
                "race_number": i + 1,
            },
            "players": players,
            "odds": {"trifecta": known},
            "prediction_context": {"source": "WINTICKET", "known_odds_count": 72},
        },
        "engine_response": {
            "success": True,
            "service": "predict-engine-dev",
            "service_version": "synthetic-e2e",
            "architecture": {"engine": "phase32-hit-priority-all210-v1"},
            "engine_candidate": "phase32-hit-priority-all210-v1",
            "saved": False,
            "db_write_enabled": False,
            "production_prediction_enabled": False,
            "input_quality": {
                "trifecta_odds_count": 72,
                "possible_trifecta_count": 210,
                "trifecta_odds_coverage": 72 / 210,
            },
            "odds_sanitization": {
                "policy": "kdreams_9999_9_unbet_as_unavailable",
                "source_matched": False,
                "ignored_combos": [],
            },
            "probability_calibration_status": "uncalibrated",
            "monetary_ev_enabled": False,
            "odds_band_ranking": "estimated_probability_only",
            "prediction": {
                "trifecta_scores": [
                    {"combo_key": combo, "estimated_probability": 1 / 210, "odds": known.get(combo)}
                    for combo in COMBOS
                ],
                "selected_predictions": {
                    "probability_calibration_status": "uncalibrated",
                    "monetary_ev_enabled": False,
                    "odds_band_ranking": "estimated_probability_only",
                    "categories": categories,
                },
            },
        },
    }


def history(i: int):
    snap = snapshot(i)
    first = 1 + (i % 7)
    second = 1 + ((i + 1) % 7)
    third = 1 + ((i + 2) % 7)
    outcome = f"{first}-{second}-{third}"
    captured = datetime.fromisoformat(snap["captured_at"])
    return build_history_record(
        snap,
        outcome_combo=outcome,
        settlement_odds=float(20 + i),
        result_timestamp=(captured + timedelta(minutes=10)).isoformat(),
    )


class ProspectivePipelineE2ETest(unittest.TestCase):
    def test_snapshot_settlement_readiness_and_lightgbm_evaluation_connect(self):
        records = [history(i) for i in range(16)]

        # Settlement must preserve only prediction-time known odds and keep targets outside training_input.
        self.assertTrue(all(len(r["training_input"]["odds"]["trifecta"]) == 72 for r in records))
        for record in records:
            training_json = json.dumps(record["training_input"], ensure_ascii=False)
            self.assertNotIn("outcome_combo", training_json)
            self.assertNotIn("settlement_odds", training_json)
            self.assertTrue(record["metadata"]["training_eligibility"]["supervised_training"])

        readiness = collection_status(records)
        self.assertEqual(readiness["eligible_unique_races"], 16)
        self.assertEqual(readiness["distinct_prediction_times"], 16)
        self.assertTrue(readiness["chronological_evaluation_may_run"])
        self.assertIsNone(readiness["blocked_reason"])
        self.assertEqual(readiness["known_trifecta_odds_count"]["min"], 72)
        self.assertEqual(readiness["known_trifecta_odds_count"]["max"], 72)

        evaluation = evaluate_records(records)
        self.assertEqual(evaluation["status"], "completed_offline_holdout")
        self.assertEqual(evaluation["evidence_scope"], "provided_prospective_history_offline_holdout")
        self.assertFalse(evaluation["promotion_eligible"])
        self.assertFalse(evaluation["monetary_ev_enabled"])
        self.assertEqual(evaluation["test_races"], 4)
        self.assertEqual(len(evaluation["per_race"]), 4)


if __name__ == "__main__":
    unittest.main()
