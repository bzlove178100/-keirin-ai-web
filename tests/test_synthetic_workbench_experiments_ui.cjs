const {chromium}=require(process.env.KEIRIN_PLAYWRIGHT_MODULE||'playwright');
const {spawn,execFileSync}=require('node:child_process');
const {once}=require('node:events');
const {createInterface}=require('node:readline');
const fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path'),assert=require('node:assert/strict');
const python=process.env.PYTHON||'python';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.KEIRIN_BROWSER_EXECUTABLE||undefined});
 try{for(const width of [390,1280]){
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'keirin-experiments-ui-'));
  execFileSync(python,['-c',"import sys; sys.path.insert(0,'tests'); from test_synthetic_workbench_experiments import audit_fixture; audit_fixture(sys.argv[1])",root]);
  const ledgerPath=path.join(root,'experiments','final-five-experiments.json');
  const sourcePaths=[ledgerPath,path.join(root,'model.json'),path.join(root,'state','synthetic-session.json'),path.join(root,'selections','final-five-selections.json')];
  const originals=await Promise.all(sourcePaths.map(p=>fs.readFile(p)));
  const model=JSON.parse(originals[1]).model.sha256,origins=[],errors=[],requests=[];
  let child,page,url;
  async function stop(){if(child&&child.exitCode===null&&child.signalCode===null){const done=once(child,'exit');child.kill('SIGKILL');await done;}}
  async function start(configured=true){
   child=spawn(python,['-m','ml.synthetic_workbench','--synthetic','--port','0','--state-dir',path.join(root,'state'),'--final-five-selection-dir',path.join(root,'selections'),'--final-five-experiment',path.join(root,'model.json'),...(configured?['--final-five-experiment-ledger',ledgerPath]:[])],{stdio:['ignore','pipe','pipe']});
   let stderr='';child.stderr.on('data',b=>stderr+=b);
   url=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>{child.kill('SIGKILL');reject(new Error('startup timeout '+stderr));},30000);
    createInterface({input:child.stdout}).on('line',line=>{try{const value=JSON.parse(line);if(value.url){clearTimeout(timer);resolve(value.url);}}catch{}});
    child.once('exit',code=>{clearTimeout(timer);reject(new Error('startup exit '+code+' '+stderr));});});origins.push(url);
  }
  async function shown(count=6){await page.locator('#status').filter({hasText:count===6?'6件の登録を確認しました。':'同じモデルIDの完了記録 2件を確認しました。'}).waitFor();assert.equal(await page.locator('.attempt').count(),count);}
  async function failed(){await page.locator('#status').filter({hasText:'保存記録を確認できませんでした。'}).waitFor();assert.equal(await page.locator('.attempt').count(),0);assert(await page.locator('#detail').isHidden());assert.equal(await page.locator('#revision').textContent(),'');}
  async function select(id){await page.locator('[data-id="'+id.repeat(32)+'"]').click();await page.locator('#detail-title').filter({hasText:'実験 #'+id+' ·'}).waitFor();}
  try{
   await start();page=await browser.newPage({viewport:{width,height:1000}});
   page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push({url:r.url(),method:r.method()}));
   await page.goto(url);await page.locator('#experiment-audit-link').click();await shown();
   assert.equal(await page.locator('#strata tr').count(),6);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   await select('2');assert((await page.locator('#overlap').textContent()).includes('検証の再使用 8'));
   await page.locator('#fields a[href$="'+'1'.repeat(32)+'"]').click();await shown();await page.locator('#detail-title').filter({hasText:'実験 #1 ·'}).waitFor();
   for(const [id,state] of [['3','条件不足・学習なし'],['4','実行失敗'],['5','中断を記録済み'],['6','登録済み・未実行']]){
    await select(id);assert((await page.locator('#detail-title').textContent()).includes(state));assert(await page.locator('#comparison').isHidden());
    if(id==='5'){assert((await page.locator('#fields').textContent()).includes('<img src=x onerror=alert(1)>理由'));assert.equal(await page.locator('img').count(),0);}
   }
   const key='0'.repeat(31)+'1';await page.goto(url+'/final-five-challenger/'+key);await page.locator('#baseline .pick').first().waitFor();
   assert.equal(await page.locator('#model-experiment-link').getAttribute('href'),'/final-five-experiments/model/'+model);
   await page.locator('#model-experiment-link').click();await shown(2);await select('2');assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   await page.goto(url+'/final-five-challenger/'+key);await page.locator('#baseline .pick').first().waitFor();
   await page.locator('#receipt-id').fill('a'.repeat(32));await page.locator('#lookup-receipt').click();await page.locator('#receipt-experiment-link').waitFor();
   assert.equal(await page.locator('#receipt-experiment-link').getAttribute('href'),'/final-five-experiments/model/'+model);
   await page.locator('#receipt-experiment-link').click();await shown(2);
   await page.goto(url+'/final-five-challenger/'+key);await page.locator('#baseline .pick').first().waitFor();
   const comparisonPattern='**/api/final-five-challenger/'+key;
   await page.route(comparisonPattern,async route=>{const response=await route.fetch(),bad=await response.json();bad.product_acceptance=true;await route.fulfill({response,json:bad});});
   await page.locator('#refresh').click();await page.locator('#status').filter({hasText:'確認できませんでした'}).waitFor();assert(await page.locator('#model-experiment-link').isHidden());assert.equal(await page.locator('#model-experiment-link').getAttribute('href'),null);await page.unroute(comparisonPattern);
   await page.locator('#receipt-id').fill('a'.repeat(32));await page.locator('#lookup-receipt').click();await page.locator('#receipt-experiment-link').waitFor();
   const receiptPattern='**/api/final-five-selection/'+'a'.repeat(32);
   await page.route(receiptPattern,async route=>{const response=await route.fetch(),bad=await response.json();bad.evaluation_eligible=true;await route.fulfill({response,json:bad});});
   await page.locator('#lookup-receipt').click();await page.locator('#receipt-status').filter({hasText:'保存済み記録を確認できませんでした。'}).waitFor();assert(await page.locator('#receipt-experiment-link').isHidden());assert.equal(await page.locator('#receipt-experiment-link').getAttribute('href'),null);await page.unroute(receiptPattern);
   await page.goto(url+'/final-five-experiments');await shown();
   const auditPattern='**/api/final-five-experiments';
   await page.route(auditPattern,async route=>{const response=await route.fetch(),bad=await response.json();bad.evaluation_eligible=true;await route.fulfill({response,json:bad});});
   await page.locator('#refresh').click();await failed();await page.unroute(auditPattern);await page.locator('#refresh').click();await shown();
   // An older successful response must never resurrect details after a newer failure.
   let release,reached,calls=0;const gate=new Promise(r=>release=r),seen=new Promise(r=>reached=r);
   await page.route(auditPattern,async route=>{if(++calls===1){const response=await route.fetch();reached();await gate;await route.fulfill({response});}else await route.fulfill({status:503,json:{error:'changed'}});});
   await page.locator('#refresh').click();await seen;await page.locator('#refresh').click();await failed();
   const late=page.waitForResponse(r=>r.url()===url+'/api/final-five-experiments');release();const lateResponse=await late;await lateResponse.finished();
   await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));await failed();await page.unroute(auditPattern);
   await page.goto(url+'/final-five-experiments/model/'+'f'.repeat(64));await page.locator('#status').filter({hasText:'同じモデルIDの完了記録が見つかりません。'}).waitFor();assert(await page.locator('#detail').isHidden());
   await page.goto(url+'/final-five-experiments/attempt/'+'f'.repeat(32));await page.locator('#status').filter({hasText:'指定した実験を確認できません。'}).waitFor();assert(await page.locator('#detail').isHidden());
   await page.goto(url+'/final-five-experiments');await shown();
   await fs.appendFile(ledgerPath,' ');await page.locator('#refresh').click();await failed();
   await fs.writeFile(ledgerPath,originals[0]);await page.locator('#refresh').click();await failed();
   await stop();await start();await page.goto(url+'/final-five-experiments');await shown();
   assert.deepEqual(await Promise.all(sourcePaths.map(p=>fs.readFile(p))),originals);
   await stop();execFileSync(python,['-c',`import sys
from unittest.mock import patch
from ml.final_five_experiment_ledger import ExperimentLedger
ledger=ExperimentLedger(sys.argv[1],synthetic=True)
try:
 with patch('lightgbm.train',side_effect=KeyboardInterrupt):
  try: ledger.run('6'*32)
  except KeyboardInterrupt: pass
finally: ledger.close()
`,path.join(root,'experiments')]);
   const running=await fs.readFile(ledgerPath);await start();await page.goto(url+'/final-five-experiments/attempt/'+'6'.repeat(32));await shown();
   await page.locator('#detail-title').filter({hasText:'実行開始済み・完了未確認'}).waitFor();assert((await page.locator('#state-note').textContent()).includes('自動再実行はしません。'));assert.deepEqual(await fs.readFile(ledgerPath),running);
   await stop();await start(false);await page.goto(url+'/final-five-experiments');await page.locator('#status').filter({hasText:'実験台帳が指定されていません。'}).waitFor();assert.equal(await page.locator('.attempt').count(),0);assert(await page.locator('#detail').isHidden());
   assert.deepEqual(await Promise.all(sourcePaths.slice(1).map(p=>fs.readFile(p))),originals.slice(1));assert.deepEqual(await fs.readFile(ledgerPath),running);
   const state=await page.evaluate(async()=>await(await fetch('/api/state')).json());assert.equal(state.model_ready,false);
   assert.deepEqual(errors,[]);assert(requests.every(r=>r.method==='GET'&&origins.some(origin=>r.url.startsWith(origin+'/'))));
   console.log(`${width}px: experiment history states, duplicate-model links, receipt links, overlap, escaped reasons, malformed/stale clearing, missing matches, changed checkpoint refusal, SIGKILL read-only restore and unfinished run, unconfigured distinction, source unchanged/no training/external requests PASS`);
  }finally{if(page)await page.close();await stop();await fs.rm(root,{recursive:true,force:true});}
 }}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
