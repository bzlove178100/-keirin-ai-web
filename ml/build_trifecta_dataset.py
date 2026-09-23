from __future__ import annotations

import argparse
import csv
import itertools
import json
from pathlib import Path
from typing import Any, Iterable

STYLE_KEYS = {"逃": "nige", "両": "ryo", "追": "oi"}

PLAYER_NUMERIC = ["race_score", "S", "H", "B", "line_position", "line_length"]

FEATURE_COLUMNS: list[str] = []
for prefix in ("first", "second", "third"):
    FEATURE_COLUMNS += [f"{prefix}_{name}" for name in PLAYER_NUMERIC]
    FEATURE_COLUMNS += [f"{prefix}_missing_{name}" for name in PLAYER_NUMERIC]
    FEATURE_COLUMNS += [
        f"{prefix}_style_nige",
        f"{prefix}_style_ryo",
        f"{prefix}_style_oi",
    ]

FEATURE_COLUMNS += [
    "first_second_same_line",
    "second_third_same_line",
    "all_same_line",
    "first_leader_second_follower",
    "second_leader_first_follower",
    "line_order_123",
    "race_score_first_minus_second",
    "race_score_second_minus_third",
    "race_score_first_minus_third",
    "race_score_sum",
    "S_sum",
    "H_sum",
    "B_sum",
]

META_COLUMNS = ["race_id", "prediction_timestamp", "combo_key", "prediction_odds"]
OUTPUT_COLUMNS = META_COLUMNS + FEATURE_COLUMNS + ["label"]


def _num(value: Any) -> tuple[float, int]:
    if value is None or value == "":
        return 0.0, 1
    try:
        return float(value), 0
    except (TypeError, ValueError):
        return 0.0, 1


def _extract_records(obj: Any) -> list[dict[str, Any]]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if not isinstance(obj, dict):
        return []
    if isinstance(obj.get("payload"), dict) and isinstance(obj["payload"].get("records"), list):
        return [x for x in obj["payload"]["records"] if isinstance(x, dict)]
    if isinstance(obj.get("records"), list):
        return [x for x in obj["records"] if isinstance(x, dict)]
    if "race_id" in obj and "outcome_combo" in obj:
        return [obj]
    return []


