from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np

from ml.feature_extraction import extract_player_model_fields, sanitize_prediction_odds
from ml.position_features import FEATURE_COLUMNS, row_to_features
from ml.train_position_models import MODEL_VERSION, _softmax
from ml.trifecta_adapter import ADAPTER_VERSION, combine_position_probabilities, validate_trifecta_table

INFERENCE_VERSION = "lightgbm-offline-inference-v1"
VALID_STYLES = {"逃", "両", "追"}
POSITIONS = ("first", "second", "third")


def validate_race_data(race_data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(race_data, dict):
        return ["race_data must be an object"]
    race = race_data.get("race")
    if not isinstance(race, dict):
        errors.append("race is required")
    players = race_data.get("players")
    if not isinstance(players, list) or len(players) < 4:
        errors.append("players must contain at least 4 riders")
        return errors

    cars: set[int] = set()
    for index, player in enumerate(players):
        if not isinstance(player, dict):
            errors.append(f"players[{index}] must be an object")
            continue
        try:
            car = int(player.get("car_number"))
        except (TypeError, ValueError):
            errors.append(f"players[{index}].car_number must be an integer")
            continue
        if car in cars:
            errors.append(f"duplicate car_number: {car}")
        cars.add(car)
        if player.get("style") not in VALID_STYLES:
            errors.append(f"players[{index}].style must be one of 逃, 両, 追")
    return sorted(set(errors))


def load_models(model_dir: Path) -> tuple[dict[str, lgb.Booster], dict[str, Any]]:
    schema_path = model_dir / "feature_schema.json"
    metrics_path = model_dir / "metrics.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"missing model feature schema: {schema_path}")
    if not metrics_path.exists():
        raise FileNotFoundError(f"missing model metrics: {metrics_path}")

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    if schema.get("model_version") != MODEL_VERSION:
        raise ValueError("model version does not match runtime")
    if schema.get("feature_columns") != FEATURE_COLUMNS:
        raise ValueError("model feature schema does not match runtime")
    if metrics.get("status") != "trained_offline_validation_only":
        raise ValueError("model artifact is not a completed offline validation artifact")
    if metrics.get("production_enabled") is not False:
        raise ValueError("offline runtime refuses production-enabled artifacts")
    if metrics.get("probability_calibration_status") != "uncalibrated":
        raise ValueError("unexpected probability calibration status")

    models: dict[str, lgb.Booster] = {}
    for position in POSITIONS:
        path = model_dir / f"{position}.txt"
        if not path.exists():
            raise FileNotFoundError(f"missing position model: {path}")
        booster = lgb.Booster(model_file=str(path))
        if booster.feature_name() != FEATURE_COLUMNS:
            raise ValueError(f"{position} model feature names do not match runtime schema")
        models[position] = booster
    return models, {"feature_schema": schema, "training_metrics": metrics}


def _position_distributions(
    models: dict[str, lgb.Booster],
    player_rows: list[dict[str, Any]],
) -> dict[str, dict[int, float]]:
    x = np.asarray([row_to_features(row) for row in player_rows], dtype=np.float64)
    cars = [int(row["car_number"]) for row in player_rows]
    distributions: dict[str, dict[int, float]] = {}
    for position in POSITIONS:
        booster = models[position]
        raw = np.asarray(booster.predict(x, num_iteration=booster.best_iteration), dtype=np.float64)
        probabilities = _softmax(raw)
        distributions[position] = {
            car: float(probability)
            for car, probability in zip(cars, probabilities, strict=True)
        }
    return distributions


def _rank_positions(distributions: dict[str, dict[int, float]]) -> dict[str, list[dict[str, Any]]]:
    ranked: dict[str, list[dict[str, Any]]] = {}
    for position in POSITIONS:
        ordered = sorted(distributions[position].items(), key=lambda item: (-item[1], item[0]))
        ranked[position] = [
            {"rank": rank, "car_number": car, "estimated_probability": probability}
            for rank, (car, probability) in enumerate(ordered, start=1)
        ]
    return ranked


def predict_race(race_data: dict[str, Any], model_dir: Path) -> dict[str, Any]:
    errors = validate_race_data(race_data)
    if errors:
        raise ValueError("; ".join(errors))

    models, artifact = load_models(model_dir)
    players = sorted(race_data["players"], key=lambda p: int(p["car_number"]))
    player_rows = [extract_player_model_fields(player) for player in players]
    distributions = _position_distributions(models, player_rows)

    table = combine_position_probabilities(
        distributions["first"],
        distributions["second"],
        distributions["third"],
    )
    validation = validate_trifecta_table(table, len(player_rows))
    if not (
        validation["combination_count_ok"]
        and validation["unique_ok"]
        and validation["probability_mass_ok"]
    ):
        raise ValueError("trifecta adapter validation failed")

    clean_odds, odds_report = sanitize_prediction_odds(race_data)
    scores: list[dict[str, Any]] = []
    for row in table:
        scores.append(
            {
                **row,
                "odds": clean_odds.get(str(row["combo_key"])),
                "monetary_expected_value": None,
            }
        )

    possible = len(scores)
    known = odds_report["known_odds_count"]
    return {
        "success": True,
        "mode": "offline_inference_only",
        "inference_version": INFERENCE_VERSION,
        "model_version": MODEL_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "production_prediction_enabled": False,
        "db_write_enabled": False,
        "external_fetch_enabled": False,
        "probability_calibration_status": "uncalibrated",
        "monetary_ev_enabled": False,
        "odds_used_as_model_feature": False,
        "position_score_conversion": "softmax_within_race",
        "race": race_data.get("race"),
        "position_probabilities": distributions,
        "position_rankings": _rank_positions(distributions),
        "trifecta_scores": scores,
        "input_quality": {
            "rider_count": len(player_rows),
            "known_trifecta_odds_count": known,
            "possible_trifecta_count": possible,
            "trifecta_odds_coverage": known / possible if possible else 0.0,
        },
        "odds_sanitization": odds_report,
        "validation": {
            **validation,
            "no_result_fields_required": True,
            "model_artifact_status": artifact["training_metrics"].get("status"),
        },
        "warning": "Offline ML candidate only. Scores are uncalibrated; monetary EV and production prediction remain disabled.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run offline LightGBM position-model inference for one race.")
    parser.add_argument("race_json", type=Path, help="Pre-race JSON. May be raw race_data or {'race_data': ...}.")
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.race_json.read_text(encoding="utf-8"))
    race_data = payload.get("race_data") if isinstance(payload, dict) and isinstance(payload.get("race_data"), dict) else payload
    result = predict_race(race_data, args.model_dir)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
