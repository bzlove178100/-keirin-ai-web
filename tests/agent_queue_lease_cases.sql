-- Synthetic PostgreSQL contract cases. The outer harness wraps all work in ROLLBACK.
set local role authenticated;
set local request.jwt.claim.sub = '00000000-0000-0000-0000-000000000001';

insert into public.agent_tasks(user_id, task_id, idempotency_key, spec, state, spec_fingerprint)
values (
  auth.uid(),
  'lease-task',
  'lease-key',
  '{"schema_version":"agent-task-v1","task_id":"lease-task"}',
  jsonb_build_object(
    'schema_version','agent-task-state-v1',
    'task_id','lease-task',
    'status','pending',
    'spec_fingerprint','sha256-v1:' || repeat('c',64)
  ),
  'sha256-v1:' || repeat('c',64)
);

insert into public.agent_tasks(
  user_id, task_id, idempotency_key, spec, state, spec_fingerprint, not_before
) values (
  auth.uid(),
  'future-task',
  'future-key',
  '{"schema_version":"agent-task-v1","task_id":"future-task"}',
  jsonb_build_object(
    'schema_version','agent-task-state-v1',
    'task_id','future-task',
    'status','pending',
    'spec_fingerprint','sha256-v1:' || repeat('d',64)
  ),
  'sha256-v1:' || repeat('d',64),
  clock_timestamp() + interval '1 day'
);

select public.agent_claim_next_task('worker-a', 120);
select pg_temp.assert_true(
  (select status='running' and revision=1 and attempt_count=1 and max_attempts=1
      and lease_owner='worker-a' and lease_generation=1 and lease_expires_at > clock_timestamp()
   from public.agent_tasks where task_id='lease-task'),
  'claim establishes fenced running lease'
);
select pg_temp.assert_true(
  (select state->>'status'='running' from public.agent_tasks where task_id='lease-task'),
  'claim synchronizes task state status'
);
select pg_temp.assert_true(
  (select count(*)=1 from public.agent_task_events
   where task_id='lease-task' and event_type='lease_claimed'),
  'claim appends explicit lease event'
);

-- A leased task cannot bypass fencing through the legacy/general checkpoint RPC.
select pg_temp.expect_error($q$
  select public.agent_save_checkpoint(
    'lease-task', 1, 'running',
    (select state from public.agent_tasks where task_id='lease-task')
  )
$q$, '40001');

-- Wrong worker and wrong generation cannot write.
select pg_temp.expect_error($q$
  select public.agent_save_leased_checkpoint(
    'lease-task', 1, 'worker-b', 1, 'running',
    (select state from public.agent_tasks where task_id='lease-task'), 120
  )
$q$, '40001');
select pg_temp.expect_error($q$
  select public.agent_save_leased_checkpoint(
    'lease-task', 1, 'worker-a', 2, 'running',
    (select state from public.agent_tasks where task_id='lease-task'), 120
  )
$q$, '40001');

-- Correct fence extends the lease and advances exactly one revision.
select public.agent_save_leased_checkpoint(
  'lease-task', 1, 'worker-a', 1, 'running',
  (select state from public.agent_tasks where task_id='lease-task'), 180
);
select pg_temp.assert_true(
  (select revision=2 and status='running' and lease_owner='worker-a' and lease_generation=1
   from public.agent_tasks where task_id='lease-task'),
  'fenced save advances revision without changing generation'
);
select pg_temp.assert_true(
  (select count(*)=1 from public.agent_task_events
   where task_id='lease-task' and event_type='lease_checkpoint_saved'),
  'running save appends lease checkpoint event'
);

-- No second claim can steal the running task; the only other row is not due.
select pg_temp.assert_true(
  public.agent_claim_next_task('worker-b', 120) is null,
  'running task is not stolen and future task is not due'
);

