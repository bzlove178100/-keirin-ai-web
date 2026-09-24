(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.ProspectiveTools = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const ENGINE_VERSION = 'phase32-hit-priority-all210-v1';
  const TRAINING_SCHEMA = 'keirin-training-input-v1';
  const OUTPUT_SCHEMA = 'backtest-record-v2';
  const CATEGORY_KEYS = ['hit_priority', 'balance', 'middle', 'longshot', 'super_longshot'];
  const AWARE_TIME = /(?:Z|[+-]\d{2}:\d{2})$/;
  const KDREAMS = /K[-\s]?Dreams|Kドリームス|ケイドリームス/i;

  function clone(value) {
    return value == null ? value : JSON.parse(JSON.stringify(value));
  }

  function fail(code) {
    const error = new Error(code);
    error.code = code;
    throw error;
  }

  function parseAwareTime(value, field) {
    if (typeof value !== 'string' || !value || !AWARE_TIME.test(value)) fail(`${field}_timezone_missing`);
    const ms = Date.parse(value);
    if (!Number.isFinite(ms)) fail(`${field}_invalid`);
    return ms;
  }

  function validCombo(value) {
    if (typeof value !== 'string' || !/^\d+-\d+-\d+$/.test(value)) return false;
    const parts = value.split('-');
    return parts.length === 3 && new Set(parts).size === 3;
  }

  function permutations3(cars) {
    const result = [];
    for (const a of cars) for (const b of cars) for (const c of cars) {
      if (a !== b && a !== c && b !== c) result.push(`${a}-${b}-${c}`);
    }
    return result;
  }

  function fullProbabilityTableValid(scores, cars) {
    const expected = new Set(permutations3(cars));
    if (!Array.isArray(scores) || scores.length !== expected.size) return false;
    const seen = new Set();
    let mass = 0;
    for (const row of scores) {
      const key = row && row.combo_key;
      const probability = row && row.estimated_probability;
      if (!expected.has(key) || seen.has(key) || typeof probability !== 'number' || !Number.isFinite(probability) || probability < 0 || probability > 1) return false;
      seen.add(key);
      mass += probability;
    }
    return seen.size === expected.size && Math.abs(mass - 1) <= 1e-6;
  }

  function categoriesValid(selected) {
    const categories = selected && selected.categories;
    if (!categories || typeof categories !== 'object' || Array.isArray(categories)) return false;
    for (const key of CATEGORY_KEYS) {
      const picks = categories[key] && categories[key].picks;
      if (!Array.isArray(picks) || picks.length > 3) return false;
      const keys = picks.map((pick) => pick && pick.combo_key);
      if (!keys.every(validCombo) || new Set(keys).size !== keys.length) return false;
    }
    return true;
  }

  function validateSnapshot(snapshot) {
    if (!snapshot || typeof snapshot !== 'object' || Array.isArray(snapshot)) fail('snapshot_required');
    if (snapshot.schema_version !== 'prediction-snapshot-v1') fail('snapshot_schema_mismatch');
    if (snapshot.validation_mode !== 'prospective-only') fail('snapshot_not_prospective_only');
    const eligibility = snapshot.snapshot_eligibility || {};
    if (eligibility.prospective !== true || eligibility.prestart_confirmed !== true) fail('snapshot_not_prospective');
    parseAwareTime(snapshot.captured_at, 'captured_at');

    const raceData = snapshot.race_data || {};
    const players = raceData.players;
    if (!Array.isArray(players) || players.length !== 7) fail('seven_riders_required');
    const cars = players.map((player) => player && player.car_number);
    if (new Set(cars).size !== 7 || !cars.every((car) => Number.isInteger(car) && car >= 1 && car <= 7)) fail('invalid_car_numbers');

    const engine = snapshot.engine_response || {};
    if (engine.success !== true) fail('engine_response_unsuccessful');
    if (engine.saved !== false || engine.db_write_enabled !== false) fail('snapshot_persistence_not_off');
    if (engine.production_prediction_enabled !== false) fail('production_prediction_must_be_off');
    const version = engine.engine_candidate || (engine.architecture || {}).engine;
    if (version !== ENGINE_VERSION) fail('engine_version_mismatch');
    const prediction = engine.prediction || {};
    if (!fullProbabilityTableValid(prediction.trifecta_scores, cars)) fail('full_probability_table_invalid');
    if (!categoriesValid(prediction.selected_predictions)) fail('selected_categories_invalid');
    return true;
  }

  function buildTrainingInput(snapshot) {
    const raceData = snapshot.race_data;
    const engine = snapshot.engine_response;
    const context = clone(raceData.prediction_context);
    const raw = clone(((raceData.odds || {}).trifecta) || {});
    const sanitization = engine.odds_sanitization || {};
    const ignored = new Set(Array.isArray(sanitization.ignored_combos) ? sanitization.ignored_combos : []);
    const source = context && typeof context === 'object' ? String(context.source || '') : '';
    const sourceMatched = KDREAMS.test(source);
    const removed = [];
    for (const key of Object.keys(raw)) {
      if (ignored.has(key) || (sourceMatched && Number(raw[key]) === 9999.9)) {
        delete raw[key];
        removed.push(key);
      }
    }
    return {
      schema_version: TRAINING_SCHEMA,
      captured_at: snapshot.captured_at,
      race: clone(raceData.race || {}),
      players: clone(raceData.players || []),
      odds: { trifecta: raw },
      prediction_context: context,
      odds_sanitization: {
        policy: sanitization.policy || 'snapshot_safety_filter',
        source_matched: sanitization.source_matched != null ? sanitization.source_matched : sourceMatched,
        removed_combos: [...new Set([...ignored, ...removed])].sort(),
      },
      evaluation_scope: 'prospective',
    };
  }

  function buildHistory(snapshot, settlement) {
    validateSnapshot(snapshot);
    const outcomeCombo = settlement && settlement.outcomeCombo;
    if (!validCombo(outcomeCombo)) fail('outcome_combo_invalid');
    const settlementOdds = Number(settlement && settlement.settlementOdds);
    if (!Number.isFinite(settlementOdds) || settlementOdds <= 0) fail('settlement_odds_invalid');
    const captured = parseAwareTime(snapshot.captured_at, 'captured_at');
    const resultTimestamp = settlement && settlement.resultTimestamp;
    const settled = parseAwareTime(resultTimestamp, 'result_timestamp');
    if (captured >= settled) fail('prediction_must_precede_result_confirmation');

    const raceData = snapshot.race_data;
    const race = raceData.race || {};
    const cars = new Set((raceData.players || []).map((player) => Number(player.car_number)));
    const outcomeCars = outcomeCombo.split('-').map(Number);
    if (!outcomeCars.every((car) => cars.has(car))) fail('outcome_not_in_riders');

    const engine = snapshot.engine_response;
    const prediction = engine.prediction;
    const trainingInput = buildTrainingInput(snapshot);
    const sourceSnapshot = {
      schema_version: snapshot.schema_version || null,
      validation_mode: snapshot.validation_mode || 'legacy',
      snapshot_eligibility: clone(snapshot.snapshot_eligibility || null),
      captured_at: snapshot.captured_at,
      engine_service_version: engine.service_version || null,
      engine_version: engine.engine_candidate || (engine.architecture || {}).engine || null,
      probability_calibration_status: engine.probability_calibration_status || (prediction.selected_predictions || {}).probability_calibration_status || null,
      monetary_ev_enabled: engine.monetary_ev_enabled != null ? engine.monetary_ev_enabled : (prediction.selected_predictions || {}).monetary_ev_enabled,
      odds_band_ranking: engine.odds_band_ranking || (prediction.selected_predictions || {}).odds_band_ranking || null,
      odds_sanitization: clone(engine.odds_sanitization || null),
      evaluation_scope: 'prospective',
    };
    const raceId = `${race.date || 'date'}-${race.venue || 'venue'}-${race.race_number || 'R'}R`;
    const record = {
      race_id: raceId,
      prediction_timestamp: snapshot.captured_at,
      outcome_combo: outcomeCombo,
      settlement_odds: settlementOdds,
      trifecta_scores: prediction.trifecta_scores.map((row) => ({
        combo_key: row.combo_key,
        estimated_probability: Number(row.estimated_probability),
        odds: row.odds == null ? null : row.odds,
      })),
      selected_predictions: clone(prediction.selected_predictions),
      training_input: trainingInput,
      metadata: {
        date: race.date || null,
        venue: race.venue || null,
        race_number: race.race_number == null ? null : race.race_number,
        result_timestamp: resultTimestamp,
        result_time_status: 'provided',
        engine_version: engine.engine_candidate || (engine.architecture || {}).engine || null,
        input_quality: clone(engine.input_quality || null),
        odds_coverage: (engine.input_quality || {}).trifecta_odds_coverage == null ? null : (engine.input_quality || {}).trifecta_odds_coverage,
        source_snapshot: sourceSnapshot,
        evaluation_scope: 'prospective',
        temporal_order: 'prediction_before_result',
        training_eligibility: {
          supervised_training: true,
          reason: 'eligible_prospective_pre_result_snapshot',
        },
        prepared_by: 'browser-local-settle-snapshot-v1',
        schema_version: OUTPUT_SCHEMA,
      },
    };
    return record;
  }

  function recordsFromJson(value) {
    const result = [];
    function visit(node) {
      if (Array.isArray(node)) {
        node.forEach(visit);
        return;
      }
      if (!node || typeof node !== 'object') return;
      if (node.mode === 'dry_run' && node.payload && typeof node.payload === 'object') {
        visit(node.payload);
        return;
      }
      if (Array.isArray(node.records)) {
        node.records.forEach(visit);
        return;
      }
      if (node.history_record && typeof node.history_record === 'object') {
        visit(node.history_record);
        return;
      }
      if (typeof node.race_id === 'string') result.push(node);
    }
    visit(value);
    return result;
  }

  function recordCandidate(record) {
    const metadata = record && record.metadata || {};
    const eligibility = metadata.training_eligibility || {};
    const training = record && record.training_input;
    if (metadata.evaluation_scope !== 'prospective') fail('not_prospective');
    if (metadata.temporal_order !== 'prediction_before_result') fail('not_pre_result');
    if (eligibility.supervised_training !== true) fail('not_marked_training_eligible');
    if (!training || typeof training !== 'object') fail('training_input_missing');
    if (training.schema_version !== TRAINING_SCHEMA) fail('training_schema_mismatch');
    if (training.evaluation_scope !== 'prospective') fail('training_input_not_prospective');
    const source = String(((training.prediction_context || {}).source) || '');
    if (source.toLowerCase().includes('synthetic')) fail('synthetic_excluded');
    const raceId = String(record.race_id || '').trim();
    if (!raceId) fail('race_id_missing');

    const predictionTime = parseAwareTime(record.prediction_timestamp, 'timestamp');
    const resultTime = parseAwareTime(metadata.result_timestamp, 'timestamp');
    const captured = parseAwareTime(training.captured_at, 'timestamp');
    if (captured !== predictionTime || predictionTime >= resultTime) fail('invalid_temporal_order');
    const players = training.players;
    if (!Array.isArray(players) || players.length !== 7) fail('seven_unique_riders_required');
    const cars = players.map((player) => player && player.car_number);
    if (new Set(cars).size !== 7 || !cars.every((car) => Number.isInteger(car) && car >= 1 && car <= 9)) fail('invalid_car_number');
    if (!players.every((player) => ['逃', '両', '追'].includes(player && player.style))) fail('invalid_style');
    if (metadata.engine_version !== ENGINE_VERSION) fail('baseline_version_mismatch');
    if (!fullProbabilityTableValid(record.trifecta_scores, cars)) fail('baseline_incomplete');
    if (!new Set(permutations3(cars)).has(record.outcome_combo)) fail('outcome_not_in_riders');
    return { record, race_id: raceId, prediction_time: predictionTime, result_time: resultTime };
  }

  function prepareRecords(records) {
    const excluded = {};
    const groups = new Map();
    function exclude(reason, count) { excluded[reason] = (excluded[reason] || 0) + (count || 1); }
    for (const record of records) {
      try {
        const item = recordCandidate(record);
        if (!groups.has(item.race_id)) groups.set(item.race_id, []);
        groups.get(item.race_id).push(item);
      } catch (error) {
        exclude(error.code || error.message || 'malformed_record');
      }
    }
    const selected = [];
    let duplicates = 0;
    for (const group of groups.values()) {
      const outcomes = new Set(group.map((item) => item.record.outcome_combo));
      if (outcomes.size !== 1) {
        exclude('conflicting_outcomes', group.length);
        continue;
      }
      const latest = Math.max(...group.map((item) => item.prediction_time));
      const tied = group.filter((item) => item.prediction_time === latest);
      const serialized = new Set(tied.map((item) => JSON.stringify(item.record)));
      if (serialized.size !== 1) {
        exclude('conflicting_latest_snapshots', group.length);
        continue;
      }
      selected.push(tied[0]);
      duplicates += group.length - 1;
    }
    selected.sort((a, b) => a.prediction_time - b.prediction_time || a.race_id.localeCompare(b.race_id));
    return { selected, excluded, duplicate_snapshots_removed: duplicates };
  }

  function splitRecords(selected) {
    const times = [...new Set(selected.map((item) => item.prediction_time))].sort((a, b) => a - b);
    if (times.length < 5) fail('need_at_least_five_distinct_prediction_times');
    const validStart = times[Math.max(2, Math.floor(times.length * 0.6))];
    const testStart = times[Math.max(3, Math.floor(times.length * 0.8))];
    const train = selected.filter((item) => item.prediction_time < validStart && item.result_time < validStart);
    const valid = selected.filter((item) => item.prediction_time >= validStart && item.prediction_time < testStart && item.result_time < testStart);
    const test = selected.filter((item) => item.prediction_time >= testStart);
    if (train.length < 2 || valid.length === 0 || test.length === 0) fail('insufficient_non_overlapping_partitions');
    return {
      train_race_ids: train.map((item) => item.race_id),
      validation_race_ids: valid.map((item) => item.race_id),
      test_race_ids: test.map((item) => item.race_id),
      train_races: train.length,
      validation_races: valid.length,
      test_races: test.length,
      purged_unsettled_at_boundary: selected.length - train.length - valid.length - test.length,
      validation_start: new Date(validStart).toISOString(),
      test_start: new Date(testStart).toISOString(),
    };
  }

  function collectionStatus(records) {
    const prepared = prepareRecords(records);
    const selected = prepared.selected;
    const distinctTimes = new Set(selected.map((item) => item.prediction_time)).size;
    const oddsCounts = selected.map((item) => {
      const odds = (((item.record.training_input || {}).odds || {}).trifecta) || {};
      return odds && typeof odds === 'object' && !Array.isArray(odds) ? Object.keys(odds).length : 0;
    });
    let split = null;
    let blockedReason = null;
    try { split = splitRecords(selected); } catch (error) { blockedReason = error.code || error.message; }
    const sortedOdds = oddsCounts.slice().sort((a, b) => a - b);
    const median = sortedOdds.length ? (sortedOdds.length % 2 ? sortedOdds[(sortedOdds.length - 1) / 2] : (sortedOdds[sortedOdds.length / 2 - 1] + sortedOdds[sortedOdds.length / 2]) / 2) : null;
    return {
      input_records: records.length,
      eligible_unique_races: selected.length,
      eligible_race_ids: selected.map((item) => item.race_id),
      distinct_prediction_times: distinctTimes,
      minimum_distinct_prediction_times: 5,
      remaining_distinct_prediction_times: Math.max(0, 5 - distinctTimes),
      collection_threshold_met: distinctTimes >= 5,
      chronological_evaluation_may_run: split !== null,
      blocked_reason: blockedReason,
      split,
      excluded: prepared.excluded,
      duplicate_snapshots_removed: prepared.duplicate_snapshots_removed,
      known_trifecta_odds_count: {
        min: sortedOdds.length ? sortedOdds[0] : null,
        median,
        max: sortedOdds.length ? sortedOdds[sortedOdds.length - 1] : null,
      },
      note: 'Passing readiness is only a technical pipeline condition. It is not evidence of statistical sufficiency, calibration, model superiority or profitability.',
    };
  }

  function historyEnvelope(record) {
    return {
      mode: 'dry_run',
      payload: { records: [record] },
      offline_builder: {
        service: 'browser-local-settle-snapshot-v1',
        saved: false,
        db_write_enabled: false,
        external_fetch_enabled: false,
        production_prediction_enabled: false,
        result_timestamp_semantics: 'confirmed_result_observed_or_recorded_at',
      },
    };
  }

  return {
    ENGINE_VERSION,
    TRAINING_SCHEMA,
    validateSnapshot,
    buildTrainingInput,
    buildHistory,
    historyEnvelope,
    recordsFromJson,
    collectionStatus,
    fullProbabilityTableValid,
  };
});
