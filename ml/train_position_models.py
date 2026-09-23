from __future__ import annotations

import argparse
import csv
import json
import math
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np

from ml.position_features import FEATURE_COLUMNS, TARGET_COLUMNS, row_to_features
from ml.trifecta_adapter import combine_position_probabilities, validate_trifecta_table

MODEL_VERSION = "lightgbm-position-rankers-v1"


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError("training CSV is empty")
    required = {"race_id", "prediction_timestamp", "car_number", "style", *TARGET_COLUMNS}
    missing = sorted(required - set(rows[0]))
    if missing:
        raise ValueError(f"training CSV missing columns: {', '.join(missing)}")
    return rows


def grouped_races(rows: list[dict[str, str]]) -> list[tuple[str, list[dict[str, str]]]]:
    grouped: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
    for row in rows:
        race_id = str(row.get("race_id") or "").strip()
        if not race_id:
            raise ValueError("race_id is required for every rider row")
        grouped.setdefault(race_id, []).append(row)

    races = list(grouped.items())
    races.sort(key=lambda item: (str(item[1][0].get("prediction_timestamp") or ""), item[0]))
    for race_id, race_rows in races:
        cars = [int(float(r["car_number"])) for r in race_rows]
        if len(cars) < 4 or len(set(cars)) != len(cars):
            raise ValueError(f"race {race_id} has invalid or duplicate riders")
        for target in TARGET_COLUMNS:
            positives = sum(int(float(r[target])) for r in race_rows)
            if positives != 1:
                raise ValueError(f"race {race_id} must have exactly one positive for {target}")
    return races


def _matrix(races: list[tuple[str, list[dict[str, str]]]], target: str) -> tuple[np.ndarray, np.ndarray, list[int]]:
    flat = [row for _, race_rows in races for row in race_rows]
    x = np.asarray([row_to_features(row) for row in flat], dtype=np.float64)
    y = np.asarray([int(float(row[target])) for row in flat], dtype=np.int32)
    groups = [len(race_rows) for _, race_rows in races]
    return x, y, groups


def _softmax(scores: np.ndarray) -> np.ndarray:
    if scores.ndim != 1 or len(scores) == 0:
        raise ValueError("scores must be a non-empty one-dimensional array")
    shifted = scores - np.max(scores)
    exp = np.exp(np.clip(shifted, -60, 60))
    total = float(np.sum(exp))
    if not math.isfinite(total) or total <= 0:
        raise ValueError("invalid softmax mass")
    return exp / total


def _train_one(
    train_races: list[tuple[str, list[dict[str, str]]]],
    valid_races: list[tuple[str, list[dict[str, str]]]],
    target: str,
) -> lgb.Booster:
    x_train, y_train, group_train = _matrix(train_races, target)
    x_valid, y_valid, group_valid = _matrix(valid_races, target)

    train_set = lgb.Dataset(
        x_train,
        label=y_train,
        group=group_train,
        feature_name=FEATURE_COLUMNS,
        free_raw_data=False,
    )
    valid_set = lgb.Dataset(
        x_valid,
        label=y_valid,
        group=group_valid,
        feature_name=FEATURE_COLUMNS,
        reference=train_set,
        free_raw_data=False,
    )

    params = {
        "objective": "lambdarank",
        "metric": "ndcg",
        "ndcg_eval_at": [1, 3],
        "learning_rate": 0.05,
        "num_leaves": 7,
        "max_depth": 3,
        "min_data_in_leaf": 1,
        "min_data_in_bin": 1,
        "feature_fraction": 0.9,
        "bagging_fraction": 0.9,
        "bagging_freq": 1,
        "seed": 42,
        "feature_fraction_seed": 42,
        "bagging_seed": 42,
        "verbosity": -1,
    }
    return lgb.train(
        params,
        train_set,
        num_boost_round=300,
        valid_sets=[valid_set],
        valid_names=["validation"],
        callbacks=[lgb.early_stopping(30, verbose=False)],
    )


