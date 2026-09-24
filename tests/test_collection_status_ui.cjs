const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const strictTools = require('../prospective-tools-core.js');

const html = fs.readFileSync('index.html','utf8');
const strictUi = /src="prospective-tools-core\.js"/.test(html) && /chronological_evaluation_may_run/.test(html);
assert.match(html,/id="dataset-prospective-count"/);
assert.match(html,/id="dataset-prospective-remaining"/);
assert.match(html,/function prospectiveCollectionStatus\(records\)/);

const source = html.match(/<script>([\s\S]*?)<\/script>/)[1]
  .replace('(async()=>{await restoreLogin();await checkStatus();})();','');
const nodes = new Map();
function node(id) {
  if (!nodes.has(id)) {
    nodes.set(id,{
      value:'',checked:false,disabled:false,textContent:'',className:'',
      addEventListener(){},
      classList:{contains(){return true},add(){},remove(){}}
    });
  }
  return nodes.get(id);
}
const storage = {getItem(){return null},setItem(){},removeItem(){}};
const sandbox = {
  console,Date,Intl,URL,Blob,setTimeout,clearTimeout,
  ProspectiveTools: strictTools,
  document:{getElementById:node},
  localStorage:storage,sessionStorage:storage
};
vm.createContext(sandbox);
vm.runInContext(source,sandbox);
function run(code){return vm.runInContext(code,sandbox)}

run(`var scores=[]; for(let a=1;a<=7;a++)for(let b=1;b<=7;b++)for(let c=1;c<=7;c++)if(a!==b&&a!==c&&b!==c)scores.push({combo_key:[a,b,c].join('-'),estimated_probability:1/210});`);
run(`
function collectionTestRecord(i, opts={}) {
  const predicted = opts.time || new Date(Date.UTC(2026,8,24,1+i,0,0)).toISOString();
  const predictedMs = Date.parse(predicted);
  const scheduled = Number.isFinite(predictedMs) ? new Date(predictedMs + 30*60*1000).toISOString() : '2026-09-24T10:30:00Z';
  const result = Number.isFinite(predictedMs) ? new Date(predictedMs + 40*60*1000).toISOString() : '2026-09-24T10:40:00Z';
  return {
    race_id: opts.raceId || 'RACE-'+i,
    prediction_timestamp: predicted,
    outcome_combo: '1-2-3',
    settlement_odds: 12.3,
    metadata: {
      evaluation_scope: opts.scope || 'prospective',
      temporal_order: 'prediction_before_result',
      result_timestamp: opts.resultTime || result,
      training_eligibility: {supervised_training: true},
      engine_version: 'phase32-hit-priority-all210-v1',
      source_snapshot: {snapshot_eligibility:{scheduled_start:scheduled}}
    },
    training_input: {
      schema_version: 'keirin-training-input-v1',
      evaluation_scope: 'prospective',
      captured_at: predicted,
      race:{scheduled_start_jst:scheduled},
      players: Array.from({length:7},(_,n)=>({car_number:n+1,style:n===0?'逃':'追'})),
      odds: {trifecta:{}},
      prediction_context:{source:'WINTICKET'}
    },
    selected_predictions:{categories:{}},
    trifecta_scores: scores
  };
}
`);

run(`var four=[0,1,2,3].map(i=>collectionTestRecord(i));`);
assert.equal(run('prospectiveCollectionStatus(four).distinct_prediction_times'),4);
assert.equal(run('prospectiveCollectionStatus(four).remaining_distinct_prediction_times'),1);
assert.equal(run('prospectiveCollectionStatus(four).collection_threshold_met'),false);

run(`var five=[0,1,2,3,4].map(i=>collectionTestRecord(i));`);
assert.equal(run('prospectiveCollectionStatus(five).distinct_prediction_times'),5);
assert.equal(run('prospectiveCollectionStatus(five).remaining_distinct_prediction_times'),0);
assert.equal(run('prospectiveCollectionStatus(five).collection_threshold_met'),true);
if (strictUi) assert.equal(run('prospectiveCollectionStatus(five).chronological_evaluation_may_run'),true);

run(`var sameRace=[collectionTestRecord(0,{raceId:'SAME'}),collectionTestRecord(1,{raceId:'SAME'}),collectionTestRecord(2)];`);
assert.equal(run('prospectiveCollectionStatus(sameRace).eligible_unique_races'),2);
assert.equal(run('prospectiveCollectionStatus(sameRace).distinct_prediction_times'),2);

run(`var naive=[collectionTestRecord(0,{time:'2026-09-24T10:00:00'})];`);
assert.equal(run('prospectiveCollectionStatus(naive).distinct_prediction_times'),0);
if (strictUi) assert.equal(run("prospectiveCollectionStatus(naive).excluded.timestamp_timezone_missing"),1);
else assert.equal(run('prospectiveCollectionStatus(naive).invalid_prediction_times'),1);

run(`historyDatasetRecords=four; historyDatasetDuplicateCount=0; refreshHistoryDatasetView();`);
assert.equal(node('dataset-prospective-count').textContent,'4/5件');
assert.equal(node('dataset-prospective-remaining').textContent,strictUi?'あと1時点':'あと1件');
run(`historyDatasetRecords=five; refreshHistoryDatasetView();`);
assert.equal(node('dataset-prospective-count').textContent,'5/5件');
assert.equal(node('dataset-prospective-remaining').textContent,strictUi?'時系列分割 準備可':'最低条件到達');

if (strictUi) {
  run(`var blocked=[0,1,2,3,4].map(i=>collectionTestRecord(i)); blocked[0].metadata.result_timestamp=blocked[4].metadata.result_timestamp; blocked[3].metadata.result_timestamp=blocked[4].metadata.result_timestamp;`);
  assert.equal(run('prospectiveCollectionStatus(blocked).collection_threshold_met'),true);
  assert.equal(run('prospectiveCollectionStatus(blocked).chronological_evaluation_may_run'),false);
  assert.equal(run("prospectiveCollectionStatus(blocked).blocked_reason"),'insufficient_non_overlapping_partitions');
  run(`historyDatasetRecords=blocked; refreshHistoryDatasetView();`);
  assert.equal(node('dataset-prospective-count').textContent,'5/5件');
  assert.equal(node('dataset-prospective-remaining').textContent,'5時点到達・分割未達');
  assert.match(node('dataset-collection-detail').textContent,/insufficient_non_overlapping_partitions/);
  assert.match(html,/script-src 'self' 'unsafe-inline'/);
}

console.log('Web prospective collection progress checks: PASS');
