from __future__ import annotations

import math
from itertools import permutations
from typing import Mapping

ADAPTER_VERSION = "position-probability-to-trifecta-v1"


def _clean_probabilities(values: Mapping[int, float], riders: set[int], label: str) -> dict[int, float]:
    if set(values) != riders:
        raise ValueError(f"{label} rider set does not match")
    cleaned: dict[int, float] = {}
    for rider, raw in values.items():
        value = float(raw)
        if not math.isfinite(value) or value < 0 or value > 1:
            raise ValueError(f"{label}[{rider}] must be a finite probability in [0, 1]")
        cleaned[int(rider)] = value
    return cleaned


def combine_position_probabilities(
    first: Mapping[int, float],
    second: Mapping[int, float],
    third: Mapping[int, float],
) -> list[dict[str, object]]:
    """Convert rider-level position probabilities into an ordered-trifecta table.

    The product is an uncalibrated combination score. It is normalized across all
    valid ordered triples so the returned mass is exactly one (within floating
    precision). The normalized value is a model-candidate probability estimate,
    not a claim of calibration.
    """
    riders = {int(x) for x in first}
    if len(riders) < 3:
        raise ValueError("at least three riders are required")

    p1 = _clean_probabilities(first, riders, "first")
    p2 = _clean_probabilities(second, riders, "second")
    p3 = _clean_probabilities(third, riders, "third")

    raw_rows: list[tuple[tuple[int, int, int], float]] = []
    for a, b, c in permutations(sorted(riders), 3):
        score = p1[a] * p2[b] * p3[c]
        raw_rows.append(((a, b, c), score))

    total = sum(score for _, score in raw_rows)
    if not math.isfinite(total) or total <= 0:
        raise ValueError("position probabilities produce zero or invalid trifecta mass")

    rows: list[dict[str, object]] = []
    for combo, score in raw_rows:
        probability = score / total
        rows.append(
            {
                "combo": list(combo),
                "combo_key": "-".join(str(x) for x in combo),
                "model_score": score,
                "estimated_probability": probability,
                "probability_calibration_status": "uncalibrated",
                "adapter_version": ADAPTER_VERSION,
            }
        )

    rows.sort(
        key=lambda row: (
            -float(row["estimated_probability"]),
            str(row["combo_key"]),
        )
    )
    return rows


def validate_trifecta_table(rows: list[dict[str, object]], rider_count: int) -> dict[str, object]:
    expected = rider_count * (rider_count - 1) * (rider_count - 2)
    keys = [str(row.get("combo_key")) for row in rows]
    mass = sum(float(row.get("estimated_probability", 0.0)) for row in rows)
    return {
        "expected_combinations": expected,
        "actual_combinations": len(rows),
        "unique_combinations": len(set(keys)),
        "probability_mass": mass,
        "combination_count_ok": len(rows) == expected,
        "unique_ok": len(set(keys)) == expected,
        "probability_mass_ok": abs(mass - 1.0) <= 1e-12,
        "calibration_status": "uncalibrated",
        "adapter_version": ADAPTER_VERSION,
    }
