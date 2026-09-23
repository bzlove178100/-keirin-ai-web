from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

from model_contract import (  # noqa: E402
    FEATURES,
    TARGETS,
    encode_style,
    feature_row,
    split_race_ids,
    time_group_split,
    validate_feature_contract,
)


def make_rows(races: int = 10) -> list[dict]:
    rows: list[dict] = []
    for race in range(races):
        for car in range(1, 8):
            rows.append(
                {
                    "race_id": f"race-{race:02d}",
                    "prediction_timestamp": f"2026-09-{race + 1:02d}T12:00:00+09:00",
                    "car_number": car,
                    "style": ["逃", "両", "追"][car % 3],
                    "race_score": 90 + car,
                    "S": car % 4,
                    "H": car % 6,
                    "B": car % 8,
                    "line_position": 1 if car in (1, 4, 6) else 2,
                    "line_length": 2,
                    "is_line_leader": 1 if car in (1, 4, 6) else 0,
                    "target_first": 1 if car == 1 else 0,
                    "target_second": 1 if car == 2 else 0,
                    "target_third": 1 if car == 3 else 0,
                }
            )
    return rows


def test_feature_contract_contains_no_post_race_targets_or_race_local_line_id():
    assert validate_feature_contract() == []
    assert "line_id" not in FEATURES
    assert "known_trifecta_odds_count" not in FEATURES
    for target in TARGETS.values():
        assert target not in FEATURES
    forbidden = ("target_", "outcome", "settlement", "result_timestamp", "result_time")
    assert all(not any(token in name.lower() for token in forbidden) for name in FEATURES)


def test_style_encoding_is_explicit_and_unknown_values_are_missing():
    assert encode_style("逃") == 0
    assert encode_style("両") == 1
    assert encode_style("追") == 2
    assert encode_style("unknown") is None
    assert encode_style(None) is None


def test_feature_row_does_not_copy_targets_or_metadata_into_model_matrix():
    row = make_rows(1)[0]
    row["outcome_combo"] = "1-2-3"
    row["settlement_odds"] = 12.3
    encoded = feature_row(row)
    assert set(encoded) == set(FEATURES)
    assert "outcome_combo" not in encoded
    assert "settlement_odds" not in encoded
    assert all(not key.startswith("target_") for key in encoded)


def test_time_group_split_never_splits_one_race_across_partitions():
    splits = time_group_split(make_rows(10), train_fraction=0.7, valid_fraction=0.15)
    ids = split_race_ids(splits)
    assert ids["train"]
    assert ids["valid"]
    assert ids["test"]
    assert ids["train"].isdisjoint(ids["valid"])
    assert ids["train"].isdisjoint(ids["test"])
    assert ids["valid"].isdisjoint(ids["test"])
    assert ids["train"] | ids["valid"] | ids["test"] == {f"race-{i:02d}" for i in range(10)}
    assert max(ids["train"]) < min(ids["valid"])
    assert max(ids["valid"]) < min(ids["test"])


def test_three_races_is_only_structural_minimum_not_a_promotion_claim():
    splits = time_group_split(make_rows(3), train_fraction=0.6, valid_fraction=0.2)
    assert all(splits.values())


if __name__ == "__main__":
    test_feature_contract_contains_no_post_race_targets_or_race_local_line_id()
    test_style_encoding_is_explicit_and_unknown_values_are_missing()
    test_feature_row_does_not_copy_targets_or_metadata_into_model_matrix()
    test_time_group_split_never_splits_one_race_across_partitions()
    test_three_races_is_only_structural_minimum_not_a_promotion_claim()
    print("model contract checks: PASS")
