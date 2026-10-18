// Real browser, generated fixtures, locally fulfilled page resources; no external service.
const {chromium}=require(process.env.KEIRIN_PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const {snapshot}=require('./test_prospective_tools.cjs');
const core=require('../prospective-tools-core.js');
const upload=(name,value)=>({name,mimeType:'application/json',buffer:Buffer.from(JSON.stringify(value))});
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.KEIRIN_BROWSER_EXECUTABLE||undefined});
 try{
  for(const width of [390,1280]){
   const context=await browser.newContext({viewport:{width,height:900},timezoneId:'Asia/Tokyo'});
   const page=await context.newPage(),errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   await page.route('**/*',async route=>{
    const url=new URL(route.request().url());
    assert.equal(url.origin,'http://held.test');
    const name=url.pathname.slice(1);
    assert(['prospective-tools.html','prospective-tools-core.js','prospective-tools-ui.js','prospective-history-bundle.js'].includes(name));
    await route.fulfill({body:await fs.readFile(path.join(process.cwd(),name)),contentType:name.endsWith('.js')?'text/javascript':'text/html'});
   });
   await page.goto('http://held.test/prospective-tools.html');
   for(const count of [7,9]){
    const snap=snapshot(0,'fixture',count);snap.race_data.race.venue='GENERATED';
    await page.locator('#snapshot-file').setInputFiles(upload('snapshot.json',snap));
    await page.locator('#snapshot-status').filter({hasText:'確認済み'}).waitFor();
    for(const status of ['dead_heat','withdrawn','cancelled']){
     await page.locator('#result-status').selectOption(status);
     assert(await page.locator('#hold-note').isVisible());
     assert(!(await page.locator('#normal-result-fields').isVisible()));
     await page.locator('#result-time').fill('2026-09-24T09:40:00');
     if(status==='withdrawn')await page.locator('#withdrawn').fill(String(count));
     await page.locator('#build-history').click();
     assert.match(await page.locator('#history-status').innerText(),/保留理由を記録/);
     const pending=page.waitForEvent('download');await page.locator('#download-history').click();
     const download=await pending;
     assert.match(download.suggestedFilename(),/^held-history-/);
     const envelope=JSON.parse(await fs.readFile(await download.path(),'utf8'));
     const held=envelope.payload.records[0];assert.equal(core.validateHeldHistory(held),true);
     assert.equal(held.settlement.result_status,status);assert.equal(held.outcome_combo,undefined);
     const normal=core.buildHistory(snap,{outcomeCombo:'1-2-3',settlementOdds:42,resultTimestamp:'2026-09-24T00:40:00Z'});
     await page.locator('#history-files').setInputFiles([upload('held.json',envelope),upload('normal.json',core.historyEnvelope(normal))]);
     await page.waitForFunction(()=>document.getElementById('held-count').textContent==='1');
     const report=JSON.parse(await page.locator('#collection-summary').innerText());
     assert.equal(report.eligible_unique_races,0);assert.equal(report.excluded.race_has_held_result,1);
     const bundlePending=page.waitForEvent('download');await page.locator('#save-history-bundle').click();
     const bundle=JSON.parse(await fs.readFile(await (await bundlePending).path(),'utf8'));
     assert.equal(bundle.payload.records.length,2);assert.equal(core.collectionStatus(bundle.payload.records).held_unique_races,1);
     // A changed input invalidates the old downloadable result immediately.
     await page.locator('#result-time').fill('2026-09-24T09:41:00');
     assert(await page.locator('#download-history').isDisabled());
    }
    await page.locator('#result-status').selectOption('withdrawn');
    await page.locator('#withdrawn').fill('1,1');await page.locator('#build-history').click();
    assert.match(await page.locator('#history-status').innerText(),/withdrawn_cars_invalid/);
    assert(await page.locator('#download-history').isDisabled());
    await page.locator('#result-status').selectOption('normal');
    await page.locator('#outcome').fill('1-2-3');await page.locator('#settlement-odds').fill('42');
    await page.locator('#build-history').click();
    assert.match(await page.locator('#history-status').innerText(),/生成成功/);
   }
   assert.deepEqual(errors,[]);await context.close();
  }
  console.log('Phase32 held JSON save/reload/bundle, 7/9 riders, phone/desktop: PASS');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
