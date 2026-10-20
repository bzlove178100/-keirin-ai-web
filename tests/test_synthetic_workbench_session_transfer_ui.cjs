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
  execFileSync(python,['-c',`
import sys
sys.path.insert(0,'tests')
from ml.synthetic_workbench import Workbench
from test_synthetic_workbench_session_transfer import seed
app=Workbench(sys.argv[1])
try:
 seed(app)
 app.hold(('a' if int(sys.argv[2])==7 else 'b')*32,'cancelled')
finally: app.close()
`,directory,String(count)]);
  let child,page;const errors=[],requests=[],origins=[],posts=[];let downloads=0;
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
   page.on('request',r=>{requests.push(r.url());if(r.url().endsWith('/import-session'))posts.push(JSON.parse(r.postData()));});
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
   const checkpoint=await fs.readFile(path.join(directory,'held-review','held-review.json'));
   await stop();url=await start();await page.goto(url+'/held-review');await ready(page);
   assert.equal(await page.locator('#counts').textContent(),'保留 2件 / 確認 0件');
   assert(await page.locator('#session-import').isDisabled());
   assert((await page.locator('#storage-note').textContent()).includes('復元'));
   assert.deepEqual(await fs.readFile(path.join(directory,'held-review','held-review.json')),checkpoint);
   const state=await page.evaluate(async()=>await(await fetch('/api/state')).json());
   assert.equal(state.model_ready,false);
   assert.equal(downloads,0);
   assert(posts.length===2&&posts.every(p=>Object.keys(p).sort().join(',')==='revision,source_revision'));
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   assert.deepEqual(errors,[]);assert(requests.every(u=>origins.some(o=>u.startsWith(o+'/'))));
   console.log(`${width}px ${count} cars: no file handoff, stale source refusal, exact saved copies, SIGKILL restore, no training PASS`);
  }finally{if(page)await page.close();await stop();await fs.rm(directory,{recursive:true,force:true});}
 }}finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
