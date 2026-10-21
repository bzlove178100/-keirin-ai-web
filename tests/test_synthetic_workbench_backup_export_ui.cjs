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
  const directory=await fs.mkdtemp(path.join(os.tmpdir(),'keirin-backup-export-'));
  execFileSync(python,['-c',`import sys
from pathlib import Path
sys.path.insert(0,'tests')
from test_synthetic_workbench_backup_export import migrated
app,_,_=migrated(Path(sys.argv[1]))
app.close()
`,directory]);
  const backup=path.join(directory,'synthetic-session-v1-before-migration.json');
  const original=await fs.readFile(backup),current=await fs.readFile(path.join(directory,'synthetic-session.json'));
  let child,page;const errors=[],requests=[];let downloads=0;
  async function start(persisted){
   child=spawn(python,['-m','ml.synthetic_workbench','--synthetic','--port','0',...(persisted?['--state-dir',directory]:[])],{stdio:['ignore','pipe','pipe']});
   let stderr='';child.stderr.on('data',b=>stderr+=b);
   return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{child.kill('SIGKILL');reject(new Error('startup timeout: '+stderr));},30000);
    createInterface({input:child.stdout}).on('line',line=>{try{const v=JSON.parse(line);if(v.url){clearTimeout(timer);resolve(v.url);}}catch{}});
    child.once('exit',code=>{clearTimeout(timer);reject(new Error('startup exit '+code+': '+stderr));});
   });
  }
  async function stop(){if(child&&child.exitCode===null&&child.signalCode===null){const done=once(child,'exit');child.kill('SIGKILL');await done;}}
  try{
   let url=await start(true);const origins=[url];page=await browser.newPage({viewport:{width,height:900}});
   page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push({url:r.url(),method:r.method()}));page.on('download',()=>downloads++);
   await page.goto(url);await page.getByText('7車または9車を選んで開始できます。',{exact:true}).waitFor();
   const check=()=>page.locator('#backup-check').click();
   const available=()=>page.getByText('現在の記録と照合できる移行前原本があります。',{exact:true}).waitFor();
   await check();await available();
   assert((await page.locator('#backup-details').textContent()).startsWith('予測 2件 · 結果 1件'));
   const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#backup-download').click()]);
   assert.equal(download.suggestedFilename(),'synthetic-session-v1-before-migration.json');
   assert.deepEqual(await fs.readFile(await download.path()),original);
   assert.equal(downloads,1);
   await check();await available();
   await fs.writeFile(backup,Buffer.concat([original,Buffer.from(' ')]));
   await page.locator('#backup-download').click();
   await page.getByText('確認後に原本または保存状態が変わりました。もう一度原本を確認してください。',{exact:true}).waitFor();
   assert.equal(downloads,1);assert(await page.locator('#backup-download').isHidden());
   await check();await available();
   await fs.writeFile(backup,'{');await check();
   await page.getByText('原本の形式や読込状態を確認できません。保存先を確認してください。',{exact:true}).waitFor();
   assert(await page.locator('#backup-download').isHidden());
   await fs.unlink(backup);await check();
   await page.getByText('保存された移行前原本はありません。原本は旧形式から移行するときに作成されます。',{exact:true}).waitFor();
   await fs.writeFile(backup,original);
   assert.deepEqual(await fs.readFile(path.join(directory,'synthetic-session.json')),current);
   const state=await page.evaluate(async()=>await(await fetch('/api/state')).json());
   assert.equal(state.model_ready,false);assert.equal(state.storage.write_blocked,false);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   await stop();url=await start(false);origins.push(url);await page.goto(url);
   await page.getByText('7車または9車を選んで開始できます。',{exact:true}).waitFor();await check();
   await page.getByText('一時モードでは移行前原本を自動保存しません。',{exact:true}).waitFor();
   assert(await page.locator('#backup-download').isHidden());
   assert.deepEqual(errors,[]);assert(requests.every(r=>r.method==='GET'&&origins.some(o=>r.url.startsWith(o+'/'))));
   console.log(`${width}px: exact original download, stale-file refusal, invalid/missing/temporary states, no writes/training/external requests PASS`);
  }finally{if(page)await page.close();await stop();await fs.rm(directory,{recursive:true,force:true});}
 }}finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
