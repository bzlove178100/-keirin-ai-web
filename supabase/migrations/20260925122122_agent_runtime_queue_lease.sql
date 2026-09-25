-- Authorized staging scope: AI-agent-only queue coordination and crash-safe leases.
-- This migration does not enable hosted task execution, provider writes, keirin
-- prediction writes, or automatic external race-data fetching.

alter table public.agent_tasks
  add column not_before timestamptz not null default now(),
  add column attempt_count integer not null default 0,
  add column max_attempts integer not null default 1,
  add column lease_owner text,
  add column lease_generation bigint not null default 0,
  add column lease_expires_at timestamptz,
  add constraint agent_tasks_attempt_count_nonnegative check (attempt_count >= 0),
  add constraint agent_tasks_max_attempts_positive check (max_attempts >= 1),
  add constraint agent_tasks_attempt_budget_valid check (attempt_count <= max_attempts),
  add constraint agent_tasks_lease_generation_nonnegative check (lease_generation >= 0),
  add constraint agent_tasks_lease_pair check (
    (lease_owner is null and lease_expires_at is null)
    or (lease_owner is not null and lease_expires_at is not null)
  ),
  add constraint agent_tasks_lease_owner_format check (
    lease_owner is null or lease_owner ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'
  ),
  add constraint agent_tasks_lease_requires_running check (
    lease_owner is null or status = 'running'
  );

create index agent_tasks_queue_due_idx
  on public.agent_tasks(user_id, status, not_before, created_at, task_id)
  where status = 'queued';

create index agent_tasks_running_lease_idx
  on public.agent_tasks(user_id, status, lease_expires_at, task_id)
  where status = 'running';

-- General checkpoint saves must not bypass an active worker fence. Legacy/unleased
-- checkpoints continue to use this path; leased tasks use agent_save_leased_checkpoint.
create or replace function public.agent_save_checkpoint(
  p_task_id text, p_expected_revision bigint, p_status text, p_state jsonb
) returns bigint language plpgsql security invoker set search_path = '' as $$
declare v_revision bigint;
begin
  if p_expected_revision is null or p_expected_revision < 0 then
    raise exception 'expected_revision_required' using errcode = '22023';
  end if;
  update public.agent_tasks
    set state = p_state,
        status = p_status,
        blocked_reason = nullif(p_state->>'blocked_reason',''),
        last_error = nullif(p_state->>'last_error',''),
        revision = revision + 1
    where user_id = (select auth.uid()) and task_id = p_task_id
      and revision = p_expected_revision
      and lease_owner is null
    returning revision into v_revision;
  if not found then
    raise exception 'checkpoint_conflict_or_not_accessible' using errcode = '40001';
  end if;
  return v_revision;
end;
$$;

create or replace function public.agent_claim_next_task(
  p_worker_id text,
  p_lease_seconds integer
) returns jsonb language plpgsql security invoker set search_path = '' as $$
declare
  v_user_id uuid := (select auth.uid());
  v_task_id text;
  v_now timestamptz := pg_catalog.clock_timestamp();
  v_row public.agent_tasks%rowtype;
begin
  if v_user_id is null then
    raise exception 'authenticated_user_required' using errcode = '28000';
  end if;
  if p_worker_id is null or p_worker_id !~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$' then
    raise exception 'invalid_worker_id' using errcode = '22023';
  end if;
  if p_lease_seconds is null or p_lease_seconds < 15 or p_lease_seconds > 3600 then
    raise exception 'invalid_lease_seconds' using errcode = '22023';
  end if;

  select t.task_id into v_task_id
  from public.agent_tasks t
  where t.user_id = v_user_id
    and t.status = 'queued'
    and t.not_before <= v_now
    and t.attempt_count < t.max_attempts
  order by t.created_at, t.task_id
  for update skip locked
  limit 1;

  if not found then
    return null;
  end if;

  update public.agent_tasks
    set state = state || pg_catalog.jsonb_build_object(
          'status', 'running',
          'blocked_reason', null,
          'last_error', null
        ),
        status = 'running',
        blocked_reason = null,
        last_error = null,
        revision = revision + 1,
        attempt_count = attempt_count + 1,
        lease_owner = p_worker_id,
        lease_generation = lease_generation + 1,
        lease_expires_at = v_now + pg_catalog.make_interval(secs => p_lease_seconds)
    where user_id = v_user_id and task_id = v_task_id
    returning * into v_row;

  insert into public.agent_task_events(user_id, task_id, event_type, payload)
  values (
    v_user_id,
    v_row.task_id,
    'lease_claimed',
    pg_catalog.jsonb_build_object(
      'worker_id', v_row.lease_owner,
      'lease_generation', v_row.lease_generation,
      'revision', v_row.revision,
      'attempt_count', v_row.attempt_count,
      'lease_expires_at', v_row.lease_expires_at
    )
  );

  return pg_catalog.to_jsonb(v_row);
end;
$$;

create or replace function public.agent_save_leased_checkpoint(
  p_task_id text,
  p_expected_revision bigint,
  p_worker_id text,
  p_lease_generation bigint,
  p_status text,
  p_state jsonb,
  p_lease_seconds integer
) returns jsonb language plpgsql security invoker set search_path = '' as $$
declare
  v_user_id uuid := (select auth.uid());
  v_now timestamptz := pg_catalog.clock_timestamp();
  v_row public.agent_tasks%rowtype;
