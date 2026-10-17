const {chromium}=require(process.env.KEIRIN_PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('node:child_process');
const {once}=require('node:events');
const {createInterface}=require('node:readline');
const fs=require('node:fs/promises');
const os=require('node:os');
const path=require('node:path');
const assert=require('node:assert/strict');

(async()=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'keirin-restart-ui-'));
 let child,browser;
 async function start(){
  child=spawn(process.env.PYTHON||'python',['-m','ml.synthetic_workbench','--synthetic','--port','0','--state-dir',directory],
   {env:{...process.env,OMP_NUM_THREADS:'2'},stdio:['ignore','pipe','pipe']});
  let stderr='';child.stderr.on('data',b=>stderr+=b);
  return new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>reject(new Error('startup timeout: '+stderr)),30000);
   const lines=createInterface({input:child.stdout});
   lines.on('line',line=>{try{const value=JSON.parse(line);if(value.url){clearTimeout(timer);resolve(value.url);}}catch{}});
   child.once('exit',code=>{clearTimeout(timer);reject(new Error('startup exited '+code+': '+stderr));});
  });
 }
 async function stop(signal){
  if(child&&child.exitCode===null&&child.signalCode===null){const exited=once(child,'exit');child.kill(signal);await exited;}
 }
 try{
  const url=await start(),origins=[url],requests=[],errors=[];
  browser=await chromium.launch({headless:true,executablePath:process.env.KEIRIN_BROWSER_EXECUTABLE||undefined});
  const page=await browser.newPage({viewport:{width:390,height:900}});
  page.on('request',r=>requests.push(r.url()));page.on('pageerror',e=>errors.push(e.message));
  const state=async()=>page.evaluate(async()=>await (await fetch('/api/state')).json());
  async function predict(count){
   await page.locator('#predict'+count).click();
   await page.getByText('予測を保存し、モデル候補を表示しました。',{exact:true}).waitFor({timeout:60000});
   return (await state()).current.snapshot_id;
  }
  await page.goto(url);await page.getByText('7車または9車を選んで開始できます。',{exact:true}).waitFor();
  assert((await page.locator('#storage-note').textContent()).includes('自動保存'));
  const ordinary=await predict(7);
  await page.locator('#settle').click();
  await page.getByText('合成結果を照合し、保存した予測を評価しました。',{exact:true}).waitFor();
  const held=await predict(9);
  await page.locator('#result-status').selectOption('cancelled');await page.locator('#settle').click();
  await page.getByText('保留理由を保存し、このレースを通常評価から除外しました。',{exact:true}).waitFor();
  const pending=await predict(7),before=await state();
  const frozen=await page.evaluate(async keys=>Promise.all(keys.map(async k=>await (await fetch('/snapshot/'+k)).json())),[ordinary,held,pending]);
  await stop('SIGKILL'); // Saved replies survive abrupt process termination.
  const restarted=await start();origins.push(restarted);
  await page.goto(restarted);await page.getByText('7車または9車を選んで開始できます。',{exact:true}).waitFor();
  const after=await state();
  assert.equal(after.storage.restored,true);assert.equal(after.model_ready,false);
  assert.equal(after.saved_snapshots,3);assert.equal(after.saved_histories,2);
  assert.deepEqual(after.report,before.report);assert.equal(after.current.snapshot_id,pending);
  assert((await page.locator('#storage-note').textContent()).includes('復元'));
  const restored=await page.evaluate(async keys=>Promise.all(keys.map(async k=>await (await fetch('/snapshot/'+k)).json())),[ordinary,held,pending]);
  assert.deepEqual(restored,frozen);
  for(const width of [390,1280]){
   await page.setViewportSize({width,height:900});
   for(const [key,status,settled] of [[ordinary,'normal',true],[held,'cancelled',true],[pending,'normal',false]]){
    await page.locator('#resume').selectOption(key);
    await page.getByText('保存した予測を開きました。',{exact:true}).waitFor();
    assert.equal(await page.locator('#result-status').inputValue(),status);
    assert.equal(await page.locator('#settle').isDisabled(),settled);
    assert.equal((await state()).current.snapshot_id,key);
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   }
  }
  await page.locator('#result-status').selectOption('dead_heat');await page.locator('#settle').click();
  await page.getByText('保留理由を保存し、このレースを通常評価から除外しました。',{exact:true}).waitFor();
  assert.equal(await page.locator('#race-count').textContent(),'0');
  assert.equal(await page.locator('#held-count').textContent(),'2');
  assert.equal((await state()).model_ready,false); // Resume/settlement does not retrain.
  assert.deepEqual(errors,[]);assert(requests.every(u=>origins.some(origin=>u.startsWith(origin+'/'))));
  console.log('390/1280px: durable save → SIGKILL → restart → identical frozen predictions/report → resume normal/held/pending → settle without training PASS');
 }finally{if(browser)await browser.close();await stop('SIGINT');await fs.rm(directory,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1});
