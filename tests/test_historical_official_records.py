"""Synthetic data only; exercise identity, chronology and review boundaries."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from agent_core.historical_preparation import run_preparation
from ml.historical_official_records import convert, join
from ml.historical_training import digest, prepare
from tests.test_historical_official_detail import blocks, page, receipt


def pair(n=7, edit_pre=None, edit_result=None):
    ph, pp = blocks(n, "pre")
    rh, rp = blocks(n)
    if edit_pre:
        edit_pre(ph, pp)
    if edit_result:
        edit_result(rh, rp)
    pre, result = page(ph, pp, "pre"), page(rh, rp)
    return {"pre_bytes": pre, "pre_receipt": receipt(pre, "pre"),
            "result_bytes": result, "result_receipt": receipt(result),
            "race_date": "2026-01-02", "venue_code": "35", "race_number": 1}


class OfficialRecordTests(unittest.TestCase):
    def test_three_to_nine_riders_preserve_raw_without_inventing_features(self):
        for count in range(3, 10):
            with self.subTest(count=count):
                args = pair(count)
                original = copy.deepcopy(args)
                r = join(**args)
                self.assertEqual(args, original)
                self.assertEqual(r["rider_count"], count)
                self.assertEqual(r["pre_race_features"][0]["style"], "追")
                self.assertEqual(r["pre_race_features"][0]["race_score"], 85.1)
                self.assertIsNone(r["pre_race_features"][0]["S"])
                raw = r["source_observations"]["pre"]["raw_blocks"]["PJ0315"]["sensyuTypeInfo"][0]
                self.assertEqual(raw["stTori"], "2")
                self.assertEqual(raw["futureSourceField"], {"preserve": True})
                self.assertFalse(r["training_approved"])
                self.assertFalse(r["prospective"])

    def test_matching_pre_known_withdrawal_changes_only_candidate_population(self):
        def pre(h, p):
            p["sensyuTypeInfo"][6]["ketujyouTuikaHojyu"] = "(欠場)"
        def result(h, p):
            p["tyakujyunItemSubData"][6].update(tyaku="", kojinStateItemSubData=[{"kojinState": "欠場"}])
            p["haraiGakuSubData"].update(APartReturnDispFlg=True, APartReturn="一部返還")
        r = join(**pair(edit_pre=pre, edit_result=result))
        self.assertEqual(r["rider_count"], 6)
        self.assertEqual(r["listed_rider_count"], 7)
        self.assertEqual(r["pre_race_withdrawn_cars"], [7])
        self.assertEqual(len(r["source_observations"]["pre"]["summary"]["rider_rows"]), 7)

    def test_result_only_withdrawal_is_not_backdated(self):
        def result(h, p):
            p["tyakujyunItemSubData"][6].update(tyaku="", kojinStateItemSubData=[{"kojinState": "欠場"}])
        with self.assertRaisesRegex(ValueError, "withdrawal_changed"):
            join(**pair(edit_result=result))

    def test_retirement_is_retained_as_starter_without_invented_finish(self):
        def result(h, p):
            p["tyakujyunItemSubData"][6].update(tyaku="", kojinStateItemSubData=[{"kojinState": "落車棄権"}])
        r = join(**pair(edit_result=result))
        self.assertEqual(r["actual_starters"], 7)
        self.assertIsNone(r["source_observations"]["result"]["summary"]["rider_rows"][6]["finish_position"])

    def test_unknown_nonfinisher_cannot_become_training_negative(self):
        def result(h, p):
            p["tyakujyunItemSubData"][6].update(tyaku="", kojinStateItemSubData=[{"kojinState": "未知"}])
        with self.assertRaisesRegex(ValueError, "starter_classification"):
            join(**pair(edit_result=result))

    def test_dead_heat_preserves_source_references_and_is_not_single_label(self):
        def result(h, p):
            p["tyakujyunItemSubData"][1]["tyaku"] = "1"
            payouts = p["haraiGakuSubData"]
            payouts["ST2HaraiGakuDispItemSubData"].append({"kumiBan": "2-1", "haraiGaku": "410", "kumiDispFlg": True})
            payouts["RT3HaraiGakuDispItemSubData"].append({"kumiBan": "2-1-3", "haraiGaku": "1,200", "kumiDispFlg": True})
        args = pair(edit_result=result)
        report = convert([args])
        self.assertEqual(report["records"], [])
        q = report["quarantined_records"][0]
        self.assertEqual(q["reason"], "dead_heat_requires_multilabel_contract")
        self.assertEqual(q["capture_hashes"]["result"], args["result_receipt"]["sha256"])

    def test_noncontiguous_ranks_require_review(self):
        def result(h, p):
            p["tyakujyunItemSubData"][6]["tyaku"] = "9"
        with self.assertRaisesRegex(ValueError, "noncontiguous_finish"):
            join(**pair(edit_result=result))

    def test_matching_internal_blocks_but_different_cross_capture_identity(self):
        def result(h, p):
            h["C0201data"]["C0201racedtl"]["C0201sensyu"][0]["numPlayer"] = "999999"
            p["tyakujyunItemSubData"][0]["sensyuRegistNo"] = "999999"
        with self.assertRaisesRegex(ValueError, "cross_capture_rider_identity"):
            join(**pair(edit_result=result))

    def test_changed_name_with_same_registration_id_requires_review(self):
        def result(h, p):
            p["tyakujyunItemSubData"][0]["sensyuName"] = "Different synthetic name"
        with self.assertRaisesRegex(ValueError, "cross_capture_rider_identity"):
            join(**pair(edit_result=result))

    def test_updated_start_cannot_backdate_pre_capture(self):
        def result(h, p):
            h["C0201data"]["C0201racedtl"].update(bfrStartTime="08:00", aftStartTime="08:00")
        with self.assertRaisesRegex(ValueError, "all_observed_starts"):
            join(**pair(edit_result=result))

    def test_receipt_mismatch_and_late_features_rejected(self):
        args = pair()
        args["pre_receipt"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "receipt_mismatch"):
            join(**args)
        args = pair()
        args["pre_receipt"] = receipt(args["pre_bytes"], "result")
        with self.assertRaisesRegex(ValueError, "not_before"):
            join(**args)

    def test_duplicate_pair_rejected_and_invalid_pair_quarantined(self):
        with self.assertRaisesRegex(ValueError, "duplicate_capture_pair"):
            convert([pair(), pair()])
        bad = pair()
        bad["pre_receipt"]["sha256"] = "0" * 64
        report = convert([bad])
        self.assertEqual(report["summary"]["quarantined_pairs"], 1)
        self.assertEqual(report["records"], [])

    def test_source_and_exact_record_reviews_still_required(self):
        report = convert([pair()])
        r = report["records"][0]
        self.assertEqual(report["record_hashes"][r["race_id"]], digest(r))
        plan = prepare(report["records"], [], "2026-02-01T00:00:00Z", "2026-03-01T00:00:00Z")
        self.assertEqual(plan["partition_counts"], {"train": 0, "validation": 0, "test": 0})
        self.assertIn("training_use_unconfirmed", plan["excluded"][0]["reasons"])
        self.assertIn("review_missing_or_record_changed", plan["excluded"][0]["reasons"])

    def test_shared_agent_accepts_output_and_completed_resume_does_not_repeat(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            records, reviews = root / "records.json", root / "reviews.json"
            records.write_text(json.dumps(convert([pair()])))
            reviews.write_text("[]")
            args = (records, reviews, root / "run", "2026-02-01T00:00:00Z", "2026-03-01T00:00:00Z")
            first, resumed = run_preparation(*args), run_preparation(*args)
            self.assertEqual(first["outcome"]["status"], "completed")
            self.assertEqual(first["preparation_sha256"], resumed["preparation_sha256"])
            self.assertEqual(resumed["outcome"]["executed_steps"], ())
            self.assertEqual(first["excluded_records"], 1)
            self.assertEqual(first["training_runs"], 0)


if __name__ == "__main__":
    unittest.main()
