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
 document:{getElementById:node,createElement:()=>new Element()}});
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
 context.forward=async(url,body)=>{
  const slug=new URL(url).pathname.split('/').pop();assert(handlers[slug],slug);
  const response=await localFetch(service+'/functions/v1/'+slug,{method:'POST',
   headers:{Authorization:'Bearer synthetic-only','Content-Type':'application/json'},body:JSON.stringify(body)});
  const data=await response.json();
  if(response.ok){assert.equal(data.saved,false);assert.equal(data.db_write_enabled,false);assert.equal(data.production_prediction_enabled,false);}
  return Response.json(slug==='predict-engine-dev'?transform(data):data,{status:response.status});
 };
 run('currentSession={user:{id:"synthetic-owner"}};historyPipelineReady=true;authenticatedPost=forward;');
 async function load(race){
  context.event={target:{files:[{name:'generated.json',size:1000,text:async()=>JSON.stringify(race)}]}};
  await run('loadRaceFile(event)');node('scheduled-start').value='2026-09-24T09:30';node('prestart-confirmed').checked=true;
 }
 for(const count of [9,7]){
  const race=snapshot(0,'SYNTHETIC_GENERATED',count).race_data;
  race.race.venue='SYNTHETIC';race.race.race_number=count;
  race.players.forEach(p=>p.name='SYNTHETIC RIDER '+p.car_number);
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
  context.record=record;assert(run('normalizeDatasetRecord(record)!==null'));assert.equal(run('trainingReadiness(record)'),null);
  // A normalized complete table for the OTHER roster must still fail closed.
  const other=count===9?7:9;
  transform=data=>({...data,prediction:{...data.prediction,trifecta_scores:snapshot(0,'SYNTHETIC_GENERATED',other).engine_response.prediction.trifecta_scores}});
  await load(race);await run('runRealDryRun()');
  assert.match(node('run-dry-note').textContent,/安全条件を確認できない/);
  assert.equal(run('lastDryRunSnapshot'),null);assert.equal(node('save-snapshot').disabled,true);
  assert(!node('cat-hit').textContent.includes('位'));transform=data=>data;
  console.log(`Web + actual dev handlers: ${count}-rider prediction -> snapshot -> history -> backtest and mismatched-roster rejection PASS`);
 }
 assert(calls.every(c=>c.method==='GET'||c.url.includes('/functions/v1/')));
})().catch(error=>{console.error(error);process.exitCode=1;});
