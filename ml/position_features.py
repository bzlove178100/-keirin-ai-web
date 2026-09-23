from __future__ import annotations

import math
from typing import Any

NUMERIC_FEATURES = [
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

STYLE_FEATURES = ["style_nige", "style_ryo", "style_oi"]
FEATURE_COLUMNS = NUMERIC_FEATURES + STYLE_FEATURES
TARGET_COLUMNS = ["target_first", "target_second", "target_third"]


def _float_or_nan(value: Any) -> float:
    if value is None or value == "":
        return math.nan
    try:
        result = float(value)
    except (TypeError, ValueError):
        return math.nan
    return result if math.isfinite(result) else math.nan


def row_to_features(row: dict[str, Any]) -> list[float]:
    values = [_float_or_nan(row.get(name)) for name in NUMERIC_FEATURES]
    style = str(row.get("style") or "")
    values.extend([
        1.0 if style == "逃" else 0.0,
        1.0 if style == "両" else 0.0,
        1.0 if style == "追" else 0.0,
    ])
    return values
