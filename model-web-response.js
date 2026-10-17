/* Independent ML display contract. Does not authenticate or grant plan access. */
(function(root){
 'use strict';
 const KEYS=['hit_priority','balance','middle','longshot','super_longshot'];
 const IDS=['cat-hit','cat-balance','cat-middle','cat-longshot','cat-super'];
 const NAMES=['的中率優先','穴＋バランス','中穴','大穴','超大穴'];
 const BANDS=[null,[20,60],[60,100],[100,500],[500,Infinity]];
 const FIXED={schema_version:'keirin-ml-web-response-v1',scope:'frozen_synthetic_snapshot_display',
  evidence_scope:'synthetic_test_only',authentication_status:'not_asserted',entitlement_status:'not_asserted',
  production_prediction_enabled:false,external_fetch_enabled:false,db_write_enabled:false,
  supervised_training_enabled:false,monetary_ev_enabled:false,probability_calibration_status:'uncalibrated',
  selection_policy:'hit_priority_all_combos_odds_bands_probability_uncalibrated_v2'};
 const MODEL={model_version:'lightgbm-position-rankers-v1',inference_version:'lightgbm-offline-inference-v1',adapter_version:'position-probability-to-trifecta-v1'};
 const TOP=[...Object.keys(FIXED),'snapshot_id','snapshot_sha256','captured_at','generated_at','race','model','model_artifact_sha256','quality','total_picks','categories'];
 const object=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
 const exact=(v,keys)=>object(v)&&Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
 const fail=()=>{throw new Error('ml_web_response_invalid');};
 const finite=v=>typeof v==='number'&&Number.isFinite(v);
 const time=v=>typeof v==='string'&&/T.*(?:Z|[+-]\d{2}:\d{2})$/.test(v)&&Number.isFinite(Date.parse(v));
 function validate(data){
  if(!exact(data,TOP)||Object.entries(FIXED).some(([k,v])=>data[k]!==v))fail();
  if(!/^[0-9a-f]{32}$/.test(data.snapshot_id)||typeof data.snapshot_id!=='string')fail();
  for(const key of ['snapshot_sha256','model_artifact_sha256'])if(typeof data[key]!=='string'||!/^[0-9a-f]{64}$/.test(data[key]))fail();
  if(!exact(data.model,Object.keys(MODEL))||Object.entries(MODEL).some(([k,v])=>data.model[k]!==v))fail();
  const race=data.race,q=data.quality;
  if(!exact(race,['date','venue','race_number','scheduled_start_jst'])||typeof race.date!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(race.date)||typeof race.venue!=='string'||!race.venue.trim()||race.venue!==race.venue.trim()||!Number.isInteger(race.race_number)||race.race_number<1)fail();
  if(![data.generated_at,data.captured_at,race.scheduled_start_jst].every(time)||Date.parse(data.generated_at)>Date.parse(data.captured_at)||Date.parse(data.captured_at)>=Date.parse(race.scheduled_start_jst))fail();
  if(new Date(Date.parse(race.scheduled_start_jst)+9*3600000).toISOString().slice(0,10)!==race.date)fail();
  if(!exact(q,['rider_count','known_trifecta_odds_count','possible_trifecta_count'])||![7,9].includes(q.rider_count)||q.possible_trifecta_count!==q.rider_count*(q.rider_count-1)*(q.rider_count-2)||!Number.isInteger(q.known_trifecta_odds_count)||q.known_trifecta_odds_count<0||q.known_trifecta_odds_count>q.possible_trifecta_count)fail();
  if(!exact(data.categories,KEYS))fail();
  const seen=new Set();let known=0;
  for(const [index,key] of KEYS.entries()){
   const c=data.categories[key];
   if(!exact(c,['category_name','status','category_note','picks'])||c.category_name!==NAMES[index]||!Array.isArray(c.picks)||c.picks.length>3||c.status!==(c.picks.length===3?'ready':c.picks.length?'partial':'skipped'))fail();
   if(c.status==='ready'?c.category_note!==null:typeof c.category_note!=='string'||!c.category_note.trim())fail();
   let previous=Infinity;
   for(const [rank,p] of c.picks.entries()){
    if(!exact(p,['rank','combo_key','estimated_probability','odds'])||p.rank!==rank+1||typeof p.combo_key!=='string'||!/^[1-9]-[1-9]-[1-9]$/.test(p.combo_key))fail();
    const cars=p.combo_key.split('-').map(Number),prob=p.estimated_probability;
    if(new Set(cars).size!==3||cars.some(n=>n>q.rider_count)||seen.has(p.combo_key)||!finite(prob)||prob<0||prob>1||prob>previous)fail();
    if(p.odds!==null&&(!finite(p.odds)||p.odds<=0))fail();
    if(index>0&&(p.odds===null||p.odds<BANDS[index][0]||p.odds>=BANDS[index][1]))fail();
    previous=prob;seen.add(p.combo_key);known+=p.odds!==null?1:0;
   }
  }
  if(data.categories.hit_priority.picks.length!==3||!Number.isInteger(data.total_picks)||data.total_picks!==seen.size||known>q.known_trifecta_odds_count)fail();
  return data;
 }
 function clear(document){
  for(const id of [...IDS,'model-race','model-identity','input-quality'])document.getElementById(id).replaceChildren();
 }
 function render(data,{document,renderCategory}){
  clear(document);
  try{
   validate(data);
   // These are the original category-renderer arguments, not a Phase32 engine response.
   KEYS.forEach((key,i)=>renderCategory(IDS[i],data.categories[key]));
   document.getElementById('model-race').textContent=data.race.date+' · '+data.race.venue+' '+data.race.race_number+'R · '+data.quality.rider_count+'車';
   document.getElementById('model-identity').textContent=data.model.model_version+' · 保存 '+data.captured_at;
   document.getElementById('input-quality').textContent='予測時の確認済みオッズ '+data.quality.known_trifecta_odds_count+'/'+data.quality.possible_trifecta_count+' · '+data.total_picks+'点';
   document.getElementById('model-status').textContent='保存済みの合成予測を表示しました。';
   return data;
  }catch(error){clear(document);document.getElementById('model-status').textContent='モデル応答を確認できないため表示を停止しました。';throw error;}
 }
 async function load(url,options){
  clear(options.document);options.document.getElementById('model-status').textContent='保存済み予測を確認しています。';
  try{
   if(typeof url!=='string'||!/^\/api\/model-view\/[0-9a-f]{32}$/.test(url))fail();
   const response=await fetch(url,{cache:'no-store',credentials:'omit',redirect:'error'});
   if(!response.ok)throw new Error('ml_web_response_unavailable');
   const data=await response.json();
   if(!object(data)||data.snapshot_id!==url.slice('/api/model-view/'.length))fail();
   return render(data,options);
  }catch(error){clear(options.document);options.document.getElementById('model-status').textContent='モデル応答を確認できないため表示を停止しました。';return null;}
 }
 const api=Object.freeze({validate,render,load});
 // The same validator is imported by the server; importing it performs no IO.
 root.KeirinModelWeb=api;
 if(typeof module==='object'&&module.exports)module.exports=api;
})(globalThis);
