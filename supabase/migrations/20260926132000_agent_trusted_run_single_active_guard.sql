-- Safety guard for the bounded trusted read-only status-run path.
-- At most one fresh trusted status run may be queued or running per owner.
-- This prevents concurrent coordinators from turning one human live-run approval into
-- multiple active run instances. Completed/failed/blocked history remains durable.
-- This migration does not execute tasks, enable schedulers, enable provider writes,
-- change keirin prediction state, or enable external race-data fetching.

create unique index if not exists agent_tasks_one_active_trusted_status_run_per_owner_idx
  on public.agent_tasks(user_id)
  where task_id like 'keirin-readonly-status-check.%'
    and status in ('queued', 'running');
