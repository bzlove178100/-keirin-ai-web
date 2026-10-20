// Standard seven-/nine-rider fields only. Missing legacy rosters retain the
// historical seven-rider interpretation; a malformed present roster never does.
// Optional legacy-compatible declaration. Omission is not proof of normality.
export function raceConditionErrors(input: any): string[] {
  if (!input || typeof input !== 'object' ||
      !Object.prototype.hasOwnProperty.call(input, 'race_conditions')) return [];
  const c = input.race_conditions;
  if (!c || typeof c !== 'object' || Array.isArray(c) ||
      Object.keys(c).sort().join(',') !== 'race_status,withdrawn_car_numbers')
    return ['race_conditions_contract_invalid'];
  if (c.race_status !== 'scheduled') return ['nonstandard_race_requires_review'];
  if (!Array.isArray(c.withdrawn_car_numbers)) return ['race_conditions_contract_invalid'];
  return c.withdrawn_car_numbers.length ? ['withdrawal_requires_review'] : [];
}

export function raceCarNumbers(players: any): number[] | null {
  if (!Array.isArray(players) || ![7, 9].includes(players.length)) return null;
  const cars = players.map(p => p?.car_number);
  return new Set(cars).size === players.length &&
      cars.every(n => Number.isInteger(n) && n >= 1 && n <= players.length)
    ? cars : null;
}

export function recordCarNumbers(record: any): number[] | null {
  return record.training_input == null
    ? [1, 2, 3, 4, 5, 6, 7]
    : raceCarNumbers(record.training_input.players);
}

export function fullProbabilityInput(record: any): boolean {
  const cars = recordCarNumbers(record);
  if (!cars) return false;
  const expected = new Set<string>();
  for (const a of cars) for (const b of cars) for (const c of cars) {
    if (a !== b && a !== c && b !== c) expected.add(`${a}-${b}-${c}`);
  }
  const scores = record.trifecta_scores;
  if (!Array.isArray(scores) || scores.length !== expected.size) return false;
  const seen = new Set<string>();
  let mass = 0;
  for (const row of scores) {
    const p = row?.estimated_probability;
    if (!expected.has(row?.combo_key) || seen.has(row.combo_key) ||
        typeof p !== 'number' || !Number.isFinite(p) || p < 0 || p > 1) return false;
    seen.add(row.combo_key);
    mass += p;
  }
  return seen.size === expected.size && Math.abs(mass - 1) <= 1e-6;
}

// A normal single-outcome history cannot represent a held settlement.
// Missing legacy status remains unverified; never discard declared result fields.
export function settlementDeclarationErrors(settlement: any): string[] {
  if (!settlement || typeof settlement !== 'object' || Array.isArray(settlement))
    return ['settlement_fields_invalid'];
  const allowed = ['outcome_combo', 'settlement_odds', 'result_timestamp', 'result_time_unknown', 'result_status'];
  if (Object.keys(settlement).some(key => !allowed.includes(key)))
    return ['settlement_fields_invalid'];
  if (!Object.prototype.hasOwnProperty.call(settlement, 'result_status')) return [];
  if (['dead_heat', 'withdrawn', 'cancelled'].includes(settlement.result_status))
    return ['nonstandard_result_requires_review'];
  return settlement.result_status === 'normal' ? [] : ['result_status_invalid'];
}

// Direct history intake must not discard declarations before computing metrics.
// Legacy omission is accepted for compatibility, not evidence of a normal race.
export function historyResultDeclarationErrors(record: any): string[] {
  const errors: string[] = [];
  for (const part of [record, record?.metadata ?? {}]) {
    if (!part || typeof part !== 'object' || Array.isArray(part)) {
      errors.push('history_result_metadata_invalid');
      continue;
    }
    if (['phase32-held-history-v1', 'ml-held-history-v1'].includes(part.schema_version))
      errors.push('held_history_requires_offline_review');
    if (Object.prototype.hasOwnProperty.call(part, 'result_status') && part.result_status !== 'normal')
      errors.push('nonstandard_result_requires_review');
    if (['dead_heat', 'withdrawn_car_numbers', 'trifecta_outcomes', 'settlement']
        .some(key => Object.prototype.hasOwnProperty.call(part, key)))
      errors.push('history_result_fields_invalid');
  }
  return [...new Set(errors)];
}

export const HELD_HISTORY_SCHEMA = 'phase32-held-history-v1';

function heldTime(value: any, field: string): number {
  if (typeof value !== 'string' || !/(?:Z|[+-]\d{2}:\d{2})$/.test(value))
    throw new Error(`${field}_timezone_missing`);
  const time = Date.parse(value);
  if (!Number.isFinite(time)) throw new Error(`${field}_invalid`);
  return time;
}

