from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

TRAINING_SCHEMA = "keirin-training-input-v1"


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _time_key(value: Any) -> float:
    if not isinstance(value, str) or not value:
        return float("-inf")
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return float("-inf")


def supervised_eligibility(record: dict[str, Any]) -> tuple[bool, str]:
    metadata = record.get("metadata") or {}
    eligibility = metadata.get("training_eligibility") or {}
    training_input = record.get("training_input")

    if metadata.get("evaluation_scope") != "prospective":
        return False, "not_prospective"
    if metadata.get("temporal_order") != "prediction_before_result":
        return False, "not_pre_result"
    if eligibility.get("supervised_training") is not True:
        return False, "not_marked_training_eligible"
    if not isinstance(training_input, dict):
        return False, "training_input_missing"
    if training_input.get("schema_version") != TRAINING_SCHEMA:
        return False, "training_schema_mismatch"
    if training_input.get("evaluation_scope") != "prospective":
        return False, "training_input_not_prospective"
    players = training_input.get("players")
    if not isinstance(players, list) or len(players) < 4:
        return False, "players_missing"
    outcome = record.get("outcome_combo")
    if not isinstance(outcome, str) or len(outcome.split("-")) != 3:
        return False, "outcome_missing"
    return True, "eligible"


def select_latest_eligible_per_race(records: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    selected: dict[str, dict[str, Any]] = {}
    excluded: dict[str, int] = {}
    for record in records:
        ok, reason = supervised_eligibility(record)
        if not ok:
            excluded[reason] = excluded.get(reason, 0) + 1
            continue
        race_id = str(record.get("race_id") or "").strip()
        if not race_id:
            excluded["race_id_missing"] = excluded.get("race_id_missing", 0) + 1
            continue
        current = selected.get(race_id)
        if current is None or _time_key(record.get("prediction_timestamp")) > _time_key(current.get("prediction_timestamp")):
            selected[race_id] = record
    return list(selected.values()), excluded


def _current_meet_avg(player: dict[str, Any]) -> float | None:
    results = ((player.get("current_meet") or {}).get("results") or [])
    finishes: list[float] = []
    for item in results:
        raw = item.get("finish") if isinstance(item, dict) else item
        value = _num(raw)
        if value is not None and value > 0:
            finishes.append(value)
    return sum(finishes) / len(finishes) if finishes else None


def rider_rows(record: dict[str, Any]) -> list[dict[str, Any]]:
    ok, reason = supervised_eligibility(record)
    if not ok:
        raise ValueError(f"record is not eligible for supervised training: {reason}")

    training = record["training_input"]
    race = training.get("race") or {}
    outcome = [int(x) for x in str(record["outcome_combo"]).split("-")]
    if len(set(outcome)) != 3:
        raise ValueError("outcome_combo must contain three distinct riders")

    known_odds = ((training.get("odds") or {}).get("trifecta") or {})
    if any(_num(v) == 9999.9 for v in known_odds.values()):
        raise ValueError("training input contains K-Dreams 9999.9 no-ticket marker")

    rows: list[dict[str, Any]] = []
    for player in training["players"]:
        if not isinstance(player, dict):
            continue
        car = int(player["car_number"])
        recent = player.get("recent_form") or {}
        factors = ((player.get("comments") or {}).get("parsed_factors") or {})
        line_position = _num(player.get("line_position"))
        row = {
            "race_id": record.get("race_id"),
            "date": race.get("date"),
            "venue": race.get("venue"),
            "race_number": race.get("race_number"),
            "prediction_timestamp": record.get("prediction_timestamp"),
            "car_number": car,
            "style": player.get("style"),
            "race_score": _num(player.get("race_score")),
            "S": _num(player.get("S")),
            "H": _num(player.get("H")),
            "B": _num(player.get("B")),
            "line_id": player.get("line_id"),
            "line_position": line_position,
            "line_length": _num(player.get("line_length")),
            "is_line_leader": 1 if line_position == 1 else 0,
            "recent_win_rate": _num(recent.get("win_rate")),
            "recent_top2_rate": _num(recent.get("top2_rate")),
            "recent_top3_rate": _num(recent.get("top3_rate")),
            "recent_avg_finish": _num(recent.get("avg_finish")),
            "current_meet_avg_finish": _current_meet_avg(player),
            "condition_score": _num((player.get("condition") or {}).get("score")),
            "bank_fit_score": _num((player.get("bank_fit") or {}).get("score")),
            "comment_condition": _num(factors.get("condition")),
            "comment_training": _num(factors.get("training")),
            "comment_equipment": _num(factors.get("equipment")),
            "comment_confidence": _num(factors.get("confidence")),
            "comment_motivation": _num(factors.get("motivation")),
            "comment_fatigue": _num(factors.get("fatigue")),
            "known_trifecta_odds_count": len(known_odds),
            "target_first": 1 if car == outcome[0] else 0,
            "target_second": 1 if car == outcome[1] else 0,
            "target_third": 1 if car == outcome[2] else 0,
            "target_top3": 1 if car in outcome else 0,
        }
        rows.append(row)

    if sum(r["target_first"] for r in rows) != 1:
        raise ValueError("exactly one first-place rider must exist in training rows")
    if sum(r["target_second"] for r in rows) != 1:
        raise ValueError("exactly one second-place rider must exist in training rows")
    if sum(r["target_third"] for r in rows) != 1:
        raise ValueError("exactly one third-place rider must exist in training rows")
    if sum(r["target_top3"] for r in rows) != 3:
        raise ValueError("exactly three top-3 riders must exist in training rows")
    return rows


def build_rows(records: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    materialized = list(records)
    selected, excluded = select_latest_eligible_per_race(materialized)
    rows: list[dict[str, Any]] = []
    for record in sorted(selected, key=lambda r: (_time_key(r.get("prediction_timestamp")), str(r.get("race_id") or ""))):
        rows.extend(rider_rows(record))
    summary = {
        "input_records": len(materialized),
        "eligible_unique_races": len(selected),
        "rider_rows": len(rows),
        "excluded": excluded,
        "selection_policy": "latest_eligible_pre_result_snapshot_per_race",
        "training_schema": TRAINING_SCHEMA,
    }
    return rows, summary
