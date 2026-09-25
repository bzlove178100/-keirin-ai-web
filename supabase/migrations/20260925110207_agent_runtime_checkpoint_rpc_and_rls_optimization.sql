-- Authorized staging follow-up for agent-only persistence.
-- Applied to keirin-ai-staging as migration 20260925110207.
-- Adds an owner-scoped create RPC, preserves CAS saves, and removes per-row auth.uid()
-- evaluation from the agent-table RLS policies. No keirin prediction table is changed.

create or replace function public.agent_create_checkpoint(
  p_task_id text,
  p_idempotency_key text,
  p_spec jsonb,
  p_state jsonb,
  p_spec_fingerprint text
) returns jsonb language plpgsql security invoker set search_path = '' as $$
declare
  v_user_id uuid := (select auth.uid());
  v_row public.agent_tasks%rowtype;
begin
  if v_user_id is null then
    raise exception 'authenticated_user_required' using errcode = '28000';
  end if;
  insert into public.agent_tasks(user_id, task_id, idempotency_key, spec, state, spec_fingerprint)
  values (v_user_id, p_task_id, p_idempotency_key, p_spec, p_state, p_spec_fingerprint)
  returning * into v_row;
  return pg_catalog.to_jsonb(v_row);
end;
$$;

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
    returning revision into v_revision;
  if not found then
    raise exception 'checkpoint_conflict_or_not_accessible' using errcode = '40001';
  end if;
  return v_revision;
end;
$$;

revoke all on function public.agent_create_checkpoint(text,text,jsonb,jsonb,text)
  from public, anon, authenticated;
grant execute on function public.agent_create_checkpoint(text,text,jsonb,jsonb,text)
  to authenticated;
revoke all on function public.agent_save_checkpoint(text,bigint,text,jsonb)
  from public, anon, authenticated;
grant execute on function public.agent_save_checkpoint(text,bigint,text,jsonb)
  to authenticated;

drop policy agent_tasks_owner_select on public.agent_tasks;
drop policy agent_tasks_owner_insert on public.agent_tasks;
drop policy agent_tasks_owner_update on public.agent_tasks;
drop policy agent_task_events_owner_select on public.agent_task_events;
drop policy agent_task_events_owner_insert on public.agent_task_events;

create policy agent_tasks_owner_select on public.agent_tasks for select to authenticated using (
  user_id = (select auth.uid()) and exists (
    select 1 from public.user_profiles p
    where p.user_id = (select auth.uid()) and p.role='owner' and p.plan='owner'
  )
);

create policy agent_tasks_owner_insert on public.agent_tasks for insert to authenticated with check (
  user_id = (select auth.uid()) and exists (
    select 1 from public.user_profiles p
    where p.user_id = (select auth.uid()) and p.role='owner' and p.plan='owner'
  )
);

create policy agent_tasks_owner_update on public.agent_tasks for update to authenticated using (
  user_id = (select auth.uid()) and exists (
    select 1 from public.user_profiles p
    where p.user_id = (select auth.uid()) and p.role='owner' and p.plan='owner'
  )
) with check (
  user_id = (select auth.uid()) and exists (
    select 1 from public.user_profiles p
    where p.user_id = (select auth.uid()) and p.role='owner' and p.plan='owner'
  )
);

create policy agent_task_events_owner_select on public.agent_task_events for select to authenticated using (
  user_id = (select auth.uid()) and exists (
    select 1 from public.user_profiles p
    where p.user_id = (select auth.uid()) and p.role='owner' and p.plan='owner'
  )
);

create policy agent_task_events_owner_insert on public.agent_task_events for insert to authenticated with check (
  user_id = (select auth.uid()) and exists (
    select 1 from public.user_profiles p
    where p.user_id = (select auth.uid()) and p.role='owner' and p.plan='owner'
  )
);
