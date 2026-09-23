from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from model_contract import FEATURES, feature_row


def readiness_report(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    materialized = list(rows)
    race_ids = {str(row.get("race_id") or "") for row in materialized if row.get("race_id")}
    feature_counts = {name: 0 for name in FEATURES}
    styles: Counter[str] = Counter()

    for row in materialized:
        encoded = feature_row(row)
        for name, value in encoded.items():
            if value is not None:
                feature_counts[name] += 1
        if row.get("style"):
            styles[str(row["style"])] += 1

    total = len(materialized)
    coverage = {
        name: (feature_counts[name] / total if total else 0.0)
        for name in FEATURES
    }
    targets = {
        target: sum(int(row.get(target) or 0) for row in materialized)
        for target in ("target_first", "target_second", "target_third", "target_top3")
    }

    return {
        "eligible_unique_races": len(race_ids),
        "rider_rows": total,
        "feature_non_null_counts": feature_counts,
        "feature_non_null_coverage": coverage,
        "style_counts": dict(styles),
        "target_positive_counts": targets,
        "statistical_sufficiency_assessed": False,
        "promotion_ready": False,
        "note": (
            "This report describes observed prospective data coverage only. "
            "It does not assert a minimum sufficient sample size or approve a model for promotion."
        ),
    }
