const {chromium}=require(process.env.KEIRIN_PLAYWRIGHT_MODULE||'playwright');
const {spawn,execFileSync}=require('node:child_process');
const {once}=require('node:events');
const {createInterface}=require('node:readline');
const fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path'),assert=require('node:assert/strict');
const python=process.env.PYTHON||'python';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.KEIRIN_BROWSER_EXECUTABLE||undefined});
 try{for(const width of [390,1280]){
  const directory=await fs.mkdtemp(path.join(os.tmpdir(),'keirin-challenger-'));
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
`,directory]);
  const modelPath=path.join(directory,'experiment.json'),statePath=path.join(directory,'state');
  const original=await fs.readFile(path.join(statePath,'synthetic-session.json'));
  let child,page;const errors=[],requests=[];
  async function stop(){if(child&&child.exitCode===null&&child.signalCode===null){const done=once(child,'exit');child.kill('SIGKILL');await done;}}
  async function start(configured){
   child=spawn(python,['-m','ml.synthetic_workbench','--synthetic','--port','0','--state-dir',statePath,...(configured?['--final-five-experiment',modelPath]:[])],{stdio:['ignore','pipe','pipe']});
   let stderr='';child.stderr.on('data',b=>stderr+=b);
   return await new Promise((resolve,reject)=>{const timer=setTimeout(()=>{child.kill('SIGKILL');reject(new Error('startup timeout '+stderr));},30000);
    createInterface({input:child.stdout}).on('line',line=>{try{const v=JSON.parse(line);if(v.url){clearTimeout(timer);resolve(v.url);}}catch{}});
    child.once('exit',code=>{clearTimeout(timer);reject(new Error('startup exit '+code+' '+stderr));});});
  }
  try{
   let url=await start(true);const origins=[url];
   page=await browser.newPage({viewport:{width,height:950}});
   page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push({url:r.url(),method:r.method()}));
   const key=String(1).padStart(32,'0');
   await page.goto(url);await page.getByText('7車または9車を選んで開始できます。',{exact:true}).waitFor();
   assert.equal(await page.locator('#final-five-challenger').getAttribute('href'),'/final-five-challenger/'+key);
   async function visible(k,size,count){
    const [response]=await Promise.all([page.waitForResponse(r=>r.url()===url+'/api/final-five-challenger/'+k),page.goto(url+'/final-five-challenger/'+k)]);
    const v=await response.json();await page.getByText(`同じ${v.baseline.candidate_count}候補から各${size}点を比較`,{exact:true}).waitFor();
    assert.equal(v.baseline.rider_count,count);assert.equal(await page.locator('#baseline .pick').count(),size);assert.equal(await page.locator('#challenger .pick').count(),size);
    assert.equal(await page.locator('#shortfall').textContent(),size===5?'':`5点に対して${5-size}点不足しています。元の候補にない買い目は追加しません。`);
    for(const p of v.challenger.picks){const card=page.locator(`#challenger [data-combo="${p.combo_key}"]`);
     assert.equal(await card.locator('h3').textContent(),`${p.rank}. ${p.combo_key}`);
     assert((await card.locator('.metrics').textContent()).includes((p.estimated_probability*100).toFixed(3)+'%'));
     assert.equal(await card.locator('.score').textContent(),`比較スコア ${p.ranking_score.toFixed(6)}（的中確率ではありません）`);
    }
    assert((await page.locator('#model').textContent()).includes(v.model.sha256));
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));return v;
   }
   let value;
   for(let i=1;i<=6;i++)value=await visible(String(i).padStart(32,'0'),[5,3,4][(i-1)%3],i<=3?7:9);
   for(const k of ['7','8','9']){
    await page.goto(url+'/final-five-challenger/'+k.repeat(32));await page.getByText('基準を表示しました。AI候補は利用できません。',{exact:true}).waitFor();
    assert.equal(await page.locator('#challenger .pick').count(),0);assert.equal(await page.locator('#baseline .pick').count(),5);
    assert((await page.locator('#blocked').textContent()).includes({7:'学習に使用済み',8:'学習境界より前',9:'保留中'}[k]));
   }
   value=await visible(key,5,7);await page.reload();await page.getByText('同じ15候補から各5点を比較',{exact:true}).waitFor();
   const pattern='**/api/final-five-challenger/'+key,fail='比較を確認できませんでした。接続を確認して再確認してください。';
   async function empty(){await page.getByText(fail,{exact:true}).waitFor();assert.equal(await page.locator('.pick').count(),0);for(const id of ['race','model','blocked','storage','shortfall'])assert.equal(await page.locator('#'+id).textContent(),'');}
   let release,reached,calls=0;const gate=new Promise(r=>release=r),intercepted=new Promise(r=>reached=r);
   await page.route(pattern,async route=>{if(++calls===1){const response=await route.fetch();reached();await gate;await route.fulfill({response});}else await route.fulfill({status:503,body:'{}'});});
   await page.locator('#refresh').click();await intercepted;assert.equal(await page.locator('.pick').count(),0);
   await page.locator('#refresh').click();await empty();const late=page.waitForResponse(r=>r.url()===url+'/api/final-five-challenger/'+key&&r.status()===200);release();await late;await page.waitForLoadState('networkidle');await empty();await page.unroute(pattern);
   for(const mutate of [v=>v.snapshot_id='f'.repeat(32),v=>v.product_acceptance=true,v=>v.challenger.picks[1].combo_key=v.challenger.picks[0].combo_key,v=>v.challenger.picks[0].ranking_score=null,v=>v.model=null]){
    const bad=structuredClone(value);mutate(bad);await page.route(pattern,r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify(bad)}));
    await page.locator('#refresh').click();await empty();await page.unroute(pattern);
   }
   const blockedStorage=structuredClone(value);blockedStorage.storage.write_blocked=true;
   await page.route(pattern,r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify(blockedStorage)}));
   await page.locator('#refresh').click();await page.getByText('保存停止中：最後に確認できたメモリの予測を表示しています。',{exact:true}).waitFor();await page.unroute(pattern);
   // The already loaded model remains fixed despite external file changes.
   await fs.writeFile(modelPath,'{bad after startup');await page.locator('#refresh').click();await page.getByText('同じ15候補から各5点を比較',{exact:true}).waitFor();
   assert.deepEqual(await page.locator('#challenger .pick').evaluateAll(nodes=>nodes.map(n=>n.dataset.combo)),value.challenger.picks.map(p=>p.combo_key));
   let state=await page.evaluate(async()=>await(await fetch('/api/state')).json());assert.equal(state.model_ready,false);
   await stop();url=await start(false);origins.push(url);
   await page.goto(url+'/final-five-challenger/'+key);await page.getByText('基準を表示しました。AI候補は利用できません。',{exact:true}).waitFor();
   assert((await page.locator('#blocked').textContent()).includes('モデルが指定されていません'));assert.equal(await page.locator('#challenger .pick').count(),0);
   assert.deepEqual(await fs.readFile(path.join(statePath,'synthetic-session.json')),original);
   assert.deepEqual(errors,[]);assert(requests.every(r=>r.method==='GET'&&origins.some(origin=>r.url.startsWith(origin+'/'))));
   console.log(`${width}px: synthetic challenger 7/9 x 3/4/5, same budget and original values, blocked model/seen/early/held, reload, stale/error/malformed clear, pinned model, restart without model, no writes/training/external requests PASS`);
  }finally{if(page)await page.close();await stop();await fs.rm(directory,{recursive:true,force:true});}
 }}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
