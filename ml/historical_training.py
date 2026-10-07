"""Private, offline historical training with explicit reviews and chronological holdout.

Review references are operator attestations, not automatic verification of a source.
This does not modify the prospective dataset contract or activate production.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

from ml.historical_audit import audit

FEATURES = ("race_score", "S", "H", "B", "recent_win_rate", "recent_top2_rate",
            "recent_top3_rate", "recent_avg_finish")


def digest(record: dict) -> str:
    return hashlib.sha256(json.dumps(record, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def timestamp(value) -> float:
    if not isinstance(value, str):
        raise ValueError("timestamp_missing")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.utcoffset() is None:
        raise ValueError("timestamp_timezone_missing")
    return dt.timestamp()


def prepare(records: list, reviews: list, validation_start: str, test_start: str) -> dict:
    """Build race-grouped partitions; never invent features, times, or reviews."""
    valid_boundary, test_boundary = timestamp(validation_start), timestamp(test_start)
    if valid_boundary >= test_boundary:
        raise ValueError("validation_must_precede_test")
    if not isinstance(records, list) or not isinstance(reviews, list):
        raise ValueError("records_and_reviews_must_be_arrays")
    intake = audit(records)
    review_map = {}
    for review in reviews:
        if not isinstance(review, dict) or not isinstance(review.get("race_id"), str):
            raise ValueError("invalid_review")
        key = review["race_id"]
        if key in review_map:
            raise ValueError("duplicate_review")
        review_map[key] = review
    originals = {}
    for record in records:
        if isinstance(record, dict) and isinstance(record.get("race_id"), str):
            originals.setdefault(record["race_id"], record)
    partitions = {name: [] for name in ("train", "validation", "test")}
    excluded = list(intake["invalid_records"])
    for item in intake["records"]:
        key = item["race_id"]
        record = originals[key]
        reasons = [r for r in item["reasons"] if r != "dedicated_historical_review_required"]
        review = review_map.get(key, {})
        try:
            if review.get("record_sha256") != digest(record):
                reasons.append("review_missing_or_record_changed")
            for field in ("reviewer", "source_use_evidence", "feature_time_evidence", "result_time_evidence"):
                if not isinstance(review.get(field), str) or not review[field].strip():
                    reasons.append(field + "_missing")
            if record.get("prospective") is not False:
                reasons.append("historical_record_must_not_claim_prospective")
            if record.get("dead_heat") is not False:
                reasons.append("explicit_non_dead_heat_required")
            feature_time = timestamp(record.get("feature_as_of"))
            start = timestamp(record.get("listed_scheduled_start_jst"))
            result_time = timestamp(record.get("result_available_at"))
            if not feature_time < start <= result_time:
                reasons.append("invalid_historical_chronology")
            features = record.get("pre_race_features")
            cars = [r["car_number"] for r in record.get("riders", [])]
            if not isinstance(features, list) or len(features) != len(cars):
                raise ValueError("reviewed_features_missing")
            feature_cars = [f.get("car_number") for f in features if isinstance(f, dict)]
            if (len(feature_cars) != len(features) or any(type(c) is not int for c in feature_cars)
                    or len(set(feature_cars)) != len(feature_cars) or set(feature_cars) != set(cars)):
                raise ValueError("feature_roster_mismatch")
            rows = []
            for feature in features:
                if set(feature) - {"car_number", "style", *FEATURES}:
                    raise ValueError("unreviewed_feature_columns")
                if feature.get("style") not in ("逃", "両", "追"):
                    raise ValueError("invalid_style")
                for name in FEATURES:
                    value = feature.get(name)
                    if value is not None and (type(value) not in (int, float) or not math.isfinite(value)):
                        raise ValueError("invalid_numeric_feature")
                    if value is not None and name in ("recent_win_rate", "recent_top2_rate", "recent_top3_rate") and not 0 <= value <= 100:
                        raise ValueError("recent_rate_out_of_range")
                    if value is not None and name == "recent_avg_finish" and not 1 <= value <= 9:
                        raise ValueError("recent_finish_out_of_range")
                rows.append({"car_number": feature["car_number"], "style": feature["style"],
                             **{name: feature.get(name) for name in FEATURES}})
            if reasons:
                excluded.append({"race_id": key, "reasons": reasons})
                continue
            outcome = record["trifecta_outcomes"][0]
            for row in rows:
                row.update({"race_id": key, **{target: int(row["car_number"] == car)
                           for target, car in zip(("target_first", "target_second", "target_third"), outcome)}})
            partition = "train" if feature_time < valid_boundary else "validation" if feature_time < test_boundary else "test"
            boundary = valid_boundary if partition == "train" else test_boundary if partition == "validation" else None
            if boundary is not None and result_time >= boundary:
                excluded.append({"race_id": key, "reasons": ["label_unavailable_before_next_partition"]})
                continue
            partitions[partition].append({"race_id": key, "rows": rows, "feature_time": feature_time,
                                           "record_sha256": digest(record), "review": review})
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
            excluded.append({"race_id": key, "reasons": reasons + [str(exc)]})
    for races in partitions.values():
        races.sort(key=lambda r: (r["feature_time"], r["race_id"]))
    return {"schema_version": "historical-training-plan-v1", "partitions": partitions,
            "partition_counts": {k: len(v) for k, v in partitions.items()}, "excluded": excluded,
            "validation_start": validation_start, "test_start": test_start,
            "training_runs": 0, "prospective": False, "production_enabled": False,
            "promotion_eligible": False, "review_verification": "operator_attestation_only",
            "statistical_sufficiency": "not_established"}


def train(plan: dict, output: Path) -> dict:
    """Fit on train, early-stop on validation, report test once. Private artifacts only."""
    groups = plan["partitions"]
    if output.exists():
        raise ValueError("output_already_exists")
    # Technical requirement only; even these counts do not establish useful accuracy.
    if len(groups["train"]) < 2 or not groups["validation"] or not groups["test"]:
        raise ValueError("insufficient_chronological_partitions")
    from ml.train_position_models import _train_one, evaluate

    races = {k: [(r["race_id"], r["rows"]) for r in v] for k, v in groups.items()}
    models = {p: _train_one(races["train"], races["validation"], "target_" + p)
              for p in ("first", "second", "third")}
    report = {k: v for k, v in plan.items() if k != "partitions"}
    report.update(status="trained_historical_offline_only", training_runs=1,
                  test_metrics=evaluate(models, races["test"]),
                  test_metrics_by_rider_count={str(n): evaluate(models, [r for r in races["test"] if len(r[1]) == n])
                                              for n in sorted({len(r[1]) for r in races["test"]})},
                  probability_calibration_status="uncalibrated",
                  evaluated_at=datetime.now().astimezone().isoformat(),
                  populated_features=list(FEATURES) + ["style"],
                  note="No paired prospective comparison or profitability claim. Do not tune on this test set.")
    output.mkdir(parents=True, exist_ok=False)
    for name, model in models.items():
        model.save_model(str(output / (name + ".txt")), num_iteration=model.best_iteration)
    (output / "dataset_manifest.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    (output / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("reviews", type=Path)
    parser.add_argument("--validation-start", required=True)
    parser.add_argument("--test-start", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--train", action="store_true", help="Output must be a NEW private directory")
    args = parser.parse_args()
    data = json.loads(args.input.read_text())
    reviews = json.loads(args.reviews.read_text())
    plan = prepare(data["records"], reviews, args.validation_start, args.test_start)
    if args.train:
        train(plan, args.output)
    else:
        with args.output.open("x", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)
            f.write("\n")
    print(json.dumps(plan["partition_counts"]))


if __name__ == "__main__":
    main()
