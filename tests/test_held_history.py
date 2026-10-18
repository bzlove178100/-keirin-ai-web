from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
from test_settle_snapshot import snapshot
from settle_snapshot import build_history_record
from held_history import build_held_history, validate_held_history, partition_holds
from dataset import build_rows, supervised_eligibility
from evaluation_protocol import prepare
from collection_status import collection_status


class HeldHistoryTest(unittest.TestCase):
    def setUp(self):
        # Generated values only. The label exercises the ordinary collection parser.
        self.snap = snapshot(source="fixture")
        self.snap["race_data"]["race"]["venue"] = "GENERATED TEST"
        self.settlement = {"result_status": "dead_heat", "result_timestamp": "2026-09-24T07:00:00Z"}

    def normal(self, snap=None):
        return build_history_record(snap or self.snap, outcome_combo="1-2-3",
                                    settlement_odds=42, result_timestamp="2026-09-24T07:00:00Z")

    def test_js_python_contract_and_batch_exclusion(self):
        cases = []
        for count in (7, 9):
            snap = snapshot(source="fixture", rider_count=count)
            snap["race_data"]["race"]["venue"] = "GENERATED TEST"
            for status in ("dead_heat", "withdrawn", "cancelled"):
                event = {**self.settlement, "result_status": status}
                if status == "withdrawn":
                    event["withdrawn_car_numbers"] = [count]
                held = build_held_history(snap, event)
                validate_held_history(held)
                self.assertNotIn("outcome_combo", held)
                self.assertNotIn("training_input", held)
                for records in ([self.normal(snap), held], [held, self.normal(snap)], [held, held, self.normal(snap)]):
                    rows, summary = build_rows(iter(records))
                    self.assertEqual(rows, [])
                    self.assertEqual(summary["excluded"]["race_has_held_result"], 1)
                    selected, quality = prepare(records)
                    self.assertEqual(selected, [])
                    self.assertEqual(quality["held_unique_races"], 1)
                    report = collection_status(records)
                    self.assertEqual(report["eligible_unique_races"], 0)
                    self.assertFalse(report["chronological_evaluation_may_run"])
                cases.append({"snapshot": snap, "settlement": event, "held": held, "normal": self.normal(snap)})
        script = """
const fs=require('fs'),assert=require('assert/strict'),core=require('./prospective-tools-core.js');
for(const c of JSON.parse(fs.readFileSync(0,'utf8'))){
 const held=core.buildHeldHistory(c.snapshot,c.settlement);assert.deepEqual(held,c.held);
 assert.equal(core.validateHeldHistory(c.held),true);
 for(const records of [[held,c.normal],[c.normal,held],[held,held,c.normal]]){
  const result=core.collectionStatus(core.recordsFromJson(core.historyEnvelope(records[0])).concat(records.slice(1)));
  assert.equal(result.eligible_unique_races,0);assert.equal(result.held_unique_races,1);
  assert.equal(result.excluded.race_has_held_result,1);
 }
 held.snapshot.race_data.players[0].name='changed';assert.equal(c.snapshot.race_data.players[0].name,undefined);
}
"""
        subprocess.run(["node", "-e", script], cwd=ROOT, input=json.dumps(cases), text=True, check=True)

    def test_timing_and_withdrawal_validation(self):
        early = "2026-09-24T02:00:00Z"  # after capture, before scheduled start
        for status in ("withdrawn", "cancelled"):
            event = {"result_status": status, "result_timestamp": early}
            if status == "withdrawn":
                event["withdrawn_car_numbers"] = [7]
            validate_held_history(build_held_history(self.snap, event))
        bad_events = [None, {}, {**self.settlement, "result_status": "normal"},
                      {**self.settlement, "outcome_combo": "1-2-3"},
                      {**self.settlement, "result_timestamp": early},
                      {**self.settlement, "result_timestamp": "2026-09-24T00:00:00Z"},
                      {**self.settlement, "result_timestamp": "2026-09-24T07:00:00"}]
        for cars in ([], [True], [7, 7], [9], ["7"], None, [0], [1.5]):
            bad_events.append({**self.settlement, "result_status": "withdrawn", "withdrawn_car_numbers": cars})
        for event in bad_events:
            with self.assertRaises((ValueError, TypeError)):
                build_held_history(self.snap, event)
        script = """
const fs=require('fs'),assert=require('assert/strict'),core=require('./prospective-tools-core.js');
const d=JSON.parse(fs.readFileSync(0,'utf8'));
for(const s of d.events)assert.throws(()=>core.buildHeldHistory(d.snapshot,s));
"""
        subprocess.run(["node", "-e", script], cwd=ROOT, input=json.dumps({"snapshot": self.snap, "events": bad_events}), text=True, check=True)

    def test_tampered_holds_never_suppress_unrelated_or_normal_records(self):
        held = build_held_history(self.snap, self.settlement)
        other = self.normal()
        other["race_id"] = "OTHER GENERATED RACE"
        self.assertEqual(collection_status([held, self.normal(), other])["eligible_race_ids"], [other["race_id"]])
        for key, value in (("race_id", "OTHER"), ("evaluation_eligible", True),
                           ("db_write_enabled", 0), ("outcome_combo", "1-2-3"),
                           ("prediction_timestamp", "2026-09-24T00:00:00Z")):
            bad = {**held, key: value}
            with self.assertRaises(ValueError):
                validate_held_history(bad)
            kept, excluded, ids = partition_holds([bad, self.normal()])
            self.assertEqual(len(kept), 1)
            self.assertEqual(excluded, {"invalid_held_record": 1})
            self.assertEqual(ids, [])

    def test_malformed_identity_does_not_crash_batch(self):
        held = build_held_history(self.snap, self.settlement)
        selected, quality = prepare([held, {"race_id": {}}, None])
        self.assertEqual(selected, [])
        self.assertEqual(quality["held_unique_races"], 1)

    def test_direct_nonstandard_annotations_cannot_be_training_labels(self):
        for location in ("root", "metadata"):
            for change in ({"result_status": "cancelled"}, {"result_status": None},
                           {"dead_heat": True}, {"trifecta_outcomes": ["1-2-3", "2-1-3"]}):
                record = self.normal()
                (record if location == "root" else record["metadata"]).update(change)
                self.assertFalse(supervised_eligibility(record)[0])
                self.assertEqual(build_rows([record])[0], [])
                self.assertEqual(prepare([record])[0], [])
        good = self.normal()
        good["metadata"]["result_status"] = "normal"
        self.assertTrue(supervised_eligibility(good)[0])


if __name__ == "__main__":
    unittest.main()
