"""Offline, hash-pinned reconciliation of Shonan Bank's ordered-payout list.

This reads previously saved bytes only. It neither fetches nor trains, changes
the pre-race source snapshot, verifies full results, nor grants training approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from ml.historical_training import digest, timestamp


class _Node:
    def __init__(self, tag="", attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def nodes(self, tag=None):
        for child in self.children:
            if isinstance(child, _Node):
                if tag is None or child.tag == tag:
                    yield child
                yield from child.nodes(tag)

    def text(self):
        return "".join(c.text() if isinstance(c, _Node) else c for c in self.children)

    def has_class(self, value):
        return value in self.attrs.get("class", "").split()


class _HTML(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node()
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def _compact(value):
    return "".join(value.split())


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _ordered(outcome_cell, money_cell, length):
    combos = [_compact(n.text()) for n in outcome_cell.nodes("div") if n.has_class("b")]
    amounts = [_compact(n.text()) for n in money_cell.nodes("div") if n.has_class("pb")]
    if not combos or len(combos) != len(amounts):
        raise ValueError("ordered_payout_column_mismatch")
    # Do not silently discard newly introduced text or unfamiliar markup.
    if _compact(outcome_cell.text()) != "".join(combos) or _compact(money_cell.text()) != "".join(amounts):
        raise ValueError("unrecognized_payout_content")
    entries = []
    for combo, amount in zip(combos, amounts):
        if not re.fullmatch(r"[1-9](?:-[1-9]){" + str(length-1) + "}", combo):
            raise ValueError("exceptional_or_invalid_outcome_requires_review")
        cars = [int(c) for c in combo.split("-")]
        if len(set(cars)) != length:
            raise ValueError("repeated_car_in_outcome")
        if not re.fullmatch(r"(?:[1-9][0-9]{0,2}(?:,[0-9]{3})+|[1-9][0-9]*)円", amount):
            raise ValueError("invalid_payout_yen")
        entries.append({"cars": cars, "payout_yen": int(amount[:-1].replace(",", ""))})
    if len({tuple(e["cars"]) for e in entries}) != len(entries):
        raise ValueError("duplicate_outcome_requires_review")
    return entries


def parse_result_list(raw: bytes, race_date: str) -> list[dict]:
    """Parse desktop rows only; preserve exceptional/partial rows as quarantines.

    Mobile duplicate tables are deliberately excluded. Missing headers, duplicate
    race keys or no matching dated rows fail instead of looking like empty data.
    """
    if not isinstance(raw, bytes) or len(raw) > 5_000_000:
        raise ValueError("invalid_html_bytes_or_size")
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", race_date):
        raise ValueError("invalid_race_date")
    parser = _HTML()
    parser.feed(raw.decode("utf-8-sig", errors="strict"))
    parser.close()
    records, seen = [], set()
    for table in parser.root.nodes("table"):
        if not table.has_class("pc-only"):
            continue
        rows = list(table.nodes("tr"))
        headers = [_compact(n.text()) for row in rows[:2] for n in row.children
                   if isinstance(n, _Node) and n.tag in ("td", "th")]
        matching = [row for row in rows if any(n.attrs.get("data-name") == race_date.replace("-", "")
                                                  for n in row.nodes("input"))]
        if not matching:
            continue
        if headers != ["R", "2車単", "3連単", "組番", "払戻金", "組番", "払戻金"]:
            raise ValueError("result_table_header_changed")
        for row in matching:
            inputs = [n for n in row.nodes("input") if n.attrs.get("data-name") == race_date.replace("-", "")]
            if len(inputs) != 1:
                raise ValueError("ambiguous_race_button")
            number = inputs[0].attrs.get("data-race", "")
            if not re.fullmatch(r"(?:[1-9]|1[0-2])", number) or inputs[0].attrs.get("value") != number + "R":
                raise ValueError("invalid_race_number")
            race_number = int(number)
            if race_number in seen:
                raise ValueError("duplicate_desktop_race")
            seen.add(race_number)
            cells = [n for n in row.children if isinstance(n, _Node) and n.tag == "td"]
            if len(cells) != 5:
                raise ValueError("result_table_columns_changed")
            observed = [_compact(n.text()) for n in cells[1:]]
            record = {"race_date": race_date, "race_number": race_number, "raw_cells": observed,
                      "exacta": [], "trifecta": [], "status": "pending", "issues": []}
            if any(observed):
                try:
                    record["exacta"] = _ordered(cells[1], cells[2], 2)
                    record["trifecta"] = _ordered(cells[3], cells[4], 3)
                    if {tuple(e["cars"]) for e in record["exacta"]} != {tuple(e["cars"][:2]) for e in record["trifecta"]}:
                        raise ValueError("exacta_trifecta_disagree")
                    record["status"] = "ordered_payouts_observed"
                except ValueError as exc:
                    record["status"] = "quarantined"
                    record["issues"].append(str(exc))
            records.append(record)
    if not records:
        raise ValueError("no_matching_dated_result_rows")
    return sorted(records, key=lambda r: r["race_number"])


def reconcile(snapshot_bytes: bytes, result_bytes: bytes, receipt: dict, expected_snapshot_sha256: str) -> dict:
    """Join exact local race keys with temporal/roster checks; retain the baseline."""
    if _sha(snapshot_bytes) != expected_snapshot_sha256:
        raise ValueError("snapshot_hash_mismatch")
    if receipt.get("sha256") != _sha(result_bytes) or receipt.get("bytes") != len(result_bytes):
        raise ValueError("result_receipt_hash_or_size_mismatch")
    if receipt.get("status") != 200:
        raise ValueError("unsuccessful_result_capture")
    requested = timestamp(receipt.get("request_started_at"))
    observed = timestamp(receipt.get("download_completed_at"))
    if requested > observed:
        raise ValueError("invalid_capture_chronology")
    snapshot = json.loads(snapshot_bytes)
    if snapshot.get("schema_version") != "keirin-official-pre-race-source-observation-v1":
        raise ValueError("unsupported_snapshot_schema")
    races = snapshot.get("races")
    if not isinstance(races, list) or not races:
        raise ValueError("snapshot_races_missing")
    dates = {r["race_date"] for r in races}
    if len(dates) != 1:
        raise ValueError("mixed_snapshot_dates")
    race_date = next(iter(dates))
    for field in ("url", "final_url"):
        url = urlparse(receipt.get(field, ""))
        if (url.scheme != "https" or url.netloc != "www.shonanbank.com"
                or url.path.rstrip("/") != "/race-result-list"
                or parse_qs(url.query).get("race_start") != [race_date.replace("-", "")]):
            raise ValueError("unexpected_result_source_or_date")
    results = parse_result_list(result_bytes, race_date)
    inputs = {}
    for race in races:
        original = {k: v for k, v in race.items() if k != "record_sha256_without_hash_field"}
        if race.get("record_sha256_without_hash_field") != digest(original):
            raise ValueError("snapshot_record_hash_mismatch")
        n = race["race_number"]
        if type(n) is not int or not 1 <= n <= 12 or n in inputs:
            raise ValueError("duplicate_or_invalid_snapshot_race")
        if race.get("venue_key") != "hiratsuka" or race.get("race_id") != race_date.replace("-", "") + "_hiratsuka" + str(n):
            raise ValueError("snapshot_venue_or_key_mismatch")
        inputs[n] = race
    if set(inputs) != {r["race_number"] for r in results}:
        raise ValueError("result_race_set_mismatch")
    joined, candidates = [], []
    for result in results:
        race = inputs[result["race_number"]]
        item = {**result, "race_id": race["race_id"],
                "pre_race_record_sha256": race["record_sha256_without_hash_field"],
                "result_source_sha256": receipt["sha256"],
                "result_observed_at": receipt["download_completed_at"],
                "full_finish_order_verified": False, "withdrawals_and_disqualifications_verified": False}
        if item["status"] == "ordered_payouts_observed":
            try:
                source_time = timestamp(race.get("source_observed_at_jst"))
                capture_time = timestamp(snapshot["capture"]["pdf"]["download_completed_at"])
                start = timestamp(race.get("listed_scheduled_start_jst"))
                if not source_time == capture_time < start <= observed:
                    raise ValueError("invalid_source_result_chronology")
                riders = race["riders"]
                cars = [r["car_number"] for r in riders]
                if (len(cars) != race.get("rider_count_as_printed") or not 3 <= len(cars) <= 9
                        or any(type(c) is not int or not 1 <= c <= 9 for c in cars) or len(cars) != len(set(cars))):
                    raise ValueError("invalid_snapshot_roster")
                if any(not set(e["cars"]).issubset(cars) for e in item["trifecta"] + item["exacta"]):
                    raise ValueError("outcome_not_in_pre_race_roster")
                features = []
                for rider in riders:
                    score = float(rider["score_as_printed"])
                    if not math.isfinite(score) or not 0 <= score <= 150:
                        raise ValueError("invalid_printed_score")
                    features.append({"car_number": rider["car_number"], "style": None, "race_score": score,
                                     "S": None, "H": None, "B": None})
                candidate = {
                    "race_id": race["race_id"], "race_date": race_date, "venue": "平塚",
                    "race_number": race["race_number"], "rider_count": len(cars),
                    "riders": [{"car_number": r["car_number"], "name": r["name_as_printed"]} for r in riders],
                    "listed_scheduled_start_jst": race["listed_scheduled_start_jst"],
                    "feature_as_of": race["source_observed_at_jst"],
                    "result_available_at": receipt["download_completed_at"],
                    "result_time_basis": "known_available_by_capture_completion_not_exact_publication_time",
                    "trifecta_outcomes": [e["cars"] for e in item["trifecta"]],
                    "trifecta_payouts_yen": [e["payout_yen"] for e in item["trifecta"]],
                    "pre_race_features": features, "dead_heat": None,
                    "pre_race_state_verified": False, "training_use_status": "unconfirmed", "prospective": False,
                    "sources": [snapshot["capture"]["pdf"]["url"], receipt["final_url"]],
                    "lineage": {"snapshot_file_sha256": expected_snapshot_sha256,
                                "pre_race_record_sha256": item["pre_race_record_sha256"],
                                "result_source_sha256": receipt["sha256"]},
                    "remaining": ["full_result_and_status_verification", "confirmed_pre_race_style",
                                  "source_use_and_feature_review", "final_record_hash_review"],
                }
                candidates.append(candidate)
                item["status"] = "joined_ordered_payouts"
                item["review_candidate_sha256"] = digest(candidate)
            except (ValueError, KeyError, TypeError, OverflowError) as exc:
                item["status"] = "quarantined"
                item["issues"].append(str(exc))
        joined.append(item)
    return {"schema_version": "official-ordered-result-reconciliation-v1",
            "input_snapshot_sha256": expected_snapshot_sha256,
            "result_source_sha256": receipt["sha256"], "result_observed_at": receipt["download_completed_at"],
            "counts": dict(Counter(r["status"] for r in joined)), "observations": joined,
            "review_candidates": candidates, "source_snapshot_modified": False,
            "training_eligible_races": 0, "training_runs": 0, "automatic_collection_enabled": False,
            "production_enabled": False,
            "limitations": ["Ordered payouts do not verify the full finish order, withdrawals or all dead heats.",
                            "Observation time is not the exact official publication timestamp.",
                            "No pre-race prediction probabilities or odds snapshot is created.",
                            "Candidates require a separate final-record review; no prior approval transfers."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("results", type=Path)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--snapshot-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = reconcile(args.snapshot.read_bytes(), args.results.read_bytes(),
                       json.loads(args.receipt.read_text()), args.snapshot_sha256)
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")
    print(json.dumps(result["counts"]))


if __name__ == "__main__":
    main()
