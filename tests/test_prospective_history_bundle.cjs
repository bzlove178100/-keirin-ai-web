const fs = require('node:fs');
const assert = require('node:assert/strict');
const bundle = require('../prospective-history-bundle.js');

function record(id, prediction = '2026-09-24T01:00:00Z') {
  return {
    race_id: id,
    prediction_timestamp: prediction,
    outcome_combo: '1-2-3',
    metadata: { result_timestamp: '2026-09-24T02:00:00Z' },
    training_input: { schema_version: 'keirin-training-input-v1' }
  };
}

const a = record('A');
const b = record('B', '2026-09-24T03:00:00Z');
const duplicateWithDifferentKeyOrder = {
  training_input: { schema_version: 'keirin-training-input-v1' },
  metadata: { result_timestamp: '2026-09-24T02:00:00Z' },
  outcome_combo: '1-2-3',
  prediction_timestamp: '2026-09-24T01:00:00Z',
  race_id: 'A'
};

const built = bundle.buildBundle([
  { mode: 'dry_run', payload: { records: [a] } },
  { history_record: b },
  duplicateWithDifferentKeyOrder
], { createdAt: '2026-09-24T04:00:00+09:00' });

assert.equal(built.mode, 'dry_run');
assert.equal(built.payload.records.length, 2);
assert.deepEqual(built.payload.records.map((row) => row.race_id), ['A', 'B']);
assert.equal(built.private_bundle.input_record_count, 3);
assert.equal(built.private_bundle.record_count, 2);
assert.equal(built.private_bundle.exact_duplicates_removed, 1);
assert.equal(built.private_bundle.created_at, '2026-09-23T19:00:00.000Z');
assert.equal(built.private_bundle.db_write_enabled, false);
assert.equal(built.private_bundle.external_fetch_enabled, false);
assert.equal(built.private_bundle.production_prediction_enabled, false);

const conflict = { ...a, settlement_odds: 99.9 };
const conflictBundle = bundle.buildBundle([a, conflict], { createdAt: '2026-09-24T04:00:00Z' });
assert.equal(conflictBundle.payload.records.length, 2, 'non-identical same-race records must be preserved for later conflict validation');
assert.equal(conflictBundle.private_bundle.exact_duplicates_removed, 0);

assert.throws(() => bundle.buildBundle([a], { createdAt: 'not-a-date' }), /created_at_invalid/);

const html = fs.readFileSync('prospective-tools.html', 'utf8');
assert.match(html, /id="save-history-bundle"/);
assert.match(html, /id="history-bundle-status"/);
assert.match(html, /src="prospective-history-bundle\.js"/);
assert.match(html, /connect-src 'none'/);

console.log('Prospective private history bundle checks: PASS');
