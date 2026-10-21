const {chromium}=require(process.env.KEIRIN_PLAYWRIGHT_MODULE||'playwright');
const {spawn,execFileSync}=require('node:child_process');
const {once}=require('node:events');
const {createInterface}=require('node:readline');
const fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path'),assert=require('node:assert/strict');
const python=process.env.PYTHON||'python';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.KEIRIN_BROWSER_EXECUTABLE||undefined});
 try{for(const width of [390,1280]){
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'keirin-selection-ui-'));
  execFileSync(python,['-c',`import json,sys
from pathlib import Path
sys.path.insert(0,'tests')
from test_synthetic_workbench_challenger import preview_fixture
from ml.synthetic_session import SessionStore
experiment,session=preview_fixture();root=Path(sys.argv[1])
(root/'experiment.json').write_text(json.dumps(experiment))
store=SessionStore(root/'state')
try:store.save(session)
finally:store.close()
`,root]);
  const statePath=path.join(root,'state','synthetic-session.json'),ledgerPath=path.join(root,'selections','final-five-selections.json');
  const original=await fs.readFile(statePath);let child,page,url;const errors=[],requests=[],origins=[];
  async function stop(){if(child&&child.exitCode===null&&child.signalCode===null){const done=once(child,'exit');child.kill('SIGKILL');await done;}}
  async function start(model=true){
   child=spawn(python,['-m','ml.synthetic_workbench','--synthetic','--port','0','--state-dir',path.join(root,'state'),'--final-five-selection-dir',path.join(root,'selections'),...(model?['--final-five-experiment',path.join(root,'experiment.json')]:[])],{stdio:['ignore','pipe','pipe']});
   let stderr='';child.stderr.on('data',b=>stderr+=b);
   return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{child.kill('SIGKILL');reject(new Error('startup timeout '+stderr));},30000);
    createInterface({input:child.stdout}).on('line',line=>{try{const value=JSON.parse(line);if(value.url){clearTimeout(timer);resolve(value.url);}}catch{}});
    child.once('exit',code=>{clearTimeout(timer);reject(new Error('startup exit '+code+' '+stderr));});});
  }
  const key=String(1).padStart(32,'0'),pendingKey='keirin-final-five-selection:'+key;
  async function goto(k=key){await page.goto(url+'/final-five-challenger/'+k);await page.locator('#baseline .pick').first().waitFor();}
  async function saved(sequence){await page.getByText(new RegExp(`^保存済み記録 #${sequence} ·`)).waitFor();assert(await page.locator('#save-selection').isDisabled());}
  async function ledger(){return JSON.parse(await fs.readFile(ledgerPath,'utf8')).payload;}
  try{
   url=await start();origins.push(url);page=await browser.newPage({viewport:{width,height:1000}});
   page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push({url:r.url(),method:r.method(),body:r.postData()}));
   await goto();assert(await page.locator('#save-selection').isEnabled());
   await assert.rejects(fs.access(ledgerPath),e=>e.code==='ENOENT');
   await page.locator('#save-selection').click();await page.getByText('保存要求を準備できませんでした。理由・ブラウザの保存設定・表示モデルを確認してください。未確認のIDは変更しません。',{exact:true}).waitFor();
   assert.equal(requests.filter(r=>r.method==='POST').length,0);
   await page.locator('#selection-reason').fill('合成比較の保存');
   // The server commits, but the browser loses the response. Retrying keeps
   // the exact ID and must return the first receipt without a second append.
   const postPattern='**/api/final-five-selection';let lost=true;
   await page.route(postPattern,async route=>{if(lost){lost=false;await route.fetch();await route.abort('failed');}else await route.continue();});
   await page.locator('#save-selection').click();await page.getByText('保存成功は未確認です。',{exact:true}).waitFor();
   const firstRequest=await page.evaluate(k=>JSON.parse(localStorage.getItem(k)),pendingKey);
   assert.equal((await ledger()).receipts.length,1);
   await page.locator('#save-selection').click();await saved(1);await page.unroute(postPattern);
   const posts=requests.filter(r=>r.method==='POST');assert.equal(posts.length,2);assert.equal(posts[0].body,posts[1].body);
   assert.equal((await ledger()).receipts.length,1);await page.reload();await saved(1);
   assert.equal(await page.locator('#receipt-id').inputValue(),firstRequest.request_id);
   await page.locator('#new-selection').click();await page.locator('#selection-reason').fill('合成選び直しを記録');
   // Two synchronous clicks cannot race two saves.
   await page.locator('#save-selection').evaluate(button=>{button.click();button.click();});await saved(2);
   const secondRequest=await page.evaluate(k=>JSON.parse(localStorage.getItem(k)),pendingKey);
   assert.notEqual(secondRequest.request_id,firstRequest.request_id);assert.equal((await ledger()).receipts.length,2);
   assert.deepEqual(await fs.readFile(statePath),original);
   // Bad/stale lookups clear the previous receipt details and never claim success.
   const lookupPattern='**/api/final-five-selection/'+secondRequest.request_id;
   await page.route(lookupPattern,async route=>{const response=await route.fetch(),bad=await response.json();bad.evaluation_eligible=true;await route.fulfill({response,json:bad});});
   await page.locator('#lookup-receipt').click();await page.getByText('保存済み記録を確認できませんでした。保存成功とは扱いません。IDと保存先を確認してください。',{exact:true}).waitFor();
   assert.equal(await page.locator('#receipt-detail').textContent(),'');await page.unroute(lookupPattern);
   let release,reached;const gate=new Promise(r=>release=r),seen=new Promise(r=>reached=r);
   await page.route(lookupPattern,async route=>{const response=await route.fetch();reached();await gate;await route.fulfill({response});});
   await page.locator('#lookup-receipt').click();await seen;await page.locator('#receipt-id').fill('f'.repeat(32));await page.locator('#lookup-receipt').click();
   await page.getByText('保存済み記録を確認できませんでした。保存成功とは扱いません。IDと保存先を確認してください。',{exact:true}).waitFor();
   const late=page.waitForResponse(r=>r.url()===url+'/api/final-five-selection/'+secondRequest.request_id);release();const lateResponse=await late;await lateResponse.finished();
   await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
   assert.equal(await page.locator('#receipt-detail').textContent(),'');await page.unroute(lookupPattern);
   console.log(`${width}px: response-loss retry, reload, reselection and stale/malformed receipt checks passed`);
   // A hold arriving after the comparison was displayed is checked at submit.
   await page.locator('#new-selection').click();await page.locator('#selection-reason').fill('保留直前の合成要求');
   let send,reachedPost;const postGate=new Promise(r=>send=r),postSeen=new Promise(r=>reachedPost=r);
   await page.route(postPattern,async route=>{reachedPost();await postGate;await route.continue();});
   await page.locator('#save-selection').click();await postSeen;
   const holdStatus=await page.evaluate(async k=>(await fetch('/api/hold',{method:'POST',headers:{'Content-Type':'application/json','X-Keirin-Local':'synthetic-only'},body:JSON.stringify({snapshot_id:k,result_status:'withdrawn',withdrawn_car_numbers:[1]})})).status,key);
   assert.equal(holdStatus,200);send();await page.getByText('保存成功は未確認です。',{exact:true}).waitFor();await page.unroute(postPattern);
   assert.equal((await ledger()).receipts.length,2);await page.locator('#refresh').click();await page.getByText('基準を表示しました。AI候補は利用できません。',{exact:true}).waitFor();
   assert(await page.locator('#save-selection').isDisabled());assert.equal(await page.locator('#challenger .pick').count(),0);
   await page.locator('#receipt-id').fill(secondRequest.request_id);await page.locator('#lookup-receipt').click();await saved(2);
   // Save each remaining 7/9 x 3/4/5 case; GET/reload alone never appends.
   for(let i=2;i<=6;i++){
    const k=String(i).padStart(32,'0');await goto(k);await page.locator('#selection-reason').fill('合成ケース '+i);await page.locator('#save-selection').click();await saved(i+1);
    const last=(await ledger()).receipts.at(-1);assert.equal(last.comparison.baseline.selected_count,[5,3,4][(i-1)%3]);assert.equal(last.comparison.baseline.rider_count,i<=3?7:9);
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   }
   const lastKey=String(6).padStart(32,'0');await page.evaluate(k=>localStorage.setItem('keirin-final-five-selection:'+k,'{bad'),lastKey);await page.reload();
   await page.getByText('ブラウザの保存要求を読めません。保存成功とは扱いません。以前の要求IDを確認してください。',{exact:true}).waitFor();assert(await page.locator('#save-selection').isDisabled());assert(await page.locator('#new-selection').isHidden());
   const checkpoint=await fs.readFile(ledgerPath),stateAfterHold=await fs.readFile(statePath);
   await stop();url=await start(false);origins.push(url);await goto();await page.getByText('基準を表示しました。AI候補は利用できません。',{exact:true}).waitFor();
   await page.locator('#receipt-id').fill(secondRequest.request_id);await page.locator('#lookup-receipt').click();await saved(2);
   assert.equal(await page.locator('#challenger .pick').count(),0);assert.deepEqual(await fs.readFile(ledgerPath),checkpoint);assert.deepEqual(await fs.readFile(statePath),stateAfterHold);
   const state=await page.evaluate(async()=>await(await fetch('/api/state')).json());assert.equal(state.model_ready,false);
   assert.deepEqual(errors,[]);assert(requests.every(r=>origins.some(origin=>r.url.startsWith(origin+'/'))));
   console.log(`${width}px: synthetic 7/9 x 3/4/5 explicit selection saves, lost response/idempotent retry, reload and SIGKILL restore, reselection retained, malformed/stale receipt clearing, late hold blocks, corrupt browser request blocks, model-free historical read, source unchanged/no training/external requests PASS`);
  }finally{if(page)await page.close();await stop();await fs.rm(root,{recursive:true,force:true});}
 }}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
