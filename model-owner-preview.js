/* Optional owner UI. Uses the host's authenticated transport; stores no session. */
(function(root){
 'use strict';
 const IDS=['cat-hit','cat-balance','cat-middle','cat-longshot','cat-super'];
 const NAMES=['的中率重視','バランス','中穴','大穴','超大穴'];
 const object=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
 const exact=(v,keys)=>object(v)&&Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
 const fail=()=>{throw Error('owner_model_response_invalid');};
 function owner(data){
  if(!object(data)||data.success!==true||data.authenticated!==true||data.owner!==true||
     data.role!=='owner'||data.plan!=='owner'||data.service!=='predict-engine-dev'||
     data.production_prediction_enabled!==false||data.db_write_enabled!==false||data.monetary_ev_enabled!==false)fail();
 }
 function catalog(data){
  owner(data);
  if(data.data_source_connected!==false)fail();
  const c=data.synthetic_model_preview;
  if(!exact(c,['available','scope','snapshots'])||c.scope!=='bundled_synthetic_snapshots'||
     typeof c.available!=='boolean'||!Array.isArray(c.snapshots))fail();
  if(!c.available){if(c.snapshots.length)fail();return [];}
  if(c.snapshots.length!==2)fail();
  for(const s of c.snapshots){
   if(!exact(s,['snapshot_id','rider_count','captured_at','model_artifact_sha256'])||
      typeof s.snapshot_id!=='string'||!/^[0-9a-f]{32}$/.test(s.snapshot_id)||
      ![7,9].includes(s.rider_count)||typeof s.captured_at!=='string'||
      !/T.*(?:Z|[+-]\d{2}:\d{2})$/.test(s.captured_at)||!Number.isFinite(Date.parse(s.captured_at))||
      typeof s.model_artifact_sha256!=='string'||!/^[0-9a-f]{64}$/.test(s.model_artifact_sha256))fail();
  }
  if(new Set(c.snapshots.map(s=>s.snapshot_id)).size!==2||c.snapshots.map(s=>s.rider_count).sort().join(',')!=='7,9')fail();
  return c.snapshots;
 }
 function view(data,selected,web){
  owner(data);
  if(!exact(data,['success','schema_version','service','mode','input_source','prediction_generated','saved',
    'production_prediction_enabled','external_fetch_enabled','db_write_enabled','monetary_ev_enabled','model_view',
    'authenticated','owner','role','plan'])||data.schema_version!=='keirin-owner-ml-preview-v1'||
    data.mode!=='synthetic_model_view'||data.input_source!=='server_bundled_synthetic_snapshot'||
    data.prediction_generated!==false||data.saved!==false||data.external_fetch_enabled!==false)fail();
  const v=web.validate(data.model_view);
  if(v.snapshot_id!==selected.snapshot_id||v.quality.rider_count!==selected.rider_count||
     v.model_artifact_sha256!==selected.model_artifact_sha256||v.captured_at!==selected.captured_at||
     v.race.venue!=='SYNTHETIC')fail();
  return v;
 }
 function attach({document,host,get,post,identity,renderCategory,web=root.KeirinModelWeb,timeoutMs=15000}){
  if(document.getElementById('owner-model-panel'))throw Error('owner_model_already_attached');
  const el=(tag,id,text,cls)=>{const e=document.createElement(tag);if(id)e.id='owner-model-'+id;
   if(text)e.textContent=text;if(cls)e.className=cls;return e;};
  const panel=el('section','panel',null,'card');
  panel.setAttribute('aria-labelledby','owner-model-title');
  panel.appendChild(el('h2','title','合成モデルの動作確認'));
  panel.appendChild(el('p',null,'7車・9車の架空レースで保存済みのモデル結果を確認できます。実レースの予想や購入には使えません。','note'));
  const refreshButton=el('button','refresh','保存済みモデルを確認');refreshButton.type='button';
  const label=el('label',null,'表示する合成レース');label.htmlFor='owner-model-select';
  const select=el('select','select');select.style.maxWidth='100%';select.style.width='100%';
  const displayButton=el('button','display','モデル結果を表示');displayButton.type='button';
  const status=el('p','model-status',null,'note');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
  for(const e of [refreshButton,label,select,displayButton,status,el('p','model-race'),el('p','model-identity',null,'note'),el('p','input-quality',null,'note')])panel.appendChild(e);
  const grid=el('div',null,null,'categories');
  IDS.forEach((id,i)=>{const box=el('article',null,null,'pick');box.appendChild(el('h3',null,NAMES[i]));box.appendChild(el('div',id));grid.appendChild(box);});
  panel.appendChild(grid);host.appendChild(panel);
  let generation=0,entries=[],catalogIdentity=null;
  const scoped={getElementById:id=>document.getElementById('owner-model-'+id)};
  const clear=()=>{for(const id of [...IDS,'model-race','model-identity','input-quality'])scoped.getElementById(id).replaceChildren();};
  function reset(message='ログイン後に保存済みモデルを確認してください。'){
   generation++;entries=[];catalogIdentity=null;select.replaceChildren();select.disabled=true;
   displayButton.disabled=true;refreshButton.disabled=false;clear();status.textContent=message;
  }
  const current=(g,who)=>g===generation&&who!==null&&identity()===who;
  async function bounded(task){
   let timer;
   try{return await Promise.race([task(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('owner_model_timeout')),timeoutMs);})]);}
   finally{clearTimeout(timer);}
  }
  function rejected(g){if(g===generation)reset('モデル結果を確認できませんでした。ログイン状態を確認し、再度お試しください。');}
  async function refresh(){
   reset();const g=generation,who=identity();
   if(who===null)return null;
   refreshButton.disabled=true;status.textContent='保存済みモデルを確認しています。';
   try{
    const data=await bounded(async()=>{const response=await get();if(!response.ok)fail();return response.json();});
    if(!current(g,who)){rejected(g);return null;}
    entries=catalog(data);catalogIdentity=who;
    for(const s of entries){const option=el('option',null,s.rider_count+'車 · 保存 '+s.captured_at);option.value=s.snapshot_id;select.appendChild(option);}
    select.disabled=!entries.length;displayButton.disabled=!entries.length;refreshButton.disabled=false;
    status.textContent=entries.length?'7車・9車の保存済みモデルを選択できます。':'保存済みモデルはまだ準備されていません。';
    return entries;
   }catch(_){rejected(g);return null;}
  }
  async function load(){
   const selected=entries.find(s=>s.snapshot_id===select.value),who=identity();
   clear();const g=++generation;
   if(!selected||who===null||who!==catalogIdentity){rejected(g);return null;}
   displayButton.disabled=true;select.disabled=true;status.textContent='モデル結果を確認しています。';
   try{
    const data=await bounded(async()=>{const response=await post({mode:'synthetic_model_view',snapshot_id:selected.snapshot_id});if(!response.ok)fail();return response.json();});
    if(!current(g,who)){rejected(g);return null;}
    const result=view(data,selected,web);
    web.render(result,{document:scoped,renderCategory:(id,c)=>renderCategory('owner-model-'+id,c)});
    displayButton.disabled=false;select.disabled=false;
    return result;
   }catch(_){rejected(g);return null;}
  }
  refreshButton.addEventListener('click',refresh);displayButton.addEventListener('click',load);
  select.addEventListener('change',()=>{generation++;clear();displayButton.disabled=!entries.some(s=>s.snapshot_id===select.value);status.textContent='選択した合成レースの結果を表示できます。';});
  reset();return Object.freeze({refresh,load,reset});
 }
 const api=Object.freeze({attach});root.KeirinOwnerModelPreview=api;
 if(typeof module==='object'&&module.exports)module.exports=api;
})(globalThis);
