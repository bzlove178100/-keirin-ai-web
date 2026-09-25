-- Authorized staging scope: AI-agent-only activity persistence.
-- Applied to keirin-ai-staging as migration 20260925115914.
-- This migration adds an owner-derived append RPC for the existing append-only
-- agent_task_events ledger. It does not modify keirin prediction tables or enable
-- hosted task execution/provider writes.

create or replace function public.agent_append_event(
  p_task_id text,
  p_event_type text,
  p_step_id text,
  p_payload jsonb
) returns bigint language plpgsql security invoker set search_path = '' as $$
declare
  v_user_id uuid := (select auth.uid());
  v_event_id bigint;
begin
  if v_user_id is null then
    raise exception 'authenticated_user_required' using errcode = '28000';
  end if;
  if p_task_id is null or p_task_id !~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$' then
    raise exception 'invalid_task_id' using errcode = '22023';
  end if;
  if p_event_type is null or length(btrim(p_event_type)) = 0 or length(p_event_type) > 128 then
    raise exception 'invalid_event_type' using errcode = '22023';
  end if;
  if p_step_id is not null and (length(btrim(p_step_id)) = 0 or length(p_step_id) > 128) then
    raise exception 'invalid_step_id' using errcode = '22023';
  end if;
  if p_payload is null or jsonb_typeof(p_payload) <> 'object' then
    raise exception 'event_payload_must_be_object' using errcode = '22023';
  end if;

  insert into public.agent_task_events(user_id, task_id, event_type, step_id, payload)
  values (v_user_id, p_task_id, btrim(p_event_type), nullif(btrim(p_step_id), ''), p_payload)
  returning event_id into v_event_id;

  return v_event_id;
end;
$$;

revoke all on function public.agent_append_event(text,text,text,jsonb)
  from public, anon, authenticated;
grant execute on function public.agent_append_event(text,text,text,jsonb)
  to authenticated;
