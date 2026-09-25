-- DESIGN ONLY / NOT DEPLOYED. Apply after the v1 design in an isolated test DB.
-- This is a checkpoint store, NOT a distributed worker claim/lease implementation.
-- The wrapper deliberately prevents persistent changes when run as written.
begin;

alter table public.agent_tasks
  add column revision bigint not null default 0 check (revision >= 0),
  add column spec_fingerprint text not null
    check (spec_fingerprint ~ '^sha256-v1:[0-9a-f]{64}$');

-- New grants are explicit rather than depending on project default privileges.
revoke all on public.agent_tasks, public.agent_task_events from public, anon, authenticated;
grant select, insert, update on public.agent_tasks to authenticated;
grant select, insert on public.agent_task_events to authenticated;
grant usage on sequence public.agent_task_events_event_id_seq to authenticated;

create function public.agent_checkpoint_guard()
returns trigger language plpgsql security invoker set search_path = '' as $$
begin
  if new.state->>'task_id' is distinct from new.task_id
     or new.spec->>'task_id' is distinct from new.task_id
     or new.state->>'schema_version' is distinct from 'agent-task-state-v1'
     or new.spec->>'schema_version' is distinct from 'agent-task-v1'
     or new.state->>'spec_fingerprint' is distinct from new.spec_fingerprint
     or new.state->>'status' is distinct from
        (case when new.status = 'queued' then 'pending' else new.status end) then
    raise exception 'checkpoint_identity_or_status_mismatch' using errcode = '23514';
  end if;
  if tg_op = 'INSERT' then
    if new.revision <> 0 or new.status <> 'queued' then
      raise exception 'checkpoint_must_start_queued_at_zero' using errcode = '23514';
    end if;
    new.created_at := pg_catalog.clock_timestamp();
  else
    if new.user_id is distinct from old.user_id
       or new.task_id is distinct from old.task_id
       or new.idempotency_key is distinct from old.idempotency_key
       or new.spec is distinct from old.spec
       or new.spec_fingerprint is distinct from old.spec_fingerprint
       or new.schema_version is distinct from old.schema_version
       or new.created_at is distinct from old.created_at then
      raise exception 'checkpoint_definition_immutable' using errcode = '23514';
    end if;
    if new.revision <> old.revision + 1 then
      raise exception 'checkpoint_revision_must_increment' using errcode = '23514';
    end if;
    if old.status = 'completed' then
      raise exception 'completed_checkpoint_immutable' using errcode = '23514';
    end if;
  end if;
  new.updated_at := pg_catalog.clock_timestamp();
  return new;
end;
$$;

create trigger agent_checkpoint_guard before insert or update on public.agent_tasks
for each row execute function public.agent_checkpoint_guard();

create function public.agent_checkpoint_event()
returns trigger language plpgsql security invoker set search_path = '' as $$
begin
  insert into public.agent_task_events(user_id, task_id, event_type, payload)
  values (new.user_id, new.task_id, 'checkpoint_saved',
          pg_catalog.jsonb_build_object('revision', new.revision, 'status', new.status));
  return new;
end;
$$;

create trigger agent_checkpoint_event after insert or update on public.agent_tasks
for each row execute function public.agent_checkpoint_event();

-- Caller identity always comes from auth.uid(); there is no caller-supplied owner.
-- Compare-and-swap is one UPDATE, so a stale writer cannot overwrite a newer state.
create function public.agent_save_checkpoint(
  p_task_id text, p_expected_revision bigint, p_status text, p_state jsonb
) returns bigint language plpgsql security invoker set search_path = '' as $$
declare v_revision bigint;
begin
  if p_expected_revision is null or p_expected_revision < 0 then
    raise exception 'expected_revision_required' using errcode = '22023';
  end if;
  update public.agent_tasks
    set state = p_state, status = p_status, revision = revision + 1
    where user_id = (select auth.uid()) and task_id = p_task_id
      and revision = p_expected_revision
    returning revision into v_revision;
  if not found then
    raise exception 'checkpoint_conflict_or_not_accessible' using errcode = '40001';
  end if;
  return v_revision;
end;
$$;

revoke all on function public.agent_checkpoint_guard() from public, anon, authenticated;
revoke all on function public.agent_checkpoint_event() from public, anon, authenticated;
revoke all on function public.agent_save_checkpoint(text, bigint, text, jsonb)
  from public, anon, authenticated;
grant execute on function public.agent_save_checkpoint(text, bigint, text, jsonb) to authenticated;

rollback;
