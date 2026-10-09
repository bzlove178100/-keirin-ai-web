"""Offline, lossless intake of saved KEIRIN.JP race-card/result data blocks.

No JavaScript execution, requests, database writes, training or approval. Capture
receipts are operator-supplied evidence, not cryptographic source authentication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date
from html.parser import HTMLParser
from itertools import permutations
from pathlib import Path
from urllib.parse import urlparse

from ml.historical_training import digest, timestamp


class _Scripts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.scripts, self.current = [], None

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.current = []

    def handle_data(self, data):
        if self.current is not None:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.current is not None:
            self.scripts.append("".join(self.current))
            self.current = None


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("non_finite_json_value")


def _block(scripts, key):
    pattern = re.compile(r'(?m)^\s*jsonData\[["\']' + re.escape(key) + r'["\']\]\s*=\s*')
    matches = [(script, match) for script in scripts for match in pattern.finditer(script)]
    if len(matches) != 1:
        raise ValueError("missing_or_duplicate_data_block:" + key)
    script, match = matches[0]
    value, end = json.JSONDecoder(object_pairs_hook=_object, parse_constant=_constant).raw_decode(script[match.end():])
    if not script[match.end()+end:].lstrip().startswith(";") or not isinstance(value, dict):
        raise ValueError("invalid_data_assignment:" + key)
    if type(value.get("resultCd")) is not int or value["resultCd"] != 0:
        raise ValueError("source_data_error:" + key)
    return value


def _car(value):
    if type(value) is int and 1 <= value <= 9:
        return value
    if isinstance(value, str) and re.fullmatch(r"[1-9]", value):
        return int(value)
    raise ValueError("invalid_car_number")


def _identity(row, car_key, id_key):
    car, rider_id = _car(row.get(car_key)), row.get(id_key)
    if not isinstance(rider_id, str) or not re.fullmatch(r"[0-9]{6}", rider_id):
        raise ValueError("invalid_rider_id")
    return car, rider_id


def _ordered_payouts(payload, key, length, cars):
    rows = payload.get(key)
    if not isinstance(rows, list) or not rows:
        raise ValueError("ordered_payouts_missing")
    outcomes = []
    for row in rows:
        combo, amount = row.get("kumiBan", ""), row.get("haraiGaku", "")
        if (not isinstance(combo, str) or not re.fullmatch(r"[1-9](?:-[1-9]){"+str(length-1)+r"}", combo)
                or not isinstance(amount, str) or not re.fullmatch(r"(?:[1-9][0-9]{0,2}(?:,[0-9]{3})+|[1-9][0-9]*)", amount)
                or row.get("kumiDispFlg") is not True):
            raise ValueError("exceptional_payout_requires_review")
        values = [int(c) for c in combo.split("-")]
        if len(set(values)) != length or not set(values).issubset(cars):
            raise ValueError("invalid_payout_cars")
        outcomes.append({"cars": values, "payout_yen": int(amount.replace(",", ""))})
    if len({tuple(x["cars"]) for x in outcomes}) != len(outcomes):
        raise ValueError("duplicate_payout")
    return outcomes


def _tied_rank_outcomes(rows, width):
    """Rank-consistent prefixes only; never derive amounts or training labels.

    Support competition ranks (1, 1, 3), retaining other conventions for review.
    Expand only the required prefix: at most 9P3, not every complete ordering.
    """
    groups = {}
    for row in rows:
        rank = row["finish_position"]
        if rank is not None:
            groups.setdefault(rank, []).append(row["car_number"])
    expected_rank = 1
    for rank, cars in sorted(groups.items()):
        if rank != expected_rank:
            raise ValueError("nonstandard_tied_finish_ranks")
        expected_rank += len(cars)
    if expected_rank - 1 < width:
        raise ValueError("insufficient_ranked_finishers")
    prefixes = {()}
    for _, cars in sorted(groups.items()):
        remaining = width - len(next(iter(prefixes)))
        if remaining == 0:
            break
        suffixes = tuple(permutations(sorted(cars), min(len(cars), remaining)))
        prefixes = {prefix + suffix for prefix in prefixes for suffix in suffixes}
    return prefixes


def _scope(race_date, venue_code, race_number, mode):
    date.fromisoformat(race_date)
    if (not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", race_date)
            or not re.fullmatch(r"[0-9]{2}", venue_code)
            or type(race_number) is not int or not 1 <= race_number <= 12 or mode not in ("pre", "result")):
        raise ValueError("invalid_expected_scope")


def ingest(raw: bytes, receipt: dict, race_date: str, venue_code: str, race_number: int, mode: str) -> dict:
    """Pin saved HTML/scope; page-update labels never backdate the capture."""
    _scope(race_date, venue_code, race_number, mode)
    if not isinstance(raw, bytes) or len(raw) > 5_000_000:
        raise ValueError("invalid_capture_size")
    source_hash = hashlib.sha256(raw).hexdigest()
    if receipt.get("sha256") != source_hash or receipt.get("bytes") != len(raw) or receipt.get("status") != 200:
        raise ValueError("capture_receipt_mismatch")
    for field in ("url", "final_url"):
        u = urlparse(receipt.get(field, ""))
        if u.scheme != "https" or u.netloc != "keirin.jp" or u.path != "/pc/racelive" or u.query or u.fragment:
            raise ValueError("unexpected_source_url")
    observed = timestamp(receipt.get("download_completed_at"))
    if timestamp(receipt.get("request_started_at")) > observed:
        raise ValueError("invalid_capture_chronology")
    parser = _Scripts()
    parser.feed(raw.decode("utf-8-sig", errors="strict")); parser.close()
    header = _block(parser.scripts, "PC0201")
    block_name = "PJ0315" if mode == "pre" else "PJ0326"
    payload = _block(parser.scripts, block_name)
    return _observation(header, payload, source_hash, receipt["final_url"],
                        receipt["download_completed_at"], race_date, venue_code, race_number, mode)


def _observation(header, payload, source_hash, source_url, observed_at,
                 race_date, venue_code, race_number, mode):
    """Shared normalization after transport-specific receipt validation."""
    observed = timestamp(observed_at)
    block_name = "PJ0315" if mode == "pre" else "PJ0326"
    h = header["C0201data"]
    if (h.get("selKaisai") != race_date.replace("-", "") or h.get("selKjyoCd") != venue_code
            or type(h.get("selRaceNo")) is not int or h["selRaceNo"] != race_number):
        raise ValueError("race_identity_mismatch")
    detail = h["C0201racedtl"]
    start_values = [detail.get(k) for k in ("bfrStartTime", "aftStartTime")]
    if any(not isinstance(t, str) or not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", t) for t in start_values):
        raise ValueError("scheduled_start_missing")
    starts = [race_date + "T" + t + ":00+09:00" for t in start_values]
    if mode == "pre" and observed >= min(map(timestamp, starts)):
        raise ValueError("capture_not_before_listed_start")
    if mode == "result" and observed < max(map(timestamp, starts)):
        raise ValueError("result_before_listed_start")
    expected_rows = detail["C0201sensyu"]
    expected = dict(_identity(r, "carNum", "numPlayer") for r in expected_rows)
    if not 3 <= len(expected) <= 9 or len(expected) != len(expected_rows) or len(set(expected.values())) != len(expected):
        raise ValueError("invalid_header_roster")
    row_key = "sensyuTypeInfo" if mode == "pre" else "tyakujyunItemSubData"
    source_rows = payload.get(row_key)
    if not isinstance(source_rows, list) or not source_rows:
        raise ValueError("rider_rows_missing")
    seen, ids, rows, issues = set(), set(), [], []
    for source in source_rows:
        car, rider_id = _identity(source, "syaban", "sensyuRegistNo")
        if car in seen or rider_id in ids or expected.get(car) != rider_id:
            raise ValueError("duplicate_or_mismatched_rider")
        seen.add(car); ids.add(rider_id)
        row = {"car_number": car, "rider_id": rider_id, "name_as_observed": source.get("sensyuName")}
        if mode == "pre":
            row.update(style_as_observed=source.get("kyakusitu"),
                       score_as_observed=source.get("heikinTokuten"),
                       roster_note_as_observed=source.get("ketujyouTuikaHojyu", ""))
            if row["roster_note_as_observed"]:
                issues.append("pre_race_roster_note_requires_review")
        else:
            rank, states = source.get("tyaku"), source.get("kojinStateItemSubData")
            if not isinstance(states, list) or any(not isinstance(s, dict) for s in states):
                raise ValueError("result_status_missing")
            row.update(rank_as_observed=rank, states_as_observed=states,
                       finish_position=int(rank) if isinstance(rank, str) and re.fullmatch(r"[1-9]", rank) else None)
            row["withdrawn_as_observed"] = any(s.get("kojinState") == "欠場" for s in states)
            row["started_but_did_not_finish_as_observed"] = any(s.get("kojinState") in ("落車棄権", "事故棄権", "故障棄権") for s in states)
            # A disqualified rider's crossing order is not an awarded finish.
            # Only classify this narrow case with explicit crossing evidence;
            # missing/unknown evidence remains blocked, even alongside DNF.
            if any(s.get("kojinState") == "失格" for s in states):
                crossing = source.get("inLineJyuni")
                row["disqualified_as_observed"] = True
                row["crossing_order_as_observed"] = crossing
                row["disqualified_crossing_verified"] = (
                    isinstance(crossing, str) and re.fullmatch(r"[1-9]", crossing) is not None
                    and int(crossing) <= len(expected))
                if not row["disqualified_crossing_verified"]:
                    issues.append("disqualified_start_evidence_requires_review")
                if rank != "":
                    issues.append("contradictory_disqualification_and_finish")
                if row["withdrawn_as_observed"]:
                    issues.append("contradictory_withdrawal_and_disqualification")
                if row["started_but_did_not_finish_as_observed"] and row["disqualified_crossing_verified"]:
                    issues.append("contradictory_retirement_and_crossing")
            has_status = any(isinstance(s.get("kojinState"), str) and s["kojinState"].strip()
                             for s in states)
            if row["finish_position"] is None and not has_status:
                issues.append("unclassified_result_row")
            if row["withdrawn_as_observed"] and row["finish_position"] is not None:
                issues.append("contradictory_withdrawal_and_finish")
            if row["started_but_did_not_finish_as_observed"] and row["finish_position"] is not None:
                issues.append("contradictory_retirement_and_finish")
            if row["withdrawn_as_observed"] and row["started_but_did_not_finish_as_observed"]:
                issues.append("contradictory_withdrawal_and_retirement")
        rows.append(row)
    if seen != set(expected):
        raise ValueError("incomplete_detail_roster")
    summary = {"listed_rider_count": len(expected), "rider_rows": rows}
    if h.get("flgRaceCancel") is not False or h.get("flgSectionCancel") is not False:
        issues.append("cancellation_state_requires_review")
    if mode == "pre":
        if payload.get("syusouInfoExistFlg") != "1":
            issues.append("pre_race_data_not_confirmed")
        summary["captured_before_both_listed_starts"] = True
    else:
        if payload.get("tyakujyunDispFlg") is not True or payload.get("haraiGakuDispFlg") is not True:
            issues.append("result_display_not_confirmed")
        withdrawals = [r["car_number"] for r in rows if r["withdrawn_as_observed"]]
        ranks = [r["finish_position"] for r in rows if r["finish_position"] is not None]
        summary.update(withdrawn_cars=withdrawals, ranked_rider_count=len(ranks),
                       confirmed_starter_count=len(rows)-len(withdrawals) if all(r["finish_position"] is not None or r["withdrawn_as_observed"] or r["started_but_did_not_finish_as_observed"] or r.get("disqualified_crossing_verified", False) for r in rows) and not issues else None,
                       repeated_finish_ranks_observed=len(set(ranks)) != len(ranks),
                       weather_as_observed=payload.get("tenki"), wind_as_observed=payload.get("husoku"))
        payouts = payload.get("haraiGakuSubData", {})
        summary["partial_refund_as_observed"] = payouts.get("APartReturnDispFlg")
        summary["refund_note_as_observed"] = payouts.get("APartReturn")
        try:
            exacta = _ordered_payouts(payouts, "ST2HaraiGakuDispItemSubData", 2, seen)
            trifecta = _ordered_payouts(payouts, "RT3HaraiGakuDispItemSubData", 3, seen)
            if {tuple(e["cars"]) for e in exacta} != {tuple(e["cars"][:2]) for e in trifecta}:
                raise ValueError("ordered_payouts_disagree")
            if any(set(e["cars"]) & set(withdrawals) for e in trifecta):
                raise ValueError("withdrawn_car_in_payout")
            if len(ranks) == len(set(ranks)):
                top = [next((r["car_number"] for r in rows if r["finish_position"] == n), None) for n in (1,2,3)]
                if len(trifecta) != 1 or trifecta[0]["cars"] != top:
                    raise ValueError("finish_order_payout_disagree")
            else:
                expected_exacta = _tied_rank_outcomes(rows, 2)
                expected_trifecta = _tied_rank_outcomes(rows, 3)
                if ({tuple(e["cars"]) for e in exacta} != expected_exacta
                        or {tuple(e["cars"]) for e in trifecta} != expected_trifecta):
                    raise ValueError("tied_finish_order_payout_disagree")
            summary.update(exacta=exacta, trifecta=trifecta)
        except ValueError as exc:
            issues.append(str(exc))
    result = {"schema_version": "official-race-detail-observation-v1", "mode": mode,
              "race_date": race_date, "venue_code": venue_code, "race_number": race_number,
              "observed_at": observed_at, "listed_start_times_jst": starts,
              "source_sha256": source_hash, "source_url": source_url,
              "raw_blocks": {"PC0201": header, block_name: payload}, "summary": summary,
              "issues": sorted(set(issues)), "training_eligible": False, "training_runs": 0,
              "automatic_collection_enabled": False, "production_enabled": False,
              "time_basis": "local_capture_completion_not_page_last_update_label"}
    result["record_sha256_without_hash_field"] = digest(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path); parser.add_argument("receipt", type=Path)
    parser.add_argument("--date", required=True); parser.add_argument("--venue-code", required=True)
    parser.add_argument("--race-number", type=int, required=True)
    parser.add_argument("--mode", choices=("pre", "result"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = ingest(args.html.read_bytes(), json.loads(args.receipt.read_text()), args.date, args.venue_code, args.race_number, args.mode)
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(result, out, ensure_ascii=False, indent=2, allow_nan=False); out.write("\n")
    print(json.dumps({"race_number": result["race_number"], "issues": result["issues"], "training_eligible": False}))


if __name__ == "__main__":
    main()
