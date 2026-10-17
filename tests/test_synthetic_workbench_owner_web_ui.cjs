// Exercise the complete prepared index.html. Every remote request is intercepted.
const {chromium}=require(process.env.KEIRIN_PLAYWRIGHT_MODULE||'playwright');
const {execFileSync}=require('node:child_process');
const fs=require('node:fs/promises');
const os=require('node:os');
const path=require('node:path');
const assert=require('node:assert/strict');
const origin='https://bzlove178100.github.io';
const service='https://omamgmyyqnawlagbemcm.supabase.co';
const token='synthetic-session',user={id:'synthetic-owner',email:'owner@example.invalid'};
let authStatus=200;
global.Deno={env:{get:k=>({SUPABASE_URL:service,SUPABASE_ANON_KEY:'synthetic-publishable'}[k])},serve(){}};
global.fetch=async(url,options)=>{
 assert.equal(options.headers.Authorization,'Bearer '+token);
 if(url===service+'/auth/v1/user')return Response.json(user,{status:authStatus});
 if(url===service+'/rest/v1/user_profiles?user_id=eq.synthetic-owner&select=role,plan')return Response.json([{role:'owner',plan:'owner'}]);
 throw Error('unexpected server request: '+url);
};
(async()=>{
 const tmp=await fs.mkdtemp(path.join(os.tmpdir(),'keirin-owner-web-ui-'));
 let browser;
 try{
  const output=path.join(tmp,'candidate');
  execFileSync(process.env.PYTHON||'python',['-m','ml.prepare_owner_web_preview','--output-dir',output]);
  const bundle=JSON.parse(execFileSync(process.env.PYTHON||'python',['-c',
   "import sys,json;sys.path.insert(0,'tests');from test_synthetic_workbench_owner_web import bundle;print(json.dumps(bundle()))"],{encoding:'utf8'}));
  const {createPredictHandler}=await import('../supabase/functions/predict-engine-dev/index.ts');
  const handler=createPredictHandler(bundle);
  browser=await chromium.launch({headless:true,executablePath:process.env.KEIRIN_BROWSER_EXECUTABLE||undefined});
  for(const width of [390,1280]){
   const page=await browser.newPage({viewport:{width,height:900}}),errors=[],unexpected=[],posts=[];
   let unavailable=false,corrupt=false,release=null,started=null,delay=false;
   page.on('pageerror',e=>errors.push(e.message));
   await page.route('**/*',async route=>{
    const request=route.request(),url=new URL(request.url());
    if(url.origin===origin){
     if(url.pathname==='/favicon.ico')return route.fulfill({status:204,body:''});
     const name=path.basename(url.pathname);
     if(['index.html','prospective-tools-core.js','model-web-response.js','model-owner-preview.js'].includes(name)){
      return route.fulfill({status:200,contentType:name.endsWith('.js')?'text/javascript':'text/html',body:await fs.readFile(path.join(output,name),'utf8')});
     }
    }else if(url.origin===service){
     const headers={'Access-Control-Allow-Origin':origin,'Access-Control-Allow-Headers':'authorization,apikey,content-type','Access-Control-Allow-Methods':'GET,POST,OPTIONS','Cache-Control':'no-store'};
     if(request.method()==='OPTIONS')return route.fulfill({status:200,headers,body:'ok'});
     const json=(body,status=200)=>route.fulfill({status,headers,contentType:'application/json',body:JSON.stringify(body)});
     if(url.pathname==='/auth/v1/token')return json({access_token:token,refresh_token:'synthetic-refresh',expires_in:3600,user});
     if(url.pathname==='/auth/v1/logout')return json({});
     if(url.pathname==='/rest/v1/user_profiles')return json([{role:'owner',plan:'owner'}]);
     if(url.pathname==='/functions/v1/predict-engine-dev'){
      assert.equal(request.headers().authorization,'Bearer '+token);
      const body=request.postData();if(body)posts.push(JSON.parse(body));
      const forwardedHeaders=new Headers(request.headers());forwardedHeaders.set('Origin',origin);
      const response=await (unavailable?createPredictHandler(null):handler)(new Request(request.url(),{
       method:request.method(),headers:forwardedHeaders,...(body?{body}:{})}));
      let data=await response.json();
      if(corrupt&&body&&JSON.parse(body).mode==='synthetic_model_view')data.model_view.snapshot_id='a'.repeat(32);
      if(delay&&body){if(started)started();await new Promise(resolve=>release=resolve);}
      return json(data,response.status);
     }
     if(url.pathname==='/functions/v1/predict-race')return json({success:true,authenticated:true,owner:true,role:'owner',plan:'owner'});
     if(url.pathname==='/functions/v1/predict-status')return json({success:true,production_prediction_enabled:false,db_write_enabled:false,external_fetch_enabled:false});
     if(['/functions/v1/history-pipeline-dev','/functions/v1/backtest-engine-dev'].includes(url.pathname))return json({success:false},503);
    }
    unexpected.push(request.url());return route.abort();
   });
   await page.goto(origin+'/-keirin-ai-web/index.html');
   await page.locator('#owner-model-panel').waitFor();
   assert(await page.locator('#owner-model-display').isDisabled());
   await page.locator('#email').fill(user.email);await page.locator('#password').fill('synthetic-password');await page.locator('#login').click();
   await page.getByText('Web側でowner権限を確認しました。',{exact:true}).waitFor();
   await page.locator('#owner-model-refresh').click();
   await page.getByText('7車・9車の保存済みモデルを選択できます。',{exact:true}).waitFor();
   for(const v of bundle.views){
    await page.locator('#owner-model-select').selectOption(v.snapshot_id);await page.locator('#owner-model-display').click();
    await page.getByText('保存済みの合成予測を表示しました。',{exact:true}).waitFor();
    assert((await page.locator('#owner-model-model-race').textContent()).includes(v.quality.rider_count+'車'));
    const ids=['cat-hit','cat-balance','cat-middle','cat-longshot','cat-super'];
    for(const [i,category] of Object.values(v.categories).entries())assert.deepEqual(
     await page.locator('#owner-model-'+ids[i]+' .combo').allTextContents(),category.picks.map(p=>`${p.rank}位  ${p.combo_key}`));
    assert.equal(await page.evaluate(()=>lastDryRunSnapshot),null);
    assert.equal(await page.locator('#cat-hit .pick-item').count(),0);
    assert(await page.locator('#save-snapshot').isDisabled());
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   }
   if(process.env.KEIRIN_SMOKE_ARTIFACT_DIR)await page.locator('#owner-model-panel').screenshot({path:path.join(process.env.KEIRIN_SMOKE_ARTIFACT_DIR,`owner-model-${width}.png`)});
   corrupt=true;await page.locator('#owner-model-display').click();
   await page.getByText('モデル結果を確認できませんでした。ログイン状態を確認し、再度お試しください。',{exact:true}).waitFor();
   assert.equal(await page.locator('#owner-model-panel .pick-item').count(),0);corrupt=false;
   unavailable=true;await page.locator('#owner-model-refresh').click();await page.getByText('保存済みモデルはまだ準備されていません。',{exact:true}).waitFor();
   assert(await page.locator('#owner-model-display').isDisabled());unavailable=false;
   await page.locator('#owner-model-refresh').click();await page.getByText('7車・9車の保存済みモデルを選択できます。',{exact:true}).waitFor();
   authStatus=401;await page.locator('#owner-model-display').click();await page.getByText('モデル結果を確認できませんでした。ログイン状態を確認し、再度お試しください。',{exact:true}).waitFor();
   assert.equal(await page.locator('#owner-model-panel .pick-item').count(),0);authStatus=200;
   await page.locator('#owner-model-refresh').click();await page.getByText('7車・9車の保存済みモデルを選択できます。',{exact:true}).waitFor();
   delay=true;const inFlight=new Promise(resolve=>started=resolve);await page.locator('#owner-model-display').click();await inFlight;
   await page.locator('#logout').click();await page.locator('#logged-out').waitFor({state:'visible'});
   const finished=page.waitForResponse(r=>r.url().endsWith('/predict-engine-dev')&&r.request().method()==='POST');release();await finished;
   await page.waitForFunction(()=>document.getElementById('owner-model-model-status').textContent==='ログイン後に保存済みモデルを確認してください。');
   assert.equal(await page.locator('#owner-model-panel .pick-item').count(),0);
   assert(posts.every(b=>b.mode==='synthetic_model_view'&&Object.keys(b).sort().join(',')==='mode,snapshot_id'));
   assert.deepEqual(unexpected,[]);assert.deepEqual(errors,[]);
   console.log(`${width}px: full owner page login + actual synthetic handler + 7/9 display + failure/logout clearing PASS`);
   await page.close();
  }
 }finally{if(browser)await browser.close();await fs.rm(tmp,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1;});
