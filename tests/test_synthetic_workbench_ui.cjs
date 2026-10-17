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
    const context=page.context(),webRequests=[];
    const track=r=>webRequests.push(r.url());context.on('request',track);
    const opened=context.waitForEvent('page');await page.locator('#web-preview').click();
    const web=await opened;web.on('pageerror',e=>errors.push(e.message));
    await web.getByText('保存済みの合成予測を表示しました。',{exact:true}).waitFor();
    const key=new URL(web.url()).pathname.split('/').pop();
    const view=await web.evaluate(async key=>(await fetch('/api/model-view/'+key)).json(),key);
    assert.equal(view.quality.rider_count,count);
    assert((await web.locator('#input-quality').textContent()).includes(count===7?'2/210':'24/504'));
    const ids=['cat-hit','cat-balance','cat-middle','cat-longshot','cat-super'];
    for(const [i,category] of Object.values(view.categories).entries()){
     assert.equal(await web.locator('#'+ids[i]+' .pick-item').count(),category.picks.length);
     assert.deepEqual(await web.locator('#'+ids[i]+' .combo').allTextContents(),category.picks.map(p=>`${p.rank}位  ${p.combo_key}`));
    }
    assert.equal(await web.locator('.pick-item p').count(),0);
    assert(await web.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    if(process.env.KEIRIN_SMOKE_ARTIFACT_DIR)await web.screenshot({path:path.join(process.env.KEIRIN_SMOKE_ARTIFACT_DIR,`model-web-${count}-${width}.png`),fullPage:true});
    for(const mismatch of ['unsafe','other_snapshot']){
     const bad=structuredClone(view);if(mismatch==='unsafe')bad.db_write_enabled=true;else bad.snapshot_id='0'.repeat(32);
     await web.route('**/api/model-view/**',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify(bad)}));
     await web.evaluate(view=>KeirinModelWeb.render(view,{document,renderCategory}),view);
     assert.equal(await web.locator('.pick-item').count(),view.total_picks);
     await web.evaluate(key=>KeirinModelWeb.load('/api/model-view/'+key,{document,renderCategory}),key);
     await web.getByText('モデル応答を確認できないため表示を停止しました。',{exact:true}).waitFor();
     assert.equal(await web.locator('.pick-item').count(),0);
     assert.equal(await web.locator('#model-race').textContent(),'');
     await web.unroute('**/api/model-view/**');
    }
    assert(webRequests.every(u=>u.startsWith(url+'/')));
    context.off('request',track);await web.close();
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
   console.log(`${width}px: actual 7/9 ML response through existing five-category renderer, unsafe/mismatched response clears old picks PASS`);
   await page.close();
  }
  for(const width of [390,1280]){
   const page=await browser.newPage({viewport:{width,height:900},acceptDownloads:true}),requests=[],errors=[];
   page.on('request',r=>requests.push(r.url()));page.on('pageerror',e=>errors.push(e.message));
   await page.goto(url);await page.getByText('7車または9車を選んで開始できます。',{exact:true}).waitFor();
   for(const [count,status] of [[7,'dead_heat'],[9,'withdrawn'],[7,'cancelled']]){
    await page.locator('#predict'+count).click();
    await page.getByText('予測を保存し、モデル候補を表示しました。',{exact:true}).waitFor();
    assert.equal(await page.locator('#result-status').inputValue(),'normal');
    await page.locator('#result-status').selectOption(status);
    assert(await page.locator('#normal-fields').isHidden());
    assert(await page.locator('#hold-note').isVisible());
    if(status==='withdrawn'){
     await page.locator('#withdrawn').fill('9,9');await page.locator('#settle').click();
     await page.getByText('欠車の車番を重複なく入力してください。',{exact:true}).waitFor();
     await page.locator('#withdrawn').fill('9');
    }
    await page.locator('#settle').click();
    await page.getByText('保留理由を保存し、このレースを通常評価から除外しました。',{exact:true}).waitFor();
    assert(await page.locator('#settle').isDisabled());
    assert.equal(await page.locator('#held-count').textContent(),width===390&&status==='dead_heat'?'1':'2');
    const downloadPromise=page.waitForEvent('download');await page.locator('#history-download').click();
    const download=await downloadPromise;const contents=JSON.parse(await fs.readFile(await download.path(),'utf8'));
    assert.equal(contents.schema_version,'ml-held-history-v1');
    assert.equal(contents.settlement.result_status,status);
    assert(!('outcome_combo' in contents.settlement));
    await page.reload();await page.getByText('7車または9車を選んで開始できます。',{exact:true}).waitFor();
    assert.equal(await page.locator('#result-status').inputValue(),status);
    assert(await page.locator('#normal-fields').isHidden());assert(await page.locator('#settle').isDisabled());
    if(status==='withdrawn')assert.equal(await page.locator('#withdrawn').inputValue(),'9');
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   }
   assert.equal(await page.locator('#race-count').textContent(),'0');
   assert.equal(await page.locator('#top3').textContent(),'—');
   assert((await page.locator('#held-cases').textContent()).includes('欠車 9番'));
   assert.deepEqual(errors,[]);assert(requests.every(u=>u.startsWith(url+'/')));
   if(process.env.KEIRIN_SMOKE_ARTIFACT_DIR)await page.screenshot({path:path.join(process.env.KEIRIN_SMOKE_ARTIFACT_DIR,`workbench-held-${width}.png`),fullPage:true});
   console.log(`${width}px: dead heat/withdrawal/cancellation held, invalid car recovery, export/reload, no ordinary metric contamination PASS`);
   await page.close();
  }
 }finally{if(browser)await browser.close();child.kill('SIGINT');}
})().catch(e=>{console.error(e);process.exitCode=1});
