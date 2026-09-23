import { buildFullPredictionWithWeights, ENGINE_VERSION } from '../supabase/functions/predict-engine-dev/engine_phase32.ts';
import partialFixture from './golden/ito9-partial-input.json' with { type: 'json' };

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

function fixture() {
  const players = [
    {car_number:1,name:'A',style:'逃',race_score:110,S:4,H:8,B:10,line_id:'L1',line_position:1,line_length:3},
    {car_number:2,name:'B',style:'追',race_score:108,S:2,H:0,B:0,line_id:'L1',line_position:2,line_length:3},
    {car_number:3,name:'C',style:'追',race_score:105,S:1,H:0,B:0,line_id:'L1',line_position:3,line_length:3},
    {car_number:4,name:'D',style:'両',race_score:107,S:3,H:3,B:4,line_id:'L2',line_position:1,line_length:2},
    {car_number:5,name:'E',style:'追',race_score:103,S:2,H:0,B:0,line_id:'L2',line_position:2,line_length:2},
    {car_number:6,name:'F',style:'両',race_score:101,S:1,H:2,B:2,line_id:'L3',line_position:1,line_length:2},
    {car_number:7,name:'G',style:'追',race_score:99,S:1,H:0,B:0,line_id:'L3',line_position:2,line_length:2},
  ];
  const odds: Record<string, number> = {};
  let i = 0;
  const bands = [30, 75, 180, 650];
  for (let a=1;a<=7;a++) for (let b=1;b<=7;b++) if (b!==a) for (let c=1;c<=7;c++) if (c!==a && c!==b) {
    odds[`${a}-${b}-${c}`] = bands[i++ % bands.length];
  }
  return {race:{date:'2099-01-01',venue:'TEST',race_number:1},players,odds:{trifecta:odds}};
}

Deno.test('Phase32 keeps the 210-combination probability contract', () => {
  const result = buildFullPredictionWithWeights(fixture());
  assert(ENGINE_VERSION === 'phase32-hit-priority-all210-v1', 'engine version changed');
  assert(result.trifecta_scores.length === 210, 'must generate exactly 210 ordered triples');
  assert(new Set(result.trifecta_scores.map((x:any)=>x.combo_key)).size === 210, 'trifecta combinations must be unique');
  const mass = result.trifecta_scores.reduce((s:number,x:any)=>s+Number(x.estimated_probability),0);
  assert(Math.abs(mass - 1) <= 1e-9, `probability mass must be 1; got ${mass}`);
});

Deno.test('Phase32 keeps five categories, three unique picks each, with no fallback', () => {
  const result = buildFullPredictionWithWeights(fixture());
  const cats:any = result.selected_predictions.categories;
  const keys = ['hit_priority','balance','middle','longshot','super_longshot'];
  assert(keys.every(k=>cats[k]), 'all five categories must exist');
  assert(keys.every(k=>cats[k].picks.length===3), 'fixture must yield three picks in every category');
  assert(cats.hit_priority.candidate_scope === 'all_combinations', 'hit priority must consider all combinations');
  assert(keys.slice(1).every(k=>cats[k].candidate_scope === 'confirmed_odds_only'), 'odds-band categories must use confirmed odds only');
  const picks = keys.flatMap(k=>cats[k].picks);
  assert(picks.length === 15, 'expected 15 total picks');
  assert(new Set(picks.map((p:any)=>p.combo_key)).size === 15, 'picks must be unique across categories');
  assert(picks.every((p:any)=>p.fallback===false), 'fallback filling must remain disabled');
  assert(result.validation.five_categories_present === true, 'five-category validation failed');
  assert(result.validation.five_categories_complete === true, 'fixture should complete all five categories');
  assert(result.validation.max_three_per_category === true, 'category limit regression');
  assert(result.validation.no_fallback_fill === true, 'fallback regression');
});

Deno.test('Real Ito 9R partial-odds fixture preserves confirmed-odds-only behavior', () => {
  const raceData:any = (partialFixture as any).race_data;
  assert(Object.keys(raceData.odds.trifecta).length === 60, 'Golden fixture must keep exactly 60 confirmed odds');
  const result = buildFullPredictionWithWeights(raceData);
  const cats:any = result.selected_predictions.categories;
  const keys = ['hit_priority','balance','middle','longshot','super_longshot'];

  assert(result.trifecta_scores.length === 210, 'partial odds must not reduce the 210 probability table');
  assert(new Set(result.trifecta_scores.map((x:any)=>x.combo_key)).size === 210, 'partial-odds probability table must remain unique');
  assert(result.trifecta_scores.filter((x:any)=>x.odds!=null).length === 60, 'known odds count changed');
  assert(result.trifecta_scores.filter((x:any)=>x.odds==null).length === 150, 'unknown odds must remain unknown');
  const mass = result.trifecta_scores.reduce((s:number,x:any)=>s+Number(x.estimated_probability),0);
  assert(Math.abs(mass - 1) <= 1e-9, 'partial-odds probability mass must remain normalized');

  assert(result.selected_predictions.known_odds_count === 60, 'selected_predictions known_odds_count changed');
  assert(cats.hit_priority.candidate_scope === 'all_combinations', 'hit priority must still use all 210 combinations');
  assert(cats.hit_priority.available_candidates === 210, 'hit priority candidate count changed');
  assert(keys.every(k=>cats[k].picks.length===3), 'historical fixture must retain three picks per category');
  assert(keys.slice(1).every(k=>cats[k].candidate_scope === 'confirmed_odds_only'), 'odds-band categories must remain confirmed-odds-only');

  const inBand = (odds:number,min:number,max:number|null) => odds >= min && (max === null || odds < max);
  const bands:any = {balance:[20,60],middle:[60,100],longshot:[100,500],super_longshot:[500,null]};
  for (const key of keys.slice(1)) {
    for (const pick of cats[key].picks) {
      assert(pick.odds != null, `${key} used an unconfirmed odd`);
      const [min,max] = bands[key];
      assert(inBand(Number(pick.odds),min,max), `${key} selected odds outside its band: ${pick.odds}`);
      assert(pick.fallback === false, `${key} used fallback fill`);
    }
  }

  const picks = keys.flatMap(k=>cats[k].picks);
  assert(picks.length === 15, 'historical fixture must produce 15 picks');
  assert(new Set(picks.map((p:any)=>p.combo_key)).size === 15, 'historical fixture picks must be unique across categories');
});
