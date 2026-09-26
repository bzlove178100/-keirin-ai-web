-- Preparation-only migration for exact-task queue claims.
-- Applying this migration does not enable hosted task execution, provider writes,
-- keirin prediction writes, production prediction, or automatic race-data fetching.
-- It only adds a narrowly targeted lease-acquisition primitive so a bounded host does
-- not consume an unrelated FIFO task before validating its trusted identity.

create or replace function public.agent_claim_task(
  p_task_id text,
  p_worker_id text,
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
  if p_worker_id is null or p_worker_id !~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$' then
    raise exception 'invalid_worker_id' using errcode = '22023';
  end if;
  if p_lease_seconds is null or p_lease_seconds < 15 or p_lease_seconds > 3600 then
    raise exception 'invalid_lease_seconds' using errcode = '22023';
  end if;

  select t.* into v_row
  from public.agent_tasks t
  where t.user_id = v_user_id
    and t.task_id = p_task_id
    and t.status = 'queued'
    and t.not_before <= v_now
    and t.attempt_count < t.max_attempts
  for update;

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
    where user_id = v_user_id
      and task_id = p_task_id
      and status = 'queued'
      and revision = v_row.revision
      and attempt_count = v_row.attempt_count
      and attempt_count < max_attempts
      and not_before <= v_now
    returning * into v_row;

  if not found then
    raise exception 'exact_task_claim_conflict' using errcode = '40001';
  end if;

  insert into public.agent_task_events(user_id, task_id, event_type, payload)
  values (
    v_user_id,
    v_row.task_id,
    'lease_claimed',
    pg_catalog.jsonb_build_object(
      'claim_mode', 'exact_task',
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

revoke all on function public.agent_claim_task(text,text,integer)
  from public, anon, authenticated;
grant execute on function public.agent_claim_task(text,text,integer)
  to authenticated;
