const {chromium}=require(process.env.KEIRIN_PLAYWRIGHT_MODULE||'playwright');
const {spawn,execFileSync}=require('node:child_process');
const {createInterface}=require('node:readline');
const fs=require('node:fs/promises');
const path=require('node:path');
const assert=require('node:assert/strict');
const python=process.env.PYTHON||'python';
const fixtures=JSON.parse(execFileSync(python,['-c',`
import sys,json
sys.path.insert(0,'tests')
from test_held_history_review import pair,evidence,decision
from ml.model_history import _digest
print(json.dumps([{'count':count,'status':status,'records':list(pair(count,status)),
 'reviews':[{'id':_digest(r),'evidence':evidence(r,normal=status!='cancelled'),
 'decision':decision(normal=status!='cancelled')} for r in pair(count,status)]}
 for count in (7,9) for status in ('dead_heat','withdrawn','cancelled')]))
`],{maxBuffer:16*1024*1024}));
async function start(){
 const child=spawn(python,['-m','ml.synthetic_workbench','--synthetic','--port','0'],{stdio:['ignore','pipe','pipe']});
 let stderr='';child.stderr.on('data',b=>stderr+=b);
 const url=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>{child.kill('SIGINT');reject(new Error(stderr||'startup timeout'));},30000);
  createInterface({input:child.stdout}).on('line',line=>{try{const value=JSON.parse(line);if(value.url){clearTimeout(timer);resolve(value.url);}}catch{}});
  child.once('exit',code=>{clearTimeout(timer);reject(new Error(`server exit ${code}: ${stderr}`));});
 });return {url,child};
}
async function stop(server){if(server.child.exitCode!==null)return;const done=new Promise(resolve=>server.child.once('exit',resolve));server.child.kill('SIGINT');await done;}
const file=value=>({name:'synthetic.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(value))});
async function importFile(page,value){await page.locator('#bundle-file').setInputFiles(file(value));await page.locator('#import').click();}
const added=page=>page.getByText('検証して追加しました。終了前に確認一式を保存してください。',{exact:true}).waitFor();
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.KEIRIN_BROWSER_EXECUTABLE||undefined});
 try{for(const width of [390,1280])for(const fixture of fixtures){
  let server=await start();let page;
  try{
   page=await browser.newPage({viewport:{width,height:900},acceptDownloads:true});const errors=[],requests=[];
   page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push(r.url()));
   await page.goto(server.url+'/held-review');await page.getByText('確認一式を読み込めます。',{exact:true}).waitFor();
   await importFile(page,fixture.records);await added(page);
   assert.equal(await page.locator('#counts').textContent(),'保留 2件 / 確認 0件');
   for(const [i,receipt] of fixture.reviews.entries()){
    await page.locator('#source').selectOption(receipt.id);
    assert(await page.locator('#record').isDisabled());
    await page.locator('#evidence-file').setInputFiles(file(receipt.evidence));
    await page.getByText('根拠を読み込みました。対象・結果・時刻を確認して判断を追加してください。',{exact:true}).waitFor();
    await page.locator('#decision').selectOption(receipt.decision.decision);
    await page.locator('#reviewer').fill(receipt.decision.reviewer_id);
    await page.locator('#reviewed-at').fill(receipt.decision.reviewed_at);
    // Empty reasons fail without changing any record; then recover in the same form.
    if(i===0){await page.locator('#record').click();await page.getByText(/review_reason_required/).waitFor();assert.equal(await page.locator('#counts').textContent(),'保留 2件 / 確認 0件');}
    await page.locator('#reason').fill(receipt.decision.reason+' <script>bad()</script>');
    await page.locator('#record').click();await added(page);
    if(i===0)assert((await page.locator('#summary').textContent()).includes('未解決 1レース'));
   }
   const summary=fixture.status==='cancelled'?'評価対象 0レース / 確認済み除外 1レース / 未解決 0レース':'評価対象 1レース / 確認済み除外 0レース / 未解決 0レース';
   assert.equal(await page.locator('#summary').textContent(),summary);
   assert.equal(await page.locator('#metrics .card').count(),2);
   if(fixture.status==='cancelled')assert.equal(await page.getByText(/—（評価対象なし）/).count(),2);
   let waiting=page.waitForEvent('download');await page.locator('#download').click();
   const bundle=JSON.parse(await fs.readFile(await (await waiting).path(),'utf8'));
   assert.equal(bundle.payload.schema_version,'synthetic-held-review-bundle-v1');
   assert.deepEqual(bundle.payload.held_records.slice().sort((a,b)=>a.schema_version.localeCompare(b.schema_version)),fixture.records.slice().sort((a,b)=>a.schema_version.localeCompare(b.schema_version)));
   assert(bundle.payload.reviews.every(r=>r.hold_released===false&&r.supervised_training_enabled===false));
   waiting=page.waitForEvent('download');await page.locator('#report-download').click();
   const report=JSON.parse(await fs.readFile(await (await waiting).path(),'utf8'));
   assert.equal(report.released_races,fixture.status==='cancelled'?0:1);
   await page.reload();await page.getByText('確認一式を読み込めます。',{exact:true}).waitFor();
   assert.equal(await page.locator('#summary').textContent(),summary);
   const bad=structuredClone(bundle);bad.sha256='0'.repeat(64);
   await importFile(page,bad);await page.getByText(/review_bundle_digest_mismatch/).waitFor();
   assert.equal(await page.locator('#counts').textContent(),'保留 2件 / 確認 2件');
   await importFile(page,[fixture.records[0]]);await added(page);
   assert.equal(await page.locator('#counts').textContent(),'保留 2件 / 確認 2件');
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   if(process.env.KEIRIN_SMOKE_ARTIFACT_DIR)await page.screenshot({path:path.join(process.env.KEIRIN_SMOKE_ARTIFACT_DIR,`held-review-${fixture.count}-${fixture.status}-${width}.png`),fullPage:true});
   assert.deepEqual(errors,[]);assert(requests.every(u=>u.startsWith(server.url+'/')));
   if(fixture.count===7&&fixture.status==='dead_heat'){
    // A second tab/import adds an unreviewed hold. The first tab cannot overwrite it.
    const extra=fixtures.find(f=>f.count===7&&f.status==='cancelled').records[0];
    const code=await page.evaluate(async extra=>{const state=await (await fetch('/api/held-review')).json();return (await fetch('/api/held-review/import',{method:'POST',headers:{'Content-Type':'application/json','X-Keirin-Local':'synthetic-only'},body:JSON.stringify({revision:state.revision,value:extra})})).status;},extra);
    assert.equal(code,200);await importFile(page,bundle);
    await page.getByText('別の画面で記録が更新されました。最新状態を表示したので、対象と根拠を選び直してください。',{exact:true}).waitFor();
    assert.equal(await page.locator('#counts').textContent(),'保留 3件 / 確認 2件');
    assert((await page.locator('#summary').textContent()).includes('未解決 1レース'));
    await page.close();page=null;await stop(server);server=await start();
    page=await browser.newPage({viewport:{width,height:900}});await page.goto(server.url+'/held-review');
    await page.getByText('確認一式を読み込めます。',{exact:true}).waitFor();
    assert.equal(await page.locator('#counts').textContent(),'保留 0件 / 確認 0件');
    await importFile(page,bundle);await added(page);assert.equal(await page.locator('#summary').textContent(),summary);
   }
   console.log(`${width}px ${fixture.count} cars ${fixture.status}: evidence/decision, missing hold, export/reload, bad file atomicity, immutable inputs PASS`);
  }finally{if(page)await page.close();await stop(server);}
 }}finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
