// Local handler composition; fake owner/child responses, no sockets or secrets.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {stripTypeScriptTypes}=require('node:module');
const root=process.cwd();
const common=require(root+'/supabase/functions/_shared/race_probability.ts');
const training=require(root+'/supabase/functions/history-pipeline-dev/training_input.ts');
const {buildFullPredictionWithWeights}=require(root+'/supabase/functions/predict-engine-dev/engine_phase32.ts');
const {snapshot}=require(root+'/tests/test_prospective_tools.cjs');
const browserCore=require(root+'/prospective-tools-core.js');
const handlers={},calls=[];
async function localFetch(url,options={}) {
  calls.push([url,options.method||'GET']);
  assert(url.startsWith('https://synthetic.invalid/'));
  if(url.endsWith('/auth/v1/user'))return Response.json({id:'fixture-owner'});
  if(url.includes('/rest/v1/user_profiles?'))return Response.json([{role:'owner',plan:'owner'}]);
  const slug=url.split('/functions/v1/')[1];
  assert(handlers[slug],`unexpected path ${url}`);
  return handlers[slug](new Request(url,options));
}
for(const slug of ['history-builder-dev','backtest-engine-dev','history-pipeline-dev']){
  const raw=fs.readFileSync(`${root}/supabase/functions/${slug}/index.ts`,'utf8').replace(/^import .*;\n/gm,'');
  const context={...common,...training,console,structuredClone,Request,Response,fetch:localFetch,Deno:{env:{get:k=>k==='SUPABASE_URL'?'https://synthetic.invalid':k==='SUPABASE_ANON_KEY'?'synthetic-only':undefined},serve:handler=>handlers[slug]=handler}};
  vm.runInNewContext(stripTypeScriptTypes(raw),context,{filename:slug});
}
(async()=>{
 for(const count of [7,9]){
  const snap=snapshot(0,'synthetic',count);
  snap.engine_response.prediction=buildFullPredictionWithWeights(snap.race_data);
  assert.equal(browserCore.validateSnapshot(snap),true);
  const browserRecord=browserCore.buildHistory(snap,{outcomeCombo:`${count}-${count-1}-${count-2}`,settlementOdds:42,resultTimestamp:'2026-09-24T00:40:00Z'});
  const response=await handlers['history-pipeline-dev'](new Request('https://synthetic.invalid/pipeline',{method:'POST',headers:{Authorization:'Bearer synthetic-only','Content-Type':'application/json'},body:JSON.stringify({mode:'dry_run',require_prospective:true,snapshot:snap,settlement:{outcome_combo:`${count}-${count-1}-${count-2}`,settlement_odds:42,result_timestamp:'2026-09-24T00:40:00Z'}})}));
  const data=await response.json();assert.equal(response.status,200,JSON.stringify(data));assert.equal(data.success,true);
  assert.deepEqual(data.history_record.trifecta_scores,browserRecord.trifecta_scores);
  assert.equal(data.history_record.outcome_combo,browserRecord.outcome_combo);
  assert.equal(data.history_quality.trifecta_score_count,count*(count-1)*(count-2));
  assert.equal(data.backtest_result.probability_quality.races_with_full_probability_input,1);
  assert.equal(data.history_warnings.length,0);
  assert.equal(data.saved,false);assert.equal(data.db_write_enabled,false);assert.equal(data.production_prediction_enabled,false);
  assert.equal(Object.keys(data.history_record.training_input.odds.trifecta).length,72);
  assert(!JSON.stringify(data.history_record.training_input).includes('outcome_combo'));
  console.log(`Synthetic ${count}-rider engine → history pipeline → builder → backtest: PASS`);
 }
 assert(calls.every(([url,method])=>method==='GET'||url.includes('/functions/v1/')));
})().catch(e=>{console.error(e);process.exitCode=1});
