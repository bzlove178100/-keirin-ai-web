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


def collection_status(records: list[dict[str, Any]]) -> dict[str, Any]:
    selected, excluded = select_latest_eligible_per_race(records)
    valid: list[tuple[dict[str, Any], datetime]] = []
    invalid_prediction_times = 0
    for record in selected:
        predicted = _parse_time(record.get("prediction_timestamp"))
        if predicted is None:
            invalid_prediction_times += 1
            continue
        valid.append((record, predicted))

    distinct_times = sorted({predicted for _, predicted in valid})
    counts = []
    for record, _ in valid:
        training = record.get("training_input") or {}
        odds = ((training.get("odds") or {}).get("trifecta") or {})
        if isinstance(odds, dict):
            counts.append(len(odds))

    eligible_race_ids = sorted(str(record.get("race_id")) for record, _ in valid)
    distinct_count = len(distinct_times)
    threshold_met = distinct_count >= MIN_DISTINCT_PREDICTION_TIMES
    report = {
        "input_records": len(records),
        "eligible_unique_races": len(valid),
        "eligible_race_ids": eligible_race_ids,
        "distinct_prediction_times": distinct_count,
        "minimum_distinct_prediction_times": MIN_DISTINCT_PREDICTION_TIMES,
        "remaining_distinct_prediction_times": max(0, MIN_DISTINCT_PREDICTION_TIMES - distinct_count),
        "collection_threshold_met": threshold_met,
        "chronological_evaluation_may_run": threshold_met,
        "excluded": dict(excluded),
        "invalid_prediction_times": invalid_prediction_times,
        "known_trifecta_odds_count": {
            "min": min(counts) if counts else None,
            "median": median(counts) if counts else None,
            "max": max(counts) if counts else None,
        },
        "prediction_times_utc": [value.isoformat() for value in distinct_times],
        "note": (
            "Five distinct prediction times are only the technical minimum. "
            "The paired evaluator can still block after chronological leakage purging, "
            "and this threshold is not evidence of statistical sufficiency or profitability."
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
        help="Exit with code 2 until the five-distinct-time technical minimum is met",
    )
    args = parser.parse_args()

    report = collection_status(load_records(args.inputs))
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)
    if args.require_ready and not report["collection_threshold_met"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
