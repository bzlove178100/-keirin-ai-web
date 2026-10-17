const {chromium}=require(process.env.KEIRIN_PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('node:child_process');
const {createInterface}=require('node:readline');
const fs=require('node:fs/promises');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
 const child=spawn(process.env.PYTHON||'python',['-m','ml.synthetic_workbench','--synthetic','--port','0'],{env:{...process.env,OMP_NUM_THREADS:'2'},stdio:['ignore','pipe','pipe']});
 let browser,stderr='';child.stderr.on('data',b=>stderr+=b);
 try{
  const url=await new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>reject(new Error('server startup timeout: '+stderr)),30000);
   const lines=createInterface({input:child.stdout});
   lines.on('line',line=>{try{const info=JSON.parse(line);if(info.url){clearTimeout(timer);resolve(info.url);}}catch{}});
   child.once('exit',code=>{clearTimeout(timer);reject(new Error('server exited '+code+': '+stderr));});
  });
  browser=await chromium.launch({headless:true,executablePath:process.env.KEIRIN_BROWSER_EXECUTABLE||undefined});
  for(const width of [390,1280]){
   const page=await browser.newPage({viewport:{width,height:900},acceptDownloads:true}),requests=[],errors=[];
   page.on('request',r=>requests.push(r.url()));page.on('pageerror',e=>errors.push(e.message));
   await page.goto(url);await page.getByText('7車または9車を選んで開始できます。',{exact:true}).waitFor();
   for(const count of [7,9]){
    await page.locator('#predict'+count).click();
    await page.getByText('予測を保存し、モデル候補を表示しました。',{exact:true}).waitFor({timeout:60000});
    assert.equal(await page.locator('.category').count(),5);
    assert((await page.locator('#race-title').textContent()).startsWith(count+'車'));
    await page.locator('#second').selectOption('1');await page.locator('#settle').click();
    await page.getByText('異なる3車を選んでください。',{exact:true}).waitFor();
    for(const [id,value] of [['first',count===7?'1':'9'],['second',count===7?'2':'8'],['third',count===7?'3':'7']])await page.locator('#'+id).selectOption(value);
    await page.locator('#settle').click();
    await page.getByText('合成結果を照合し、保存した予測を評価しました。',{exact:true}).waitFor();
    assert(await page.locator('#settle').isDisabled());
    assert.equal(await page.locator('#first').inputValue(),count===7?'1':'9');
    assert.equal(await page.locator('#race-count').textContent(),width===390&&count===7?'1':'2');
    const downloadPromise=page.waitForEvent('download');await page.locator('#history-download').click();
    const download=await downloadPromise;const contents=JSON.parse(await fs.readFile(await download.path(),'utf8'));
    assert.equal(contents.snapshot.prediction.input_quality.rider_count,count);
    assert.equal(contents.schema_version,'ml-settled-history-v1');
    assert.equal(contents.production_prediction_enabled,false);
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   }
   await page.reload();await page.getByText('7車または9車を選んで開始できます。',{exact:true}).waitFor();
   assert.equal(await page.locator('#race-count').textContent(),'2');
   assert(await page.locator('#settle').isDisabled());
   assert.equal(await page.locator('#first').inputValue(),'9');
   assert.equal(await page.locator('#duplicates').textContent(),width===390?'0':'2');
   assert.deepEqual(errors,[]);assert(requests.every(u=>u.startsWith(url+'/')));
   if(process.env.KEIRIN_SMOKE_ARTIFACT_DIR)await page.screenshot({path:path.join(process.env.KEIRIN_SMOKE_ARTIFACT_DIR,`workbench-${width}.png`),fullPage:true});
   console.log(`${width}px: actual train/inference/capture/settlement/review, invalid input recovery, export, reload, no external requests PASS`);
   await page.close();
  }
 }finally{if(browser)await browser.close();child.kill('SIGINT');}
})().catch(e=>{console.error(e);process.exitCode=1});
