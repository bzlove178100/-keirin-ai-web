from __future__ import annotations

import argparse
import csv
import json
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np

from ml.build_trifecta_dataset import FEATURE_COLUMNS


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError("dataset is empty")
    missing = [c for c in FEATURE_COLUMNS + ["race_id", "prediction_timestamp", "label"] if c not in rows[0]]
    if missing:
        raise ValueError(f"dataset missing columns: {', '.join(missing)}")
    return rows


def group_rows(rows: list[dict[str, str]]) -> list[tuple[str, list[dict[str, str]]]]:
    grouped: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
    for row in rows:
        race_id = row["race_id"]
        grouped.setdefault(race_id, []).append(row)
    groups = list(grouped.items())
    groups.sort(key=lambda item: (item[1][0].get("prediction_timestamp", ""), item[0]))
    return groups


def matrix(groups: list[tuple[str, list[dict[str, str]]]]) -> tuple[np.ndarray, np.ndarray, list[int]]:
    flat = [row for _, group in groups for row in group]
    x = np.asarray([[float(row[col]) for col in FEATURE_COLUMNS] for row in flat], dtype=np.float64)
    y = np.asarray([int(row["label"]) for row in flat], dtype=np.int32)
    sizes = [len(group) for _, group in groups]
    return x, y, sizes


def ranking_metrics(groups: list[tuple[str, list[dict[str, str]]]], scores: np.ndarray) -> dict[str, Any]:
    offset = 0
    top_hits = {1: 0, 3: 0, 5: 0, 10: 0}
    reciprocal_rank_sum = 0.0
    per_race: list[dict[str, Any]] = []

    for race_id, rows in groups:
        group_scores = scores[offset : offset + len(rows)]
        offset += len(rows)
        order = np.argsort(-group_scores, kind="stable")
        labels = np.asarray([int(r["label"]) for r in rows], dtype=np.int32)
        positive = np.flatnonzero(labels == 1)
        if len(positive) != 1:
            raise ValueError(f"race {race_id} must have exactly one positive target")
        target_index = int(positive[0])
        rank = int(np.where(order == target_index)[0][0]) + 1
        reciprocal_rank_sum += 1.0 / rank
        for k in top_hits:
            top_hits[k] += int(rank <= k)
        per_race.append({"race_id": race_id, "target_rank": rank})

    n = len(groups)
    return {
        "validation_races": n,
        "top1_accuracy": top_hits[1] / n if n else None,
        "top3_accuracy": top_hits[3] / n if n else None,
        "top5_accuracy": top_hits[5] / n if n else None,
        "top10_accuracy": top_hits[10] / n if n else None,
        "mean_reciprocal_rank": reciprocal_rank_sum / n if n else None,
        "per_race": per_race,
    }


def train(dataset: Path, model_out: Path, metrics_out: Path, min_races: int, validation_fraction: float) -> dict[str, Any]:
    rows = load_rows(dataset)
    groups = group_rows(rows)
    race_count = len(groups)
    if race_count < min_races:
        result = {
            "status": "blocked_insufficient_prospective_races",
            "race_count": race_count,
            "minimum_required_races": min_races,
            "production_enabled": False,
            "note": "This threshold is an operational guardrail, not a claim of statistical sufficiency.",
        }
        metrics_out.parent.mkdir(parents=True, exist_ok=True)
        metrics_out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    if not (0 < validation_fraction < 0.5):
        raise ValueError("validation_fraction must be between 0 and 0.5")

    split = max(2, int(round(race_count * (1.0 - validation_fraction))))
    split = min(split, race_count - 1)
    train_groups = groups[:split]
    valid_groups = groups[split:]

    x_train, y_train, group_train = matrix(train_groups)
    x_valid, y_valid, group_valid = matrix(valid_groups)

    ranker = lgb.LGBMRanker(
        objective="lambdarank",
        metric="ndcg",
        ndcg_at=[1, 3, 5, 10],
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=31,
        min_child_samples=20,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=42,
        verbosity=-1,
    )
    ranker.fit(
        x_train,
        y_train,
        group=group_train,
        eval_set=[(x_valid, y_valid)],
        eval_group=[group_valid],
        eval_at=[1, 3, 5, 10],
        callbacks=[lgb.early_stopping(30, verbose=False)],
        feature_name=FEATURE_COLUMNS,
    )

    scores = ranker.predict(x_valid, num_iteration=ranker.best_iteration_)
    metrics = ranking_metrics(valid_groups, np.asarray(scores, dtype=np.float64))
    metrics.update(
        {
            "status": "trained_validation_only",
            "model_type": "LightGBM LGBMRanker lambdarank",
            "model_output": "ranking_score_not_probability",
            "production_enabled": False,
            "training_races": len(train_groups),
            "total_eligible_races": race_count,
            "validation_fraction": validation_fraction,
            "best_iteration": int(ranker.best_iteration_ or ranker.n_estimators),
            "feature_count": len(FEATURE_COLUMNS),
            "features": FEATURE_COLUMNS,
            "prediction_time_odds_used_as_feature": False,
            "split_policy": "chronological_by_prediction_timestamp",
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "notes": [
                "Replay/legacy records are excluded before this stage.",
                "Ranking scores are not calibrated probabilities and must not be presented as hit probabilities.",
                "This model is not connected to production prediction.",
            ],
        }
    )

    model_out.parent.mkdir(parents=True, exist_ok=True)
    metrics_out.parent.mkdir(parents=True, exist_ok=True)
    ranker.booster_.save_model(str(model_out), num_iteration=ranker.best_iteration_)
    metrics_out.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Train an offline LightGBM trifecta ranker from prospective-only data.")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--model-out", type=Path, default=Path("ml/artifacts/lightgbm_trifecta_ranker.txt"))
    parser.add_argument("--metrics-out", type=Path, default=Path("ml/artifacts/lightgbm_trifecta_ranker.metrics.json"))
    parser.add_argument("--min-races", type=int, default=200)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    args = parser.parse_args()

    result = train(args.dataset, args.model_out, args.metrics_out, args.min_races, args.validation_fraction)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("status") == "trained_validation_only" else 2


if __name__ == "__main__":
    raise SystemExit(main())