def _position_rank_metrics(
    race_rows: list[dict[str, str]],
    probabilities: dict[str, dict[int, float]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    mapping = {
        "first": "target_first",
        "second": "target_second",
        "third": "target_third",
    }
    for position, target in mapping.items():
        actual = next(int(float(r["car_number"])) for r in race_rows if int(float(r[target])) == 1)
        ordered = sorted(probabilities[position].items(), key=lambda item: (-item[1], item[0]))
        rank = next(i + 1 for i, (car, _) in enumerate(ordered) if car == actual)
        result[position] = {
            "actual_car": actual,
            "rank": rank,
            "top1_hit": rank == 1,
            "top3_hit": rank <= 3,
            "reciprocal_rank": 1.0 / rank,
        }
    return result


def evaluate(
    models: dict[str, lgb.Booster],
    valid_races: list[tuple[str, list[dict[str, str]]]],
) -> dict[str, Any]:
    top = {1: 0, 3: 0, 5: 0, 10: 0}
    mrr = 0.0
    position_acc = {"first": 0, "second": 0, "third": 0}
    position_mrr = {"first": 0.0, "second": 0.0, "third": 0.0}
    per_race: list[dict[str, Any]] = []

    for race_id, race_rows in valid_races:
        x = np.asarray([row_to_features(row) for row in race_rows], dtype=np.float64)
        cars = [int(float(row["car_number"])) for row in race_rows]
        probabilities: dict[str, dict[int, float]] = {}
        for position in ("first", "second", "third"):
            raw = np.asarray(models[position].predict(x, num_iteration=models[position].best_iteration), dtype=np.float64)
            probs = _softmax(raw)
            probabilities[position] = {car: float(prob) for car, prob in zip(cars, probs, strict=True)}

        pos_metrics = _position_rank_metrics(race_rows, probabilities)
        for position in position_acc:
            position_acc[position] += int(pos_metrics[position]["top1_hit"])
            position_mrr[position] += float(pos_metrics[position]["reciprocal_rank"])

        actual_first = pos_metrics["first"]["actual_car"]
        actual_second = pos_metrics["second"]["actual_car"]
        actual_third = pos_metrics["third"]["actual_car"]
        actual_combo = f"{actual_first}-{actual_second}-{actual_third}"

        table = combine_position_probabilities(
            probabilities["first"],
            probabilities["second"],
            probabilities["third"],
        )
        validation = validate_trifecta_table(table, len(cars))
        if not (validation["combination_count_ok"] and validation["unique_ok"] and validation["probability_mass_ok"]):
            raise ValueError(f"adapter validation failed for race {race_id}")

        trifecta_rank = next(i + 1 for i, row in enumerate(table) if row["combo_key"] == actual_combo)
        for k in top:
            top[k] += int(trifecta_rank <= k)
        mrr += 1.0 / trifecta_rank
        per_race.append(
            {
                "race_id": race_id,
                "actual_combo": actual_combo,
                "trifecta_rank": trifecta_rank,
                "position_metrics": pos_metrics,
            }
        )

    n = len(valid_races)
    return {
        "validation_races": n,
        "trifecta_top1_accuracy": top[1] / n,
        "trifecta_top3_accuracy": top[3] / n,
        "trifecta_top5_accuracy": top[5] / n,
        "trifecta_top10_accuracy": top[10] / n,
        "trifecta_mean_reciprocal_rank": mrr / n,
        "position_top1_accuracy": {k: position_acc[k] / n for k in position_acc},
        "position_mean_reciprocal_rank": {k: position_mrr[k] / n for k in position_mrr},
        "per_race": per_race,
    }


def train(
    csv_path: Path,
    output_dir: Path,
    min_races: int = 5,
    validation_fraction: float = 0.2,
) -> dict[str, Any]:
    rows = load_rows(csv_path)
    races = grouped_races(rows)
    if len(races) < min_races:
        result = {
            "status": "blocked_insufficient_races",
            "race_count": len(races),
            "technical_minimum_races": min_races,
            "production_enabled": False,
            "promotion_eligible": False,
            "note": "The minimum is only a technical development guardrail and is not a production sufficiency claim.",
        }
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "metrics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    if not (0 < validation_fraction < 0.5):
        raise ValueError("validation_fraction must be between 0 and 0.5")

    split = int(round(len(races) * (1.0 - validation_fraction)))
    split = max(2, min(split, len(races) - 1))
    train_races = races[:split]
    valid_races = races[split:]

    models = {
        "first": _train_one(train_races, valid_races, "target_first"),
        "second": _train_one(train_races, valid_races, "target_second"),
        "third": _train_one(train_races, valid_races, "target_third"),
    }
    metrics = evaluate(models, valid_races)
    metrics.update(
        {
            "status": "trained_offline_validation_only",
            "model_version": MODEL_VERSION,
            "production_enabled": False,
            "promotion_eligible": False,
            "probability_calibration_status": "uncalibrated",
            "position_score_conversion": "softmax_within_race",
            "adapter": "position-probability-to-trifecta-v1",
            "total_races": len(races),
            "training_races": len(train_races),
            "validation_races": len(valid_races),
            "split_policy": "chronological_by_prediction_timestamp",
            "feature_columns": FEATURE_COLUMNS,
            "odds_used_as_model_feature": False,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "notes": [
                "Only rider-level rows built from supervised-training-eligible prospective history are accepted upstream.",
                "LightGBM ranker scores are softmax-normalized within each race but remain uncalibrated.",
                "The three position distributions are combined by the existing trifecta adapter.",
                "This artifact is not connected to predict-engine-dev.",
            ],
        }
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    for position, booster in models.items():
        booster.save_model(str(output_dir / f"{position}.txt"), num_iteration=booster.best_iteration)
    (output_dir / "feature_schema.json").write_text(
        json.dumps(
            {
                "model_version": MODEL_VERSION,
                "feature_columns": FEATURE_COLUMNS,
                "style_encoding": {"逃": "style_nige", "両": "style_ryo", "追": "style_oi"},
                "missing_numeric_policy": "NaN passed to LightGBM",
                "odds_used_as_model_feature": False,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (output_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Train offline LightGBM rankers for first/second/third place.")
    parser.add_argument("csv", type=Path, help="Rider-level CSV from build_training_dataset.py")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/lightgbm-position-models-v1"))
    parser.add_argument("--min-races", type=int, default=5)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    args = parser.parse_args()

    result = train(args.csv, args.output_dir, args.min_races, args.validation_fraction)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("status") == "trained_offline_validation_only" else 2


if __name__ == "__main__":
    raise SystemExit(main())
