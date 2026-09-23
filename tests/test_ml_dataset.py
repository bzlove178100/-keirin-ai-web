from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

from dataset import build_rows, rider_rows, supervised_eligibility  # noqa: E402


def prospective_record(timestamp: str = "2026-09-16T14:24:00+09:00") -> dict:
    players = [
        {"car_number": 1, "style": "逃", "race_score": 96.7, "S": 6, "H": 6, "B": 6, "line_id": "L1", "line_position": 1, "line_length": 3},
        {"car_number": 2, "style": "逃", "race_score": 87.5, "S": 0, "H": 18, "B": 20, "line_id": "L2", "line_position": 1, "line_length": 2},
        {"car_number": 3, "style": "逃", "race_score": 87.6, "S": 1, "H": 5, "B": 7, "line_id": "L3", "line_position": 1, "line_length": 2},
        {"car_number": 4, "style": "追", "race_score": 86.8, "S": 2, "H": 0, "B": 0, "line_id": "L1", "line_position": 2, "line_length": 3},
        {"car_number": 5, "style": "追", "race_score": 94.1, "S": 8, "H": 0, "B": 0, "line_id": "L3", "line_position": 2, "line_length": 2},
        {"car_number": 6, "style": "追", "race_score": 79.5, "S": 0, "H": 0, "B": 0, "line_id": "L1", "line_position": 3, "line_length": 3},
        {"car_number": 7, "style": "逃", "race_score": 82.0, "S": 1, "H": 0, "B": 1, "line_id": "L2", "line_position": 2, "line_length": 2},
    ]
    return {
        "race_id": "2026-09-16-いわき平-11R",
        "prediction_timestamp": timestamp,
        "outcome_combo": "1-4-5",
        "settlement_odds": 9.0,
        "training_input": {
            "schema_version": "keirin-training-input-v1",
            "captured_at": timestamp,
            "race": {"date": "2026-09-16", "venue": "いわき平", "race_number": 11},
            "players": players,
            "odds": {"trifecta": {"1-4-5": 9.0, "1-5-4": 15.5}},
            "prediction_context": {"source": "K-Dreams"},
            "evaluation_scope": "prospective",
        },
        "metadata": {
            "evaluation_scope": "prospective",
            "temporal_order": "prediction_before_result",
            "training_eligibility": {
                "supervised_training": True,
                "reason": "eligible_prospective_pre_result_snapshot",
            },
        },
    }


def test_only_prospective_pre_result_records_are_training_eligible():
    record = prospective_record()
    assert supervised_eligibility(record) == (True, "eligible")

    replay = copy.deepcopy(record)
    replay["metadata"]["evaluation_scope"] = "replay_or_legacy"
    replay["training_input"]["evaluation_scope"] = "replay_or_legacy"
    replay["metadata"]["training_eligibility"]["supervised_training"] = False
    assert supervised_eligibility(replay)[0] is False

    late = copy.deepcopy(record)
    late["metadata"]["temporal_order"] = "snapshot_at_or_after_result"
    late["metadata"]["training_eligibility"]["supervised_training"] = False
    assert supervised_eligibility(late)[0] is False


def test_rider_rows_create_position_targets_without_using_settlement_as_feature():
    rows = rider_rows(prospective_record())
    assert len(rows) == 7
    assert sum(r["target_first"] for r in rows) == 1
    assert sum(r["target_second"] for r in rows) == 1
    assert sum(r["target_third"] for r in rows) == 1
    assert sum(r["target_top3"] for r in rows) == 3
    assert next(r for r in rows if r["car_number"] == 1)["target_first"] == 1
    assert next(r for r in rows if r["car_number"] == 4)["target_second"] == 1
    assert next(r for r in rows if r["car_number"] == 5)["target_third"] == 1
    assert all("settlement_odds" not in r for r in rows)


def test_latest_eligible_snapshot_is_selected_once_per_race():
    old = prospective_record("2026-09-16T14:00:00+09:00")
    latest = prospective_record("2026-09-16T14:24:00+09:00")
    replay = copy.deepcopy(old)
    replay["race_id"] = "2026-09-15-伊東温泉-9R"
    replay["metadata"]["evaluation_scope"] = "replay_or_legacy"
    replay["metadata"]["training_eligibility"]["supervised_training"] = False
    replay["training_input"]["evaluation_scope"] = "replay_or_legacy"

    rows, summary = build_rows([old, replay, latest])
    assert summary["input_records"] == 3
    assert summary["eligible_unique_races"] == 1
    assert summary["rider_rows"] == 7
    assert summary["excluded"]["not_prospective"] == 1
    assert {r["prediction_timestamp"] for r in rows} == {"2026-09-16T14:24:00+09:00"}


def test_9999_9_marker_is_rejected_if_it_ever_reaches_dataset_builder():
    record = prospective_record()
    record["training_input"]["odds"]["trifecta"]["2-6-3"] = 9999.9
    try:
        rider_rows(record)
    except ValueError as exc:
        assert "9999.9" in str(exc)
    else:
        raise AssertionError("9999.9 marker must be rejected")


if __name__ == "__main__":
    test_only_prospective_pre_result_records_are_training_eligible()
    test_rider_rows_create_position_targets_without_using_settlement_as_feature()
    test_latest_eligible_snapshot_is_selected_once_per_race()
    test_9999_9_marker_is_rejected_if_it_ever_reaches_dataset_builder()
    print("ml dataset checks: PASS")
