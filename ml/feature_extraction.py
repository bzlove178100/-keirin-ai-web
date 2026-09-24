from __future__ import annotations

import re
import math
from typing import Any

_KDREAMS = re.compile(r"K[-\s]?Dreams|Kドリームス|ケイドリームス", re.IGNORECASE)


def num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def current_meet_avg(player: dict[str, Any]) -> float | None:
    results = ((player.get("current_meet") or {}).get("results") or [])
    finishes: list[float] = []
    for item in results:
        raw = item.get("finish") if isinstance(item, dict) else item
        value = num(raw)
        if value is not None and value > 0:
            finishes.append(value)
    return sum(finishes) / len(finishes) if finishes else None


def extract_player_model_fields(player: dict[str, Any]) -> dict[str, Any]:
    """Extract the exact rider fields consumed by the position models.

    This function is shared by dataset construction and offline inference to
    reduce training-serving skew. It never reads settlement/result fields.
    """
    car = int(player["car_number"])
    recent = player.get("recent_form") or {}
    factors = ((player.get("comments") or {}).get("parsed_factors") or {})
    line_position = num(player.get("line_position"))
    return {
        "car_number": car,
        "style": player.get("style"),
        "race_score": num(player.get("race_score")),
        "S": num(player.get("S")),
        "H": num(player.get("H")),
        "B": num(player.get("B")),
        "line_id": player.get("line_id"),
        "line_position": line_position,
        "line_length": num(player.get("line_length")),
        "is_line_leader": 1 if line_position == 1 else 0,
        "recent_win_rate": num(recent.get("win_rate")),
        "recent_top2_rate": num(recent.get("top2_rate")),
        "recent_top3_rate": num(recent.get("top3_rate")),
        "recent_avg_finish": num(recent.get("avg_finish")),
        "current_meet_avg_finish": current_meet_avg(player),
        "condition_score": num((player.get("condition") or {}).get("score")),
        "bank_fit_score": num((player.get("bank_fit") or {}).get("score")),
        "comment_condition": num(factors.get("condition")),
        "comment_training": num(factors.get("training")),
        "comment_equipment": num(factors.get("equipment")),
        "comment_confidence": num(factors.get("confidence")),
        "comment_motivation": num(factors.get("motivation")),
        "comment_fatigue": num(factors.get("fatigue")),
    }


def sanitize_prediction_odds(race_data: dict[str, Any]) -> tuple[dict[str, float], dict[str, Any]]:
    """Return only confirmed usable prediction-time trifecta odds.

    K-Dreams' 9999.9 no-ticket marker is removed only when the source matches
    K-Dreams, mirroring the existing development prediction safety rule.
    Unknown odds are never inferred.
    """
    raw = (((race_data.get("odds") or {}).get("trifecta")) or {})
    if not isinstance(raw, dict):
        return {}, {
            "policy": "kdreams_9999_9_unbet_as_unavailable",
            "source_matched": False,
            "ignored_combos": [],
            "known_odds_count": 0,
        }

    context = race_data.get("prediction_context") or {}
    source = str(context.get("source") or "") if isinstance(context, dict) else ""
    source_matched = bool(_KDREAMS.search(source))
    clean: dict[str, float] = {}
    ignored: list[str] = []
    cars = {str(int(p["car_number"])) for p in race_data.get("players", [])}

    for key, raw_value in raw.items():
        parts = str(key).split("-")
        if len(parts) != 3 or len(set(parts)) != 3 or not set(parts) <= cars:
            continue
        if isinstance(raw_value, bool):
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(value) or value <= 0:
            continue
        if source_matched and value == 9999.9:
            ignored.append(str(key))
            continue
        clean[str(key)] = value

    return clean, {
        "policy": "kdreams_9999_9_unbet_as_unavailable",
        "source_matched": source_matched,
        "source": source,
        "ignored_combos": sorted(ignored),
        "known_odds_count": len(clean),
    }
