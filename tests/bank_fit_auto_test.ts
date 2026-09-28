import { applyAutomaticBankFit, BANK_FIT_AUTO_VERSION } from '../supabase/functions/predict-engine-dev/bank_fit_auto.ts';

function assert(cond:boolean,msg:string){if(!cond)throw new Error(msg);}
function player(car:number,style:'逃'|'両'|'追',extra:Record<string,unknown>={}){return{car_number:car,name:`P${car}`,style,...extra};}

Deno.test('automatic bank fit preserves explicit scores',()=>{
  const input={bank_context:{track_length_m:333,home_stretch_m:40,max_banking_deg:34,wind_speed_mps:4,wind_direction:'home_tailwind'},players:[player(1,'逃',{bank_fit:{score:7.5}})]};
  const out=applyAutomaticBankFit(input) as any;
  assert(out.raceData.players[0].bank_fit.score===7.5,'explicit bank_fit.score must be preserved');
  assert(out.report.preserved_cars.includes(1),'preserved car must be audited');
  assert(out.report.version===BANK_FIT_AUTO_VERSION,'version must be reported');
});

Deno.test('headwind differentiates escape and chase styles',()=>{
  const input={bank_context:{track_length_m:400,home_stretch_m:55,max_banking_deg:30,wind_speed_mps:6,wind_direction:'home_headwind',surface_condition:'dry',weather:'clear'},players:[player(1,'逃'),player(2,'追')]};
  const out=applyAutomaticBankFit(input) as any;
  const escape=out.raceData.players[0].bank_fit.score;
  const chase=out.raceData.players[1].bank_fit.score;
  assert(escape<chase,`headwind should not favor escape over chase: ${escape} vs ${chase}`);
  assert(out.report.computed_cars.length===2,'both riders should receive automatic scores');
});

Deno.test('venue and similar-bank history affect automatic score',()=>{
  const context={track_length_m:400,home_stretch_m:55,max_banking_deg:30,wind_speed_mps:0,wind_direction:'calm'};
  const strong=player(1,'両',{bank_history:{venue:{starts:16,win_rate:35,top2_rate:55,top3_rate:70,avg_finish:2.4},similar:{starts:20,win_rate:30,top2_rate:50,top3_rate:65,avg_finish:2.6}}});
  const weak=player(2,'両',{bank_history:{venue:{starts:16,win_rate:5,top2_rate:15,top3_rate:25,avg_finish:5.2},similar:{starts:20,win_rate:8,top2_rate:18,top3_rate:30,avg_finish:4.9}}});
  const out=applyAutomaticBankFit({bank_context:context,players:[strong,weak]}) as any;
  assert(out.raceData.players[0].bank_fit.score>out.raceData.players[1].bank_fit.score,'strong bank history must rank above weak bank history');
  assert(out.raceData.players[0].bank_fit.auto.history.venue.starts===16,'venue history sample size must be audited');
});

Deno.test('missing bank evidence leaves bank_fit unset',()=>{
  const out=applyAutomaticBankFit({players:[player(1,'両')]}) as any;
  assert(out.raceData.players[0].bank_fit===undefined,'no evidence must not fabricate a bank-fit score');
  assert(out.report.skipped_cars.includes(1),'missing-evidence car must be audited');
});
