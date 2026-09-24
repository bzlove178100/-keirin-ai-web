-- Hosted autonomous-agent durable state schema (DESIGN ONLY / NOT DEPLOYED)
--
-- This file is intentionally stored outside supabase/migrations so repository tooling
-- cannot apply it as an ordinary migration by accident. Applying it would introduce
-- new database writes for the agent runtime and therefore requires an explicit later
-- authorization. Existing keirin prediction/database-write settings are unchanged.

begin;

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

-- Direct client access is restricted to the authenticated owner profile and the
-- caller's own rows. The hosted runtime should continue to verify owner status before
-- issuing any future write. No service-role bypass is part of this design.
create policy agent_tasks_owner_select
  on public.agent_tasks
  for select
  to authenticated
  using (
    user_id = auth.uid()
    and exists (
      select 1
      from public.user_profiles p
      where p.user_id = auth.uid()
        and p.role = 'owner'
        and p.plan = 'owner'
    )
  );

create policy agent_tasks_owner_insert
  on public.agent_tasks
  for insert
  to authenticated
  with check (
    user_id = auth.uid()
    and exists (
      select 1
      from public.user_profiles p
      where p.user_id = auth.uid()
        and p.role = 'owner'
        and p.plan = 'owner'
    )
  );

create policy agent_tasks_owner_update
  on public.agent_tasks
  for update
  to authenticated
  using (
    user_id = auth.uid()
    and exists (
      select 1
      from public.user_profiles p
      where p.user_id = auth.uid()
        and p.role = 'owner'
        and p.plan = 'owner'
    )
  )
  with check (
    user_id = auth.uid()
    and exists (
      select 1
      from public.user_profiles p
      where p.user_id = auth.uid()
        and p.role = 'owner'
        and p.plan = 'owner'
    )
  );

create policy agent_task_events_owner_select
  on public.agent_task_events
  for select
  to authenticated
  using (
    user_id = auth.uid()
    and exists (
      select 1
      from public.user_profiles p
      where p.user_id = auth.uid()
        and p.role = 'owner'
        and p.plan = 'owner'
    )
  );

create policy agent_task_events_owner_insert
  on public.agent_task_events
  for insert
  to authenticated
  with check (
    user_id = auth.uid()
    and exists (
      select 1
      from public.user_profiles p
      where p.user_id = auth.uid()
        and p.role = 'owner'
        and p.plan = 'owner'
    )
  );

-- Event rows are append-only in v1: no UPDATE or DELETE policies are defined.
-- Task DELETE is also intentionally omitted from direct-client policies. Retention or
-- administrative cleanup requires a separate, explicit design decision.

rollback;
