// Local handler composition; fake owner/child responses, no sockets or secrets.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {stripTypeScriptTypes}=require('node:module');
const root=process.cwd();
const common=require(root+'/supabase/functions/_shared/race_probability.ts');
const training=require(root+'/supabase/functions/history-pipeline-dev/training_input.ts');
const {validateRaceData}=require(root+'/supabase/functions/predict-engine-dev/race_data_contract.ts');
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
  snap.race_data.players.forEach(p=>p.name=`SYNTHETIC RIDER ${p.car_number}`);
  snap.race_data.race_conditions={race_status:'scheduled',withdrawn_car_numbers:[]};
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
  assert.deepEqual(data.history_record.training_input.race_conditions,snap.race_data.race_conditions);
  assert.deepEqual(browserRecord.training_input.race_conditions,snap.race_data.race_conditions);
  assert.equal(validateRaceData(snap.race_data).length,0);
  assert(!JSON.stringify(data.history_record.training_input).includes('outcome_combo'));
  const normalSettlement={outcome_combo:browserRecord.outcome_combo,settlement_odds:42,result_timestamp:'2026-09-24T00:40:00Z'};
  async function directBacktest(records, accepted) {
    calls.length=0;
    const res=await handlers['backtest-engine-dev'](new Request('https://synthetic.invalid/backtest',{method:'POST',headers:{Authorization:'Bearer synthetic-only','Content-Type':'application/json'},body:JSON.stringify({mode:'dry_run',payload:{records}})}));
    const result=await res.json();
    assert.equal(res.status,accepted?200:422,JSON.stringify(result));
    assert.equal(result.saved,false);assert.equal(result.db_write_enabled,false);
    assert(calls.every(([url,method])=>method==='GET'&&!url.includes('/functions/v1/')),'direct review must only read synthetic owner identity');
    if(!accepted){assert.equal(result.input_validation_ok,false);assert.equal(result.result,undefined,'rejected batch must not return partial metrics');}
    return result.result;
  }
  const originalMetrics=await directBacktest([browserRecord],true);
  for(const location of ['root','metadata']){
    const normal=structuredClone(browserRecord);
    (location==='root'?normal:normal.metadata).result_status='normal';
    assert.deepEqual(await directBacktest([normal],true),originalMetrics,'normal declaration must preserve all metrics');
    for(const declaration of [{result_status:'dead_heat'},{result_status:'withdrawn'},{result_status:'cancelled'},
      {result_status:'unknown'},{result_status:null},{result_status:0},{result_status:false},
      {dead_heat:false},{withdrawn_car_numbers:[]},{trifecta_outcomes:['1-2-3','2-1-3']},{settlement:null},
      {schema_version:'phase32-held-history-v1'},{schema_version:'ml-held-history-v1'}]){
      const bad=structuredClone(browserRecord);
      Object.assign(location==='root'?bad:bad.metadata,declaration);
      await directBacktest([bad],false);
      await directBacktest([browserRecord,bad],false);
      await directBacktest([bad,browserRecord],false);
    }
  }
  const held=browserCore.buildHeldHistory(snap,{result_status:'cancelled',result_timestamp:normalSettlement.result_timestamp});
  const otherSnap=structuredClone(snap);otherSnap.race_data.race.race_number=2;
  const other=browserCore.buildHistory(otherSnap,{outcomeCombo:normalSettlement.outcome_combo,settlementOdds:42,resultTimestamp:normalSettlement.result_timestamp});
  const otherMetrics=await directBacktest([other],true);
  for(const status of ['dead_heat','withdrawn','cancelled']){
    const event={result_status:status,result_timestamp:normalSettlement.result_timestamp,...(status==='withdrawn'?{withdrawn_car_numbers:[count]}:{})};
    const expected=browserCore.buildHeldHistory(snap,event);
    calls.length=0;
    const res=await handlers['history-pipeline-dev'](new Request('https://synthetic.invalid/pipeline',{method:'POST',headers:{Authorization:'Bearer synthetic-only','Content-Type':'application/json'},body:JSON.stringify({mode:'dry_run',require_prospective:true,snapshot:snap,settlement:event})}));
    const result=await res.json();assert.equal(res.status,200,JSON.stringify(result));
    assert.deepEqual(result.history_record,expected);assert.equal(result.held,true);
    for(const flag of ['saved','db_write_enabled','external_fetch_enabled','production_prediction_enabled','monetary_ev_enabled','supervised_training_eligible','prospective_eligible'])assert.equal(result[flag],false);
    assert.equal(result.backtest_result,null);assert.equal(result.history_record.outcome_combo,undefined);
    assert(calls.every(([url,method])=>method==='GET'&&!url.includes('/functions/v1/')),'held generation must not call normal history/backtest children');
    for(const records of [[expected,browserRecord],[browserRecord,expected],[expected,expected,browserRecord],[expected]]){
      const empty=await directBacktest(records,true);
      assert.equal(empty.records,0);assert.equal(empty.evaluation_performed,false);assert.equal(empty.held_unique_races,1);
      for(const key of ['selection_performance','categories','probability_quality'])assert.equal(empty[key],null);
      const mixed=await directBacktest([...records,other],true);
      assert.equal(mixed.records,1);assert.equal(mixed.input_records,records.length+1);assert.equal(mixed.held_unique_races,1);
      assert.equal(mixed.excluded.race_has_held_result,records.includes(browserRecord)?1:0);
      for(const key of ['selection_performance','categories','probability_quality'])assert.deepEqual(mixed[key],otherMetrics[key]);
    }
    for(const body of [
      {mode:'live',snapshot:snap,settlement:event},
      {mode:'dry_run',snapshot:snap,settlement:event,race_id:'DIFFERENT'},
      {mode:'dry_run',snapshot:snap,settlement:event,evaluation_scope:'replay_or_legacy'},
      {mode:'dry_run',snapshot:snap,settlement:{...event,result_timestamp:'2026-09-23T00:00:00Z'}},
      {mode:'dry_run',snapshot:{...snap,validation_mode:'replay'},settlement:event},
    ]){
      calls.length=0;
      const rejected=await handlers['history-pipeline-dev'](new Request('https://synthetic.invalid/pipeline',{method:'POST',headers:{Authorization:'Bearer synthetic-only','Content-Type':'application/json'},body:JSON.stringify(body)}));
      assert.equal(rejected.status,422);assert(calls.every(([url])=>!url.includes('/functions/v1/')));
    }
  }
  for(const change of [{outcome_combo:'1-2-3'},{evaluation_eligible:true},{db_write_enabled:0},{race_id:'DIFFERENT'}])
    await directBacktest([other,{...held,...change}],false);
  for(const slug of ['history-pipeline-dev','backtest-engine-dev']){
    calls.length=0;
    const unauthenticated=await handlers[slug](new Request('https://synthetic.invalid/'+slug,{method:'POST',body:'{}'}));
    assert.equal(unauthenticated.status,401);assert.equal(calls.length,0);
  }
  for(const metadata of [[],false,0,'normal'])await directBacktest([{...browserRecord,metadata}],false);
  console.log(`Synthetic ${count}-rider held API generation, whole-race exclusion and empty metrics: PASS`);
  console.log(`Synthetic ${count}-rider direct backtest result declarations: PASS`);
  for(const declaration of [{result_status:'normal'},{result_status:'dead_heat'},{result_status:'withdrawn',withdrawn_car_numbers:[count]},{result_status:'cancelled'},{result_status:null},{result_status:'unknown'},{dead_heat:true},{trifecta_outcomes:['1-2-3','2-1-3']},{unexpected:true}]){
    const accepted=declaration.result_status==='normal';
    const settlement={...normalSettlement,...declaration};
    const browserSettlement={outcomeCombo:normalSettlement.outcome_combo,settlementOdds:42,resultTimestamp:normalSettlement.result_timestamp,...declaration};
    if(accepted)assert.equal(browserCore.buildHistory(snap,browserSettlement).metadata.result_status,'normal');
    else assert.throws(()=>browserCore.buildHistory(snap,browserSettlement),/settlement_fields_invalid|nonstandard_result_requires_review|result_status_invalid/);
    const payloads={
      'history-pipeline-dev':{mode:'dry_run',snapshot:snap,settlement},
      'history-builder-dev':{mode:'dry_run',include_backtest:true,payload:{race:{race_id:browserRecord.race_id},prediction:{prediction_timestamp:browserRecord.prediction_timestamp,selected_predictions:browserRecord.selected_predictions,trifecta_scores:browserRecord.trifecta_scores,training_input:browserRecord.training_input},settlement}}
    };
    for(const [slug,body] of Object.entries(payloads)){
      calls.length=0;
      const res=await handlers[slug](new Request('https://synthetic.invalid/'+slug,{method:'POST',headers:{Authorization:'Bearer synthetic-only','Content-Type':'application/json'},body:JSON.stringify(body)}));
      const result=await res.json();assert.equal(res.status,accepted?200:422,JSON.stringify(result));
      assert.equal(result.saved,false);assert.equal(result.db_write_enabled,false);
      if(accepted)assert.equal((result.history_record||result.record).metadata.result_status,'normal');
      else assert(calls.every(([url])=>!url.includes('/functions/v1/')),'nonstandard settlement must not call a child function');
    }
  }
  const invalid=[null,{},[],false,'scheduled',
    {race_status:'cancelled',withdrawn_car_numbers:[]},
    {race_status:'scheduled',withdrawn_car_numbers:[count]},
    {race_status:'scheduled',withdrawn_car_numbers:null},
    {race_status:'scheduled',withdrawn_car_numbers:[],extra:true}];
  for(const conditions of invalid){
    const bad=structuredClone(snap);bad.race_data.race_conditions=conditions;
    assert(validateRaceData(bad.race_data).length>0,'predict must reject declared nonstandard conditions');
    assert.throws(()=>browserCore.validateSnapshot(bad));
    assert.throws(()=>browserCore.buildTrainingInput(bad));
    assert.throws(()=>training.buildTrainingInput(bad,bad.engine_response,'prospective'));
    const badRecord=structuredClone(browserRecord);badRecord.training_input.race_conditions=conditions;
    const payloads={
      'history-pipeline-dev':{mode:'dry_run',require_prospective:true,snapshot:bad,settlement:{outcome_combo:`${count}-${count-1}-${count-2}`,settlement_odds:42,result_timestamp:'2026-09-24T00:40:00Z'}},
      'history-builder-dev':{mode:'dry_run',include_backtest:true,payload:{race:{race_id:browserRecord.race_id},prediction:{prediction_timestamp:browserRecord.prediction_timestamp,selected_predictions:browserRecord.selected_predictions,trifecta_scores:browserRecord.trifecta_scores,training_input:badRecord.training_input},settlement:{outcome_combo:browserRecord.outcome_combo,settlement_odds:42,result_timestamp:'2026-09-24T00:40:00Z'}}},
      'backtest-engine-dev':{mode:'dry_run',payload:{records:[badRecord]}},
    };
    for(const [slug,body] of Object.entries(payloads)){
      calls.length=0;
      const res=await handlers[slug](new Request('https://synthetic.invalid/'+slug,{method:'POST',headers:{Authorization:'Bearer synthetic-only','Content-Type':'application/json'},body:JSON.stringify(body)}));
      const rejected=await res.json();assert.equal(res.status,422,JSON.stringify(rejected));
      assert.equal(rejected.saved,false);assert.equal(rejected.db_write_enabled,false);
      assert(calls.every(([url])=>!url.includes('/functions/v1/')),'invalid conditions must not call a child function');
    }
  }
  console.log(`Synthetic ${count}-rider engine → history pipeline → builder → backtest: PASS`);
 }
 assert(calls.every(([url,method])=>method==='GET'||url.includes('/functions/v1/')));
})().catch(e=>{console.error(e);process.exitCode=1});
