# Hosted recovery inspection

This document describes the non-mutating recovery step after an interrupted hosted repository/CI run.

The recovery inspector reads only:

- the exact TaskSpec-bound durable checkpoint/queue row;
- append-only activity events for the same task.

It does **not** claim, save, reconcile, requeue or execute a task.

## Classification rules

- `queued_unstarted`: no prior attempt/evidence; this is the only classification that may be treated as not yet executed.
- `running_active_do_not_touch`: lease is still active; do not reclaim or retry.
- `running_expired_with_verified_evidence`: provider read + verification evidence exist but the durable task is still running; explicit expired-lease reconciliation is required, never provider replay.
- `running_expired_with_observation_only`: a repository observation was persisted but verification/final transition is uncertain; explicit reconciliation/manual review is required.
- `running_expired_without_provider_evidence`: no provider evidence was found for the current fence, but the attempt was already claimed; do not infer that execution is safe to repeat.
- `completed_verified_no_reexecution`: checkpoint is completed and current-generation verification evidence says verified. Never run again.
- `completed_without_verification_evidence_review`: checkpoint says completed but evidence is incomplete; inspect, do not rerun.
- `blocked_requires_explicit_reconciliation` / `failed_requires_explicit_reconciliation`: terminal recovery states; no automatic retry.

Evidence with a different TaskSpec fingerprint, a future lease generation, a revision ahead of the durable checkpoint or malformed verification result fails closed as an integrity error.

## Expired lease handling

`may_reconcile_expired_to_blocked=true` is only a statement that the existing explicit expired-lease reconciliation RPC is structurally applicable. The inspector itself never calls that RPC.

Reconciliation is not a retry signal. It converts ambiguous expired running work to a durable blocked state so a later human/authorized process can decide what happened.

## Hard deadline

The prepared hosted repository worker now uses a POSIX real-time interval timer around an explicitly authorized run. Live execution fails closed when this hard timer is unavailable or already in use. The existing cooperative lease/time checks and per-request socket timeout remain in place as additional guards.

This still does not activate hosted execution. `execution_authorized` remains false by default and the deployed Edge runtime continues to report task execution disabled.
