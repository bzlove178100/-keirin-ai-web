const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync('index.html','utf8');
const source = html.match(/<script>([\s\S]*?)<\/script>/)[1].replace('(async()=>{await restoreLogin();await checkStatus();})();','');
const nodes = new Map();
function node(id) {
  if (!nodes.has(id)) nodes.set(id,{value:'',checked:false,disabled:false,textContent:'',className:'',addEventListener(){},classList:{contains(){return true},add(){},remove(){}}});
  return nodes.get(id);
}
const sandbox = {console, Date, Intl, URL, Blob, setTimeout, clearTimeout, document:{getElementById:node}, localStorage:{getItem(){return null},setItem(){},removeItem(){}}};
vm.createContext(sandbox);
vm.runInContext(source,sandbox);
function run(code){return vm.runInContext(code,sandbox)}
run(`var race={race:{date:'2026-09-24'}}; var now=new Date('2026-09-24T03:00:00Z');`);
assert.equal(run("prospectiveEligibility(race,'2026-09-24T12:01',true,now).prospective"),true);
for(const args of ["'',true", "'2026-09-24T12:00',true", "'2026-09-25T12:01',true", "'2026-09-24T12:01',false", "'2026-09-24T25:00',true"]){
  assert.equal(run(`prospectiveEligibility(race,${args},now).prospective`),false);
}
assert.equal(run("prospectiveEligibility({race:{date:'2026-02-30'}},'2026-02-30T12:00',true,new Date('2026-02-01')).prospective"),false);
run(`var scores=[]; for(let a=1;a<=7;a++)for(let b=1;b<=7;b++)for(let c=1;c<=7;c++)if(a!==b&&a!==c&&b!==c)scores.push({combo_key:[a,b,c].join('-'),estimated_probability:1/210});`);
assert.equal(run('fullProbabilityTableValid(scores)'),true);
// Bad probabilities must not pass just because their total remains one.
assert.equal(run('fullProbabilityTableValid(scores.map((x,i)=>({...x,estimated_probability:i===0?-0.1:i===1?0.1+2/210:x.estimated_probability})))'),false);
assert.equal(run('fullProbabilityTableValid(scores.map((x,i)=>({...x,estimated_probability:i===0?NaN:x.estimated_probability})))'),false);
assert.equal(run('fullProbabilityTableValid(scores.map((x,i)=>({...x,combo_key:i===0?scores[1].combo_key:x.combo_key})))'),false);
assert.equal(run("historyEvaluationScope({validation_mode:'prospective-only',snapshot_eligibility:{prospective:true,reason:'date_only_same_day'}})"),'replay_or_legacy');
run(`var saved=0; downloadJson=()=>saved++; lastDryRunSnapshot={captured_at:'2026-09-24T02:59:00Z',validation_mode:'prospective-only',snapshot_eligibility:prospectiveEligibility(race,'2026-09-24T12:01',true,now),race_data:race};`);
assert.equal(run('historyEvaluationScope(lastDryRunSnapshot)'),'prospective');
run('Date.now=()=>new Date("2026-09-24T03:02:00Z").getTime(); savePredictionSnapshot();');
assert.equal(run('saved'),0);
assert.equal(run("trainingReadiness({metadata:{evaluation_scope:'prospective'}})"),'学習用入力が含まれていません');
run(`var rec={prediction_timestamp:'2026-09-24T02:59:00Z',metadata:{evaluation_scope:'prospective',result_timestamp:'2026-09-24T03:10:00Z',engine_version:'phase32-hit-priority-all210-v1',training_eligibility:{supervised_training:true}},training_input:{schema_version:'keirin-training-input-v1',evaluation_scope:'prospective',captured_at:'2026-09-24T02:59:00Z',players:Array.from({length:7},(_,i)=>({car_number:i+1,style:'追'}))},trifecta_scores:scores};`);
assert.equal(run('trainingReadiness(rec)'),null);
(async()=>{
  run(`currentSession={}; loadedHistorySnapshot=lastDryRunSnapshot; var posts=0; authenticatedPost=async()=>{posts++;throw Error('unexpected network')};`);
  node('result-combo').value='1-2-3';node('result-odds').value='12.3';
  node('result-time').value='2099-01-01T00:00';
  await run('runHistoryPipeline()');
  assert.equal(run('posts'),0);
  assert.match(node('history-note').textContent,/未来/);
  console.log('Web capture, cutoff, probability and result-time checks: PASS');
})().catch(e=>{console.error(e);process.exitCode=1});
