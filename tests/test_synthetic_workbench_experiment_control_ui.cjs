const {chromium}=require(process.env.KEIRIN_PLAYWRIGHT_MODULE||'playwright');
const {spawn,execFileSync}=require('node:child_process');
const {once}=require('node:events');
const {createInterface}=require('node:readline');
const fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path'),assert=require('node:assert/strict');
const python=process.env.PYTHON||'python';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.KEIRIN_BROWSER_EXECUTABLE||undefined});
 try{for(const width of [390,1280]){
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'keirin-control-ui-'));
  const cutoff=execFileSync(python,['-c',`import sys
from pathlib import Path
sys.path.insert(0,'tests')
from test_synthetic_workbench_experiment_control import control_fixture
from ml.synthetic_session import SessionStore
cutoff=control_fixture(sys.argv[1])
# Keep one existing snapshot pending so a later hold is a valid new result,
# never an attempted overwrite of an already settled immutable history.
store=SessionStore(Path(sys.argv[1])/'state')
try:
 payload=store.loaded
 del payload['histories'][sorted(payload['histories'])[-1]]
 store.save(payload)
finally: store.close()
print(cutoff)
`,root],{encoding:'utf8'}).trim();
  const statePath=path.join(root,'state','synthetic-session.json'),ledgerPath=path.join(root,'experiments','final-five-experiments.json'),gatePath=path.join(root,'entered');
  const original=await fs.readFile(statePath),origins=[],errors=[],requests=[];let child,page,url;
  async function stop(){if(child&&child.exitCode===null&&child.signalCode===null){const done=once(child,'exit');child.kill('SIGKILL');await done;}}
  async function start(configured=true,gated=false){
   const args=['--synthetic','--port','0','--state-dir',path.join(root,'state'),...(configured?['--final-five-experiment-dir',path.join(root,'experiments')]:[])];
   const entry=gated?['-c',`import sys
from pathlib import Path
from threading import Event
from unittest.mock import patch
from ml.synthetic_workbench import main
root=Path(sys.argv.pop(1))
def gate(*args,**kwargs):
 (root/'entered').write_text('entered')
 Event().wait(60)
 raise RuntimeError('test gate timeout')
with patch('lightgbm.train',side_effect=gate): main()
`,root]:['-m','ml.synthetic_workbench'];
   child=spawn(python,[...entry,...args],{stdio:['ignore','pipe','pipe']});let stderr='';child.stderr.on('data',b=>stderr+=b);
   url=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>{child.kill('SIGKILL');reject(new Error('startup timeout '+stderr));},30000);
    createInterface({input:child.stdout}).on('line',line=>{try{const value=JSON.parse(line);if(value.url){clearTimeout(timer);resolve(value.url);}}catch{}});
    child.once('exit',code=>{clearTimeout(timer);reject(new Error('startup exit '+code+' '+stderr));});});origins.push(url);
  }
  async function shown(){await page.locator('#status').filter({hasText:'保存状態を確認しました。'}).waitFor();}
  const card=id=>page.locator('#attempts [data-id="'+id+'"]');
  async function ledger(){return JSON.parse(await fs.readFile(ledgerPath,'utf8')).payload;}
  async function register(reason,parent=null){await page.locator('#cutoff').selectOption(cutoff);await page.locator('#reason').fill(reason);if(parent)await page.locator('#retry').selectOption(parent);await page.locator('#synthetic-confirm').check();await page.locator('#register').click();}
  async function registered(){await page.locator('#status').filter({hasText:'条件の登録を確認しました。'}).waitFor();return (await ledger()).attempts.at(-1).attempt_id;}
  async function abandon(id,reason){await page.locator('#abandon-'+id).fill(reason);await card(id).locator('[data-action=abandon]').click();await page.locator('#status').filter({hasText:'中断の保存を確認しました。'}).waitFor();}
  async function unconfirmed(){await page.locator('#status').filter({hasText:'操作結果は未確認です。'}).waitFor();assert.equal(await page.locator('#attempts .card').count(),0);}
  async function stateFailed(){await page.locator('#status').filter({hasText:'保存状態を確認できませんでした。'}).waitFor();assert.equal(await page.locator('#attempts .card').count(),0);assert(await page.locator('#registration').isHidden());}
  try{
   await start();page=await browser.newPage({viewport:{width,height:1000},acceptDownloads:true});page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push({url:r.url(),method:r.method(),body:r.postData()}));
   await page.goto(url);await page.locator('#experiment-control-link').click();await shown();assert(await page.locator('#register').isDisabled());
   await assert.rejects(fs.access(ledgerPath),e=>e.code==='ENOENT');
   const registrationPattern='**/api/final-five-training/register';let lose=true;
   await page.route(registrationPattern,async route=>{if(lose){lose=false;await route.fetch();await route.abort('failed');}else await route.continue();});
   await register('条件を固定して合成登録');await unconfirmed();
   const pending=await page.evaluate(()=>JSON.parse(localStorage.getItem('keirin-final-five-experiment-registration-v1'))),first=pending.attempt_id;
   assert.equal((await ledger()).attempts.length,1);assert.equal((await ledger()).attempts[0].status,'registered');
   await page.reload();await shown();assert.equal(await page.evaluate(()=>localStorage.getItem('keirin-final-five-experiment-registration-v1')),null);assert((await card(first).textContent()).includes('登録済み・未実行'));await page.unroute(registrationPattern);
   const runPattern='**/api/final-five-training/run';
   await page.route(runPattern,async route=>{await route.fetch();await route.abort('failed');});
   await card(first).locator('[data-action=run]').click();await unconfirmed();assert.equal((await ledger()).attempts[0].status,'completed');
   const completed=await fs.readFile(ledgerPath);await page.unroute(runPattern);await page.reload();await shown();assert((await card(first).textContent()).includes('合成比較完了'));assert.deepEqual(await fs.readFile(ledgerPath),completed);
   const downloadPromise=page.waitForEvent('download');await card(first).getByText('保存モデルを取得',{exact:true}).click();const download=await downloadPromise;const exported=JSON.parse(await fs.readFile(await download.path(),'utf8'));assert.equal(exported.model.sha256,(await ledger()).attempts[0].result.model.sha256);
   await card(first).getByText('条件・重複・結果の詳細',{exact:true}).click();await page.locator('#detail-title').filter({hasText:'実験 #1'}).waitFor();await page.locator('#manage-link').click();await shown();
   await register('元の実験を残して再試行',first);const second=await registered();
   await card(second).locator('[data-action=abandon]').click();await page.locator('#status').filter({hasText:'中断理由を入力してください。'}).waitFor();assert.equal((await ledger()).attempts[1].status,'registered');
   await abandon(second,'未実行のまま中断を記録');assert.equal((await ledger()).attempts[1].status,'interrupted');
   await register('中断後の明示再試行',second);const third=await registered();assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   assert.deepEqual(await fs.readFile(statePath),original);
   // Kill an actual HTTP fit after its durable running checkpoint. Restoration
   // must expose uncertainty, never continue training or silently retry it.
   await stop();await start(true,true);await page.goto(url+'/final-five-training');await shown();await card(third).locator('[data-action=run]').click();
   let entered=false;for(let i=0;i<250;i++){try{await fs.access(gatePath);entered=true;break;}catch{await new Promise(r=>setTimeout(r,20));}}assert(entered);
   assert.equal((await ledger()).attempts[2].status,'running');const running=await fs.readFile(ledgerPath);await stop();await start();await page.goto(url+'/final-five-training');await shown();
   assert((await card(third).textContent()).includes('実行開始済み・完了未確認'));assert.equal(await card(third).locator('[data-action=run]').count(),0);assert.deepEqual(await fs.readFile(ledgerPath),running);assert.deepEqual(await fs.readFile(statePath),original);
   await abandon(third,'サーバー中断後の完了未確認');await register('原因確認後の別ID再試行',third);const fourth=await registered();
   const hold=await page.evaluate(async()=>{const state=await(await fetch('/api/state')).json(),pending=state.snapshot_list.filter(r=>r.result_status==='pending');if(pending.length!==1)throw Error('expected exactly one pending hold fixture');const r=await fetch('/api/hold',{method:'POST',headers:{'Content-Type':'application/json','X-Keirin-Local':'synthetic-only'},body:JSON.stringify({snapshot_id:pending[0].snapshot_id,result_status:'withdrawn',withdrawn_car_numbers:[1]})});return {status:r.status,body:await r.json()};});assert.equal(hold.status,200,JSON.stringify(hold.body));
   await card(fourth).locator('[data-action=run]').click();await unconfirmed();assert.equal((await ledger()).attempts[3].status,'registered');
   await page.locator('#refresh').click();await shown();assert(await card(fourth).locator('[data-action=run]').isDisabled());assert((await card(fourth).textContent()).includes('登録後に元の履歴が変わったため実行できません。'));
   const statePattern='**/api/final-five-training';
   await page.route(statePattern,async route=>{const response=await route.fetch(),bad=await response.json();bad.audit.product_acceptance=true;await route.fulfill({response,json:bad});});
   await page.locator('#refresh').click();await stateFailed();await page.unroute(statePattern);await page.locator('#refresh').click();await shown();
   let release,reached,calls=0;const gate=new Promise(r=>release=r),seen=new Promise(r=>reached=r);
   await page.route(statePattern,async route=>{if(++calls===1){const response=await route.fetch();reached();await gate;await route.fulfill({response});}else await route.fulfill({status:503,json:{error:'unavailable'}});});
   await page.locator('#refresh').click();await seen;await page.locator('#refresh').click();await stateFailed();const late=page.waitForResponse(r=>r.url()===url+'/api/final-five-training');release();const lateResponse=await late;await lateResponse.finished();await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));await stateFailed();await page.unroute(statePattern);
   await page.evaluate(()=>localStorage.setItem('keirin-final-five-experiment-registration-v1','{bad'));await page.reload();await shown();await page.locator('#pending-note').filter({hasText:'未確認要求を読めません。'}).waitFor();assert(await page.locator('#register').isDisabled());await page.locator('#reset-request').click();assert.equal(await page.evaluate(()=>localStorage.getItem('keirin-final-five-experiment-registration-v1')),null);
   const saved=await fs.readFile(ledgerPath),heldState=await fs.readFile(statePath);await stop();await start(false);await page.goto(url+'/final-five-training');await page.locator('#status').filter({hasText:'操作用の実験台帳が指定されていません。'}).waitFor();assert(await page.locator('#registration').isHidden());assert.equal(await page.locator('#attempts .card').count(),0);
   assert.deepEqual(await fs.readFile(ledgerPath),saved);assert.deepEqual(await fs.readFile(statePath),heldState);assert.equal((await ledger()).attempts.length,4);
   const state=await page.evaluate(async()=>await(await fetch('/api/state')).json());assert.equal(state.model_ready,false);assert.deepEqual(errors,[]);assert(requests.every(r=>origins.some(origin=>r.url.startsWith(origin+'/'))));
   assert(requests.filter(r=>r.method==='POST').every(r=>/\/api\/(final-five-training\/(register|run|abandon)|hold)$/.test(r.url)));
   console.log(`${width}px: explicit synthetic registration/run/abandon, lost responses/reload, saved model download, owned audit, reason/retry chain, real SIGKILL during fit and unknown restore, late hold blocks, malformed/stale state clearing, corrupt request, unconfigured gate, unchanged prediction/model/no external requests PASS`);
  }finally{if(page)await page.close();await stop();await fs.rm(root,{recursive:true,force:true});}
 }}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
