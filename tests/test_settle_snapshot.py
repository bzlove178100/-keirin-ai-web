from copy import deepcopy
from datetime import datetime, timedelta, timezone
from itertools import permutations
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

from settle_snapshot import build_history_record, build_training_input, validate_snapshot  # noqa: E402


def snapshot(*, source="WINTICKET", odds_count=72, rider_count=7):
    captured = "2026-09-24T01:20:46.432Z"
    players = [
        {
            "car_number": car,
            "style": "逃" if car in {1, 7} else "追",
            "race_score": 80.0 + car,
            "S": car,
            "H": car if car in {1, 7} else 0,
            "B": car if car in {1, 7} else 0,
            "line_id": f"L{car}",
            "line_position": 1,
            "line_length": 1,
        }
        for car in range(1, rider_count + 1)
    ]
    combos = ["-".join(map(str, p)) for p in permutations(range(1, rider_count + 1), 3)]
    scores = [
        {"combo_key": combo, "estimated_probability": 1 / len(combos), "odds": None}
        for combo in combos
    ]
    known = {combo: float(i + 10) for i, combo in enumerate(combos[:odds_count])}
    categories = {
        key: {"picks": [{"combo_key": combos[index]}]}
        for index, key in enumerate(("hit_priority", "balance", "middle", "longshot", "super_longshot"))
    }
    return {
        "schema_version": "prediction-snapshot-v1",
        "captured_at": captured,
        "validation_mode": "prospective-only",
        "snapshot_eligibility": {
            "prospective": True,
            "reason": "before_scheduled_start",
            "scheduled_start": "2026-09-24T06:53:00.000Z",
            "prestart_confirmed": True,
            "clock_source": "client_unverified",
        },
        "race_data": {
            "race": {
                "date": "2026-09-24",
                "venue": "伊東温泉",
                "race_number": 1,
                "class": "A級一般",
                "scheduled_start_jst": "2026-09-24T15:53:00+09:00",
            },
            "players": players,
            "odds": {"trifecta": known},
            "prediction_context": {"source": source, "known_odds_count": odds_count},
        },
        "engine_response": {
            "success": True,
            "service": "predict-engine-dev",
            "service_version": "test-v1",
            "architecture": {"engine": "phase32-hit-priority-all210-v1"},
            "engine_candidate": "phase32-hit-priority-all210-v1",
            "saved": False,
            "db_write_enabled": False,
            "production_prediction_enabled": False,
            "input_quality": {"trifecta_odds_count": odds_count, "trifecta_odds_coverage": odds_count / len(combos)},
            "odds_sanitization": {
                "policy": "kdreams_9999_9_unbet_as_unavailable",
                "source_matched": False,
                "ignored_combos": [],
            },
            "probability_calibration_status": "uncalibrated",
            "monetary_ev_enabled": False,
            "odds_band_ranking": "estimated_probability_only",
            "prediction": {
                "trifecta_scores": scores,
                "selected_predictions": {"categories": categories},
            },
        },
    }


