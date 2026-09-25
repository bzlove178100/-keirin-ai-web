# Hosted queue / worker contract

Status: pure planner implemented and locally testable; hosted worker **not active**.

`agent_core.queue_planner.plan_queue` accepts an owner-scoped snapshot and an
explicit timezone-aware clock. It returns deterministic FIFO claim proposals,
wait decisions and reconciliation requirements. It performs no I/O, claims,
DB writes, provider calls or task execution. A proposal is not authorization.

## State mapping and recovery

Hosted `queued` maps to local runner `pending` only after a future atomic claim.
The local runner and reconciliation now share a nonblocking POSIX per-task file
lock. This protects callers using the same state directory on one supported host,
not independent hosts or distributed filesystems. Raw state-store writes remain
low-level operations and must not be used concurrently outside that lock.
An interrupted attempted step without saved completion blocks before any further
tool call, including when the step was marked retry-safe. Explicit reconciliation
is required. Already completed steps and unstarted next steps can still resume.
This local protection does not replace a hosted atomic claim/lease mechanism.
Completed, blocked and failed tasks are never automatically enqueued again.
Running tasks with missing/expired leases require explicit reconciliation of
external effects; lease expiry alone is not evidence that a tool did nothing.
Running tasks continue to consume capacity until reconciliation commits.
Queued tasks with exhausted attempt budgets require reconciliation as well.

`attempts`/`max_attempts` in this contract count worker claims, separately from
per-step attempt budgets in TaskState. An authorized requeue must retain both
budgets and completed-step evidence; it must never manufacture a fresh task ID
to evade retry limits. Future dates wait; equal timestamps sort by task ID.
Mixed owners, duplicate task IDs/idempotency keys and invalid input are rejected.

## Required future persistence extension (not applied)

The rollback-only v1 state schema does not yet contain the planner's revision,
not-before timestamp, worker attempt budget or lease fields. Do not fabricate
defaults from existing rows and call them safe to execute. A reviewed future
migration and adapter must add explicit values, immutable task-spec checks and
lease fencing before this contract can control a hosted queue.

The host must establish owner identity from authenticated authorization, not
from a user-supplied `owner_id`. RLS remains necessary even though the planner
rejects mixed-owner snapshots.

## Future worker lifecycle

1. Read an authenticated owner's queue snapshot and plan a bounded batch.
2. In one transaction, recheck owner, queued status, expected revision,
   not-before, attempt budget and per-owner capacity; acquire a lease with a new
   fencing token, increment attempts/revision, and append the claim event.
   Use a per-owner transactional lock or equivalent serialization so workers
   cannot each claim different rows and exceed the same owner's capacity.
3. Only the successful claimant may perform capability authorization/preflight.
   Missing capabilities block before any provider operation.
4. Verify immutable TaskSpec and resume existing completed-step evidence through
   the shared runtime. Use stable task/step idempotency keys, not lease IDs.
5. Renew the lease and condition every checkpoint/completion on the current
   fencing token. A stale worker cannot persist completion. Provider operations
   also need idempotency/reconciliation: database fencing alone cannot undo an
   already-dispatched external side effect.
6. Commit outcome and append-only event together. On unknown outcome, block for
   reconciliation; never infer success or blindly retry after a timeout.

Before activation, test competing claims, owner isolation, worker crashes before
and after external effects, stale completions, lease renewal, bounded retries,
atomic event/state commits and resume without repeating completed steps.

No cron, daemon, hosted persistence or credential store is enabled by this change.
The 21:00 Asia/Tokyo reporting contract stays disabled pending its data source and
destination. Keirin prediction, DB writing and automatic race-data fetching
settings remain unchanged.