// Same immutable, prospective-only contract as browser/Python held histories.
// No result, training label or prediction is inferred or regenerated here.
export function buildPhase32HeldHistory(snapshot: any, settlement: any): any {
  if (!snapshot || snapshot.schema_version !== 'prediction-snapshot-v1')
    throw new Error('snapshot_schema_mismatch');
  const eligibility = snapshot.snapshot_eligibility;
  if (snapshot.validation_mode !== 'prospective-only' || eligibility?.prospective !== true ||
      eligibility?.prestart_confirmed !== true) throw new Error('snapshot_not_prospective');
  const captured = heldTime(snapshot.captured_at, 'captured_at');
  const scheduled = heldTime(eligibility.scheduled_start, 'scheduled_start');
  if (captured >= scheduled) throw new Error('snapshot_capture_not_before_scheduled_start');
  const input = snapshot.race_data, race = input?.race;
  if (race?.scheduled_start_jst != null && heldTime(race.scheduled_start_jst, 'race_scheduled_start') !== scheduled)
    throw new Error('scheduled_start_mismatch');
  const conditions = raceConditionErrors(input);
  if (conditions.length) throw new Error(conditions[0]);
  const cars = raceCarNumbers(input?.players), engine = snapshot.engine_response;
  if (!cars) throw new Error('invalid_car_numbers');
  if (engine?.success !== true || engine.saved !== false || engine.db_write_enabled !== false ||
      engine.production_prediction_enabled !== false) throw new Error('snapshot_safety_flags_invalid');
  if ((engine.engine_candidate || engine.architecture?.engine) !== 'phase32-hit-priority-all210-v1')
    throw new Error('engine_version_mismatch');
  if ([engine.engine_candidate, engine.architecture?.engine]
      .some(value => value != null && value !== 'phase32-hit-priority-all210-v1')) throw new Error('engine_version_mismatch');
  const prediction = engine.prediction;
  if (!fullProbabilityInput({training_input: input, trifecta_scores: prediction?.trifecta_scores}))
    throw new Error('full_probability_table_invalid');
  const combos = new Set(prediction.trifecta_scores.map((row: any) => row.combo_key));
  for (const key of ['hit_priority', 'balance', 'middle', 'longshot', 'super_longshot']) {
    const picks = prediction.selected_predictions?.categories?.[key]?.picks;
    if (!Array.isArray(picks) || picks.length > 3 || picks.some(p => !combos.has(p?.combo_key)) ||
        new Set(picks.map(p => p.combo_key)).size !== picks.length) throw new Error('selected_categories_invalid');
  }
  const status = settlement?.result_status;
  if (!['dead_heat', 'withdrawn', 'cancelled'].includes(status)) throw new Error('held_result_status_invalid');
  const fields = ['result_status', 'result_timestamp', ...(status === 'withdrawn' ? ['withdrawn_car_numbers'] : [])];
  if (!settlement || Array.isArray(settlement) || Object.keys(settlement).sort().join(',') !== fields.sort().join(','))
    throw new Error('held_settlement_fields_invalid');
  const observed = heldTime(settlement.result_timestamp, 'result_timestamp');
  if (observed < captured) throw new Error('result_before_capture');
  if (status === 'dead_heat' && observed < scheduled) throw new Error('result_before_scheduled_start');
  if (status === 'withdrawn') {
    const withdrawn = settlement.withdrawn_car_numbers;
    if (!Array.isArray(withdrawn) || !withdrawn.length ||
        withdrawn.some(car => !Number.isInteger(car) || !cars.includes(car)) ||
        new Set(withdrawn).size !== withdrawn.length) throw new Error('withdrawn_cars_invalid');
  }
  if (typeof race?.date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(race.date) ||
      typeof race.venue !== 'string' || !race.venue.trim() || !Number.isInteger(race.race_number) ||
      race.race_number < 1 || race.race_number > 12) throw new Error('held_race_identity_invalid');
  return {
    schema_version: HELD_HISTORY_SCHEMA,
    race_id: `${race.date}-${race.venue}-${race.race_number}R`, prediction_timestamp: snapshot.captured_at,
    snapshot: JSON.parse(JSON.stringify(snapshot)), settlement: JSON.parse(JSON.stringify(settlement)),
    evaluation_eligible: false, supervised_training_eligible: false,
    db_write_enabled: false, external_fetch_enabled: false,
    production_prediction_enabled: false, monetary_ev_enabled: false,
  };
}

function heldCanonical(value: any): string {
  if (Array.isArray(value)) return '[' + value.map(heldCanonical).join(',') + ']';
  if (value && typeof value === 'object') return '{' + Object.keys(value).sort()
    .map(key => JSON.stringify(key) + ':' + heldCanonical(value[key])).join(',') + '}';
  return JSON.stringify(value);
}

export function validatePhase32HeldHistory(record: any): boolean {
  if (!record || record.schema_version !== HELD_HISTORY_SCHEMA) throw new Error('held_schema_mismatch');
  if (heldCanonical(record) !== heldCanonical(buildPhase32HeldHistory(record.snapshot, record.settlement)))
    throw new Error('held_record_mismatch');
  return true;
}

export function partitionPhase32Holds(records: any[]): any {
  const held = new Set<string>(), ordinary: any[] = [];
  const excluded = {held_result: 0, race_has_held_result: 0};
  for (const record of records) {
    if (record?.schema_version === HELD_HISTORY_SCHEMA) {
      validatePhase32HeldHistory(record); held.add(record.race_id); excluded.held_result++;
    } else ordinary.push(record);
  }
  return {records: ordinary.filter(record => {
    if (held.has(record.race_id)) { excluded.race_has_held_result++; return false; }
    return true;
  }), excluded, held_race_ids: [...held].sort()};
}