def load_records(paths: Iterable[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as f:
            records.extend(_extract_records(json.load(f)))
    return records


def is_supervised_eligible(record: dict[str, Any]) -> bool:
    metadata = record.get("metadata") or {}
    eligibility = metadata.get("training_eligibility") or {}
    training_input = record.get("training_input")
    return (
        metadata.get("evaluation_scope") == "prospective"
        and metadata.get("temporal_order") == "prediction_before_result"
        and eligibility.get("supervised_training") is True
        and isinstance(training_input, dict)
        and training_input.get("evaluation_scope") == "prospective"
        and isinstance(training_input.get("players"), list)
    )


def _player_features(prefix: str, player: dict[str, Any], row: dict[str, Any]) -> None:
    for name in PLAYER_NUMERIC:
        value, missing = _num(player.get(name))
        row[f"{prefix}_{name}"] = value
        row[f"{prefix}_missing_{name}"] = missing
    style_key = STYLE_KEYS.get(str(player.get("style", "")))
    row[f"{prefix}_style_nige"] = int(style_key == "nige")
    row[f"{prefix}_style_ryo"] = int(style_key == "ryo")
    row[f"{prefix}_style_oi"] = int(style_key == "oi")


def _same_line(a: dict[str, Any], b: dict[str, Any]) -> int:
    la, lb = a.get("line_id"), b.get("line_id")
    return int(la is not None and la == lb)


def record_to_rows(record: dict[str, Any]) -> list[dict[str, Any]]:
    if not is_supervised_eligible(record):
        return []

    training_input = record["training_input"]
    players = training_input.get("players") or []
    player_map: dict[int, dict[str, Any]] = {}
    for player in players:
        if not isinstance(player, dict):
            continue
        try:
            car = int(player.get("car_number"))
        except (TypeError, ValueError):
            continue
        player_map[car] = player

    if len(player_map) < 4:
        return []

    outcome = str(record.get("outcome_combo") or "")
    outcome_parts = outcome.split("-")
    if len(outcome_parts) != 3 or len(set(outcome_parts)) != 3:
        return []

    odds = ((training_input.get("odds") or {}).get("trifecta") or {})
    race_id = str(record.get("race_id") or "")
    prediction_timestamp = str(record.get("prediction_timestamp") or "")

    rows: list[dict[str, Any]] = []
    for a, b, c in itertools.permutations(sorted(player_map), 3):
        pa, pb, pc = player_map[a], player_map[b], player_map[c]
        combo_key = f"{a}-{b}-{c}"
        row: dict[str, Any] = {
            "race_id": race_id,
            "prediction_timestamp": prediction_timestamp,
            "combo_key": combo_key,
            "prediction_odds": odds.get(combo_key, ""),
            "label": int(combo_key == outcome),
        }
        _player_features("first", pa, row)
        _player_features("second", pb, row)
        _player_features("third", pc, row)

        fs = _same_line(pa, pb)
        st = _same_line(pb, pc)
        all_same = int(fs and st and pa.get("line_id") == pc.get("line_id"))
        row["first_second_same_line"] = fs
        row["second_third_same_line"] = st
        row["all_same_line"] = all_same

        first_pos = _num(pa.get("line_position"))[0]
        second_pos = _num(pb.get("line_position"))[0]
        third_pos = _num(pc.get("line_position"))[0]
        row["first_leader_second_follower"] = int(fs and first_pos == 1 and second_pos == 2)
        row["second_leader_first_follower"] = int(fs and first_pos == 2 and second_pos == 1)
        row["line_order_123"] = int(all_same and first_pos == 1 and second_pos == 2 and third_pos == 3)

        r1 = row["first_race_score"]
        r2 = row["second_race_score"]
        r3 = row["third_race_score"]
        row["race_score_first_minus_second"] = r1 - r2
        row["race_score_second_minus_third"] = r2 - r3
        row["race_score_first_minus_third"] = r1 - r3
        row["race_score_sum"] = r1 + r2 + r3
        row["S_sum"] = row["first_S"] + row["second_S"] + row["third_S"]
        row["H_sum"] = row["first_H"] + row["second_H"] + row["third_H"]
        row["B_sum"] = row["first_B"] + row["second_B"] + row["third_B"]
        rows.append(row)

    positives = sum(int(r["label"]) for r in rows)
    if positives != 1:
        return []
    return rows


def build_dataset(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    eligible = [r for r in records if is_supervised_eligible(r)]
    eligible.sort(key=lambda r: (str(r.get("prediction_timestamp") or ""), str(r.get("race_id") or "")))

    rows: list[dict[str, Any]] = []
    accepted_races = 0
    skipped_after_eligibility = 0
    group_sizes: list[int] = []
    for record in eligible:
        race_rows = record_to_rows(record)
        if not race_rows:
            skipped_after_eligibility += 1
            continue
        rows.extend(race_rows)
        group_sizes.append(len(race_rows))
        accepted_races += 1

    manifest = {
        "schema_version": "trifecta-ranking-dataset-v1",
        "model_target": "rank_true_trifecta_above_other_ordered_triples",
        "uses_prediction_time_odds_as_feature": False,
        "feature_columns": FEATURE_COLUMNS,
        "input_records": len(records),
        "eligible_records": len(eligible),
        "accepted_races": accepted_races,
        "skipped_after_eligibility": skipped_after_eligibility,
        "rows": len(rows),
        "group_sizes": group_sizes,
        "positive_rows": sum(int(r["label"]) for r in rows),
        "notes": [
            "Only explicit prospective pre-result records marked supervised_training=true are included.",
            "Prediction-time odds are retained as metadata only and excluded from model features.",
            "Replay/legacy records are excluded from supervised training.",
        ],
    }
    return rows, manifest


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build leakage-safe trifecta ranking rows from backtest records.")
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=Path("ml/data/trifecta_ranking.csv"))
    parser.add_argument("--manifest", type=Path, default=Path("ml/data/trifecta_ranking.manifest.json"))
    args = parser.parse_args()

    records = load_records(args.inputs)
    rows, manifest = build_dataset(records)
    write_csv(rows, args.output)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
