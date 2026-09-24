"""Build a canonical prospective history JSON from a saved prediction snapshot and a confirmed settlement.

This tool is local/offline only. It performs no network calls, database writes, or model promotion.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
from itertools import permutations
import json
import math
from pathlib import Path
import re
from typing import Any

ENGINE_VERSION = "phase32-hit-priority-all210-v1"
TRAINING_SCHEMA = "keirin-training-input-v1"
OUTPUT_SCHEMA = "backtest-record-v2"
CATEGORIES = ("hit_priority", "balance", "middle", "longshot", "super_longshot")
COMBO_RE = re.compile(r"^\d+-\d+-\d+$")
KDREAMS_RE = re.compile(r"K[-\s]?Dreams|Kドリームス|ケイドリームス", re.I)


def _iso(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field}_missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field}_invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field}_timezone_missing")
    return parsed


def _combo(value: Any) -> bool:
    if not isinstance(value, str) or not COMBO_RE.fullmatch(value):
        return False
    parts = value.split("-")
    return len(parts) == 3 and len(set(parts)) == 3


def _full_probability_table(scores: Any, cars: list[int]) -> bool:
    expected = {"-".join(map(str, p)) for p in permutations(cars, 3)}
    if not isinstance(scores, list) or len(scores) != len(expected):
        return False
    seen: dict[str, float] = {}
    for row in scores:
        if not isinstance(row, dict):
            return False
        key = row.get("combo_key")
        raw = row.get("estimated_probability")
        if key in seen or key not in expected or isinstance(raw, bool):
            return False
        try:
            probability = float(raw)
        except (TypeError, ValueError):
            return False
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            return False
        seen[str(key)] = probability
    return abs(sum(seen.values()) - 1.0) <= 1e-6


def _categories_valid(selected: Any) -> bool:
    categories = (selected or {}).get("categories") if isinstance(selected, dict) else None
    if not isinstance(categories, dict):
        return False
    for key in CATEGORIES:
        block = categories.get(key)
        picks = block.get("picks") if isinstance(block, dict) else None
        if not isinstance(picks, list) or len(picks) > 3:
            return False
        keys = [pick.get("combo_key") for pick in picks if isinstance(pick, dict)]
        if len(keys) != len(picks) or len(set(keys)) != len(keys) or not all(_combo(x) for x in keys):
            return False
    return True


def validate_snapshot(snapshot: dict[str, Any]) -> None:
    if snapshot.get("schema_version") != "prediction-snapshot-v1":
        raise ValueError("snapshot_schema_mismatch")
    if snapshot.get("validation_mode") != "prospective-only":
        raise ValueError("snapshot_not_prospective_only")
    eligibility = snapshot.get("snapshot_eligibility") or {}
    if eligibility.get("prospective") is not True or eligibility.get("prestart_confirmed") is not True:
        raise ValueError("snapshot_not_prospective")
    _iso(snapshot.get("captured_at"), "captured_at")

    race_data = snapshot.get("race_data") or {}
    players = race_data.get("players")
    if not isinstance(players, list) or len(players) != 7:
        raise ValueError("seven_riders_required")
    cars = [player.get("car_number") for player in players if isinstance(player, dict)]
    if len(cars) != 7 or len(set(cars)) != 7 or not all(isinstance(car, int) and 1 <= car <= 7 for car in cars):
        raise ValueError("invalid_car_numbers")

    engine = snapshot.get("engine_response") or {}
    if engine.get("success") is not True:
        raise ValueError("engine_response_unsuccessful")
    if engine.get("saved") is not False or engine.get("db_write_enabled") is not False:
        raise ValueError("snapshot_persistence_not_off")
    if engine.get("production_prediction_enabled") is not False:
        raise ValueError("production_prediction_must_be_off")
    version = (engine.get("architecture") or {}).get("engine") or engine.get("engine_candidate")
    if version != ENGINE_VERSION:
        raise ValueError("engine_version_mismatch")

    prediction = engine.get("prediction") or {}
    scores = prediction.get("trifecta_scores")
    if not _full_probability_table(scores, cars):
        raise ValueError("full_probability_table_invalid")
    if not _categories_valid(prediction.get("selected_predictions")):
        raise ValueError("selected_categories_invalid")


def build_training_input(snapshot: dict[str, Any], evaluation_scope: str = "prospective") -> dict[str, Any]:
    race_data = snapshot["race_data"]
    engine = snapshot["engine_response"]
    race = deepcopy(race_data.get("race") or {})
    players = deepcopy(race_data.get("players") or [])
    context = deepcopy(race_data.get("prediction_context"))
    raw = deepcopy(((race_data.get("odds") or {}).get("trifecta") or {}))
    sanitization = engine.get("odds_sanitization") or {}
    ignored = set(sanitization.get("ignored_combos") or [])
    source = str((context or {}).get("source") or "") if isinstance(context, dict) else ""
    kdreams = bool(KDREAMS_RE.search(source))
    removed: list[str] = []
    for key in list(raw):
        if key in ignored or (kdreams and float(raw[key]) == 9999.9):
            raw.pop(key, None)
            removed.append(key)
    return {
        "schema_version": TRAINING_SCHEMA,
        "captured_at": snapshot["captured_at"],
        "race": race,
        "players": players,
        "odds": {"trifecta": raw},
        "prediction_context": context,
        "odds_sanitization": {
            "policy": sanitization.get("policy") or "snapshot_safety_filter",
            "source_matched": sanitization.get("source_matched", kdreams),
            "removed_combos": sorted(ignored | set(removed)),
        },
        "evaluation_scope": evaluation_scope,
    }


def build_history_record(
    snapshot: dict[str, Any],
    *,
    outcome_combo: str,
    settlement_odds: float,
    result_timestamp: str,
) -> dict[str, Any]:
    validate_snapshot(snapshot)
    if not _combo(outcome_combo):
        raise ValueError("outcome_combo_invalid")
    odds = float(settlement_odds)
    if not math.isfinite(odds) or odds <= 0:
        raise ValueError("settlement_odds_invalid")

    captured = _iso(snapshot["captured_at"], "captured_at")
    result_time = _iso(result_timestamp, "result_timestamp")
    if captured >= result_time:
        raise ValueError("prediction_must_precede_result_confirmation")

    race_data = snapshot["race_data"]
    race = race_data.get("race") or {}
    players = race_data.get("players") or []
    cars = {int(player["car_number"]) for player in players}
    outcome_cars = {int(part) for part in outcome_combo.split("-")}
    if not outcome_cars <= cars:
        raise ValueError("outcome_not_in_riders")

    engine = snapshot["engine_response"]
    prediction = engine["prediction"]
    scores = [
        {
            "combo_key": row["combo_key"],
            "estimated_probability": float(row["estimated_probability"]),
            "odds": row.get("odds"),
        }
        for row in prediction["trifecta_scores"]
    ]
    source_snapshot = {
        "schema_version": snapshot.get("schema_version"),
        "validation_mode": snapshot.get("validation_mode", "legacy"),
        "snapshot_eligibility": deepcopy(snapshot.get("snapshot_eligibility")),
        "captured_at": snapshot["captured_at"],
        "engine_service_version": engine.get("service_version"),
        "engine_version": engine.get("engine_candidate") or (engine.get("architecture") or {}).get("engine"),
        "probability_calibration_status": engine.get("probability_calibration_status")
        or (prediction.get("selected_predictions") or {}).get("probability_calibration_status"),
        "monetary_ev_enabled": engine.get("monetary_ev_enabled")
        if engine.get("monetary_ev_enabled") is not None
        else (prediction.get("selected_predictions") or {}).get("monetary_ev_enabled"),
        "odds_band_ranking": engine.get("odds_band_ranking")
        or (prediction.get("selected_predictions") or {}).get("odds_band_ranking"),
        "odds_sanitization": deepcopy(engine.get("odds_sanitization")),
        "evaluation_scope": "prospective",
    }
    race_id = f"{race.get('date', 'date')}-{race.get('venue', 'venue')}-{race.get('race_number', 'R')}R"
    training_input = build_training_input(snapshot, "prospective")
    record = {
        "race_id": race_id,
        "prediction_timestamp": snapshot["captured_at"],
        "outcome_combo": outcome_combo,
        "settlement_odds": odds,
        "trifecta_scores": scores,
        "selected_predictions": deepcopy(prediction["selected_predictions"]),
        "training_input": training_input,
        "metadata": {
            "date": race.get("date"),
            "venue": race.get("venue"),
            "race_number": race.get("race_number"),
            "result_timestamp": result_timestamp,
            "result_time_status": "provided",
            "engine_version": engine.get("engine_candidate") or (engine.get("architecture") or {}).get("engine"),
            "input_quality": deepcopy(engine.get("input_quality")),
            "odds_coverage": (engine.get("input_quality") or {}).get("trifecta_odds_coverage"),
            "source_snapshot": source_snapshot,
            "evaluation_scope": "prospective",
            "temporal_order": "prediction_before_result",
            "training_eligibility": {
                "supervised_training": True,
                "reason": "eligible_prospective_pre_result_snapshot",
            },
            "prepared_by": "offline-settle-snapshot-v1",
            "schema_version": OUTPUT_SCHEMA,
        },
    }
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--outcome", required=True, help="Confirmed trifecta, e.g. 3-4-7")
    parser.add_argument("--odds", required=True, type=float, help="Confirmed trifecta odds in decimal multiple")
    parser.add_argument(
        "--result-timestamp",
        required=True,
        help="Timezone-aware timestamp when the confirmed result was observed/recorded",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    record = build_history_record(
        snapshot,
        outcome_combo=args.outcome,
        settlement_odds=args.odds,
        result_timestamp=args.result_timestamp,
    )
    export = {
        "mode": "dry_run",
        "payload": {"records": [record]},
        "offline_builder": {
            "service": "offline-settle-snapshot-v1",
            "saved": False,
            "db_write_enabled": False,
            "external_fetch_enabled": False,
            "production_prediction_enabled": False,
            "result_timestamp_semantics": "confirmed_result_observed_or_recorded_at",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(export, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({
        "race_id": record["race_id"],
        "outcome_combo": record["outcome_combo"],
        "settlement_odds": record["settlement_odds"],
        "known_trifecta_odds_count": len(record["training_input"]["odds"]["trifecta"]),
        "supervised_training_eligible": record["metadata"]["training_eligibility"]["supervised_training"],
        "saved": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
