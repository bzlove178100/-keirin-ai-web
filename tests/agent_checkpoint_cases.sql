set local role authenticated;
set local request.jwt.claim.sub = '00000000-0000-0000-0000-000000000001';
insert into public.agent_tasks(user_id, task_id, idempotency_key, spec, state, spec_fingerprint)
values (auth.uid(), 'ci-task', 'ci-key',
  '{"schema_version":"agent-task-v1","task_id":"ci-task"}',
  jsonb_build_object('schema_version','agent-task-state-v1','task_id','ci-task',
                    'status','pending','spec_fingerprint','sha256-v1:' || repeat('a',64)),
  'sha256-v1:' || repeat('a',64));
select pg_temp.assert_true((select count(*) = 1 from public.agent_task_events), 'insert audit');
select pg_temp.expect_error($q$
  insert into public.agent_tasks select * from public.agent_tasks
$q$, '23505');
select pg_temp.expect_error($q$
  update public.agent_tasks set spec = spec || '{"goal":"changed"}', revision=revision+1
$q$, '23514');
select pg_temp.expect_error($q$
  update public.agent_tasks set user_id='00000000-0000-0000-0000-000000000002', revision=revision+1
$q$, '23514');
select pg_temp.expect_error($q$
  update public.agent_tasks set revision=7
$q$, '23514');
select pg_temp.expect_error($q$
  delete from public.agent_task_events
$q$, '42501');
select pg_temp.expect_error($q$
  update public.agent_task_events set event_type='changed'
$q$, '42501');
select pg_temp.expect_error($q$
  delete from public.agent_tasks
$q$, '42501');

select public.agent_save_checkpoint('ci-task',0,'running',
  (select state || '{"status":"running"}' from public.agent_tasks));
select pg_temp.assert_true((select revision=1 from public.agent_tasks), 'revision advanced');
select pg_temp.assert_true((select count(*)=2 from public.agent_task_events), 'update audit');
select pg_temp.expect_error($q$
  select public.agent_save_checkpoint('ci-task',0,'running',(select state from public.agent_tasks))
$q$, '40001');
select pg_temp.assert_true((select count(*)=2 from public.agent_task_events), 'stale write has no event');

-- A second owner cannot read or update the first owner's checkpoint/events.
set local request.jwt.claim.sub = '00000000-0000-0000-0000-000000000002';
select pg_temp.assert_true((select count(*)=0 from public.agent_tasks), 'other owner task hidden');
select pg_temp.assert_true((select count(*)=0 from public.agent_task_events), 'other owner events hidden');
select pg_temp.expect_error($q$
  select public.agent_save_checkpoint('ci-task',1,'running','{}')
$q$, '40001');
set local request.jwt.claim.sub = '00000000-0000-0000-0000-000000000003';
select pg_temp.assert_true((select count(*)=0 from public.agent_tasks), 'non-owner task hidden');
select pg_temp.expect_error($q$
  insert into public.agent_tasks(user_id,task_id,idempotency_key,spec,state,spec_fingerprint)
  values(auth.uid(),'denied','denied','{"schema_version":"agent-task-v1","task_id":"denied"}',
    jsonb_build_object('schema_version','agent-task-state-v1','task_id','denied','status','pending',
                      'spec_fingerprint','sha256-v1:' || repeat('b',64)),
    'sha256-v1:' || repeat('b',64))
$q$, '42501');
set local role anon;
select pg_temp.expect_error('select * from public.agent_tasks', '42501');
select pg_temp.expect_error($q$
  select public.agent_save_checkpoint('ci-task',1,'running','{}')
$q$, '42501');

-- A failed audit insert must roll back the checkpoint update as well.
reset role;
revoke insert on public.agent_task_events from authenticated;
set local role authenticated;
set local request.jwt.claim.sub = '00000000-0000-0000-0000-000000000001';
select pg_temp.expect_error($q$
  select public.agent_save_checkpoint('ci-task',1,'running',(select state from public.agent_tasks))
$q$, '42501');
select pg_temp.assert_true((select revision=1 from public.agent_tasks), 'audit failure rolls back state');
reset role;
grant insert on public.agent_task_events to authenticated;
set local role authenticated;
select public.agent_save_checkpoint('ci-task',1,'completed',
  (select state || '{"status":"completed"}' from public.agent_tasks));
select pg_temp.expect_error($q$
  select public.agent_save_checkpoint('ci-task',2,'running',
    (select state || '{"status":"running"}' from public.agent_tasks))
$q$, '23514');
select pg_temp.assert_true((select revision=2 and status='completed' from public.agent_tasks), 'completed preserved');
select pg_temp.assert_true((select count(*)=3 from public.agent_task_events), 'final audit count');
reset role;
