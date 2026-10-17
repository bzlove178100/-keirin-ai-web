const assert=require('node:assert/strict');
const fs=require('node:fs');
const api=require('../model-web-response.js');
const fixtures=JSON.parse(fs.readFileSync(0,'utf8'));
const clone=x=>structuredClone(x);
const mutations=[
 d=>d.production_prediction_enabled=true,d=>d.db_write_enabled=0,
 d=>d.entitlement_status='owner',d=>d.schema_version='prediction-snapshot-v1',
 d=>d.model.model_version='unknown',d=>d.private_extra='secret',
 d=>d.quality.rider_count=8,d=>d.quality.possible_trifecta_count=999,
 d=>d.quality.known_trifecta_odds_count=0,d=>d.total_picks++,
 d=>d.captured_at=d.race.scheduled_start_jst,d=>d.race.date='1999-01-01',
 d=>d.snapshot_sha256='bad',d=>d.categories.hit_priority.status='partial',
 d=>d.categories.hit_priority.picks[1].combo_key=d.categories.hit_priority.picks[0].combo_key,
 d=>d.categories.hit_priority.picks[0].combo_key='1-1-2',
 d=>d.categories.hit_priority.picks[0].estimated_probability=NaN,
 d=>d.categories.hit_priority.picks[0].odds=true,
 d=>d.categories.hit_priority.picks[0].reason='fabricated',
 d=>d.categories.hit_priority.picks[0].rank=0,
 d=>d.categories.hit_priority.picks[0].estimated_probability=0,
];
(async()=>{
 for(const original of fixtures){
  assert.equal(api.validate(original),original);
  const nodes=new Map();
  const document={getElementById:id=>{if(!nodes.has(id))nodes.set(id,{textContent:'',replaceChildren(){this.textContent='';}});return nodes.get(id);}};
  const options={document,renderCategory:(id,c)=>document.getElementById(id).textContent=JSON.stringify(c)};
  for(const mutate of mutations){
   api.render(original,options);assert(document.getElementById('cat-hit').textContent);
   const bad=clone(original);mutate(bad);
   assert.throws(()=>api.render(bad,options),/ml_web_response_invalid/);
   for(const id of ['cat-hit','cat-balance','cat-middle','cat-longshot','cat-super','model-race','model-identity','input-quality'])assert.equal(document.getElementById(id).textContent,'');
  }
  let calls=0;
  global.fetch=async(url,init)=>{calls++;assert.deepEqual(init,{cache:'no-store',credentials:'omit',redirect:'error'});return {ok:true,json:async()=>original};};
  const url='/api/model-view/'+original.snapshot_id;
  assert.equal(await api.load(url,options),original);
  assert.equal(await api.load('/api/model-view/'+'b'.repeat(32),options),null);
  assert.equal(document.getElementById('cat-hit').textContent,'');
  const before=calls;
  for(const url of ['https://example.invalid/x','/api/model-view/../secret'])assert.equal(await api.load(url,options),null);
  assert.equal(calls,before);
  global.fetch=async()=>({ok:false,json:async()=>original});
  assert.equal(await api.load(url,options),null);
  global.fetch=async()=>{throw new Error('network failure');};
  assert.equal(await api.load(url,options),null);
 }
 console.log('ML display rejection and clearing PASS');
})().catch(e=>{console.error(e);process.exitCode=1;});
