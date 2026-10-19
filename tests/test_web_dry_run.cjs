// Actual Web and dev handlers, generated races, synthetic owner auth; no sockets.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {stripTypeScriptTypes}=require('node:module');
const {snapshot}=require('./test_prospective_tools.cjs');
const common=require('../supabase/functions/_shared/race_probability.ts');
const training=require('../supabase/functions/history-pipeline-dev/training_input.ts');
class Element {
 constructor(){this.value='';this.checked=false;this.disabled=false;this.children=[];this._text='';this.className='';this.classList={contains:()=>true,add(){},remove(){}};}
 appendChild(child){this.children.push(child);return child;}
 replaceChildren(){this.children=[];this._text='';}
 set textContent(value){this._text=value;this.children=[];}
 get textContent(){return this._text+this.children.map(c=>c.textContent).join('');}
 addEventListener(){}
}
const nodes=new Map(),node=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
const fixed='2026-09-24T00:00:00.000Z';
class Clock extends Date {constructor(...args){super(...(args.length?args:[fixed]));}static now(){return Date.parse(fixed);}}
const context=vm.createContext({console,Date:Clock,Intl,URL,Blob,setTimeout,clearTimeout,
 ProspectiveTools:require('../prospective-tools-core.js'),
 sessionStorage:{removeItem(){}},document:{getElementById:node,createElement:()=>new Element()}});
const source=fs.readFileSync('index.html','utf8').match(/<script>([\s\S]*?)<\/script>/)[1]
 .replace('(async()=>{await restoreLogin();await checkStatus();})();','');
