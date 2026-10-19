// Actual owner page and Edge handlers; all HTTP is fulfilled locally with generated fixtures.
const {chromium}=require(process.env.KEIRIN_PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs'),fsp=require('node:fs/promises'),path=require('node:path'),vm=require('node:vm');
const {stripTypeScriptTypes}=require('node:module'),assert=require('node:assert/strict');
const {snapshot}=require('./test_prospective_tools.cjs'),core=require('../prospective-tools-core.js');
const common=require('../supabase/functions/_shared/race_probability.ts');
const training=require('../supabase/functions/history-pipeline-dev/training_input.ts');
const origin='https://bzlove178100.github.io',service='https://omamgmyyqnawlagbemcm.supabase.co';
const token='synthetic-only',user={id:'synthetic-owner',email:'owner@example.invalid'};
const handlers={},posts=[];
async function localFetch(url,options={}){
 assert.equal(options.headers.Authorization,'Bearer '+token);
 if(url===service+'/auth/v1/user')return Response.json(user);
 if(url===service+'/rest/v1/user_profiles?user_id=eq.synthetic-owner&select=role,plan')return Response.json([{role:'owner',plan:'owner'}]);
 const slug=url.split('/functions/v1/')[1];assert(handlers[slug],url);
 return handlers[slug](new Request(url,options));
}
for(const slug of ['history-builder-dev','backtest-engine-dev','history-pipeline-dev']){
 const source=fs.readFileSync(`supabase/functions/${slug}/index.ts`,'utf8').replace(/^import .*;\n/gm,'');
 vm.runInNewContext(stripTypeScriptTypes(source),{...common,...training,console,structuredClone,Request,Response,fetch:localFetch,
  Deno:{env:{get:key=>({SUPABASE_URL:service,SUPABASE_ANON_KEY:'synthetic-key'}[key])},serve:handler=>handlers[slug]=handler}});
}
const upload=(name,value)=>({name,mimeType:'application/json',buffer:Buffer.from(JSON.stringify(value))});
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.KEIRIN_BROWSER_EXECUTABLE||undefined});
 try{
  for(const width of [390,1280]){
   const context=await browser.newContext({viewport:{width,height:900},timezoneId:'Asia/Tokyo'});
   const page=await context.newPage(),errors=[],unexpected=[];
   let supported=false;
   page.on('pageerror',error=>errors.push(error.message));
   await page.route('**/*',async route=>{
    const request=route.request(),url=new URL(request.url());
    if(url.origin===origin){
     if(url.pathname==='/favicon.ico')return route.fulfill({status:204,body:''});
     const name=path.basename(url.pathname);
     if(['index.html','prospective-tools-core.js','model-web-response.js','model-owner-preview.js'].includes(name))
      return route.fulfill({body:await fsp.readFile(name),contentType:name.endsWith('.js')?'text/javascript':'text/html'});
    }
    if(url.origin===service){
     const headers={'Access-Control-Allow-Origin':origin,'Access-Control-Allow-Headers':'authorization,apikey,content-type','Access-Control-Allow-Methods':'GET,POST,OPTIONS'};
     const json=(body,status=200)=>route.fulfill({status,headers,contentType:'application/json',body:JSON.stringify(body)});
     if(request.method()==='OPTIONS')return route.fulfill({headers,body:'ok'});
     if(url.pathname==='/auth/v1/token')return json({access_token:token,refresh_token:'synthetic-refresh',expires_in:3600,user});
     if(url.pathname==='/auth/v1/logout')return json({});
     if(url.pathname==='/rest/v1/user_profiles')return json([{role:'owner',plan:'owner'}]);
     if(url.pathname==='/functions/v1/predict-race')return json({success:true,authenticated:true,owner:true,role:'owner',plan:'owner'});
     if(url.pathname==='/functions/v1/predict-status')return json({success:true,production_prediction_enabled:false,db_write_enabled:false,external_fetch_enabled:false});
     if(url.pathname==='/functions/v1/predict-engine-dev')return json({success:false},503);
     const slug=url.pathname.split('/').pop();
     if(handlers[slug]){
      const body=request.postData();if(body)posts.push({slug,body:JSON.parse(body)});
      const forwarded=new Headers(request.headers());forwarded.set('Origin',origin);
      const response=await handlers[slug](new Request(request.url(),{method:request.method(),headers:forwarded,...(body?{body}:{})}));
      const data=await response.json();
      if(!body&&!supported){delete data.held_history_schema;delete data.held_result_supported;}
      return json(data,response.status);
     }
    }
    unexpected.push(request.url());return route.abort();
   });
   await page.goto(origin+'/-keirin-ai-web/index.html');
   await page.locator('#email').fill(user.email);await page.locator('#password').fill('synthetic-password');await page.locator('#login').click();
   await page.getByText('Web側でowner権限を確認しました。',{exact:true}).waitFor();
   await page.waitForFunction(()=>historyPipelineReady && backtestEngineReady);
   for(const count of [7,9]){
    const snap=snapshot(0,'SYNTHETIC_GENERATED',count);snap.race_data.race.venue='GENERATED';snap.race_data.race.race_number=count;
    await page.locator('#history-snapshot-file').setInputFiles(upload('generated-snapshot.json',snap));
    await page.locator('#history-snapshot-note').filter({hasText:'読み込み済み'}).waitFor();
    await page.locator('#result-status').selectOption('dead_heat');
    if(!supported){
     assert(await page.locator('#run-history').isDisabled());assert.equal(posts.length,0);
     supported=true;await page.locator('#refresh').click();
     await page.waitForFunction(()=>historyHeldReady && backtestHeldReady);
    }
    for(const status of ['dead_heat','withdrawn','cancelled']){
     await page.locator('#result-status').selectOption(status);
     assert(await page.locator('#result-combo').isDisabled());assert(await page.locator('#result-odds').isDisabled());
     assert.equal(await page.locator('#withdrawn-cars').isVisible(),status==='withdrawn');
     await page.locator('#result-time').fill(status==='dead_heat'?'2026-09-24T09:40':'2026-09-24T09:20');
     if(status==='withdrawn')await page.locator('#withdrawn-cars').fill(String(count));
     await page.locator('#run-history').click();
     await page.locator('#history-note').filter({hasText:'保留履歴JSONを生成しました'}).waitFor();
     assert.match(await page.locator('#training-readiness').textContent(),/学習対象外/);
     await new Promise(resolve=>setTimeout(resolve,300));
     const pending=page.waitForEvent('download');await page.locator('#save-history').click();
     const download=await pending;
     assert.match(download.suggestedFilename(),new RegExp(`^backtest-history-2026-09-24-GENERATED-${count}\\.json$`));
     const envelope=JSON.parse(await fsp.readFile(await download.path(),'utf8')),held=envelope.payload.records[0];
     assert.equal(core.validateHeldHistory(held),true);assert.equal(held.settlement.result_status,status);
     // Real input listeners invalidate a previous download immediately.
     await page.locator('#result-time').fill('2026-09-24T09:41');assert(await page.locator('#save-history').isDisabled());
     const normal=core.buildHistory(snap,{outcomeCombo:'1-2-3',settlementOdds:42,resultTimestamp:'2026-09-24T00:40:00Z'});
     await page.locator('#history-dataset-files').setInputFiles(upload('mixed.json',{records:[normal,held]}));
     await page.waitForFunction(()=>document.getElementById('history-dataset-files').value==='');
     await page.locator('#run-dataset-backtest').click();
     await page.locator('#bt-overall').filter({hasText:'評価対象なし'}).waitFor();
     assert.equal(await page.locator('#bt-hit').textContent(),'評価対象なし');
     assert(!(await page.locator('#bt-overall').textContent()).includes('ROI'));
     assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    }
   }
   await page.locator('#logout').click();await page.locator('#logged-out').waitFor({state:'visible'});
   assert(await page.locator('#run-history').isDisabled());assert(await page.locator('#run-dataset-backtest').isDisabled());
   assert.equal(await page.evaluate(()=>historyHeldReady || backtestHeldReady),false);
   assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[]);posts.length=0;
   await context.close();
  }
  console.log('Owner held capability, generation/save/reload/exclusion, 7/9 riders, phone/desktop: PASS');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
