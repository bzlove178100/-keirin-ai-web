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
    from .evaluation_protocol import prepare, readiness
except ImportError:
    from build_training_dataset import load_records
    from evaluation_protocol import prepare, readiness

MIN_DISTINCT_PREDICTION_TIMES = 5


def collection_status(records: list[dict[str, Any]]) -> dict[str, Any]:
    selected, quality = prepare(records)
    protocol = readiness(records)
    counts: list[int] = []
    for item in selected:
        training = item["record"].get("training_input") or {}
        odds = ((training.get("odds") or {}).get("trifecta") or {})
        if isinstance(odds, dict):
            counts.append(len(odds))

    prediction_times = sorted({item["prediction_time"] for item in selected})
    report = {
        "input_records": len(records),
        "eligible_unique_races": len(selected),
        "eligible_race_ids": [item["race_id"] for item in selected],
        "distinct_prediction_times": protocol["distinct_prediction_times"],
        "minimum_distinct_prediction_times": MIN_DISTINCT_PREDICTION_TIMES,
        "remaining_distinct_prediction_times": protocol["remaining_distinct_prediction_times"],
        "collection_threshold_met": protocol["technical_time_minimum_met"],
        "chronological_evaluation_may_run": protocol["chronological_partitions_ready"],
        "blocked_reason": protocol["blocked_reason"],
        "split": protocol["split"],
        "excluded": quality["excluded"],
        "duplicate_snapshots_removed": quality["duplicate_snapshots_removed"],
        "missing_feature_counts": quality["missing_feature_counts"],
        "missing_feature_fraction": quality["missing_feature_fraction"],
        "known_trifecta_odds_count": {
            "min": min(counts) if counts else None,
            "median": median(counts) if counts else None,
            "max": max(counts) if counts else None,
        },
        "prediction_times_utc": [
            datetime.fromtimestamp(value, timezone.utc).isoformat() for value in prediction_times
        ],
        "note": protocol["note"],
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path, help="History JSON files or directories")
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Exit with code 2 until leakage-safe chronological partitions can be formed",
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