-- Simulate a crashed worker by expiring its lease. The stale worker can no longer save.
update public.agent_tasks
set lease_expires_at = clock_timestamp() - interval '1 second', revision = revision + 1
where task_id='lease-task';
select pg_temp.assert_true(
  (select revision=3 and lease_expires_at <= clock_timestamp()
   from public.agent_tasks where task_id='lease-task'),
  'synthetic lease expiry prepared'
);
select pg_temp.expect_error($q$
  select public.agent_save_leased_checkpoint(
    'lease-task', 3, 'worker-a', 1, 'running',
    (select state from public.agent_tasks where task_id='lease-task'), 120
  )
$q$, '40001');

-- Expired work is never auto-requeued. Explicit reconciliation blocks it and clears the lease.
select public.agent_reconcile_expired_lease(
  'lease-task', 3, 1,
  (select state || jsonb_build_object(
     'status','blocked',
     'blocked_reason','expired_lease_requires_reconciliation'
   ) from public.agent_tasks where task_id='lease-task')
);
select pg_temp.assert_true(
  (select revision=4 and status='blocked' and lease_owner is null and lease_expires_at is null
      and attempt_count=1 and lease_generation=1
   from public.agent_tasks where task_id='lease-task'),
  'expired lease becomes blocked without retry or generation reset'
);
select pg_temp.assert_true(
  (select state->>'status'='blocked'
      and state->>'blocked_reason'='expired_lease_requires_reconciliation'
   from public.agent_tasks where task_id='lease-task'),
  'reconciliation persists blocked state'
);
select pg_temp.assert_true(
  (select count(*)=1 from public.agent_task_events
   where task_id='lease-task' and event_type='lease_expiry_reconciled'),
  'expired lease reconciliation is audited'
);
select pg_temp.assert_true(
  public.agent_claim_next_task('worker-b', 120) is null,
  'blocked task is never automatically reclaimed'
);

-- Terminal save releases a healthy lease and stale writes remain fenced out.
insert into public.agent_tasks(user_id, task_id, idempotency_key, spec, state, spec_fingerprint)
values (
  auth.uid(),
  'terminal-task',
  'terminal-key',
  '{"schema_version":"agent-task-v1","task_id":"terminal-task"}',
  jsonb_build_object(
    'schema_version','agent-task-state-v1',
    'task_id','terminal-task',
    'status','pending',
    'spec_fingerprint','sha256-v1:' || repeat('e',64)
  ),
  'sha256-v1:' || repeat('e',64)
);
select public.agent_claim_next_task('worker-c', 120);
select public.agent_save_leased_checkpoint(
  'terminal-task', 1, 'worker-c', 1, 'completed',
  (select state || jsonb_build_object('status','completed')
   from public.agent_tasks where task_id='terminal-task'),
  120
);
select pg_temp.assert_true(
  (select revision=2 and status='completed' and lease_owner is null and lease_expires_at is null
   from public.agent_tasks where task_id='terminal-task'),
  'terminal leased save releases lease'
);
select pg_temp.expect_error($q$
  select public.agent_save_leased_checkpoint(
    'terminal-task', 2, 'worker-c', 1, 'running',
    (select state || jsonb_build_object('status','running')
     from public.agent_tasks where task_id='terminal-task'),
    120
  )
$q$, '40001');

-- Other owners/non-owners see no claimable rows from this owner scope.
set local request.jwt.claim.sub = '00000000-0000-0000-0000-000000000002';
select pg_temp.assert_true(
  public.agent_claim_next_task('worker-other-owner',120) is null,
  'other owner cannot claim first owner tasks'
);
set local request.jwt.claim.sub = '00000000-0000-0000-0000-000000000003';
select pg_temp.assert_true(
  public.agent_claim_next_task('worker-non-owner',120) is null,
  'non-owner cannot see claimable owner tasks through RLS'
);

-- Anonymous role has no execute grant on queue coordination functions.
set local role anon;
select pg_temp.expect_error($q$
  select public.agent_claim_next_task('worker-anon',120)
$q$, '42501');
reset role;
