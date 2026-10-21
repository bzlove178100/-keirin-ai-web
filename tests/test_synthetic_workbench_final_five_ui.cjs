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
 try{for(const width of [390,1280])for(const count of [7,9]){
  const directory=await fs.mkdtemp(path.join(os.tmpdir(),'keirin-final-five-'));
  const full='a'.repeat(32),partial='b'.repeat(32);
  execFileSync(python,['-c',`import sys
sys.path.insert(0,'tests')
from ml.synthetic_session import SessionStore
from test_synthetic_workbench_session import saved_session
from test_synthetic_workbench_final_five import baseline_snapshot
value=saved_session(); count=int(sys.argv[2]); value['histories']={}
value['snapshots']={'a'*32:baseline_snapshot(count),'b'*32:baseline_snapshot(count,partial=True)}
store=SessionStore(sys.argv[1])
try: store.save(value)
finally: store.close()
`,directory,String(count)]);
  const original=await fs.readFile(path.join(directory,'synthetic-session.json'));
  let child,page;const errors=[],requests=[];
  try{
   child=spawn(python,['-m','ml.synthetic_workbench','--synthetic','--port','0','--state-dir',directory],{stdio:['ignore','pipe','pipe']});
   let stderr='';child.stderr.on('data',b=>stderr+=b);
   const url=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>{child.kill('SIGKILL');reject(new Error('startup timeout: '+stderr));},30000);
    createInterface({input:child.stdout}).on('line',line=>{try{const v=JSON.parse(line);if(v.url){clearTimeout(timer);resolve(v.url);}}catch{}});
    child.once('exit',code=>{clearTimeout(timer);reject(new Error('startup exit '+code+': '+stderr));});
   });
   page=await browser.newPage({viewport:{width,height:900}});
   page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push({url:r.url(),method:r.method()}));
   const fail='候補を確認できませんでした。接続を確認して再確認してください。';
   async function visible(key,size,candidates){
    const [response]=await Promise.all([page.waitForResponse(r=>r.url()===url+'/api/final-five-view/'+key),page.goto(url+'/final-five-view/'+key)]);
    const value=await response.json();
    await page.getByText(`保存済み${candidates}候補から${size}点 · 未校正確率順の比較基準`,{exact:true}).waitFor();
    assert.equal(value.selected_count,size);assert.equal(value.candidate_count,candidates);
    assert.equal(await page.locator('.pick').count(),size);
    assert((await page.locator('#race').textContent()).endsWith(`${count}車`));
    assert.equal(await page.locator('#shortfall').textContent(),size===5?'':'5点に対して2点不足しています。元の候補にない買い目は追加しません。');
    for(const pick of value.picks){
     const card=page.locator(`[data-combo="${pick.combo_key}"]`);
     assert.equal(await card.locator('h2').textContent(),`${pick.rank}. ${pick.combo_key}`);
     assert.equal(await card.locator('.source').textContent(),`選定元：${pick.source_category_name} ${pick.source_rank}位`);
     assert((await card.locator('.metrics').textContent()).includes((pick.estimated_probability*100).toFixed(3)+'%'));
    }
    assert.equal(value.second_stage_ai_enabled,false);assert.equal(value.monetary_ev_enabled,false);
    assert(!Object.hasOwn(value,'trifecta_scores'));assert(!Object.hasOwn(value,'categories'));
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    return value;
   }
   await page.goto(url);await page.getByText('7車または9車を選んで開始できます。',{exact:true}).waitFor();
   assert.equal(await page.locator('#final-five-preview').getAttribute('href'),'/final-five-view/'+full);
   const selected=await visible(full,5,15);
   assert.deepEqual(selected.picks.map(p=>p.source_category),['hit_priority','hit_priority','hit_priority','balance','balance']);
   const short=await visible(partial,3,3);assert(short.picks.every(p=>p.odds===null));
   assert.equal(await page.locator('.metrics').filter({hasText:'オッズ未確認'}).count(),3);
   await page.reload();await page.getByText('保存済み3候補から3点 · 未校正確率順の比較基準',{exact:true}).waitFor();
   assert.deepEqual(await page.locator('.pick').evaluateAll(nodes=>nodes.map(n=>n.dataset.combo)),short.picks.map(p=>p.combo_key));
   const pattern='**/api/final-five-view/'+partial;
   async function empty(){await page.getByText(fail,{exact:true}).waitFor();assert.equal(await page.locator('.pick').count(),0);assert.equal(await page.locator('#race').textContent(),'');assert.equal(await page.locator('#shortfall').textContent(),'');}
   // A fresh failure must clear candidates; a late successful reply stays stale.
   let release,reached,calls=0;const gate=new Promise(r=>release=r),intercepted=new Promise(r=>reached=r);
   await page.route(pattern,async route=>{
    if(++calls===1){const response=await route.fetch();reached();await gate;await route.fulfill({response});}
    else await route.fulfill({status:503,contentType:'application/json',body:'{"error":"synthetic_failure"}'});
   });
   await page.locator('#refresh').click();await intercepted;
   assert.equal(await page.locator('.pick').count(),0);
   await page.locator('#refresh').click();await empty();
   const late=page.waitForResponse(r=>r.url()===url+'/api/final-five-view/'+partial&&r.status()===200);release();await late;
   await page.waitForLoadState('networkidle');await empty();await page.unroute(pattern);
   // Reject mismatched identity, false safety claims and duplicated output.
   for(const mutate of [v=>v.snapshot_id=full,v=>v.second_stage_ai_enabled=true,v=>v.picks[1].combo_key=v.picks[0].combo_key]){
    const bad=structuredClone(short);mutate(bad);
    await page.route(pattern,route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(bad)}));
    await page.locator('#refresh').click();await empty();await page.unroute(pattern);
   }
   await page.locator('#refresh').click();await page.getByText('保存済み3候補から3点 · 未校正確率順の比較基準',{exact:true}).waitFor();
   assert.equal(await page.locator('.pick').count(),3);
   assert.deepEqual(await fs.readFile(path.join(directory,'synthetic-session.json')),original);
   const state=await page.evaluate(async()=>await(await fetch('/api/state')).json());assert.equal(state.model_ready,false);
   assert.deepEqual(errors,[]);assert(requests.every(r=>r.method==='GET'&&r.url.startsWith(url+'/')));
   console.log(`${width}px ${count} cars: FINAL 5 baseline 15-to-5, partial 3, original odds/probabilities/source ranks, reload, stale/failure/malformed clear, no writes/training/external requests PASS`);
  }finally{
   if(page)await page.close();if(child&&child.exitCode===null&&child.signalCode===null){const done=once(child,'exit');child.kill('SIGKILL');await done;}
   await fs.rm(directory,{recursive:true,force:true});
  }
 }}finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
