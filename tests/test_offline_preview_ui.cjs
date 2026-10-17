const {chromium}=require(process.env.KEIRIN_PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const path=require('node:path');
const directory=process.env.KEIRIN_SMOKE_ARTIFACT_DIR;
assert(directory, 'KEIRIN_SMOKE_ARTIFACT_DIR required');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.KEIRIN_BROWSER_EXECUTABLE || undefined});
 for(const count of [7,9])for(const width of [390,1280]){
  const page=await browser.newPage({viewport:{width,height:900}}),requests=[];
  page.on('request',r=>requests.push(r.url()));
  await page.goto(pathToFileURL(path.join(directory,`prediction-${count}.html`)).href);
  assert.equal(await page.locator('h1').textContent(),'学習モデルの出力を確認');
  assert.equal(await page.locator('table').count(),5);
  assert.equal(await page.locator('.positions tbody tr').count(),count*3);
  await page.locator('summary').click();
  assert.equal(await page.locator('details tbody tr').count(),count*(count-1)*(count-2));
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert(requests.every(url=>url.startsWith('file:')));
  await page.locator('summary').click();
  if(count===9)await page.screenshot({path:path.join(directory,`review-${width}.png`)});
  console.log(`${count} riders / ${width}px: DOM, table counts, no overflow, no network PASS`);
  await page.close();
 }
 await browser.close();
})().catch(e=>{console.error(e);process.exitCode=1});
