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
