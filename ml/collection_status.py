"""Summarize prospective history collection progress without training a model."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from statistics import median
from typing import Any

try:
    from .build_training_dataset import load_records
    from .dataset import select_latest_eligible_per_race
except ImportError:
    from build_training_dataset import load_records
    from dataset import select_latest_eligible_per_race

MIN_DISTINCT_PREDICTION_TIMES = 5


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _split_preview(valid: list[tuple[dict[str, Any], datetime, datetime]]) -> dict[str, Any]:
    """Mirror evaluate_offline split boundaries without fitting any model."""
    times = sorted({predicted for _, predicted, _ in valid})
    if len(times) < MIN_DISTINCT_PREDICTION_TIMES:
        return {
            "feasible": False,
            "blocked_reason": "need_at_least_five_distinct_prediction_times",
            "train_races": 0,
            "validation_races": 0,
            "test_races": 0,
            "purged_unsettled_at_boundary": 0,
            "validation_start": None,
            "test_start": None,
        }

    valid_start = times[max(2, int(len(times) * 0.6))]
    test_start = times[max(3, int(len(times) * 0.8))]
    train = [x for x in valid if x[1] < valid_start and x[2] < valid_start]
    validation = [x for x in valid if valid_start <= x[1] < test_start and x[2] < test_start]
    test = [x for x in valid if x[1] >= test_start]
    purged = len(valid) - len(train) - len(validation) - len(test)
    feasible = len(train) >= 2 and bool(validation) and bool(test)
    return {
        "feasible": feasible,
        "blocked_reason": None if feasible else "insufficient_non_overlapping_partitions",
        "train_races": len(train),
        "validation_races": len(validation),
        "test_races": len(test),
        "purged_unsettled_at_boundary": purged,
        "validation_start": valid_start.isoformat(),
        "test_start": test_start.isoformat(),
    }


def collection_status(records: list[dict[str, Any]]) -> dict[str, Any]:
    selected, excluded = select_latest_eligible_per_race(records)
    valid_prediction: list[tuple[dict[str, Any], datetime]] = []
    valid_for_split: list[tuple[dict[str, Any], datetime, datetime]] = []
    invalid_prediction_times = 0
    invalid_result_times = 0
    for record in selected:
        predicted = _parse_time(record.get("prediction_timestamp"))
        if predicted is None:
            invalid_prediction_times += 1
            continue
        valid_prediction.append((record, predicted))
        result_time = _parse_time((record.get("metadata") or {}).get("result_timestamp"))
        if result_time is None or result_time <= predicted:
            invalid_result_times += 1
            continue
        valid_for_split.append((record, predicted, result_time))

    distinct_times = sorted({predicted for _, predicted in valid_prediction})
    counts = []
    for record, _ in valid_prediction:
        training = record.get("training_input") or {}
        odds = ((training.get("odds") or {}).get("trifecta") or {})
        if isinstance(odds, dict):
            counts.append(len(odds))

    eligible_race_ids = sorted(str(record.get("race_id")) for record, _ in valid_prediction)
    distinct_count = len(distinct_times)
    threshold_met = distinct_count >= MIN_DISTINCT_PREDICTION_TIMES
    split_preview = _split_preview(valid_for_split)
    report = {
        "input_records": len(records),
        "eligible_unique_races": len(valid_prediction),
        "eligible_race_ids": eligible_race_ids,
        "distinct_prediction_times": distinct_count,
        "minimum_distinct_prediction_times": MIN_DISTINCT_PREDICTION_TIMES,
        "remaining_distinct_prediction_times": max(0, MIN_DISTINCT_PREDICTION_TIMES - distinct_count),
        "collection_threshold_met": threshold_met,
        "chronological_evaluation_may_run": split_preview["feasible"],
        "split_preview": split_preview,
        "excluded": dict(excluded),
        "invalid_prediction_times": invalid_prediction_times,
        "invalid_result_times": invalid_result_times,
        "known_trifecta_odds_count": {
            "min": min(counts) if counts else None,
            "median": median(counts) if counts else None,
            "max": max(counts) if counts else None,
        },
        "prediction_times_utc": [value.isoformat() for value in distinct_times],
        "note": (
            "Five distinct prediction times are only the technical collection minimum. "
            "chronological_evaluation_may_run also previews the evaluator's non-overlapping "
            "train/validation/test requirement after purging labels unavailable at boundaries. "
            "Neither condition is evidence of statistical sufficiency or profitability."
        ),
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path, help="History JSON files or directories")
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Exit with code 2 until chronological train/validation/test evaluation can run",
    )
    args = parser.parse_args()

    report = collection_status(load_records(args.inputs))
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)
    if args.require_ready and not report["chronological_evaluation_may_run"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
