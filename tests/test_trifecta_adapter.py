from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

from trifecta_adapter import combine_position_probabilities, validate_trifecta_table  # noqa: E402


def position_maps():
    riders = range(1, 8)
    first = {r: (0.90 if r == 1 else 0.05) for r in riders}
    second = {r: (0.90 if r == 2 else 0.05) for r in riders}
    third = {r: (0.90 if r == 3 else 0.05) for r in riders}
    return first, second, third


def test_seven_riders_produce_exactly_210_unique_normalized_combinations():
    first, second, third = position_maps()
    rows = combine_position_probabilities(first, second, third)
    validation = validate_trifecta_table(rows, 7)

    assert validation["expected_combinations"] == 210
    assert validation["actual_combinations"] == 210
    assert validation["unique_combinations"] == 210
    assert validation["combination_count_ok"] is True
    assert validation["unique_ok"] is True
    assert validation["probability_mass_ok"] is True
    assert abs(float(validation["probability_mass"]) - 1.0) <= 1e-12
    assert all(len(set(row["combo"])) == 3 for row in rows)
    assert all(row["probability_calibration_status"] == "uncalibrated" for row in rows)


def test_position_specific_signal_maps_to_expected_top_combo():
    first, second, third = position_maps()
    rows = combine_position_probabilities(first, second, third)
    assert rows[0]["combo_key"] == "1-2-3"
    assert float(rows[0]["estimated_probability"]) > float(rows[1]["estimated_probability"])


def test_mismatched_rider_sets_are_rejected():
    first, second, third = position_maps()
    third.pop(7)
    try:
        combine_position_probabilities(first, second, third)
    except ValueError as exc:
        assert "rider set" in str(exc)
    else:
        raise AssertionError("mismatched rider sets must fail")


def test_zero_mass_is_rejected_instead_of_inventing_probabilities():
    riders = range(1, 8)
    zeros = {r: 0.0 for r in riders}
    try:
        combine_position_probabilities(zeros, zeros, zeros)
    except ValueError as exc:
        assert "zero or invalid trifecta mass" in str(exc)
    else:
        raise AssertionError("zero probability mass must fail")


if __name__ == "__main__":
    test_seven_riders_produce_exactly_210_unique_normalized_combinations()
    test_position_specific_signal_maps_to_expected_top_combo()
    test_mismatched_rider_sets_are_rejected()
    test_zero_mass_is_rejected_instead_of_inventing_probabilities()
    print("trifecta adapter checks: PASS")
