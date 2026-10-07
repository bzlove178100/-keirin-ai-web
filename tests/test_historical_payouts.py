import copy
import csv
import tempfile
import unittest
from pathlib import Path

from ml.historical_payouts import load_csv, normalize
from ml.historical_training import digest


def fixture(count=7):
    key = "20200101_synthetic1"
    info = [{"Race_ID": key, "Date": "20200101", "Venue": "synthetic",
             "Race_Number": "1", "Unit": str(count), "Race_Status": "held"}]
    results = [{"Race_ID": key, "Car": str(i), "Player_ID": str(90000+i),
                "Rank": str(i), "Status": ""} for i in range(1, count+1)]
    payoffs = [{"Race_ID": key, "Bet_Type": bet, "Outcome": combo, "Payout": amount}
               for bet, combo, amount in (("2車単", "1月2日", "410"), ("3連単", "2001/2/3", "1,550"))]
    return info, results, payoffs


class HistoricalPayoutTests(unittest.TestCase):
    def test_conversion_preserves_raw_and_does_not_approve_training(self):
        original = fixture()
        before = copy.deepcopy(original)
        report = normalize(*original)
        row = report["records"][0]
        self.assertEqual(row["settlements"]["3連単"]["outcomes"], [{"combination": [1,2,3], "payout_yen":1550}])
        self.assertEqual(row["raw"]["payoffs"][1]["Outcome"], "2001/2/3")
        self.assertEqual(original, before)
        self.assertFalse(row["training_approved"])
        self.assertFalse(row["external_source_verified"])
        self.assertIsNone(row["feature_as_of"])
        self.assertEqual(report["summary"]["training_runs"], 0)
        self.assertEqual(row["candidate_sha256"], digest({k:v for k,v in row.items() if k != "candidate_sha256"}))

    def test_literal_outcomes_need_no_date_repair(self):
        info, results, payoffs = fixture(9)
        payoffs[0]["Outcome"], payoffs[1]["Outcome"] = "1-2", "1-2-3"
        row = normalize(info, results, payoffs)["records"][0]
        self.assertEqual(row["settlements"]["3連単"]["changes"], [])
        self.assertEqual(row["actual_starters"], 9)

    def test_wrong_date_like_combination_is_not_repaired_from_label(self):
        info, results, payoffs = fixture()
        payoffs[1]["Outcome"] = "2001/3/2"
        row = normalize(info, results, payoffs)["records"][0]
        self.assertEqual(row["normalization_status"], "quarantined")
        self.assertNotIn("settlements", row)
        self.assertIn("payout_disagrees_with_finish_order", row["reasons"])

    def test_unknown_formats_and_amounts_stay_quarantined(self):
        for field, value in (("Outcome","2021/2/3"),("Outcome","01/02/03"),
                             ("Outcome","2001/1/3"),("Payout","NaN"),
                             ("Payout","0"),("Payout","1,55"),("Payout","-10")):
            info, results, payoffs = fixture()
            payoffs[1][field] = value
            self.assertEqual(normalize(info, results, payoffs)["records"][0]["normalization_status"], "quarantined")

    def test_second_place_tie_requires_all_paid_orders(self):
        info, results, payoffs = fixture()
        results[2]["Rank"] = "2"
        payoffs.extend([{**payoffs[0], "Outcome":"1月3日"}, {**payoffs[1], "Outcome":"2001/3/2"}])
        row = normalize(info, results, payoffs)["records"][0]
        self.assertEqual(row["settlements"]["3連単"]["status"], "dead_heat")
        self.assertEqual([p["combination"] for p in row["settlements"]["3連単"]["outcomes"]], [[1,2,3],[1,3,2]])
        self.assertEqual(normalize(info, results, payoffs[:-1])["records"][0]["normalization_status"], "quarantined")

    def test_third_place_tie_leaves_exacta_ordinary(self):
        info, results, payoffs = fixture()
        results[3]["Rank"] = "3"
        payoffs.append({**payoffs[1], "Outcome":"2001/2/4"})
        row = normalize(info, results, payoffs)["records"][0]
        self.assertEqual(row["settlements"]["2車単"]["status"], "ordinary")
        self.assertEqual(len(row["settlements"]["3連単"]["outcomes"]), 2)

    def test_first_place_tie_keeps_both_orders(self):
        info, results, payoffs = fixture()
        results[1]["Rank"] = "1"
        payoffs.extend([{**payoffs[0], "Outcome":"2月1日"}, {**payoffs[1], "Outcome":"2002/1/3"}])
        row = normalize(info, results, payoffs)["records"][0]
        self.assertEqual(row["settlements"]["2車単"]["status"], "dead_heat")
        self.assertEqual(len(row["settlements"]["3連単"]["outcomes"]), 2)

    def test_refund_is_not_a_zero_payout_or_invented_third_place(self):
        info, results, payoffs = fixture(5)
        for row in results[2:]: row.update(Rank="",Status="落車")
        payoffs[1].update(Outcome="全返還",Payout="全返還")
        row = normalize(info, results, payoffs)["records"][0]
        self.assertEqual(row["settlements"]["3連単"], {"status":"full_refund","outcomes":[],"changes":[]})
        self.assertEqual(row["settlements"]["2車単"]["status"], "ordinary")
        self.assertEqual(row["actual_starters"], 5)

    def test_insufficient_finishers_need_explicit_refund_evidence(self):
        info, results, payoffs = fixture()
        for row in results[2:]: row.update(Rank="",Status="失格")
        self.assertEqual(normalize(info, results, payoffs)["records"][0]["normalization_status"], "quarantined")

    def test_fault_abbreviation_and_dns_remain_distinct(self):
        info, results, payoffs = fixture()
        results[-1].update(Rank="",Status="欠場")
        results[-2].update(Rank="故",Status="")
        row = normalize(info, results, payoffs)["records"][0]
        self.assertEqual([r["status"] for r in row["participants"][-2:]], ["DNF","DNS"])
        self.assertEqual(row["actual_starters"], 6)
        self.assertEqual(len(row["result_status_changes"]), 1)

    def test_invalid_rank_gap_status_or_identity_rejected(self):
        mutations = [lambda r:r[0].update(Rank="2"), lambda r:r[0].update(Status="unknown"),
                     lambda r:r[0].update(Status="欠場"),lambda r:r[0].update(Car="2"),
                     lambda r:r[0].update(Player_ID=r[1]["Player_ID"])]
        for mutate in mutations:
            info, results, payoffs = fixture()
            mutate(results)
            self.assertEqual(normalize(info, results, payoffs)["records"][0]["normalization_status"], "quarantined")

    def test_info_count_prevents_missing_terminal_finisher(self):
        info, results, payoffs = fixture()
        self.assertIn("result_roster_incomplete", normalize(info, results[:-1], payoffs)["records"][0]["reasons"])

    def test_conflicting_or_cancelled_info_and_orphan_rows_rejected(self):
        for field, value in (("Race_Status","cancelled"),("Date","20200230"),("Venue","elsewhere")):
            info, results, payoffs = fixture()
            info[0][field] = value
            self.assertEqual(normalize(info, results, payoffs)["records"][0]["normalization_status"], "quarantined")
        info, results, payoffs = fixture()
        self.assertEqual(normalize([], results, payoffs)["records"][0]["normalization_status"], "quarantined")
        self.assertEqual(normalize(info+[{**info[0],"Unit":"6"}], results, payoffs)["records"][0]["normalization_status"], "quarantined")

    def test_identical_duplicates_dedup_but_conflicting_amount_blocks(self):
        info, results, payoffs = fixture()
        report = normalize(info*2, results*2, payoffs*2)
        self.assertEqual(report["summary"]["identical_duplicate_rows_ignored"], {"info":1,"results":7,"payoffs":2})
        self.assertEqual(report["records"][0]["normalization_status"], "internally_consistent_candidate")
        payoffs.append({**payoffs[1],"Payout":"900"})
        self.assertEqual(normalize(info, results, payoffs)["records"][0]["normalization_status"], "quarantined")

    def test_csv_blank_rows_are_counted_without_mutating_source(self):
        _, results, _ = fixture()
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/"results.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as f:
                writer=csv.DictWriter(f, fieldnames=list(results[0]))
                writer.writeheader(); writer.writerows(results); writer.writerow({})
            before = path.read_bytes()
            rows, receipt = load_csv(path, "results")
            self.assertEqual(rows, results)
            self.assertEqual(receipt["blank_rows_ignored"], 1)
            self.assertEqual(path.read_bytes(), before)
            path.write_text("Race_ID,Car,Player_ID,Rank,Status\nx,1,2,1,,extra\n")
            with self.assertRaises(ValueError): load_csv(path, "results")


if __name__ == "__main__":
    unittest.main()