begin
  if v_user_id is null then
    raise exception 'authenticated_user_required' using errcode = '28000';
  end if;
  if p_task_id is null or p_task_id !~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$' then
    raise exception 'invalid_task_id' using errcode = '22023';
  end if;
  if p_expected_revision is null or p_expected_revision < 0 then
    raise exception 'expected_revision_required' using errcode = '22023';
  end if;
  if p_worker_id is null or p_worker_id !~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$' then
    raise exception 'invalid_worker_id' using errcode = '22023';
  end if;
  if p_lease_generation is null or p_lease_generation < 1 then
    raise exception 'invalid_lease_generation' using errcode = '22023';
  end if;
  if p_status not in ('running','blocked','completed','failed') then
    raise exception 'invalid_leased_checkpoint_status' using errcode = '22023';
  end if;
  if p_state is null or pg_catalog.jsonb_typeof(p_state) <> 'object' then
    raise exception 'state_must_be_object' using errcode = '22023';
  end if;
  if p_lease_seconds is null or p_lease_seconds < 15 or p_lease_seconds > 3600 then
    raise exception 'invalid_lease_seconds' using errcode = '22023';
  end if;

  update public.agent_tasks
    set state = p_state,
        status = p_status,
        blocked_reason = nullif(p_state->>'blocked_reason',''),
        last_error = nullif(p_state->>'last_error',''),
        revision = revision + 1,
        lease_owner = case when p_status = 'running' then lease_owner else null end,
        lease_expires_at = case
          when p_status = 'running'
            then v_now + pg_catalog.make_interval(secs => p_lease_seconds)
          else null
        end
    where user_id = v_user_id
      and task_id = p_task_id
      and revision = p_expected_revision
      and status = 'running'
      and lease_owner = p_worker_id
      and lease_generation = p_lease_generation
      and lease_expires_at > v_now
    returning * into v_row;

  if not found then
    raise exception 'lease_conflict_or_expired' using errcode = '40001';
  end if;

  insert into public.agent_task_events(user_id, task_id, event_type, payload)
  values (
    v_user_id,
    v_row.task_id,
    case when p_status = 'running' then 'lease_checkpoint_saved' else 'lease_released' end,
    pg_catalog.jsonb_build_object(
      'worker_id', p_worker_id,
      'lease_generation', p_lease_generation,
      'revision', v_row.revision,
      'status', v_row.status,
      'lease_expires_at', v_row.lease_expires_at
    )
  );

  return pg_catalog.to_jsonb(v_row);
end;
$$;

-- Expired running work is ambiguous. This owner-only reconciliation primitive never
-- requeues it automatically; it moves the task to blocked and clears the stale lease.
create or replace function public.agent_reconcile_expired_lease(
  p_task_id text,
  p_expected_revision bigint,
  p_lease_generation bigint,
  p_state jsonb
) returns jsonb language plpgsql security invoker set search_path = '' as $$
declare
  v_user_id uuid := (select auth.uid());
  v_now timestamptz := pg_catalog.clock_timestamp();
  v_reason text;
  v_state jsonb;
  v_worker_id text;
  v_row public.agent_tasks%rowtype;
begin
  if v_user_id is null then
    raise exception 'authenticated_user_required' using errcode = '28000';
  end if;
  if p_task_id is null or p_task_id !~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$' then
    raise exception 'invalid_task_id' using errcode = '22023';
  end if;
  if p_expected_revision is null or p_expected_revision < 0 then
    raise exception 'expected_revision_required' using errcode = '22023';
  end if;
  if p_lease_generation is null or p_lease_generation < 1 then
    raise exception 'invalid_lease_generation' using errcode = '22023';
  end if;
  if p_state is null or pg_catalog.jsonb_typeof(p_state) <> 'object'
     or p_state->>'status' is distinct from 'blocked' then
    raise exception 'blocked_state_required' using errcode = '22023';
  end if;

  v_reason := coalesce(
    nullif(p_state->>'blocked_reason',''),
    'expired_lease_requires_reconciliation'
  );
  v_state := p_state || pg_catalog.jsonb_build_object('blocked_reason', v_reason);

  select lease_owner into v_worker_id
  from public.agent_tasks
  where user_id = v_user_id
    and task_id = p_task_id
    and revision = p_expected_revision
    and status = 'running'
    and lease_generation = p_lease_generation
    and lease_owner is not null
    and lease_expires_at <= v_now
  for update;

  if not found then
    raise exception 'expired_lease_conflict_or_not_accessible' using errcode = '40001';
  end if;

  update public.agent_tasks
    set state = v_state,
        status = 'blocked',
        blocked_reason = v_reason,
        last_error = nullif(v_state->>'last_error',''),
        revision = revision + 1,
        lease_owner = null,
        lease_expires_at = null
    where user_id = v_user_id
      and task_id = p_task_id
      and revision = p_expected_revision
      and status = 'running'
      and lease_generation = p_lease_generation
    returning * into v_row;

  insert into public.agent_task_events(user_id, task_id, event_type, payload)
  values (
    v_user_id,
    v_row.task_id,
    'lease_expiry_reconciled',
    pg_catalog.jsonb_build_object(
      'previous_worker_id', v_worker_id,
      'lease_generation', p_lease_generation,
      'revision', v_row.revision,
      'status', v_row.status,
      'blocked_reason', v_reason
    )
  );

  return pg_catalog.to_jsonb(v_row);
end;
$$;

revoke all on function public.agent_claim_next_task(text,integer)
  from public, anon, authenticated;
grant execute on function public.agent_claim_next_task(text,integer)
  to authenticated;

revoke all on function public.agent_save_leased_checkpoint(text,bigint,text,bigint,text,jsonb,integer)
  from public, anon, authenticated;
grant execute on function public.agent_save_leased_checkpoint(text,bigint,text,bigint,text,jsonb,integer)
  to authenticated;

revoke all on function public.agent_reconcile_expired_lease(text,bigint,bigint,jsonb)
  from public, anon, authenticated;
grant execute on function public.agent_reconcile_expired_lease(text,bigint,bigint,jsonb)
  to authenticated;
