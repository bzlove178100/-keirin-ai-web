import { buildTrainingInput, TRAINING_SCHEMA } from '../supabase/functions/history-pipeline-dev/training_input.ts';
import iwaki from './golden/iwakitaira11-raw-kdreams-input.json' with { type: 'json' };

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

Deno.test('training input removes K-Dreams no-ticket marker without inventing unknown odds', () => {
  const snapshot:any = {
    captured_at:'2026-09-16T14:24:00+09:00',
    race_data:iwaki,
  };
  const engineResponse:any = {
    odds_sanitization:{
      policy:'kdreams_9999_9_unbet_as_unavailable',
      source_matched:true,
      ignored_combos:['2-6-3'],
    },
  };
  const result:any = buildTrainingInput(snapshot,engineResponse,'prospective');
  const odds = result.odds.trifecta;

  assert(result.schema_version === TRAINING_SCHEMA, 'training schema changed');
  assert(result.evaluation_scope === 'prospective', 'evaluation scope changed');
  assert(result.players.length === 7, 'all seven pre-race riders must be preserved');
  assert(Object.keys((iwaki as any).odds.trifecta).length === 60, 'raw fixture must contain 60 displayed odds');
  assert(Object.keys(odds).length === 59, 'exactly one K-Dreams no-ticket marker should be removed');
  assert(!('2-6-3' in odds), '9999.9 no-ticket combo must not enter training input');
  assert(Object.values(odds).every(v=>Number(v)!==9999.9), 'training odds must contain no 9999.9 values');
  assert(result.odds_sanitization.removed_combos.includes('2-6-3'), 'sanitization audit trail missing removed combo');
});

Deno.test('training input contains pre-race features only and no settlement target', () => {
  const snapshot:any = {
    captured_at:'2026-09-16T14:24:00+09:00',
    race_data:iwaki,
  };
  const result:any = buildTrainingInput(snapshot,{odds_sanitization:{ignored_combos:['2-6-3']}},'replay_or_legacy');
  const serialized = JSON.stringify(result);

  assert(result.captured_at === snapshot.captured_at, 'capture timestamp must be preserved');
  assert(Array.isArray(result.players) && result.players.length === 7, 'rider features missing');
  assert(!('outcome_combo' in result), 'settlement outcome must not leak into training input');
  assert(!('settlement_odds' in result), 'settlement odds must not leak into training input');
  assert(!serialized.includes('result_timestamp'), 'result timestamp must not leak into training input');
});

Deno.test('prospective WINTICKET input preserves confirmed partial odds without inventing missing combinations', () => {
  const players = Array.from({length:7},(_,i)=>({
    car_number:i+1,
    name:`rider-${i+1}`,
    style:i===0?'逃':'追',
    race_score:80+i,
    S:0,
    H:0,
    B:0,
    line_id:`L${i+1}`,
    line_position:1,
    line_length:1,
  }));
  const snapshot:any = {
    captured_at:'2026-09-24T10:20:46+09:00',
    race_data:{
      race:{date:'2026-09-24',venue:'test',race_number:1,scheduled_start_jst:'2026-09-24T15:53:00+09:00'},
      players,
      odds:{trifecta:{'1-2-3':21.4,'1-2-4':36.9,'7-3-6':52.4}},
      prediction_context:{source:'WINTICKET',pre_race_confirmed:true},
    },
  };
  const engineResponse:any = {
    odds_sanitization:{
      policy:'snapshot_safety_filter',
      source_matched:false,
      ignored_combos:[],
    },
  };
  const result:any = buildTrainingInput(snapshot,engineResponse,'prospective');
  const odds = result.odds.trifecta;

  assert(result.schema_version === TRAINING_SCHEMA, 'training schema changed');
  assert(result.evaluation_scope === 'prospective', 'prospective scope must be preserved');
  assert(result.players.length === 7, 'all riders must be preserved');
  assert(Object.keys(odds).length === 3, 'partial confirmed odds must remain partial');
  assert(odds['1-2-3'] === 21.4 && odds['7-3-6'] === 52.4, 'confirmed odds changed');
  assert(!('1-3-2' in odds), 'missing combinations must never be invented');
  assert(result.prediction_context?.source === 'WINTICKET', 'source context must be preserved');
});

// Generated data only: the same full-field contract used by history/backtest.
import { fullProbabilityInput, raceCarNumbers } from '../supabase/functions/_shared/race_probability.ts';

function generatedRecord(count: number): any {
  const players = Array.from({length:count}, (_, i) => ({car_number:i+1, style:'追'}));
  const trifecta_scores = [];
  for (let a=1;a<=count;a++) for (let b=1;b<=count;b++) for (let c=1;c<=count;c++) {
    if (a!==b && a!==c && b!==c) trifecta_scores.push({combo_key:`${a}-${b}-${c}`,estimated_probability:1/(count*(count-1)*(count-2))});
  }
  return {training_input:{players},trifecta_scores};
}

Deno.test('history/backtest full probability contract accepts 7/9 and preserves legacy seven', () => {
  for (const count of [7,9]) {
    const record = generatedRecord(count);
    assert(fullProbabilityInput(record), `${count}-rider table rejected`);
    assert(record.trifecta_scores.length === (count===7 ? 210 : 504), 'wrong combination count');
    delete record.training_input;
    assert(fullProbabilityInput(record) === (count===7), 'roster-free legacy inference changed');
  }
});

Deno.test('history/backtest rejects malformed rosters and incomplete probability tables', () => {
  for (const count of [7,9]) {
    for (const value of [true,'1',null,0,count+1,2]) {
      const record = generatedRecord(count);
      record.training_input.players[0].car_number = value;
      assert(raceCarNumbers(record.training_input.players) === null, 'malformed roster accepted');
      assert(!fullProbabilityInput(record), 'invalid roster fell back to legacy seven');
    }
    for (const mutate of [
      (r:any) => r.trifecta_scores.pop(),
      (r:any) => r.trifecta_scores[0].combo_key = '10-2-3',
      (r:any) => r.trifecta_scores[0].combo_key = r.trifecta_scores[1].combo_key,
      (r:any) => r.trifecta_scores[0].estimated_probability = NaN,
      (r:any) => r.trifecta_scores[0].estimated_probability = '0.1',
      (r:any) => r.trifecta_scores.forEach((x:any) => x.estimated_probability *= 0.99),
      (r:any) => { r.trifecta_scores[0].estimated_probability = -0.1; r.trifecta_scores[1].estimated_probability += 0.1+1/(count*(count-1)*(count-2)); },
    ]) {
      const record = generatedRecord(count); mutate(record);
      assert(!fullProbabilityInput(record), 'malformed probability table accepted');
    }
  }
  for (const count of [6,8,10]) assert(!fullProbabilityInput(generatedRecord(count)), 'unsupported field accepted');
  assert(!fullProbabilityInput({...generatedRecord(7),training_input:{}}), 'missing players accepted');
});
