const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const web=require('../model-web-response.js');
const client=require('../model-owner-preview.js');
const bundle=JSON.parse(fs.readFileSync(0,'utf8'));
class Element{
 constructor(tag){this.tag=tag;this.children=[];this._text='';this.value='';this.events={};}
 appendChild(node){this.children.push(node);if(this.tag==='select'&&this.children.length===1)this.value=node.value;return node;}
 replaceChildren(){this.children=[];this._text='';if(this.tag==='select')this.value='';}
 set textContent(text){this.children=[];this._text=text;}
 get textContent(){return this._text+this.children.map(c=>c.textContent).join('');}
 setAttribute(){} addEventListener(name,fn){this.events[name]=fn;}
 get style(){return this._style??={};}
}
const host=new Element('main');
const find=(node,id)=>node.id===id?node:node.children.map(n=>find(n,id)).find(Boolean);
const document={createElement:tag=>new Element(tag),getElementById:id=>find(host,id)||null};
const legacy=document.createElement('div');legacy.id='cat-hit';legacy.textContent='existing Phase32 result';host.appendChild(legacy);
const source=fs.readFileSync('index.html','utf8');
const renderer=source.slice(source.indexOf('function appendPick(box, pick) {'),source.indexOf('function renderDryRun(data) {'));
const context=vm.createContext({document,element:id=>document.getElementById(id)});
vm.runInContext(renderer,context);
const service='https://synthetic-auth.invalid';
let userStatus=200,profiles=[{role:'owner',plan:'owner'}],authCalls=0;
global.Deno={env:{get:k=>({SUPABASE_URL:service,SUPABASE_ANON_KEY:'synthetic-publishable'}[k])},serve(){}};
global.fetch=async(url,options)=>{
 authCalls++;assert.equal(options.headers.Authorization,'Bearer synthetic-session');
 if(url===service+'/auth/v1/user')return Response.json({id:'synthetic-owner'},{status:userStatus});
 if(url===service+'/rest/v1/user_profiles?user_id=eq.synthetic-owner&select=role,plan')return Response.json(profiles);
 throw Error('unexpected request');
};
(async()=>{
 const {createPredictHandler}=await import('../supabase/functions/predict-engine-dev/index.ts');
 let handler=createPredictHandler(bundle),who=null,getTransform=x=>x,postTransform=x=>x,pending=null;
 const requests=[];
 const request=body=>new Request('https://synthetic-function.invalid',{method:body?'POST':'GET',
  headers:{Origin:'https://bzlove178100.github.io',Authorization:'Bearer synthetic-session','Content-Type':'application/json'},
  ...(body?{body:JSON.stringify(body)}:{})});
 const api=client.attach({document,host,identity:()=>who,web,timeoutMs:100,
  renderCategory:context.renderCategory,
  get:async()=>getTransform(await handler(request())),
  post:async body=>{requests.push(body);if(pending)return pending;return postTransform(await handler(request(body)));}});
 const node=id=>document.getElementById('owner-model-'+id);
 assert.equal(authCalls,0);await api.refresh();assert.equal(authCalls,0);
 who='synthetic-owner';await api.refresh();assert.equal(node('select').children.length,2);
 for(const v of bundle.views){
  node('select').value=v.snapshot_id;const result=await api.load();assert.deepEqual(result,v);
  assert.equal(node('cat-hit').children.length,3);
  assert(node('model-race').textContent.includes(v.quality.rider_count+'車'));
  assert.deepEqual(requests.at(-1),{mode:'synthetic_model_view',snapshot_id:v.snapshot_id});
  assert.equal(legacy.textContent,'existing Phase32 result');
 }
 // Server claims alone cannot bypass the display contract or selected catalog identity.
 for(const mutate of [d=>d.owner=false,d=>d.plan='free',d=>d.authenticated=false,d=>d.db_write_enabled=true,
  d=>d.saved=true,d=>d.mode='dry_run',d=>d.model_view.snapshot_id='a'.repeat(32),
  d=>d.model_view.model_artifact_sha256='b'.repeat(64),d=>d.model_view.quality.rider_count=8]){
  postTransform=async response=>{const d=await response.json();mutate(d);return Response.json(d);};
  await api.refresh();assert.equal(await api.load(),null);assert.equal(node('cat-hit').textContent,'');assert(node('display').disabled);
 }
 postTransform=x=>x;
 for(const status of [401,403,503]){
  await api.refresh();await api.load();postTransform=()=>Response.json({success:false},{status});
  assert.equal(await api.load(),null);assert.equal(node('cat-hit').textContent,'');postTransform=x=>x;
 }
 for(const mutate of [d=>d.synthetic_model_preview.snapshots[1].snapshot_id=d.synthetic_model_preview.snapshots[0].snapshot_id,
  d=>d.synthetic_model_preview.snapshots[1].rider_count=7,d=>d.data_source_connected=true,d=>d.owner=false]){
  getTransform=async response=>{const d=await response.json();mutate(d);return Response.json(d);};
  assert.equal(await api.refresh(),null);assert(node('display').disabled);
 }
 getTransform=x=>x;handler=createPredictHandler(null);await api.refresh();assert(node('model-status').textContent.includes('準備されていません'));
 handler=createPredictHandler(bundle);userStatus=401;assert.equal(await api.refresh(),null);userStatus=200;
 profiles=[{role:'admin',plan:'owner'}];assert.equal(await api.refresh(),null);profiles=[{role:'owner',plan:'owner'}];
 // A response started before logout must not repaint, even after same-user login.
 await api.refresh();let release;pending=new Promise(resolve=>release=resolve);const old=api.load();
 api.reset();who=null;who='synthetic-owner';pending=null;await api.refresh();node('select').value=bundle.views[1].snapshot_id;await api.load();
 const newer=node('model-race').textContent;
 release(await handler(request({mode:'synthetic_model_view',snapshot_id:bundle.views[0].snapshot_id})));
 assert.equal(await old,null);assert.equal(node('model-race').textContent,newer);
 // Account changes without a reset also invalidate a pending response.
 pending=new Promise(resolve=>release=resolve);const switched=api.load();who='different-owner';
 release(await handler(request(requests.at(-1))));assert.equal(await switched,null);assert.equal(node('cat-hit').textContent,'');
 who='synthetic-owner';pending=null;await api.refresh();pending=new Promise(()=>{});
 assert.equal(await api.load(),null);assert.equal(node('cat-hit').textContent,'');assert.equal(node('refresh').disabled,false);
 assert.equal(legacy.textContent,'existing Phase32 result');
 console.log('owner Web 7/9 and stale-response isolation PASS');
})().catch(e=>{console.error(e);process.exitCode=1;});
