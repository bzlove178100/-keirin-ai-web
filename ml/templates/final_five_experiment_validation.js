const states={registered:'登録済み・未実行',running:'実行開始済み・完了未確認',completed:'合成比較完了',blocked:'条件不足・学習なし',failed:'実行失敗',interrupted:'中断を記録済み'};
const eligibility={ready:'固定条件を満たす',blocked_fewer_than_five_training_times:'異なる学習時刻が5件未満',blocked_no_test_races:'検証対象がない',blocked_training_requires_both_labels:'学習に正負両方のラベルがない'};
const hex=(v,n)=>typeof v==='string'&&new RegExp('^[0-9a-f]{'+n+'}$').test(v);
const integer=v=>Number.isInteger(v)&&v>=0&&v<=200;
const time=v=>typeof v==='string'&&/(?:Z|[+-]\d\d:\d\d)$/.test(v)&&Number.isFinite(Date.parse(v));
const text=v=>typeof v==='string'&&v.trim().length>0&&[...v].length<=500&&!/[\x00-\x1f\x7f]/.test(v);
function fail(){throw new Error('invalid_experiment_response');}
function keys(v,expected){if(!v||typeof v!=='object'||Array.isArray(v)||Object.keys(v).sort().join(',')!==expected.split(',').sort().join(','))fail();}
function validate(v){
 if(!v||v.schema_version!=='synthetic-final-five-experiment-audit-view-v1'||v.synthetic_only!==true||v.read_only!==true||v.evidence_scope!=='synthetic_test_only'||v.clock_source!=='local_unverified'||v.tracking_scope!=='this_local_ledger_only'||v.hold_status!=='provided_histories_only'||!['pinned_checkpoint_with_change_refusal','owned_ledger_current_checkpoint'].includes(v.loading_policy)||v.model_match_basis!=='saved_model_sha256_only_not_provenance'||v.overlap_basis!=='all_prior_registrations_including_failed_or_unrun'||typeof v.configured!=='boolean')fail();
 for(const k of ['production_prediction_enabled','external_fetch_enabled','db_write_enabled','real_data_training_enabled','monetary_ev_enabled','promotion_eligible','provenance_independently_verified','product_acceptance','evaluation_eligible','independent_evaluation_established','automatic_retry_enabled','training_on_request'])if(v[k]!==false)fail();
 if(!Array.isArray(v.attempts)||v.attempts.length>20||(v.configured?!hex(v.revision,64):v.revision!==null||v.attempts.length!==0))fail();
 const seen=new Map();
 for(const [i,r] of v.attempts.entries()){
  keys(r,'attempt_id,sequence,status,retry_of,input_sha256,registered_at,reason,cutoff,plan_sha256,previous_registered_overlap,model_sha256,started_at,finished_at,terminal_reason,eligibility,counts,strata');
  if(!hex(r.attempt_id,32)||seen.has(r.attempt_id)||r.sequence!==i+1||!Object.hasOwn(states,r.status)||!text(r.reason)||!time(r.registered_at)||!time(r.cutoff)||!hex(r.input_sha256,64)||!hex(r.plan_sha256,64)||!Object.hasOwn(eligibility,r.eligibility))fail();
  if(r.retry_of!==null&&(!hex(r.retry_of,32)||!seen.has(r.retry_of)||['registered','running'].includes(seen.get(r.retry_of).status)||seen.get(r.retry_of).input_sha256!==r.input_sha256||seen.get(r.retry_of).plan_sha256!==r.plan_sha256))fail();
  if(r.started_at!==null&&!time(r.started_at)||r.finished_at!==null&&!time(r.finished_at))fail();
  const terminal=!['registered','running'].includes(r.status);
  if(terminal!==Boolean(r.finished_at)||(r.status==='registered'&&r.started_at!==null)||(r.status!=='registered'&&r.status!=='interrupted'&&r.started_at===null)||(!terminal&&i!==v.attempts.length-1))fail();
  if(['failed','interrupted'].includes(r.status)?!text(r.terminal_reason):r.terminal_reason!==null)fail();
  if(r.status==='failed'&&r.terminal_reason!=='execution_exception')fail();
  if(r.status==='completed'?(r.eligibility!=='ready'||!hex(r.model_sha256,64)):r.model_sha256!==null||r.strata!==null)fail();
  if(r.status==='blocked'&&r.eligibility==='ready')fail();
  const c=r.counts;keys(c,'input_records,training_races,test_races,held_races,duplicate_snapshots_removed,excluded');
  for(const k of ['input_records','training_races','test_races','held_races','duplicate_snapshots_removed'])if(!integer(c[k])||c[k]>c.input_records)fail();
  if(c.training_races+c.test_races>c.input_records||!c.excluded||typeof c.excluded!=='object'||Array.isArray(c.excluded)||Object.entries(c.excluded).some(([k,n])=>!text(k)||!integer(n)||n>c.input_records))fail();
  if(!Array.isArray(r.previous_registered_overlap)||r.previous_registered_overlap.length>i)fail();
  const overlaps=new Set();for(const o of r.previous_registered_overlap){
   keys(o,'attempt_id,validation_reused,validation_previously_training,training_previously_validation');
   if(!seen.has(o.attempt_id)||overlaps.has(o.attempt_id))fail();overlaps.add(o.attempt_id);
   for(const k of ['validation_reused','validation_previously_training','training_previously_validation'])if(!integer(o[k]))fail();
   const p=seen.get(o.attempt_id).counts;
   if(o.validation_reused>Math.min(c.test_races,p.test_races)||o.validation_previously_training>Math.min(c.test_races,p.training_races)||o.training_previously_validation>Math.min(c.training_races,p.test_races)||o.validation_reused+o.validation_previously_training+o.training_previously_validation===0)fail();
  }
  if(r.status==='completed'){
   if(!Array.isArray(r.strata)||r.strata.length!==6)fail();let total=0;
   for(const [n,s] of r.strata.entries()){
    keys(s,'rider_count,selected_count,races,baseline_hits,challenger_hits,baseline_hit_rate,challenger_hit_rate,challenger_only,baseline_only,both,neither,outside_pool');
    if(s.rider_count!==[7,9][Math.floor(n/3)]||s.selected_count!==3+n%3||!integer(s.races))fail();total+=s.races;
    for(const k of ['baseline_hits','challenger_hits','challenger_only','baseline_only','both','neither','outside_pool'])if(!integer(s[k])||s[k]>s.races)fail();
    if(s.challenger_only+s.baseline_only+s.both+s.neither!==s.races||s.baseline_hits!==s.baseline_only+s.both||s.challenger_hits!==s.challenger_only+s.both||s.outside_pool>s.neither)fail();
    if(s.baseline_hit_rate!==(s.races?s.baseline_hits/s.races:null)||s.challenger_hit_rate!==(s.races?s.challenger_hits/s.races:null))fail();
   }if(total!==c.test_races)fail();
  }
  seen.set(r.attempt_id,r);
 }
}
