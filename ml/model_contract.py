from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

MODEL_FAMILY = "lightgbm-position-binary-v1"

# Initial candidate intentionally uses only pre-race, rider-level fields.
# Race-local identifiers such as line_id and post-race targets are excluded.
NUMERIC_FEATURES = [
    "car_number",
    "race_score",
    "S",
    "H",
    "B",
    "line_position",
    "line_length",
    "is_line_leader",
    "recent_win_rate",
    "recent_top2_rate",
    "recent_top3_rate",
    "recent_avg_finish",
    "current_meet_avg_finish",
    "condition_score",
    "bank_fit_score",
    "comment_condition",
    "comment_training",
    "comment_equipment",
    "comment_confidence",
    "comment_motivation",
    "comment_fatigue",
]

STYLE_MAP = {"逃": 0, "両": 1, "追": 2}
CATEGORICAL_FEATURES = ["style_code"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
TARGETS = {
    "first": "target_first",
    "second": "target_second",
    "third": "target_third",
}

FORBIDDEN_FEATURE_TOKENS = (
    "target_",
    "outcome",
    "settlement",
    "result_timestamp",
    "result_time",
)


def validate_feature_contract() -> list[str]:
    errors: list[str] = []
    if len(FEATURES) != len(set(FEATURES)):
        errors.append("duplicate feature names")
    for feature in FEATURES:
        lowered = feature.lower()
        if any(token in lowered for token in FORBIDDEN_FEATURE_TOKENS):
            errors.append(f"forbidden post-race/target feature: {feature}")
    if "line_id" in FEATURES:
        errors.append("line_id is race-local and must not be used as a persistent model feature")
    if "known_trifecta_odds_count" in FEATURES:
        errors.append("odds coverage is diagnostic and is excluded from the initial performance model")
    return errors


def encode_style(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return STYLE_MAP.get(str(value))


def feature_row(row: dict[str, Any]) -> dict[str, float | int | None]:
    values: dict[str, float | int | None] = {}
    for name in NUMERIC_FEATURES:
        raw = row.get(name)
        if raw is None or raw == "":
            values[name] = None
        else:
            try:
                values[name] = float(raw)
            except (TypeError, ValueError):
                values[name] = None
    values["style_code"] = encode_style(row.get("style"))
    return values


def _time_key(row: dict[str, Any]) -> float:
    value = row.get("prediction_timestamp") or row.get("date")
    if not isinstance(value, str) or not value:
        return float("-inf")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        try:
            return datetime.fromisoformat(value).timestamp()
        except ValueError:
            return float("-inf")


def time_group_split(
    rows: Iterable[dict[str, Any]],
    *,
    train_fraction: float,
    valid_fraction: float,
) -> dict[str, list[dict[str, Any]]]:
    """Chronological split by race; every rider from a race stays in one split.

    Fractions are engineering configuration only, not a statistical sufficiency or
    promotion threshold. At least three unique races are required structurally so
    train, validation, and test can all be non-empty.
    """
    if not (0 < train_fraction < 1):
        raise ValueError("train_fraction must be between 0 and 1")
    if not (0 < valid_fraction < 1):
        raise ValueError("valid_fraction must be between 0 and 1")
    if train_fraction + valid_fraction >= 1:
        raise ValueError("train_fraction + valid_fraction must be less than 1")

    materialized = list(rows)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in materialized:
        race_id = str(row.get("race_id") or "").strip()
        if not race_id:
            raise ValueError("every row must have race_id")
        grouped.setdefault(race_id, []).append(row)

    if len(grouped) < 3:
        raise ValueError("at least three unique races are required for a structural train/valid/test split")

    ordered_ids = sorted(
        grouped,
        key=lambda race_id: (
            min(_time_key(r) for r in grouped[race_id]),
            race_id,
        ),
    )
    n = len(ordered_ids)
    train_end = max(1, int(n * train_fraction))
    valid_count = max(1, int(n * valid_fraction))
    if train_end + valid_count >= n:
        valid_count = 1
        train_end = n - 2
    valid_end = train_end + valid_count

    ids = {
        "train": set(ordered_ids[:train_end]),
        "valid": set(ordered_ids[train_end:valid_end]),
        "test": set(ordered_ids[valid_end:]),
    }
    if not all(ids.values()):
        raise ValueError("train/valid/test must all contain at least one race")

    result: dict[str, list[dict[str, Any]]] = {"train": [], "valid": [], "test": []}
    for split_name, race_ids in ids.items():
        for race_id in ordered_ids:
            if race_id in race_ids:
                result[split_name].extend(grouped[race_id])
    return result


def split_race_ids(splits: dict[str, list[dict[str, Any]]]) -> dict[str, set[str]]:
    return {
        name: {str(row["race_id"]) for row in rows}
        for name, rows in splits.items()
    }
