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
