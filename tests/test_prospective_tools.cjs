'use strict';

const assert = require('assert');
const { permutations } = (() => {
  function permutations(values) {
    const out = [];
    for (const a of values) for (const b of values) for (const c of values) {
      if (a !== b && a !== c && b !== c) out.push(`${a}-${b}-${c}`);
    }
    return out;
  }
  return { permutations };
})();
const tools = require('../prospective-tools-core.js');

const COMBOS = permutations([1,2,3,4,5,6,7]);

function snapshot(i = 0, source = 'WINTICKET') {
  const captured = new Date(Date.UTC(2026, 8, 24, 0 + i, 0, 0));
  const scheduled = new Date(captured.getTime() + 30 * 60 * 1000);
  const players = Array.from({length: 7}, (_, index) => {
    const car = index + 1;
    return {
      car_number: car,
      style: car === 2 ? '両' : (car === 1 || car === 7 ? '逃' : '追'),
      race_score: 78 + car,
      S: car,
      H: car === 1 || car === 7 ? car : 0,
      B: car === 1 || car === 7 ? car : 0,
      line_id: `L${car}`,
      line_position: 1,
      line_length: 1,
    };
  });
  const known = Object.fromEntries(COMBOS.slice(0, 72).map((combo, index) => [combo, 10 + index]));
  const categories = Object.fromEntries(
    ['hit_priority','balance','middle','longshot','super_longshot'].map((key, index) => [key, {picks:[{combo_key: COMBOS[index]}]}])
  );
  return {
    schema_version: 'prediction-snapshot-v1',
    captured_at: captured.toISOString(),
    validation_mode: 'prospective-only',
    snapshot_eligibility: {
      prospective: true,
      reason: 'before_scheduled_start',
      scheduled_start: scheduled.toISOString(),
      prestart_confirmed: true,
      clock_source: 'client_unverified',
    },
    race_data: {
      race: {date: '2026-09-24', venue: 'TEST', race_number: i + 1, scheduled_start_jst: scheduled.toISOString()},
      players,
      odds: {trifecta: known},
      prediction_context: {source, known_odds_count: 72},
    },
    engine_response: {
      success: true,
      service_version: 'test-v1',
      architecture: {engine: tools.ENGINE_VERSION},
      engine_candidate: tools.ENGINE_VERSION,
      saved: false,
      db_write_enabled: false,
      production_prediction_enabled: false,
      input_quality: {trifecta_odds_count: 72, possible_trifecta_count: 210, trifecta_odds_coverage: 72/210},
      odds_sanitization: {policy:'kdreams_9999_9_unbet_as_unavailable', source_matched:false, ignored_combos:[]},
      probability_calibration_status: 'uncalibrated',
      monetary_ev_enabled: false,
      odds_band_ranking: 'estimated_probability_only',
      prediction: {
        trifecta_scores: COMBOS.map((combo) => ({combo_key:combo, estimated_probability:1/210, odds:known[combo] ?? null})),
        selected_predictions: {probability_calibration_status:'uncalibrated', monetary_ev_enabled:false, odds_band_ranking:'estimated_probability_only', categories},
      },
    },
  };
}

function history(i) {
  const snap = snapshot(i);
  const captured = new Date(snap.captured_at);
  return tools.buildHistory(snap, {
    outcomeCombo: `${1 + (i % 5)}-${2 + (i % 5)}-${3 + (i % 5)}`,
    settlementOdds: 39.3 + i,
    resultTimestamp: new Date(captured.getTime() + 40 * 60 * 1000).toISOString(),
  });
}

(function testHistoryBuildPreservesPartialOddsAndSafety() {
  const snap = snapshot(0);
  const record = tools.buildHistory(snap, {
    outcomeCombo: '3-4-7',
    settlementOdds: 39.3,
    resultTimestamp: '2026-09-24T17:31:54+09:00',
  });
  assert.strictEqual(record.outcome_combo, '3-4-7');
  assert.strictEqual(record.settlement_odds, 39.3);
  assert.strictEqual(record.trifecta_scores.length, 210);
  assert.strictEqual(Object.keys(record.training_input.odds.trifecta).length, 72);
  assert.strictEqual(record.metadata.training_eligibility.supervised_training, true);
  assert.strictEqual(record.metadata.evaluation_scope, 'prospective');
  const serializedTraining = JSON.stringify(record.training_input);
  assert(!serializedTraining.includes('outcome_combo'));
  assert(!serializedTraining.includes('settlement_odds'));
})();

