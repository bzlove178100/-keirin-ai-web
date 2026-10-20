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
  const directory=await fs.mkdtemp(path.join(os.tmpdir(),'keirin-category-preview-'));
  const key=(count===7?'a':'b').repeat(32);
  execFileSync(python,['-c',`import sys
sys.path.insert(0,'tests')
from ml.synthetic_session import SessionStore
from test_synthetic_workbench_session import saved_session
value=saved_session(); value['current']=sys.argv[2]
store=SessionStore(sys.argv[1])
try: store.save(value)
finally: store.close()
`,directory,key]);
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
   await page.goto(url);await page.getByText('7車または9車を選んで開始できます。',{exact:true}).waitFor();
   assert.equal(await page.locator('#category-preview').getAttribute('href'),'/category-view/'+key);
   await page.goto(url+'/category-view/'+key);
   await page.getByText('表示するカテゴリの指定がありません。',{exact:true}).waitFor();
   assert.equal(await page.locator('.pick').count(),0);
   async function select(scenario,expected){
    const [response]=await Promise.all([page.waitForResponse(r=>r.url()===url+'/api/category-view/'+key+'/'+scenario),page.locator('#scenario').selectOption(scenario)]);
    const value=await response.json();assert.equal(Object.keys(value.categories).length,expected);
    if(expected)await page.waitForFunction(n=>document.getElementById('status').textContent.startsWith(`合成ケース：${n}カテゴリ`),expected);
    else await page.waitForFunction(()=>document.getElementById('status').textContent!=='確認しています。');
    assert.equal(await page.locator('.pick').count(),value.total_picks);
    assert.equal(await page.locator('.locked').count(),5-expected);
    for(const [category,model] of Object.entries(value.categories)){
     const section=page.locator(`[data-category="${category}"]`);
     assert.equal(await section.locator('.pick').count(),model.picks.length);
    }
    assert(!Object.hasOwn(value,'prediction'));assert(!Object.hasOwn(value,'full_scores'));
    if(!expected)assert(!Object.hasOwn(value,'race'));
   }
   for(const [scenario,size] of [['all',5],['hit',1],['two',2],['three',3],['expired',0],['future',0],['other-snapshot',0],['none',0]])await select(scenario,size);
   // A delayed all-category response may never replace a newer restricted view.
   let release,reached;const gate=new Promise(r=>release=r),intercepted=new Promise(r=>reached=r);
   const pattern='**/api/category-view/*/all';
   await page.route(pattern,async route=>{const response=await route.fetch();reached();await gate;await route.fulfill({response});});
   await page.locator('#scenario').selectOption('all');await intercepted;
   await select('hit',1);const delayed=page.waitForResponse(r=>r.url()===url+'/api/category-view/'+key+'/all');release();await delayed;
   await page.waitForLoadState('networkidle');
   assert((await page.locator('#status').textContent()).startsWith('合成ケース：1カテゴリ'));
   assert.equal(await page.locator('.locked').count(),4);
   await page.unroute(pattern);
   // Failure must clear the previous visible candidates, then recover on demand.
   await page.route(pattern,route=>route.fulfill({status:503,contentType:'application/json',body:'{"error":"synthetic_failure"}'}));
   await page.locator('#scenario').selectOption('all');
   await page.getByText('表示を確認できませんでした。接続を確認して再確認してください。',{exact:true}).waitFor();
   assert.equal(await page.locator('.pick').count(),0);assert.equal(await page.locator('#race').textContent(),'');
   await page.unroute(pattern);await page.locator('#refresh').click();
   await page.waitForFunction(()=>document.getElementById('status').textContent.startsWith('合成ケース：5カテゴリ'));
   assert.equal(await page.locator('.locked').count(),0);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   assert.deepEqual(await fs.readFile(path.join(directory,'synthetic-session.json')),original);
   const state=await page.evaluate(async()=>await(await fetch('/api/state')).json());assert.equal(state.model_ready,false);
   assert.deepEqual(errors,[]);assert(requests.every(r=>r.method==='GET'&&r.url.startsWith(url+'/')));
   console.log(`${width}px ${count} cars: server category subset, closed fixtures, stale response discarded, failure clears/retry restores, frozen session/no training/no external requests PASS`);
  }finally{
   if(page)await page.close();if(child&&child.exitCode===null&&child.signalCode===null){const done=once(child,'exit');child.kill('SIGKILL');await done;}
   await fs.rm(directory,{recursive:true,force:true});
  }
 }}finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