class SettleSnapshotTest(unittest.TestCase):
    def test_seven_and_nine_rider_settlement_round_trip(self):
        from evaluation_protocol import prepare
        for count, total, outcome in ((7, 210, "7-6-5"), (9, 504, "9-8-7")):
            with self.subTest(count=count):
                snap = snapshot(source="synthetic", rider_count=count)
                original = deepcopy(snap)
                record = build_history_record(snap, outcome_combo=outcome,
                    settlement_odds=42.0, result_timestamp="2026-09-24T17:24:17+09:00")
                selected, quality = prepare([record], synthetic=True)
                self.assertEqual(len(selected), 1, quality)
                self.assertEqual(len(selected[0]["baseline"]), total)
                self.assertEqual(quality["rider_rows"], count)
                self.assertEqual(snap, original)
                self.assertEqual(prepare([record])[1]["excluded"], {"synthetic_excluded": 1})

    def test_invalid_rider_counts_and_car_numbers(self):
        for count in (6, 8, 10):
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, "seven_or_nine_riders_required"):
                validate_snapshot(snapshot(rider_count=count))
        for count in (7, 9):
            for value in (True, 1.0, "1", 0, count + 1, 2, [], {}):
                snap = snapshot(rider_count=count)
                snap["race_data"]["players"][0]["car_number"] = value
                with self.subTest(count=count, value=value), self.assertRaisesRegex(ValueError, "invalid_car_numbers"):
                    validate_snapshot(snap)

    def test_nine_rider_safety_flags_and_result_time_remain_enforced(self):
        for flag in ("saved", "db_write_enabled", "production_prediction_enabled"):
            snap = snapshot(rider_count=9)
            snap["engine_response"][flag] = True
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                validate_snapshot(snap)
        with self.assertRaisesRegex(ValueError, "result_confirmation_before_scheduled_start"):
            build_history_record(snapshot(rider_count=9), outcome_combo="9-8-7",
                settlement_odds=42, result_timestamp="2026-09-24T02:00:00Z")

    def test_nine_rider_probability_table_and_selected_pick_guards(self):
        for mutation in ("missing", "duplicate", "foreign", "mass", "pick"):
            snap = snapshot(rider_count=9)
            prediction = snap["engine_response"]["prediction"]
            scores = prediction["trifecta_scores"]
            if mutation == "missing": scores.pop()
            elif mutation == "duplicate": scores[-1] = deepcopy(scores[0])
            elif mutation == "foreign": scores[-1]["combo_key"] = "10-8-9"
            elif mutation == "mass": scores[-1]["estimated_probability"] = 0
            else: prediction["selected_predictions"]["categories"]["balance"]["picks"][0]["combo_key"] = "10-8-9"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_snapshot(snap)

    def test_builds_supervised_history_without_inventing_missing_odds(self):
        snap = snapshot(odds_count=72)
        record = build_history_record(
            snap,
            outcome_combo="3-4-7",
            settlement_odds=39.3,
            result_timestamp="2026-09-24T17:24:17+09:00",
        )
        self.assertEqual(record["outcome_combo"], "3-4-7")
        self.assertEqual(record["settlement_odds"], 39.3)
        self.assertEqual(len(record["trifecta_scores"]), 210)
        self.assertEqual(len(record["training_input"]["odds"]["trifecta"]), 72)
        self.assertTrue(record["metadata"]["training_eligibility"]["supervised_training"])
        self.assertEqual(record["metadata"]["temporal_order"], "prediction_before_result")
        self.assertEqual(record["metadata"]["engine_version"], "phase32-hit-priority-all210-v1")
        self.assertEqual(record["training_input"]["captured_at"], record["prediction_timestamp"])

    def test_kdreams_no_ticket_marker_is_removed_from_training_input(self):
        snap = snapshot(source="K-Dreams", odds_count=2)
        raw = snap["race_data"]["odds"]["trifecta"]
        first = next(iter(raw))
        raw[first] = 9999.9
        snap["engine_response"]["odds_sanitization"]["source_matched"] = True
        snap["engine_response"]["odds_sanitization"]["ignored_combos"] = [first]
        training = build_training_input(snap)
        self.assertNotIn(first, training["odds"]["trifecta"])
        self.assertIn(first, training["odds_sanitization"]["removed_combos"])
        self.assertNotIn(9999.9, training["odds"]["trifecta"].values())

    def test_rejects_naive_or_pre_prediction_result_time(self):
        snap = snapshot()
        with self.assertRaisesRegex(ValueError, "result_timestamp_timezone_missing"):
            build_history_record(
                snap,
                outcome_combo="3-4-7",
                settlement_odds=39.3,
                result_timestamp="2026-09-24T17:24:17",
            )
        with self.assertRaisesRegex(ValueError, "prediction_must_precede_result_confirmation"):
            build_history_record(
                snap,
                outcome_combo="3-4-7",
                settlement_odds=39.3,
                result_timestamp="2026-09-24T01:20:00Z",
            )

    def test_rejects_result_confirmation_before_scheduled_start(self):
        snap = snapshot()
        with self.assertRaisesRegex(ValueError, "result_confirmation_before_scheduled_start"):
            build_history_record(
                snap,
                outcome_combo="3-4-7",
                settlement_odds=39.3,
                result_timestamp="2026-09-24T02:00:00Z",
            )

    def test_rejects_snapshot_capture_at_or_after_scheduled_start(self):
        snap = snapshot()
        snap["snapshot_eligibility"]["scheduled_start"] = "2026-09-24T01:20:00Z"
        snap["race_data"]["race"]["scheduled_start_jst"] = "2026-09-24T10:20:00+09:00"
        with self.assertRaisesRegex(ValueError, "snapshot_capture_not_before_scheduled_start"):
            validate_snapshot(snap)

    def test_rejects_mismatched_schedule_fields(self):
        snap = snapshot()
        snap["race_data"]["race"]["scheduled_start_jst"] = "2026-09-24T15:54:00+09:00"
        with self.assertRaisesRegex(ValueError, "scheduled_start_mismatch"):
            validate_snapshot(snap)

    def test_rejects_incomplete_probability_table_and_bad_outcome(self):
        snap = snapshot()
        snap["engine_response"]["prediction"]["trifecta_scores"].pop()
        with self.assertRaisesRegex(ValueError, "full_probability_table_invalid"):
            validate_snapshot(snap)
        snap = snapshot()
        with self.assertRaisesRegex(ValueError, "outcome_not_in_riders"):
            build_history_record(
                snap,
                outcome_combo="3-4-8",
                settlement_odds=39.3,
                result_timestamp="2026-09-24T17:24:17+09:00",
            )


if __name__ == "__main__":
    unittest.main()
