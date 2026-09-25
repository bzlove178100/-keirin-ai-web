-- Authorized staging activation: dedicated agent task checkpoints only.
-- Applied to keirin-ai-staging as migration 20260925103650.
-- Derived from the PostgreSQL-tested v1/v2 designs; no prediction writes.

create table if not exists public.agent_tasks (
  user_id uuid not null references auth.users(id) on delete cascade,
  task_id text not null,
  schema_version text not null default 'agent-task-state-v1',
  status text not null default 'queued',
  idempotency_key text not null,
  spec jsonb not null,
  state jsonb not null,
  blocked_reason text,
  last_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (user_id, task_id),
  unique (user_id, idempotency_key),
  constraint agent_tasks_task_id_format
    check (task_id ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$'),
  constraint agent_tasks_status_valid
    check (status in ('queued', 'running', 'blocked', 'completed', 'failed')),
  constraint agent_tasks_spec_is_object
    check (jsonb_typeof(spec) = 'object'),
  constraint agent_tasks_state_is_object
    check (jsonb_typeof(state) = 'object')
);

create table if not exists public.agent_task_events (
  event_id bigint generated always as identity primary key,
  user_id uuid not null,
  task_id text not null,
  event_type text not null,
  step_id text,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint agent_task_events_task_fk
    foreign key (user_id, task_id)
    references public.agent_tasks(user_id, task_id)
    on delete cascade,
  constraint agent_task_events_event_type_nonempty
    check (length(btrim(event_type)) > 0),
  constraint agent_task_events_payload_is_object
    check (jsonb_typeof(payload) = 'object')
);

create index if not exists agent_tasks_user_status_updated_idx
  on public.agent_tasks(user_id, status, updated_at desc);

create index if not exists agent_task_events_task_created_idx
  on public.agent_task_events(user_id, task_id, created_at, event_id);

alter table public.agent_tasks enable row level security;
alter table public.agent_task_events enable row level security;

create policy agent_tasks_owner_select
  on public.agent_tasks for select to authenticated
  using (
    user_id = auth.uid()
    and exists (
      select 1 from public.user_profiles p
      where p.user_id = auth.uid() and p.role = 'owner' and p.plan = 'owner'
    )
  );

create policy agent_tasks_owner_insert
  on public.agent_tasks for insert to authenticated
  with check (
    user_id = auth.uid()
    and exists (
      select 1 from public.user_profiles p
      where p.user_id = auth.uid() and p.role = 'owner' and p.plan = 'owner'
    )
  );

create policy agent_tasks_owner_update
  on public.agent_tasks for update to authenticated
  using (
    user_id = auth.uid()
    and exists (
      select 1 from public.user_profiles p
      where p.user_id = auth.uid() and p.role = 'owner' and p.plan = 'owner'
    )
  )
  with check (
    user_id = auth.uid()
    and exists (
      select 1 from public.user_profiles p
      where p.user_id = auth.uid() and p.role = 'owner' and p.plan = 'owner'
    )
  );

create policy agent_task_events_owner_select
  on public.agent_task_events for select to authenticated
  using (
    user_id = auth.uid()
    and exists (
      select 1 from public.user_profiles p
      where p.user_id = auth.uid() and p.role = 'owner' and p.plan = 'owner'
    )
  );

create policy agent_task_events_owner_insert
  on public.agent_task_events for insert to authenticated
  with check (
    user_id = auth.uid()
    and exists (
      select 1 from public.user_profiles p
      where p.user_id = auth.uid() and p.role = 'owner' and p.plan = 'owner'
    )
  );

alter table public.agent_tasks
  add column revision bigint not null default 0 check (revision >= 0),
  add column spec_fingerprint text not null
    check (spec_fingerprint ~ '^sha256-v1:[0-9a-f]{64}$');

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
