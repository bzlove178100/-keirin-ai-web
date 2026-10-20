const {chromium}=require(process.env.KEIRIN_PLAYWRIGHT_MODULE||'playwright');
const {spawn,execFileSync}=require('node:child_process');
const {once}=require('node:events');
const {createInterface}=require('node:readline');
const fs=require('node:fs/promises');
const os=require('node:os');
const path=require('node:path');
const assert=require('node:assert/strict');
const python=process.env.PYTHON||'python';
const ready=page=>page.getByText('確認一式を読み込めます。',{exact:true}).waitFor();
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.KEIRIN_BROWSER_EXECUTABLE||undefined});
 try{for(const width of [390,1280])for(const count of [7,9]){
  const directory=await fs.mkdtemp(path.join(os.tmpdir(),'keirin-session-transfer-'));
  const evidenceText=execFileSync(python,['-c',`
import sys,json
sys.path.insert(0,'tests')
from ml.synthetic_workbench import Workbench
from test_synthetic_workbench_session_transfer import seed
from test_held_history_review import evidence
app=Workbench(sys.argv[1])
try:
 seed(app)
 count=int(sys.argv[2]); key=('a' if count==7 else 'b')*32
 app.hold(key,'cancelled')
 value=evidence(app.histories[key],normal=count==7)
 if count==7: value['result']['settlement_odds']=40.0
 print(json.dumps(value,ensure_ascii=False))
finally: app.close()
`,directory,String(count)]).toString().trim();
  let child,page;const errors=[],requests=[],origins=[],posts=[],decisions=[];let downloads=0;
  async function start(){
   child=spawn(python,['-m','ml.synthetic_workbench','--synthetic','--port','0','--state-dir',directory],{stdio:['ignore','pipe','pipe']});
   let stderr='';child.stderr.on('data',b=>stderr+=b);
   return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{child.kill('SIGKILL');reject(new Error('startup timeout: '+stderr));},30000);
    createInterface({input:child.stdout}).on('line',line=>{try{const v=JSON.parse(line);if(v.url){clearTimeout(timer);origins.push(v.url);resolve(v.url);}}catch{}});
    child.once('exit',code=>{clearTimeout(timer);reject(new Error('startup exit '+code+': '+stderr));});
   });
  }
  async function stop(){if(child&&child.exitCode===null&&child.signalCode===null){const done=once(child,'exit');child.kill('SIGKILL');await done;}}
  try{
   let url=await start();page=await browser.newPage({viewport:{width,height:900}});
   page.on('pageerror',e=>errors.push(e.message));page.on('download',()=>downloads++);
   page.on('request',r=>{requests.push(r.url());if(r.url().endsWith('/import-session'))posts.push(JSON.parse(r.postData()));if(r.url().endsWith('/decision'))decisions.push(JSON.parse(r.postData()));});
   await page.goto(url+'/held-review');await ready(page);
   assert.equal(await page.locator('#session-summary').textContent(),'予測画面の保留 1件 / 追加済み 0件');
   // A second tab changes the source after the displayed list was read.
   const other=(count===7?'b':'a').repeat(32);
   const code=await page.evaluate(async snapshot_id=>(await fetch('/api/hold',{method:'POST',headers:{'Content-Type':'application/json','X-Keirin-Local':'synthetic-only'},body:JSON.stringify({snapshot_id,result_status:'withdrawn',withdrawn_car_numbers:[1]})})).status,other);
   assert.equal(code,200);
   const frozen=await fs.readFile(path.join(directory,'synthetic-session.json'));
   await page.locator('#session-import').click();
   await page.getByText('別の画面で記録が更新されました。最新状態を表示したので、対象と根拠を選び直してください。',{exact:true}).waitFor();
   await page.getByText('予測画面の保留 2件 / 追加済み 0件',{exact:true}).waitFor();
   assert.equal(await page.locator('#counts').textContent(),'保留 0件 / 確認 0件');
   await page.locator('#session-import').click();
   await page.getByText('検証して追加し、自動保存しました。',{exact:true}).waitFor();
   await page.getByText('予測画面の保留 2件 / 追加済み 2件',{exact:true}).waitFor();
   assert.equal(await page.locator('#counts').textContent(),'保留 2件 / 確認 0件');
   assert((await page.locator('#summary').textContent()).includes('未解決 2レース'));
   assert(await page.locator('#session-import').isDisabled());
   assert.deepEqual(await fs.readFile(path.join(directory,'synthetic-session.json')),frozen);
   const reviewState=await page.evaluate(async()=>await(await fetch('/api/held-review')).json());
   const target=reviewState.records.find(r=>r.race_identity.race_number===count);
   const otherTarget=reviewState.records.find(r=>r.sha256!==target.sha256);
   await page.locator('#source').selectOption(target.sha256);
   // Syntax/UTF-8 limits and edits must never leave an older loaded input active.
   for(const text of [evidenceText,'{',JSON.stringify('あ'.repeat(1100))]){
    await page.locator('#evidence-text').fill(text);
    assert(await page.locator('#record').isDisabled());
    await page.locator('#evidence-use').click();
    assert.equal(await page.locator('#record').isEnabled(),text===evidenceText);
   }
   await page.locator('#evidence-text').fill(evidenceText);
   await page.locator('#evidence-use').click();
   await page.locator('#source').selectOption(otherTarget.sha256);
   assert.equal(await page.locator('#evidence-text').inputValue(),'');
   assert(await page.locator('#record').isDisabled());
   await page.locator('#source').selectOption(target.sha256);
   await page.locator('#decision').selectOption(count===7?'correct_declaration':'confirm_nonstandard');
   await page.locator('#reviewer').fill('synthetic-paste-reviewer');
   await page.locator('#reviewed-at').fill('2026-10-17T02:30:00Z');
   await page.locator('#reason').fill('Explicitly supplied generated test evidence.');
   const beforeDecision=await fs.readFile(path.join(directory,'held-review','held-review.json'));
   const wrong=JSON.parse(evidenceText);wrong.race_identity.race_number=12;
   await page.locator('#evidence-text').fill(JSON.stringify(wrong));await page.locator('#evidence-use').click();
   const submit=async()=>{const [response]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/held-review/decision')),page.locator('#record').click()]);return response.status();};
   assert.equal(await submit(),400);
   await page.waitForFunction(()=>!document.getElementById('evidence-text').disabled);
   assert.deepEqual(await fs.readFile(path.join(directory,'held-review','held-review.json')),beforeDecision);
   await page.locator('#evidence-text').fill(evidenceText);await page.locator('#evidence-use').click();
   await page.locator('#evidence-text').fill(evidenceText+' ');
   assert(await page.locator('#record').isDisabled());
   await page.locator('#evidence-use').click();
   assert.equal(await submit(),200);
   await page.getByText('保留 2件 / 確認 1件',{exact:true}).waitFor();
   assert.equal(decisions.length,2);assert.equal(decisions[1].evidence_json,evidenceText+' ');
   assert.equal(await page.locator('#evidence-text').inputValue(),'');
   assert(await page.locator('#record').isDisabled());
   assert.deepEqual(await fs.readFile(path.join(directory,'synthetic-session.json')),frozen);
   const checkpoint=await fs.readFile(path.join(directory,'held-review','held-review.json'));
   await stop();url=await start();await page.goto(url+'/held-review');await ready(page);
   assert.equal(await page.locator('#counts').textContent(),'保留 2件 / 確認 1件');
   assert(await page.locator('#session-import').isDisabled());
   assert((await page.locator('#storage-note').textContent()).includes('復元'));
   assert.deepEqual(await fs.readFile(path.join(directory,'held-review','held-review.json')),checkpoint);
   const state=await page.evaluate(async()=>await(await fetch('/api/state')).json());
   assert.equal(state.model_ready,false);
   assert.equal(downloads,0);
   assert(posts.length===2&&posts.every(p=>Object.keys(p).sort().join(',')==='revision,source_revision'));
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   assert.deepEqual(errors,[]);assert(requests.every(u=>origins.some(o=>u.startsWith(o+'/'))));
   console.log(`${width}px ${count} cars: no file handoff, pasted evidence exact text, UTF-8/syntax/mismatch refusal, edit/source invalidation, saved decision SIGKILL restore, no training PASS`);
  }finally{if(page)await page.close();await stop();await fs.rm(directory,{recursive:true,force:true});}
 }}finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
