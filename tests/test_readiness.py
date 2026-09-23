from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

from readiness import readiness_report  # noqa: E402


def test_readiness_report_describes_coverage_without_claiming_promotion_readiness():
    rows = [
        {
            "race_id": "r1",
            "car_number": 1,
            "style": "逃",
            "race_score": 100,
            "S": 1,
            "H": 3,
            "B": 4,
            "line_position": 1,
            "line_length": 2,
            "is_line_leader": 1,
            "target_first": 1,
            "target_second": 0,
            "target_third": 0,
            "target_top3": 1,
        },
        {
            "race_id": "r1",
            "car_number": 2,
            "style": "追",
            "race_score": 98,
            "S": 0,
            "H": 0,
            "B": 0,
            "line_position": 2,
            "line_length": 2,
            "is_line_leader": 0,
            "target_first": 0,
            "target_second": 1,
            "target_third": 0,
            "target_top3": 1,
        },
    ]
    report = readiness_report(rows)
    assert report["eligible_unique_races"] == 1
    assert report["rider_rows"] == 2
    assert report["style_counts"] == {"逃": 1, "追": 1}
    assert report["target_positive_counts"]["target_first"] == 1
    assert report["feature_non_null_coverage"]["race_score"] == 1.0
    assert report["statistical_sufficiency_assessed"] is False
    assert report["promotion_ready"] is False
    assert "does not assert" in report["note"]


if __name__ == "__main__":
    test_readiness_report_describes_coverage_without_claiming_promotion_readiness()
    print("readiness checks: PASS")
