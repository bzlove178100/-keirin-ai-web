"""Offline, auditable payout normalization. Never approves historical training.

Known spreadsheet date conversions are candidates only and must agree with the
complete supplied finish ranks. Internal agreement is not external verification.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from itertools import permutations, product
from pathlib import Path

from ml.historical_training import digest

WIDTHS = {"2車単": 2, "3連単": 3}
NONFINISH = {"欠場": "DNS", "落車": "DNF", "故障": "DNF", "失格": "DSQ"}
REQUIRED = {
    "info": {"Race_ID", "Date", "Venue", "Race_Number", "Unit", "Race_Status"},
    "results": {"Race_ID", "Car", "Player_ID", "Rank", "Status"},
    "payoffs": {"Race_ID", "Bet_Type", "Outcome", "Payout"},
}


def load_csv(path: Path, kind: str) -> tuple[list[dict], dict]:
    data = path.read_bytes()
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    header = reader.fieldnames or []
    if len(header) != len(set(header)) or not REQUIRED[kind].issubset(header):
        raise ValueError("invalid_csv_header")
    rows, blank = [], 0
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("invalid_csv_row_width")
        if not any(value.strip() for value in row.values()):
            blank += 1
            continue
        if any(not row[field].strip() for field in REQUIRED[kind] - {"Rank", "Status"}):
            raise ValueError("required_csv_value_missing")
        rows.append(row)
    return rows, {"kind": kind, "filename": path.name,
                  "sha256": hashlib.sha256(data).hexdigest(),
                  "nonempty_rows": len(rows), "blank_rows_ignored": blank}


def _car(value: str) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"[1-9]", value):
        raise ValueError("invalid_car_or_rank")
    return int(value)


def _result_groups(rows: list[dict]) -> tuple[list[list[int]], list[dict], list[dict]]:
    if not 3 <= len(rows) <= 9:
        raise ValueError("result_roster_size_invalid")
    cars, ids, ranks, participants, changes = set(), set(), defaultdict(list), [], []
    for row in rows:
        car = _car(row["Car"])
        identity = row["Player_ID"]
        if not isinstance(identity, str) or not re.fullmatch(r"[0-9]+", identity):
            raise ValueError("player_identity_missing")
        if car in cars or identity in ids:
            raise ValueError("duplicate_car_or_player_result")
        cars.add(car)
        ids.add(identity)
        rank, status = row["Rank"], row["Status"]
        if rank == "故" and status == "":
            rank, status = "", "故障"
            changes.append({"field": "Rank/Status", "original": ["故", ""],
                            "normalized": [None, "DNF"], "car_number": car,
                            "rule": "explicit_fault_abbreviation", "source_row_sha256": digest(row)})
        if status == "":
            rank = _car(rank)
            if rank > len(rows):
                raise ValueError("rank_outside_roster")
            ranks[rank].append(car)
            state = "FINISHED"
        elif status in NONFINISH and rank == "":
            rank, state = None, NONFINISH[status]
        else:
            raise ValueError("unknown_or_conflicting_finish_status")
        participants.append({"car_number": car, "rider_id": "keirindb:" + identity,
                             "finish_rank": rank, "status": state})
    expected, groups = 1, []
    for rank, group in sorted(ranks.items()):
        if rank != expected:
            raise ValueError("incomplete_or_invalid_competition_ranks")
        expected += len(group)
        groups.append(sorted(group))
    return groups, sorted(participants, key=lambda r: r["car_number"]), changes


def _outcomes(groups: list[list[int]], width: int) -> set[tuple[int, ...]]:
    """Permute only tied groups needed for the requested finishing positions."""
    if sum(map(len, groups)) < width:
        return set()
    choices, remaining = [], width
    for group in groups:
        if remaining <= 0:
            break
        take = min(remaining, len(group))
        choices.append(list(permutations(group, take)))
        remaining -= take
    return {tuple(car for part in parts for car in part) for parts in product(*choices)}


def _parse_ordered(raw: str, width: int) -> tuple[tuple[int, ...], str]:
    rule = "literal_ordered_combination"
    if re.fullmatch(r"[1-9](?:-[1-9]){" + str(width - 1) + "}", raw):
        cars = tuple(map(int, raw.split("-")))
    elif width == 2 and (match := re.fullmatch(r"([1-9])月([1-9])日", raw)):
        cars = tuple(map(int, match.groups()))
        rule = "date_like_exacta_candidate"
    elif width == 3 and (match := re.fullmatch(r"200([1-9])/([1-9])/([1-9])", raw)):
        cars = tuple(map(int, match.groups()))
        rule = "date_like_trifecta_candidate"
    else:
        raise ValueError("unsupported_ordered_outcome_format")
    if len(set(cars)) != width:
        raise ValueError("duplicate_car_in_outcome")
    return cars, rule


def _money(raw: str) -> int:
    if not re.fullmatch(r"(?:[1-9][0-9]*|[1-9][0-9]{0,2}(?:,[0-9]{3})+)", raw):
        raise ValueError("invalid_payout_amount")
    return int(raw.replace(",", ""))


def _settlement(rows: list[dict], groups: list[list[int]], width: int) -> dict:
    expected = _outcomes(groups, width)
    if not rows:
        raise ValueError("ordered_payout_missing")
    if not expected:
        if len(rows) == 1 and rows[0]["Outcome"] == rows[0]["Payout"] == "全返還":
            return {"status": "full_refund", "outcomes": [], "changes": []}
        raise ValueError("insufficient_finishers_without_explicit_full_refund")
    found, outcomes, changes = set(), [], []
    for row in rows:
        combination, rule = _parse_ordered(row["Outcome"], width)
        if combination not in expected:
            raise ValueError("payout_disagrees_with_finish_order")
        if combination in found:
            raise ValueError("duplicate_payout_outcome")
        amount = _money(row["Payout"])
        found.add(combination)
        outcomes.append({"combination": list(combination), "payout_yen": amount})
        if rule != "literal_ordered_combination":
            changes.append({"field": "Outcome", "original": row["Outcome"],
                            "normalized": "-".join(map(str, combination)), "rule": rule,
                            "source_row_sha256": digest(row)})
    if found != expected:
        raise ValueError("missing_tied_payout_outcome")
    return {"status": "dead_heat" if len(expected) > 1 else "ordinary",
            "outcomes": sorted(outcomes, key=lambda x: x["combination"]), "changes": changes}


def normalize(info: list[dict], results: list[dict], payoffs: list[dict]) -> dict:
    grouped = {name: defaultdict(list) for name in ("info", "results", "payoffs")}
    duplicates = Counter()
    for name, rows in (("info", info), ("results", results), ("payoffs", payoffs)):
        seen = set()
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("Race_ID"), str) or not row["Race_ID"].strip():
                raise ValueError("race_id_missing")
            fingerprint = digest(row)
            if fingerprint in seen:
                duplicates[name] += 1
                continue
            seen.add(fingerprint)
            grouped[name][row["Race_ID"]].append(row)
    output = []
    for key in sorted(set().union(*(set(g) for g in grouped.values()))):
        info_rows = grouped["info"][key]
        result_rows, payoff_rows = grouped["results"][key], grouped["payoffs"][key]
        # Canonical raw values retain every input column; originals are never modified.
        raw = {"info": info_rows, "results": result_rows, "payoffs": payoff_rows}
        item = {"race_id": key, "raw": raw, "raw_sha256": digest(raw),
                "normalization_status": "quarantined", "reasons": [],
                "external_source_verified": False, "training_approved": False,
                "feature_as_of": None, "result_available_at": None,
                "pre_race_state_verified": False, "pre_race_features": [], "prospective": False}
        try:
            if len(info_rows) != 1:
                raise ValueError("missing_or_conflicting_race_info")
            metadata = info_rows[0]
            if metadata["Race_Status"] != "held":
                raise ValueError("held_race_required")
            if not re.fullmatch(r"[0-9]{8}", metadata["Date"]):
                raise ValueError("invalid_race_date")
            race_date = datetime.strptime(metadata["Date"], "%Y%m%d").date().isoformat()
            if not re.fullmatch(r"[1-9]|1[0-2]", metadata["Race_Number"]):
                raise ValueError("invalid_race_number")
            if key != metadata["Date"] + "_" + metadata["Venue"] + metadata["Race_Number"]:
                raise ValueError("race_identity_disagrees_with_metadata")
            if _car(metadata["Unit"]) != len(result_rows):
                raise ValueError("result_roster_incomplete")
            groups, participants, changes = _result_groups(result_rows)
            settlements = {bet: _settlement([r for r in payoff_rows if r["Bet_Type"] == bet], groups, width)
                           for bet, width in WIDTHS.items()}
            item.update(normalization_status="internally_consistent_candidate",
                        race_date=race_date, venue=metadata["Venue"], race_number=int(metadata["Race_Number"]),
                        participants=participants, finish_order_groups=groups,
                        listed_result_roster_count=len(participants),
                        actual_starters=sum(p["status"] != "DNS" for p in participants),
                        settlements=settlements, result_status_changes=changes)
        except (ValueError, TypeError, KeyError) as exc:
            item["reasons"].append(str(exc))
        item["candidate_sha256"] = digest(item)
        output.append(item)
    return {"schema_version": "historical-payout-candidates-v1", "records": output,
            "summary": {"unique_races": len(output),
                        "normalization_status_counts": dict(Counter(r["normalization_status"] for r in output)),
                        "identical_duplicate_rows_ignored": dict(duplicates),
                        "trifecta_settlement_counts": dict(Counter(r["settlements"]["3連単"]["status"]
                            for r in output if "settlements" in r)),
                        "external_source_verified_races": 0, "training_eligible_races": 0,
                        "training_runs": 0},
            "production_enabled": False, "automatic_collection_enabled": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--info", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--payoffs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    info, info_source = load_csv(args.info, "info")
    results, result_source = load_csv(args.results, "results")
    payoffs, payoff_source = load_csv(args.payoffs, "payoffs")
    report = normalize(info, results, payoffs)
    report["source_files"] = [info_source, result_source, payoff_source]
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