(function testNaiveResultTimestampRejected() {
  assert.throws(() => tools.buildHistory(snapshot(0), {
    outcomeCombo: '3-4-7', settlementOdds: 39.3, resultTimestamp: '2026-09-24T17:31:54'
  }), /result_timestamp_timezone_missing/);
})();

(function testResultBeforeScheduledStartRejected() {
  const snap = snapshot(0);
  assert.throws(() => tools.buildHistory(snap, {
    outcomeCombo: '3-4-7',
    settlementOdds: 39.3,
    resultTimestamp: new Date(new Date(snap.captured_at).getTime() + 10 * 60 * 1000).toISOString(),
  }), /result_confirmation_before_scheduled_start/);
})();

(function testCaptureAtOrAfterScheduledStartRejected() {
  const snap = snapshot(0);
  snap.snapshot_eligibility.scheduled_start = snap.captured_at;
  snap.race_data.race.scheduled_start_jst = snap.captured_at;
  assert.throws(() => tools.validateSnapshot(snap), /snapshot_capture_not_before_scheduled_start/);
})();

(function testMismatchedScheduledStartRejected() {
  const snap = snapshot(0);
  snap.race_data.race.scheduled_start_jst = new Date(Date.parse(snap.snapshot_eligibility.scheduled_start) + 60 * 1000).toISOString();
  assert.throws(() => tools.validateSnapshot(snap), /scheduled_start_mismatch/);
})();

(function testKDreamsMarkerRemovedOnlyAsUnavailable() {
  const snap = snapshot(0, 'K-Dreams');
  const first = Object.keys(snap.race_data.odds.trifecta)[0];
  snap.race_data.odds.trifecta[first] = 9999.9;
  snap.engine_response.odds_sanitization.source_matched = true;
  snap.engine_response.odds_sanitization.ignored_combos = [first];
  const training = tools.buildTrainingInput(snap);
  assert(!(first in training.odds.trifecta));
  assert(training.odds_sanitization.removed_combos.includes(first));
})();

(function testCollectionReadinessUsesChronologicalPartitions() {
  const records = [0,1,2,3,4].map(history);
  const status = tools.collectionStatus(records);
  assert.strictEqual(status.eligible_unique_races, 5);
  assert.strictEqual(status.distinct_prediction_times, 5);
  assert.strictEqual(status.remaining_distinct_prediction_times, 0);
  assert.strictEqual(status.chronological_evaluation_may_run, true);
  assert.strictEqual(status.split.train_races, 3);
  assert.strictEqual(status.split.validation_races, 1);
  assert.strictEqual(status.split.test_races, 1);
  assert.strictEqual(status.known_trifecta_odds_count.min, 72);
})();

(function testCollectionAuditRejectsImpossibleScheduleOrder() {
  const record = history(0);
  record.metadata.result_timestamp = new Date(Date.parse(record.prediction_timestamp) + 10 * 60 * 1000).toISOString();
  const status = tools.collectionStatus([record]);
  assert.strictEqual(status.eligible_unique_races, 0);
  assert.strictEqual(status.excluded.invalid_schedule_order, 1);
})();

(function testBoundaryPurgeCanStillBlockFiveTimes() {
  const records = [0,1,2,3,4].map(history);
  records[0].metadata.result_timestamp = records[4].metadata.result_timestamp;
  records[3].metadata.result_timestamp = records[4].metadata.result_timestamp;
  const status = tools.collectionStatus(records);
  assert.strictEqual(status.collection_threshold_met, true);
  assert.strictEqual(status.chronological_evaluation_may_run, false);
  assert.strictEqual(status.blocked_reason, 'insufficient_non_overlapping_partitions');
})();

(function testEnvelopeRoundTrip() {
  const record = history(0);
  const envelope = tools.historyEnvelope(record);
  const records = tools.recordsFromJson(envelope);
  assert.strictEqual(records.length, 1);
  assert.strictEqual(records[0].race_id, record.race_id);
})();

console.log('prospective browser-local tools checks: PASS');