vm.runInContext(source,context);
const run=code=>vm.runInContext(code,context);
const service='https://synthetic.invalid',handlers={},calls=[];
const deno={env:{get:key=>({SUPABASE_URL:service,SUPABASE_ANON_KEY:'synthetic-only'}[key])},serve(){}};
async function localFetch(url,options={}){
 calls.push({url,method:options.method||'GET'});
 assert(url.startsWith(service+'/'));
 assert.equal(options.headers.Authorization,'Bearer synthetic-only');
 if(url===service+'/auth/v1/user')return Response.json({id:'synthetic-owner'});
 if(url===service+'/rest/v1/user_profiles?user_id=eq.synthetic-owner&select=role,plan')return Response.json([{role:'owner',plan:'owner'}]);
 const slug=url.split('/functions/v1/')[1];assert(handlers[slug],url);
 return handlers[slug](new Request(url,options));
}
global.Deno=deno;global.fetch=localFetch;
for(const slug of ['history-builder-dev','backtest-engine-dev','history-pipeline-dev']){
 const raw=fs.readFileSync(`supabase/functions/${slug}/index.ts`,'utf8').replace(/^import .*;\n/gm,'');
 vm.runInNewContext(stripTypeScriptTypes(raw),{...common,...training,console,structuredClone,Request,Response,
  fetch:localFetch,Deno:{...deno,serve:handler=>handlers[slug]=handler}},{filename:slug});
}
(async()=>{
 const {createPredictHandler}=await import('../supabase/functions/predict-engine-dev/index.ts');
 handlers['predict-engine-dev']=createPredictHandler(null);
 let transform=data=>data;
 let transformGet=data=>data, transformPost=data=>data, pausePost=null;
 context.get=async url=>{
  const slug=new URL(url).pathname.split('/').pop();
  const response=await localFetch(service+'/functions/v1/'+slug,{headers:{Authorization:'Bearer synthetic-only'}});
  return Response.json(transformGet(await response.json()),{status:response.status});
 };
 context.forward=async(url,body)=>{
  const slug=new URL(url).pathname.split('/').pop();assert(handlers[slug],slug);
  const response=await localFetch(service+'/functions/v1/'+slug,{method:'POST',
   headers:{Authorization:'Bearer synthetic-only','Content-Type':'application/json'},body:JSON.stringify(body)});
  const data=await response.json();
  if(response.ok){assert.equal(data.saved,false);assert.equal(data.db_write_enabled,false);assert.equal(data.production_prediction_enabled,false);}
  if(pausePost){const wait=pausePost;pausePost=null;await wait;}
  return Response.json(slug==='predict-engine-dev'?transform(data):transformPost(data,slug),{status:response.status});
 };
 run('currentSession={user:{id:"synthetic-owner"}};authenticatedPost=forward;authenticatedGet=get;');
 async function load(race){
  context.event={target:{files:[{name:'generated.json',size:1000,text:async()=>JSON.stringify(race)}]}};
  await run('loadRaceFile(event)');node('scheduled-start').value='2026-09-24T09:30';node('prestart-confirmed').checked=true;
 }
 for(const count of [9,7]){
  node('result-status').value='normal';await run('checkHistoryPipeline()');await run('checkBacktestEngine()');
  const race=snapshot(0,'SYNTHETIC_GENERATED',count).race_data;
  race.race.venue='SYNTHETIC';race.race.race_number=count;
  race.players.forEach(p=>p.name='SYNTHETIC RIDER '+p.car_number);
  race.race_conditions={race_status:'scheduled',withdrawn_car_numbers:[]};
  await load(race);await run('runRealDryRun()');
  assert.match(node('run-dry-note').textContent,/dry-run完了/,`${count}-rider prediction must display`);
  assert.equal(node('save-snapshot').disabled,false);
  const captured=JSON.parse(run('JSON.stringify(lastDryRunSnapshot)'));
  assert.equal(captured.race_data.players.length,count);
  assert.equal(captured.engine_response.prediction.trifecta_scores.length,count*(count-1)*(count-2));
  assert.equal(captured.snapshot_eligibility.prospective,true);
  assert.equal(node('cat-hit').children.length,3);
  assert(!node('cat-hit').textContent.includes('undefined'));
  context.event={target:{files:[{name:'generated-snapshot.json',size:1000,text:async()=>JSON.stringify(captured)}]}};
  await run('loadHistorySnapshotFile(event)');
  node('result-combo').value=`${count}-${count-1}-${count-2}`;node('result-odds').value='42';
  // Settlement is later than the fixed prediction/start and before the test result clock.
  Clock.now=()=>Date.parse('2026-09-24T00:45:00Z');node('result-time').value='2026-09-24T00:40:00Z';
  await run('runHistoryPipeline()');
  assert.match(node('history-note').textContent,/履歴JSONを生成しました.*DB保存0件/);
  const record=JSON.parse(node('history-json').value).payload.records[0];
  assert.equal(record.outcome_combo,`${count}-${count-1}-${count-2}`);
  assert.equal(record.trifecta_scores.length,count*(count-1)*(count-2));
  assert.deepEqual(record.training_input.race_conditions,race.race_conditions);
  context.record=record;assert(run('normalizeDatasetRecord(record)!==null'));assert.equal(run('trainingReadiness(record)'),null);
  const held=context.ProspectiveTools.buildHeldHistory(captured,{result_status:'withdrawn',withdrawn_car_numbers:[count],result_timestamp:'2026-09-24T00:20:00Z'});
  context.held=held;assert(run('normalizeDatasetRecord(held)!==null'));
  // A safe older API still supports normal results, but cannot receive holds.
  transformGet=data=>{delete data.held_result_supported;delete data.held_history_schema;return data;};
  await run('checkHistoryPipeline()');await run('checkBacktestEngine()');
  node('result-status').value='withdrawn';node('withdrawn-cars').value=String(count);await run('historyInputChanged()');
  assert.equal(node('run-history').disabled,true);calls.length=0;
  await run('runHistoryPipeline()');assert.equal(calls.length,0);
  context.event={target:{files:[{name:'mixed.json',size:1000,text:async()=>JSON.stringify({records:[record,held]})}]}};
  run('historyDatasetRecords=[]');await run('loadHistoryDatasetFiles(event)');
  assert.equal(run('historyDatasetRecords.length'),2);
  assert.equal(run('prospectiveCollectionStatus(historyDatasetRecords).held_unique_races'),1);
  assert.equal(node('run-dataset-backtest').disabled,true);
  calls.length=0;await run('runHistoryDatasetBacktest()');assert.equal(calls.length,0);
  assert.match(node('history-dataset-note').textContent,/保留記録を保持/);
  node('backtest-json').value=JSON.stringify({records:[held]});
  calls.length=0;await run('runBacktestDryRun()');assert.equal(calls.length,0);
  // Supported schema and verified owner are both needed; stale flags are cleared.
  for(const mutate of [data=>({...data,held_history_schema:'unknown'}),data=>({...data,held_result_supported:false}),data=>({...data,authenticated:false}),data=>({...data,db_write_enabled:true})]){
   transformGet=mutate;await run('checkHistoryPipeline()');await run('checkBacktestEngine()');
   assert.equal(run('historyHeldReady || backtestHeldReady'),false);
   assert.equal(node('run-dataset-backtest').disabled,true);
  }
  transformGet=data=>data;await run('checkHistoryPipeline()');await run('checkBacktestEngine()');
  assert.equal(node('run-dataset-backtest').disabled,false);
  for(const status of ['dead_heat','withdrawn','cancelled']){
   node('result-status').value=status;node('result-time').value=status==='dead_heat'?'2026-09-24T00:40:00Z':'2026-09-24T00:20:00Z';
   run('historyInputChanged()');calls.length=0;await run('runHistoryPipeline()');
   const generated=JSON.parse(node('history-json').value).payload.records[0];
   assert.equal(generated.settlement.result_status,status);assert.equal(generated.race_id,held.race_id);
   assert.equal(context.ProspectiveTools.validateHeldHistory(generated),true);
   assert.equal(node('save-history').disabled,false);assert.match(node('training-readiness').textContent,/学習対象外/);
   assert.match(node('history-backtest-summary').textContent,/未実行/);
   assert(!calls.some(c=>/history-builder-dev|backtest-engine-dev/.test(c.url)));
   run('historyInputChanged()');assert.equal(run('lastHistoryBacktestPayload'),null);
   assert.equal(node('save-history').disabled,true);assert.equal(node('backtest-json').value,'');
  }
  // Corrupt or unsafe held responses never become downloadable JSON.
  for(const corrupt of [
   data=>({...data,saved:true}),data=>({...data,monetary_ev_enabled:true}),
   data=>({...data,backtest_result:{records:1}}),data=>({...data,training_input_present:true}),
   data=>{data.history_record.outcome_combo='1-2-3';return data;},
   data=>{data.history_record.snapshot.race_data.race.venue='OTHER';return data;},
   data=>{data.backtest_request.payload.records=[];return data;}
  ]){
   transformPost=corrupt;await run('runHistoryPipeline()');
   assert.equal(run('lastHistoryBacktestPayload'),null);assert.equal(node('save-history').disabled,true);
   assert.match(node('history-note').textContent,/安全条件を確認できません/);
  }
  transformPost=data=>data;
  // Input edits invalidate pending responses too, not just already rendered output.
  let release;pausePost=new Promise(resolve=>release=resolve);
  const pending=run('runHistoryPipeline()');run('historyInputChanged()');release();await pending;
  assert.equal(run('lastHistoryBacktestPayload'),null);
  // Held-only and same-race mixed batches render no numeric metric; another race remains evaluable.
  for(const records of [[held],[held,record],[record,held]]){
   context.batch=records;run('historyDatasetRecords=batch');await run('runHistoryDatasetBacktest()');
   assert.match(node('bt-overall').textContent,/評価対象なし/);assert(!/ROI|0\.00%/.test(node('bt-overall').textContent));
   assert.equal(node('bt-hit').textContent,'評価対象なし');
  }
  const unrelated=structuredClone(record);unrelated.race_id+='-unrelated';
  context.batch=[held,record,unrelated];run('historyDatasetRecords=batch');await run('runHistoryDatasetBacktest()');
  assert.match(node('bt-overall').textContent,/レース 1.*保留 1レース.*同一レース通常履歴除外 1件/);
  for(const corrupt of [data=>{data.result.records++;return data;},data=>{data.result.held_race_ids=[];return data;},data=>{data.result.excluded={};return data;}]){
   transformPost=corrupt;await run('runHistoryDatasetBacktest()');
   assert.match(node('backtest-note').textContent,/バックテストできません/);
   assert(!node('bt-overall').textContent.includes('ROI'));
  }
  context.batch=[held];run('historyDatasetRecords=batch');
  transformPost=data=>{data.result.selection_performance={picks:0,hits:0};return data;};
  await run('runHistoryDatasetBacktest()');assert.match(node('backtest-note').textContent,/バックテストできません/);
  transformPost=data=>data;
  pausePost=new Promise(resolve=>release=resolve);
  const expired=run('runHistoryPipeline()');run('clearSession()');release();await expired;
  assert.equal(run('lastHistoryBacktestPayload'),null);assert.equal(run('historyHeldReady || backtestHeldReady'),false);
  run('currentSession={user:{id:"synthetic-owner"}}');await run('checkHistoryPipeline()');await run('checkBacktestEngine()');
  const heldTools=context.ProspectiveTools;delete context.ProspectiveTools;
  assert.equal(run('normalizeDatasetRecord(held)'),null);
  assert.equal(run('prospectiveCollectionStatus(historyDatasetRecords).eligible_unique_races'),0);
  await run('loadHistoryDatasetFiles(event)');assert.equal(run('historyDatasetRecords.length'),0);
  assert.match(node('history-dataset-note').textContent,/検査器を読み込めません/);
  context.ProspectiveTools=heldTools;run('historyDatasetRecords=[]');
  node('result-status').value='normal';run('historyInputChanged()');
  // A normalized complete table for the OTHER roster must still fail closed.
  const other=count===9?7:9;
  transform=data=>({...data,prediction:{...data.prediction,trifecta_scores:snapshot(0,'SYNTHETIC_GENERATED',other).engine_response.prediction.trifecta_scores}});
  await load(race);await run('runRealDryRun()');
  assert.match(node('run-dry-note').textContent,/安全条件を確認できない/);
  assert.equal(run('lastDryRunSnapshot'),null);assert.equal(node('save-snapshot').disabled,true);
  assert(!node('cat-hit').textContent.includes('位'));transform=data=>data;
  for(const conditions of [null,{race_status:'cancelled',withdrawn_car_numbers:[]},{race_status:'scheduled',withdrawn_car_numbers:[count]}]){
   const bad=structuredClone(race);bad.race_conditions=conditions;
   calls.length=0;await load(bad);await run('runRealDryRun()');
   assert.match(node('run-dry-note').textContent,/通常レースとして処理できません/);
   assert.equal(calls.length,0);assert.equal(run('lastDryRunSnapshot'),null);
   assert.equal(node('save-snapshot').disabled,true);
   context.record=structuredClone(record);context.record.training_input.race_conditions=conditions;
   assert.equal(run('normalizeDatasetRecord(record)'),null);
   assert.match(run('trainingReadiness(record)'),/通常レースとして処理できません/);
   const badSnapshot=structuredClone(captured);badSnapshot.race_data.race_conditions=conditions;
   context.event={target:{files:[{name:'invalid.json',size:1000,text:async()=>JSON.stringify(badSnapshot)}]}};
   await run('loadHistorySnapshotFile(event)');assert.equal(run('loadedHistorySnapshot'),null);
   assert.equal(node('run-history').disabled,true);
  }
  const tools=context.ProspectiveTools;delete context.ProspectiveTools;
  context.race=race;assert.match(run('raceConditionsIssue(race)'),/読み込めません/);
  context.ProspectiveTools=tools;
  console.log(`Web + actual dev handlers: ${count}-rider prediction -> snapshot -> history -> backtest and mismatched-roster rejection PASS`);
 }
 assert(calls.every(c=>c.method==='GET'||c.url.includes('/functions/v1/')));
})().catch(error=>{console.error(error);process.exitCode=1;});
