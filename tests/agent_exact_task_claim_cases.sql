-- Synthetic exact-task queue claim cases. Outer harness wraps all work in ROLLBACK.
set local role authenticated;
set local request.jwt.claim.sub = '00000000-0000-0000-0000-000000000001';

insert into public.agent_tasks(user_id, task_id, idempotency_key, spec, state, spec_fingerprint)
values
(
  auth.uid(),
  'exact-other',
  'exact-other-key',
  '{"schema_version":"agent-task-v1","task_id":"exact-other"}',
  jsonb_build_object(
    'schema_version','agent-task-state-v1','task_id','exact-other','status','pending',
    'spec_fingerprint','sha256-v1:' || repeat('a',64)
  ),
  'sha256-v1:' || repeat('a',64)
),
(
  auth.uid(),
  'exact-target',
  'exact-target-key',
  '{"schema_version":"agent-task-v1","task_id":"exact-target"}',
  jsonb_build_object(
    'schema_version','agent-task-state-v1','task_id','exact-target','status','pending',
    'spec_fingerprint','sha256-v1:' || repeat('b',64)
  ),
  'sha256-v1:' || repeat('b',64)
);

-- Targeted claim must not consume a different FIFO row.
select public.agent_claim_task('exact-target', 'worker-exact', 120);
select pg_temp.assert_true(
  (select status='running' and revision=1 and attempt_count=1
      and lease_owner='worker-exact' and lease_generation=1
   from public.agent_tasks where task_id='exact-target'),
  'exact target acquires its own fenced lease'
);
select pg_temp.assert_true(
  (select status='queued' and revision=0 and attempt_count=0 and lease_owner is null
   from public.agent_tasks where task_id='exact-other'),
  'unrelated queued row is untouched by exact claim'
);
select pg_temp.assert_true(
  (select count(*)=1 from public.agent_task_events
   where task_id='exact-target' and event_type='lease_claimed'
     and payload->>'claim_mode'='exact_task'),
  'exact claim is explicitly audited'
);

-- A running target, unknown target, future target, or exhausted target is not claimed.
select pg_temp.assert_true(
  public.agent_claim_task('exact-target', 'worker-second', 120) is null,
  'running exact target is never stolen'
);
select pg_temp.assert_true(
  public.agent_claim_task('exact-missing', 'worker-second', 120) is null,
  'missing exact target returns no claim'
);

insert into public.agent_tasks(
  user_id, task_id, idempotency_key, spec, state, spec_fingerprint, not_before
) values (
  auth.uid(), 'exact-future', 'exact-future-key',
  '{"schema_version":"agent-task-v1","task_id":"exact-future"}',
  jsonb_build_object(
    'schema_version','agent-task-state-v1','task_id','exact-future','status','pending',
    'spec_fingerprint','sha256-v1:' || repeat('c',64)
  ),
  'sha256-v1:' || repeat('c',64),
  clock_timestamp() + interval '1 day'
);
select pg_temp.assert_true(
  public.agent_claim_task('exact-future', 'worker-second', 120) is null,
  'not-before remains enforced for exact claims'
);

insert into public.agent_tasks(
  user_id, task_id, idempotency_key, spec, state, spec_fingerprint,
  attempt_count, max_attempts
) values (
  auth.uid(), 'exact-exhausted', 'exact-exhausted-key',
  '{"schema_version":"agent-task-v1","task_id":"exact-exhausted"}',
  jsonb_build_object(
    'schema_version','agent-task-state-v1','task_id','exact-exhausted','status','pending',
    'spec_fingerprint','sha256-v1:' || repeat('d',64)
  ),
  'sha256-v1:' || repeat('d',64),
  1, 1
);
select pg_temp.assert_true(
  public.agent_claim_task('exact-exhausted', 'worker-second', 120) is null,
  'attempt budget remains enforced for exact claims'
);

-- Other users cannot claim this owner's task by naming it.
set local request.jwt.claim.sub = '00000000-0000-0000-0000-000000000002';
select pg_temp.assert_true(
  public.agent_claim_task('exact-other', 'worker-other-owner', 120) is null,
  'exact task id does not bypass owner isolation'
);

-- Anonymous role receives no execute permission.
set local role anon;
select pg_temp.expect_error($q$
  select public.agent_claim_task('exact-other', 'worker-anon', 120)
$q$, '42501');
reset role;
