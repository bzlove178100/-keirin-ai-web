"""Dependency-light validation and chronological partition logic for prospective evaluation.

This module intentionally contains no LightGBM imports. It mirrors the record preparation
and split rules used by ``ml.evaluate_offline`` so collection readiness can be checked before
model-training dependencies are installed.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from itertools import permutations
import json
import math
from typing import Any

try:
    from .dataset import rider_rows, supervised_eligibility
    from .position_features import FEATURE_COLUMNS, row_to_features
except ImportError:
    from dataset import rider_rows, supervised_eligibility
    from position_features import FEATURE_COLUMNS, row_to_features

BASELINE = "phase32-hit-priority-all210-v1"


def timestamp(value: Any) -> float:
    if not isinstance(value, str):
        raise ValueError("timestamp_missing")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp_timezone_missing")
    return dt.timestamp()


def probability_table(rows: Any, cars: list[int]) -> dict[str, float]:
    expected = {"-".join(map(str, p)) for p in permutations(cars, 3)}
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError("baseline_incomplete")
    values: dict[str, float] = {}
    for row in rows:
        key = row["combo_key"]
        raw = row["estimated_probability"]
        if key in values or key not in expected or isinstance(raw, bool):
            raise ValueError("baseline_invalid")
        probability = float(raw)
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError("baseline_invalid_probability")
        values[key] = probability
    if abs(sum(values.values()) - 1) > 1e-6:
        raise ValueError("baseline_invalid_mass")
    return values


def prepare(records: list[dict], *, synthetic: bool = False) -> tuple[list[dict], dict]:
    excluded: Counter[str] = Counter()
    candidates: dict[str, list[dict]] = {}
    for record in records:
        try:
            eligible, reason = supervised_eligibility(record)
            if not eligible:
                raise ValueError(reason)
            source = record["training_input"].get("prediction_context", {}).get("source", "")
            if "synthetic" in str(source).lower() and not synthetic:
                raise ValueError("synthetic_excluded")
            race_id = str(record.get("race_id") or "").strip()
            if not race_id:
                raise ValueError("race_id_missing")
            prediction_time = timestamp(record.get("prediction_timestamp"))
            result_time = timestamp(record["metadata"].get("result_timestamp"))
            captured = timestamp(record["training_input"].get("captured_at"))
            if captured != prediction_time or not prediction_time < result_time:
                raise ValueError("invalid_temporal_order")
            rows = rider_rows(record)
            raw_cars = [player["car_number"] for player in record["training_input"]["players"]]
            if any(isinstance(car, bool) or str(car) not in {str(i) for i in range(1, 10)} for car in raw_cars):
                raise ValueError("invalid_car_number")
            cars = [row["car_number"] for row in rows]
            if len(rows) != len(raw_cars) or len(set(cars)) != len(cars) or len(cars) != 7:
                raise ValueError("seven_unique_riders_required")
            if any(row["style"] not in {"逃", "両", "追"} for row in rows):
                raise ValueError("invalid_style")
            if record["metadata"].get("engine_version") != BASELINE:
                raise ValueError("baseline_version_mismatch")
            baseline = probability_table(record.get("trifecta_scores"), cars)
            if record["outcome_combo"] not in baseline:
                raise ValueError("outcome_not_in_riders")
            candidates.setdefault(race_id, []).append(
                {
                    "record": record,
                    "rows": rows,
                    "prediction_time": prediction_time,
                    "result_time": result_time,
                    "baseline": baseline,
                    "race_id": race_id,
                }
            )
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
            reason = str(exc) if isinstance(exc, ValueError) else "malformed_record"
            excluded[reason] += 1

    selected: list[dict] = []
    duplicates = 0
    for group in candidates.values():
        outcomes = {item["record"]["outcome_combo"] for item in group}
        if len(outcomes) != 1:
            excluded["conflicting_outcomes"] += len(group)
            continue
        latest = max(item["prediction_time"] for item in group)
        tied = [item for item in group if item["prediction_time"] == latest]
        if len({json.dumps(item["record"], sort_keys=True) for item in tied}) != 1:
            excluded["conflicting_latest_snapshots"] += len(group)
            continue
        selected.append(tied[0])
        duplicates += len(group) - 1

    selected.sort(key=lambda item: (item["prediction_time"], item["race_id"]))
    matrix = [row_to_features(row) for item in selected for row in item["rows"]]
    missing = {
        name: sum(not math.isfinite(row[index]) for row in matrix)
        for index, name in enumerate(FEATURE_COLUMNS)
    }
    return selected, {
        "input_records": len(records),
        "eligible_unique_races": len(selected),
        "excluded": dict(excluded),
        "duplicate_snapshots_removed": duplicates,
        "rider_rows": len(matrix),
        "missing_feature_counts": missing,
        "missing_feature_fraction": {
            key: value / len(matrix) if matrix else None for key, value in missing.items()
        },
    }


def split_records(records: list[dict]) -> tuple[list[dict], list[dict], list[dict], dict]:
    times = sorted({item["prediction_time"] for item in records})
    if len(times) < 5:
        raise ValueError("need_at_least_five_distinct_prediction_times")
    valid_start = times[max(2, int(len(times) * 0.6))]
    test_start = times[max(3, int(len(times) * 0.8))]
    train = [
        item for item in records
        if item["prediction_time"] < valid_start and item["result_time"] < valid_start
    ]
    valid = [
        item for item in records
        if valid_start <= item["prediction_time"] < test_start and item["result_time"] < test_start
    ]
    test = [item for item in records if item["prediction_time"] >= test_start]
    if len(train) < 2 or not valid or not test:
        raise ValueError("insufficient_non_overlapping_partitions")
    return train, valid, test, {
        "train_race_ids": [item["race_id"] for item in train],
        "validation_race_ids": [item["race_id"] for item in valid],
        "test_race_ids": [item["race_id"] for item in test],
        "purged_unsettled_at_boundary": len(records) - len(train) - len(valid) - len(test),
        "validation_start": datetime.fromtimestamp(valid_start, timezone.utc).isoformat(),
        "test_start": datetime.fromtimestamp(test_start, timezone.utc).isoformat(),
    }


def readiness(records: list[dict], *, synthetic: bool = False) -> dict[str, Any]:
    selected, quality = prepare(records, synthetic=synthetic)
    distinct_times = len({item["prediction_time"] for item in selected})
    result: dict[str, Any] = {
        "data_quality": quality,
        "distinct_prediction_times": distinct_times,
        "minimum_distinct_prediction_times": 5,
        "remaining_distinct_prediction_times": max(0, 5 - distinct_times),
        "technical_time_minimum_met": distinct_times >= 5,
        "chronological_partitions_ready": False,
        "blocked_reason": None,
        "split": None,
        "note": (
            "Passing readiness is only a technical pipeline condition. It is not evidence "
            "of statistical sufficiency, calibration, model superiority or profitability."
        ),
    }
    try:
        train, valid, test, split = split_records(selected)
    except ValueError as exc:
        result["blocked_reason"] = str(exc)
        return result
    result["chronological_partitions_ready"] = True
    result["split"] = {
        **split,
        "train_races": len(train),
        "validation_races": len(valid),
        "test_races": len(test),
    }
    return result
