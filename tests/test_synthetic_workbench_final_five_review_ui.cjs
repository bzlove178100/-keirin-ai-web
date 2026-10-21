const {chromium}=require(process.env.KEIRIN_PLAYWRIGHT_MODULE||'playwright');
const {spawn,execFileSync}=require('node:child_process');
const {once}=require('node:events');
const {createInterface}=require('node:readline');
const fs=require('node:fs/promises');
const os=require('node:os');
const path=require('node:path');
const assert=require('node:assert/strict');
const python=process.env.PYTHON||'python';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.KEIRIN_BROWSER_EXECUTABLE||undefined});
 try{for(const width of [390,1280]){
  const directory=await fs.mkdtemp(path.join(os.tmpdir(),'keirin-final-review-'));
  execFileSync(python,['-c',`import sys
sys.path.insert(0,'tests')
from ml.synthetic_session import SessionStore
from test_synthetic_workbench_final_five_review import review_session
store=SessionStore(sys.argv[1])
try: store.save(review_session())
finally: store.close()
`,directory]);
  const empty=JSON.parse(execFileSync(python,['-c',`import json
from ml.synthetic_workbench import Workbench
app=Workbench()
try: print(json.dumps(app.final_five_report()))
finally: app.close()
`],{encoding:'utf8'}));
  const original=await fs.readFile(path.join(directory,'synthetic-session.json'));
  let child,page;const errors=[],requests=[];
  try{
   child=spawn(python,['-m','ml.synthetic_workbench','--synthetic','--port','0','--state-dir',directory],{stdio:['ignore','pipe','pipe']});
   let stderr='';child.stderr.on('data',b=>stderr+=b);
   const url=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>{child.kill('SIGKILL');reject(new Error('startup timeout: '+stderr));},30000);
    createInterface({input:child.stdout}).on('line',line=>{try{const v=JSON.parse(line);if(v.url){clearTimeout(timer);resolve(v.url);}}catch{}});
    child.once('exit',code=>{clearTimeout(timer);reject(new Error('startup exit '+code+': '+stderr));});
   });
   page=await browser.newPage({viewport:{width,height:900},acceptDownloads:true});
   page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push({url:r.url(),method:r.method()}));
   await page.goto(url);await page.getByText('7車または9車を選んで開始できます。',{exact:true}).waitFor();
   assert.equal(await page.locator('#final-five-review-link').getAttribute('href'),'/final-five-review');
   const [response]=await Promise.all([page.waitForResponse(r=>r.url()===url+'/api/final-five-review'),page.locator('#final-five-review-link').click()]);
   const value=await response.json();
   async function populated(){
    await page.getByText('合成結果の診断を表示しています。',{exact:true}).waitFor();
    assert.equal(await page.locator('#counts').textContent(),'評価 10レース · 保留 2レース · 結果未入力 2予測 · 古い重複 0件');
    assert.equal(await page.locator('.race').count(),10);
    for(const count of [7,9])for(const size of [3,4,5]){
     const group=page.locator(`[data-group="${count}-${size}"]`);
     assert.equal(await group.locator('p').textContent(),size===5?'1/3レース · 33.3%（合成）':'1/1レース · 100.0%（合成）');
    }
    for(const [kind,n] of [['selected_hit',6],['removed_by_five',2],['outside_pool',2]])assert.equal(await page.locator(`[data-diagnostic="${kind}"]`).count(),n);
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   }
   await populated();
   const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#download').click()]);
   assert.equal(download.suggestedFilename(),'synthetic-final-five-review.json');
   assert.deepEqual(JSON.parse(await fs.readFile(await download.path(),'utf8')),value);
   await page.reload();await populated();
   const pattern='**/api/final-five-review';
   await page.route(pattern,route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(empty)}));
   await page.locator('#refresh').click();await page.getByText('評価できる通常履歴がありません。',{exact:true}).waitFor();
   assert.equal(await page.locator('.race').count(),0);assert.equal(await page.getByText('0/0レース · 未算出',{exact:true}).count(),6);
   assert(!(await page.locator('#strata').textContent()).includes('0.0%'));await page.unroute(pattern);
   const fail='集計を確認できませんでした。接続を確認して再確認してください。';
   async function cleared(){await page.getByText(fail,{exact:true}).waitFor();assert.equal(await page.locator('.race').count(),0);assert.equal(await page.locator('.stratum').count(),0);assert.equal(await page.locator('#summary').textContent(),'');}
   // A late successful report cannot overwrite a more recent failed refresh.
   let release,reached,calls=0;const gate=new Promise(r=>release=r),intercepted=new Promise(r=>reached=r);
   await page.route(pattern,async route=>{
    if(++calls===1){const response=await route.fetch();reached();await gate;await route.fulfill({response});}
    else await route.fulfill({status:503,contentType:'application/json',body:'{"error":"synthetic_failure"}'});
   });
   await page.locator('#refresh').click();await intercepted;await page.locator('#refresh').click();await cleared();
   const late=page.waitForResponse(r=>r.url()===url+'/api/final-five-review'&&r.status()===200);release();await late;
   await page.waitForLoadState('networkidle');await cleared();await page.unroute(pattern);
   const bad=structuredClone(empty);bad.strata[0].selected_hit_rate=0;
   await page.route(pattern,route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(bad)}));
   await page.locator('#refresh').click();await cleared();await page.unroute(pattern);
   const stopped=structuredClone(value);stopped.storage.write_blocked=true;
   await page.route(pattern,route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(stopped)}));
   await page.locator('#refresh').click();await populated();assert((await page.locator('#storage').textContent()).startsWith('保存停止中：'));
   await page.unroute(pattern);await page.locator('#refresh').click();await populated();
   assert.deepEqual(await fs.readFile(path.join(directory,'synthetic-session.json')),original);
   const state=await page.evaluate(async()=>await(await fetch('/api/state')).json());assert.equal(state.model_ready,false);
   assert.deepEqual(errors,[]);assert(requests.every(r=>r.method==='GET'&&r.url.startsWith(url+'/')));
   console.log(`${width}px mixed 7/9 cars: FINAL 5 result diagnostic, 3/4/5 denominators, held/pending, exact JSON download, empty null rates, reload, stale/error clear/recovery, no writes/training/external requests PASS`);
  }finally{
   if(page)await page.close();if(child&&child.exitCode===null&&child.signalCode===null){const done=once(child,'exit');child.kill('SIGKILL');await done;}
   await fs.rm(directory,{recursive:true,force:true});
  }
 }}finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
