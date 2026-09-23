import {readFileSync} from 'node:fs';
import {stripTypeScriptTypes} from 'node:module';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import test from 'node:test';

// Pure computation only. No real auth, database, or network requests.
function load(slug, names) {
 const source=readFileSync(new URL('../backend/'+slug+'/index.ts',import.meta.url),'utf8');
 const context=vm.createContext({Deno:{serve(){}}, console});
 return vm.runInContext(stripTypeScriptTypes(source)+'\n;({'+names.join(',')+'})',context);
}
const bt=load('backtest-engine-dev',['validate','run']);
const hb=load('history-builder-dev',['validate','normalize']);
const hp=load('history-pipeline-dev',['validate']);
const cats=['hit_priority','balance','middle','longshot','super_longshot'];
function payload(full=true) {
 const scores=[];
 for(let a=1;a<=7;a++)for(let b=1;b<=7;b++)for(let c=1;c<=7;c++)
 if(a!==b&&b!==c&&a!==c)scores.push({combo_key:[a,b,c].join('-'),estimated_probability:1/210});
 return {evaluation_scope:'replay_or_legacy',race:{race_id:'synthetic-only'},
 prediction:{prediction_timestamp:'2026-01-02T00:00:00Z',
 selected_predictions:{categories:Object.fromEntries(cats.map((k,i)=>[k,{picks:i?[]:[{combo_key:'1-2-3',estimated_probability:1/210,odds:99}]}]))},
 trifecta_scores:full?scores:scores.slice(0,3)},
 settlement:{outcome_combo:'1-2-3',settlement_odds:9.1,result_time_unknown:true,result_timestamp:null}};
}
test('complete synthetic history uses settlement odds and remains replay',()=>{
 const p=payload();assert.equal(hb.validate(p).length,0);
 const {record}=hb.normalize(p);assert.equal(bt.validate({records:[record]}).length,0);
 const r=bt.run({records:[record]});assert.equal(r.prospective_records,0);
 assert.equal(r.selection_performance.roi_multiple,9.1);
 assert.equal(r.probability_quality.races_with_full_probability_input,1);
});
test('partial probability table is not reported as full or scored as full',()=>{
 const {record}=hb.normalize(payload(false));const q=bt.run({records:[record]}).probability_quality;
 assert.equal(q.races_with_full_probability_input,0);
 assert.equal(q.races_missing_outcome_probability,0);
 assert.equal(q.mean_multiclass_brier_sum,null);
});
test('210 entries with invalid car numbers are not full coverage',()=>{
 const p=payload();p.prediction.trifecta_scores[209].combo_key='8-9-10';
 const q=bt.run({records:[hb.normalize(p).record]}).probability_quality;
 assert.equal(q.races_with_full_probability_input,0);
});
test('non-normalized probability mass is not full valid input',()=>{
 const p=payload();p.prediction.trifecta_scores.forEach(x=>x.estimated_probability=.001);
 assert.equal(bt.run({records:[hb.normalize(p).record]}).probability_quality.races_with_full_probability_input,0);
});
test('prospective history rejects unknown result time',()=>{
 const p=payload();p.evaluation_scope='prospective';
 assert.ok(hb.validate(p).some(x=>x.includes('unknown result time')));
});
test('pipeline rejects raw race input without a prediction snapshot',()=>{
 assert.ok(hp.validate({mode:'dry_run',snapshot:{race:{}},settlement:payload().settlement}).length>0);
});
