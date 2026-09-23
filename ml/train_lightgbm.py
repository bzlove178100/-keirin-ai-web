from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from model_contract import FEATURES, MODEL_FAMILY, TARGETS, feature_row, time_group_split, validate_feature_contract


def _matrix(rows: list[dict[str, Any]]):
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - runtime dependency
        raise RuntimeError("numpy is required to train the LightGBM candidate") from exc

    values = []
    for row in rows:
        encoded = feature_row(row)
        values.append([
            np.nan if encoded[name] is None else float(encoded[name])
            for name in FEATURES
        ])
    return np.asarray(values, dtype=float)


def _target(rows: list[dict[str, Any]], target: str):
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - runtime dependency
        raise RuntimeError("numpy is required to train the LightGBM candidate") from exc
    return np.asarray([int(row.get(target) or 0) for row in rows], dtype=int)


def _binary_log_loss(y_true, y_prob) -> float:
    import numpy as np

    eps = 1e-15
    p = np.clip(y_prob, eps, 1 - eps)
    y = y_true.astype(float)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def train_candidate(
    rows: list[dict[str, Any]],
    output_dir: Path,
    *,
    train_fraction: float,
    valid_fraction: float,
) -> dict[str, Any]:
    contract_errors = validate_feature_contract()
    if contract_errors:
        raise RuntimeError(f"feature contract invalid: {contract_errors}")

    try:
        import lightgbm as lgb
    except ImportError as exc:  # pragma: no cover - runtime dependency
        raise RuntimeError("lightgbm is required to train the candidate") from exc

    splits = time_group_split(
        rows,
        train_fraction=train_fraction,
        valid_fraction=valid_fraction,
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    x_train = _matrix(splits["train"])
    x_valid = _matrix(splits["valid"])
    x_test = _matrix(splits["test"])

    metadata: dict[str, Any] = {
        "model_family": MODEL_FAMILY,
        "status": "candidate_only",
        "probability_calibration_status": "uncalibrated",
        "production_prediction_enabled": False,
        "features": FEATURES,
        "targets": TARGETS,
        "split_policy": "chronological_by_race_keep_all_riders_together",
        "split_fractions": {
            "train": train_fraction,
            "valid": valid_fraction,
            "test": 1 - train_fraction - valid_fraction,
        },
        "split_unique_races": {
            name: len({str(row["race_id"]) for row in split_rows})
            for name, split_rows in splits.items()
        },
        "metrics": {},
        "note": (
            "Candidate training output only. These metrics do not establish statistical sufficiency, "
            "probability calibration, monetary EV validity, or production promotion."
        ),
    }

    params = {
        "objective": "binary",
        "n_estimators": 200,
        "learning_rate": 0.03,
        "num_leaves": 15,
        "min_child_samples": 10,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "random_state": 42,
        "verbosity": -1,
    }

    for position, target_name in TARGETS.items():
        y_train = _target(splits["train"], target_name)
        y_valid = _target(splits["valid"], target_name)
        y_test = _target(splits["test"], target_name)
        if len(set(y_train.tolist())) < 2:
            raise ValueError(f"training split has only one class for {target_name}")

        model = lgb.LGBMClassifier(**params)
        model.fit(
            x_train,
            y_train,
            eval_set=[(x_valid, y_valid)],
            eval_metric="binary_logloss",
            callbacks=[lgb.early_stopping(30, verbose=False)],
            feature_name=FEATURES,
        )

        valid_prob = model.predict_proba(x_valid)[:, 1]
        test_prob = model.predict_proba(x_test)[:, 1]
        model.booster_.save_model(str(output_dir / f"{position}.txt"))
        metadata["metrics"][position] = {
            "valid_binary_log_loss": _binary_log_loss(y_valid, valid_prob),
            "test_binary_log_loss": _binary_log_loss(y_test, test_prob),
            "best_iteration": int(model.best_iteration_ or 0),
        }

    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return metadata


def load_csv(path: Path) -> list[dict[str, Any]]:
    import csv

    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def main() -> int:
    parser = argparse.ArgumentParser(description="Train candidate-only position-specific LightGBM models.")
    parser.add_argument("--input", type=Path, required=True, help="Rider-level prospective training CSV")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for candidate model files")
    parser.add_argument("--train-fraction", type=float, default=0.70)
    parser.add_argument("--valid-fraction", type=float, default=0.15)
    args = parser.parse_args()

    rows = load_csv(args.input)
    metadata = train_candidate(
        rows,
        args.output_dir,
        train_fraction=args.train_fraction,
        valid_fraction=args.valid_fraction,
    )
    print(json.dumps(metadata, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
