const assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const fs=require('node:fs');
const web=require('../model-web-response.js');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const origin='https://bzlove178100.github.io';
const service='https://synthetic-auth.invalid';
let registered,calls=[],userStatus=200,profiles=[{role:'owner',plan:'owner'}];
global.Deno={env:{get:k=>({SUPABASE_URL:service,SUPABASE_ANON_KEY:'synthetic-publishable'}[k])},serve:handler=>{registered=handler;}};
global.fetch=async(url,options)=>{
 calls.push({url,options});assert.equal(options.headers.Authorization,'Bearer synthetic-session');
 assert.equal(options.headers.apikey,'synthetic-publishable');assert(!options.method||options.method==='GET');
 if(url===service+'/auth/v1/user')return Response.json({id:'synthetic-owner'},{status:userStatus});
 if(url===service+'/rest/v1/user_profiles?user_id=eq.synthetic-owner&select=role,plan')return Response.json(profiles);
 throw Error('unexpected external request: '+url);
};
(async()=>{
 const {SYNTHETIC_MODEL_VIEWS:bundle}=await import(pathToFileURL(process.argv[2]).href);
 const {createPredictHandler}=await import('../supabase/functions/predict-engine-dev/index.ts');
 const handler=createPredictHandler(bundle),key=bundle.views[0].snapshot_id;
 const request=(body,headers={})=>new Request('https://synthetic-function.invalid',{method:body===undefined?'GET':'POST',headers:{Origin:origin,Authorization:'Bearer synthetic-session','Content-Type':'application/json',...headers},...(body===undefined?{}:{body:JSON.stringify(body)})});
 const valid={mode:'synthetic_model_view',snapshot_id:key};
 for(const [body,headers,status] of [[valid,{Authorization:''},401],[valid,{Origin:'https://untrusted.invalid'},403]]){
  calls=[];assert.equal((await handler(request(body,headers))).status,status);assert.equal(calls.length,0);
 }
 userStatus=401;calls=[];assert.equal((await handler(request(valid))).status,401);assert.equal(calls.length,1);userStatus=200;
 for(const p of [[{role:'owner',plan:'free'}],[{role:'admin',plan:'owner'}],[{role:'owner',plan:'admin'}],[],[{role:'owner',plan:'owner'},{role:'owner',plan:'owner'}]]){
  profiles=p;calls=[];const response=await handler(request(valid));assert.equal(response.status,403);assert(!('model_view' in await response.json()));assert.equal(calls.length,2);
 }
 profiles=[{role:'owner',plan:'owner'}];
 let response=await registered(request(valid));assert.equal(response.status,503);assert.equal((await response.json()).error,'synthetic_model_bundle_not_prepared');
 response=await registered(request());assert.equal((await response.json()).synthetic_model_preview.available,false);
 response=await handler(request());const status=await response.json();assert.equal(status.synthetic_model_preview.available,true);
 assert.deepEqual(status.synthetic_model_preview.snapshots.map(v=>v.rider_count),[7,9]);
 for(const view of bundle.views){
  calls=[];response=await handler(request({...valid,snapshot_id:view.snapshot_id}));assert.equal(response.status,200);
  assert.equal(response.headers.get('access-control-allow-origin'),origin);assert.equal(response.headers.get('cache-control'),'no-store');
  const body=await response.json();assert.equal(body.authenticated,true);assert.equal(body.owner,true);
  assert.equal(body.prediction_generated,false);assert.equal(body.saved,false);assert.equal(body.production_prediction_enabled,false);assert.equal(body.db_write_enabled,false);
  assert.deepEqual(body.model_view,view);web.validate(body.model_view);assert.equal(calls.length,2);
 }
 for(const bad of [{...valid,model_view:bundle.views[0]},{...valid,bundle},{...valid,race_data:input.legacy_input},{...valid,url:service},{...valid,snapshot_id:'../x'}])assert.equal((await handler(request(bad))).status,400);
 assert.equal((await handler(request({...valid,snapshot_id:'0'.repeat(32)}))).status,404);
 for(const mutate of [b=>b.views[0].db_write_enabled=true,b=>b.views[0].private_extra='secret',b=>b.views[1].snapshot_id=b.views[0].snapshot_id,b=>b.views[0].race.venue='REAL',b=>b.views.pop()]){
  const bad=structuredClone(bundle);mutate(bad);response=await createPredictHandler(bad)(request(valid));assert.equal(response.status,503);assert(!('model_view' in await response.json()));
 }
 response=await handler(request({mode:'dry_run',race_data:input.legacy_input}));assert.equal(response.status,200);
 const legacy=await response.json();assert.equal(legacy.mode,'dry_run');assert.equal(legacy.prediction_generated,true);assert.equal(legacy.saved,false);assert(!('model_view' in legacy));
 assert.equal(legacy.prediction.trifecta_scores.length,210);
 for(const race_conditions of [null,{},[],{race_status:'cancelled',withdrawn_car_numbers:[]},{race_status:'scheduled',withdrawn_car_numbers:[7]}]){
  response=await handler(request({mode:'dry_run',race_data:{...input.legacy_input,race_conditions}}));
  assert.equal(response.status,422);
  const rejected=await response.json();assert.equal(rejected.prediction_generated,false);
  assert.equal(rejected.saved,false);assert.equal(rejected.db_write_enabled,false);
 }
 console.log('owner API: actual 7/9 ML bundle, unchanged role+plan gate, no bundle/unsafe/client override rejection, legacy dry-run PASS');
})().catch(error=>{console.error(error);process.exitCode=1;});
