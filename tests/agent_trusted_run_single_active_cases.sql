-- Synthetic single-active trusted-run guard cases. Outer harness wraps all work in ROLLBACK.
set local role authenticated;
set local request.jwt.claim.sub = '00000000-0000-0000-0000-000000000001';

insert into public.agent_tasks(user_id, task_id, idempotency_key, spec, state, spec_fingerprint)
values (
  auth.uid(),
  'keirin-readonly-status-check.1111111111111111',
  'keirin-readonly-status-check.1111111111111111',
  '{"schema_version":"agent-task-v1","task_id":"keirin-readonly-status-check.1111111111111111"}',
  jsonb_build_object(
    'schema_version','agent-task-state-v1',
    'task_id','keirin-readonly-status-check.1111111111111111',
    'status','pending',
    'spec_fingerprint','sha256-v1:' || repeat('1',64)
  ),
  'sha256-v1:' || repeat('1',64)
);

select pg_temp.expect_error($q$
  insert into public.agent_tasks(user_id, task_id, idempotency_key, spec, state, spec_fingerprint)
  values (
    auth.uid(),
    'keirin-readonly-status-check.2222222222222222',
    'keirin-readonly-status-check.2222222222222222',
    '{"schema_version":"agent-task-v1","task_id":"keirin-readonly-status-check.2222222222222222"}',
    jsonb_build_object(
      'schema_version','agent-task-state-v1',
      'task_id','keirin-readonly-status-check.2222222222222222',
      'status','pending',
      'spec_fingerprint','sha256-v1:' || repeat('2',64)
    ),
    'sha256-v1:' || repeat('2',64)
  )
$q$, '23505');

select public.agent_claim_task(
  'keirin-readonly-status-check.1111111111111111',
  'single-active-worker',
  120
);

select pg_temp.expect_error($q$
  insert into public.agent_tasks(user_id, task_id, idempotency_key, spec, state, spec_fingerprint)
  values (
    auth.uid(),
    'keirin-readonly-status-check.2222222222222222',
    'keirin-readonly-status-check.2222222222222222',
    '{"schema_version":"agent-task-v1","task_id":"keirin-readonly-status-check.2222222222222222"}',
    jsonb_build_object(
      'schema_version','agent-task-state-v1',
      'task_id','keirin-readonly-status-check.2222222222222222',
      'status','pending',
      'spec_fingerprint','sha256-v1:' || repeat('2',64)
    ),
    'sha256-v1:' || repeat('2',64)
  )
$q$, '23505');

select public.agent_save_leased_checkpoint(
  'keirin-readonly-status-check.1111111111111111',
  1,
  'single-active-worker',
  1,
  'completed',
  (select state || jsonb_build_object('status','completed')
   from public.agent_tasks
   where task_id='keirin-readonly-status-check.1111111111111111'),
  120
);

insert into public.agent_tasks(user_id, task_id, idempotency_key, spec, state, spec_fingerprint)
values (
  auth.uid(),
  'keirin-readonly-status-check.2222222222222222',
  'keirin-readonly-status-check.2222222222222222',
  '{"schema_version":"agent-task-v1","task_id":"keirin-readonly-status-check.2222222222222222"}',
  jsonb_build_object(
    'schema_version','agent-task-state-v1',
    'task_id','keirin-readonly-status-check.2222222222222222',
    'status','pending',
    'spec_fingerprint','sha256-v1:' || repeat('2',64)
  ),
  'sha256-v1:' || repeat('2',64)
);

select pg_temp.assert_true(
  (select count(*)=1 from public.agent_tasks
   where user_id=auth.uid()
     and task_id like 'keirin-readonly-status-check.%'
     and status in ('queued','running')),
  'only one active trusted run exists per owner'
);

set local request.jwt.claim.sub = '00000000-0000-0000-0000-000000000002';
insert into public.agent_tasks(user_id, task_id, idempotency_key, spec, state, spec_fingerprint)
values (
  auth.uid(),
  'keirin-readonly-status-check.3333333333333333',
  'keirin-readonly-status-check.3333333333333333',
  '{"schema_version":"agent-task-v1","task_id":"keirin-readonly-status-check.3333333333333333"}',
  jsonb_build_object(
    'schema_version','agent-task-state-v1',
    'task_id','keirin-readonly-status-check.3333333333333333',
    'status','pending',
    'spec_fingerprint','sha256-v1:' || repeat('3',64)
  ),
  'sha256-v1:' || repeat('3',64)
);

select pg_temp.assert_true(
  (select count(*)=1 from public.agent_tasks
   where user_id=auth.uid()
     and task_id like 'keirin-readonly-status-check.%'
     and status in ('queued','running')),
  'guard is owner-scoped rather than global'
);
reset role;
