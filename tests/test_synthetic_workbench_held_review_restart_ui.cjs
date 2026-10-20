const {chromium}=require(process.env.KEIRIN_PLAYWRIGHT_MODULE||'playwright');
const {spawn,execFileSync}=require('node:child_process');
const {once}=require('node:events');
const {createInterface}=require('node:readline');
const fs=require('node:fs/promises');
const os=require('node:os');
const path=require('node:path');
const assert=require('node:assert/strict');
const python=process.env.PYTHON||'python';
const fixtures=JSON.parse(execFileSync(python,['-c',`
import sys,json
sys.path.insert(0,'tests')
from test_held_history_review import pair,evidence,decision
from ml.model_history import _digest
print(json.dumps([{'count':count,'normal':normal,'records_json':json.dumps(list(pair(count,status))),
 'decisions':[{'id':_digest(r),'evidence_json':json.dumps(evidence(r,normal=normal)),
 'decision':decision(normal=normal)} for r in pair(count,status)]}
 for count,status,normal in [(7,'dead_heat',True),(9,'cancelled',False)]]))
`],{maxBuffer:16*1024*1024}));
const file=text=>({name:'generated.json',mimeType:'application/json',buffer:Buffer.from(text)});
const ready=page=>page.getByText('確認一式を読み込めます。',{exact:true}).waitFor();
const saved=page=>page.getByText('検証して追加し、自動保存しました。',{exact:true}).waitFor();
const state=page=>page.evaluate(async()=>await (await fetch('/api/held-review')).json());
async function importFile(page,text){await page.locator('#bundle-file').setInputFiles(file(text));await page.locator('#import').click();}
async function decide(page,receipt){
 await page.locator('#source').selectOption(receipt.id);
 await page.locator('#evidence-file').setInputFiles(file(receipt.evidence_json));
 await page.getByText('根拠を読み込みました。対象・結果・時刻を確認して判断を追加してください。',{exact:true}).waitFor();
 await page.locator('#decision').selectOption(receipt.decision.decision);
 await page.locator('#reviewer').fill(receipt.decision.reviewer_id);
 await page.locator('#reviewed-at').fill(receipt.decision.reviewed_at);
 await page.locator('#reason').fill(receipt.decision.reason);
 await page.locator('#record').click();await saved(page);
}
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.KEIRIN_BROWSER_EXECUTABLE||undefined});
 try{for(const width of [390,1280])for(const fixture of fixtures){
  const directory=await fs.mkdtemp(path.join(os.tmpdir(),'keirin-held-restart-'));
  const checkpoint=path.join(directory,'held-review','held-review.json');
  let child,page;const origins=[],requests=[],errors=[];
  async function start(){
   child=spawn(python,['-m','ml.synthetic_workbench','--synthetic','--port','0','--state-dir',directory],{stdio:['ignore','pipe','pipe']});
   let stderr='';child.stderr.on('data',b=>stderr+=b);
   return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{child.kill('SIGKILL');reject(new Error('startup timeout: '+stderr));},30000);
    createInterface({input:child.stdout}).on('line',line=>{try{const v=JSON.parse(line);if(v.url){clearTimeout(timer);origins.push(v.url);resolve(v.url);}}catch{}});
    child.once('exit',code=>{clearTimeout(timer);reject(new Error('startup exit '+code+': '+stderr));});
   });
  }
  async function stop(signal='SIGINT'){
   if(child&&child.exitCode===null&&child.signalCode===null){const stopped=once(child,'exit');child.kill(signal);await stopped;}
  }
  try{
   let url=await start();page=await browser.newPage({viewport:{width,height:900},acceptDownloads:true});
   page.on('request',r=>requests.push(r.url()));page.on('pageerror',e=>errors.push(e.message));
   await page.goto(url+'/held-review');await ready(page);
   assert((await page.locator('#storage-note').textContent()).includes('自動保存'));
   assert.equal((await state(page)).storage.checkpoint_saved,false);
   await importFile(page,fixture.records_json);await saved(page);
   await decide(page,fixture.decisions[0]);const partial=await state(page);
   assert.equal(partial.report.unresolved_races,1);
   assert.equal(partial.report.released_races,0);
   assert.equal(JSON.parse(await fs.readFile(checkpoint,'utf8')).sha256,partial.revision);
   await stop('SIGKILL');url=await start();await page.goto(url+'/held-review');await ready(page);
   let restored=await state(page);
   assert.equal(restored.storage.restored,true);assert.equal(restored.storage.write_blocked,false);
   assert.equal(restored.revision,partial.revision);assert.deepEqual(restored.report,partial.report);
   assert.deepEqual(restored.records,partial.records);
   assert((await page.locator('#storage-note').textContent()).includes('復元'));
   await decide(page,fixture.decisions[1]);const complete=await state(page);
   assert.equal(complete.report.released_races,fixture.normal?1:0);
   assert.equal(complete.report.confirmed_excluded_races,fixture.normal?0:1);
   const downloaded=page.waitForEvent('download');await page.locator('#download').click();
   const backup=await fs.readFile(await (await downloaded).path(),'utf8');
   assert.equal(JSON.parse(backup).sha256,complete.revision);
   await stop('SIGKILL');url=await start();await page.goto(url+'/held-review');await ready(page);
   restored=await state(page);assert.equal(restored.revision,complete.revision);assert.deepEqual(restored.report,complete.report);
   // A real external file edit causes an actual API 503; the UI must stop writes.
   const disk=await fs.readFile(checkpoint);
   await fs.writeFile(checkpoint,'synthetic external edit');
   await importFile(page,fixture.records_json);
   await page.getByText('保存を確認できないため、追加操作を停止しました。サーバーを再起動して保存済み記録を照合してください。',{exact:true}).waitFor();
   assert.equal(await fs.readFile(checkpoint,'utf8'),'synthetic external edit');
   assert.equal((await state(page)).revision,complete.revision);
   assert(await page.locator('#import').isDisabled());assert(await page.locator('#record').isDisabled());
   assert(await page.locator('#evidence-file').isDisabled());assert(!(await page.locator('#source').isDisabled()));
   // Explicitly repairing a generated test file does not unblock the old process.
   await fs.writeFile(checkpoint,disk);assert.equal((await state(page)).storage.write_blocked,true);
   await stop('SIGKILL');url=await start();await page.goto(url+'/held-review');await ready(page);
   restored=await state(page);assert.equal(restored.storage.write_blocked,false);assert.equal(restored.revision,complete.revision);
   const predictions=await page.evaluate(async()=>await (await fetch('/api/state')).json());
   assert.equal(predictions.model_ready,false);assert.equal(predictions.saved_snapshots,0);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   assert.deepEqual(errors,[]);assert(requests.every(u=>origins.some(origin=>u.startsWith(origin+'/'))));
   console.log(`${width}px ${fixture.count} cars: automatic save, SIGKILL, partial/complete restore, real 503 blocks writes, verified restart without training PASS`);
  }finally{if(page)await page.close();await stop();await fs.rm(directory,{recursive:true,force:true});}
 }}finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
