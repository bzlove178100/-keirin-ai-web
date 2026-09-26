# Work status

Updated: 2026-09-26 (Asia/Tokyo).

## Product direction

`AI_AGENT_REQUIREMENTS.md` is the authoritative goal. The target is a broad autonomous AI agent for research, text/image/video/code generation, learning/evaluation, task execution, recovery and reporting. Keirin AI is the first major execution target, not the only scope.

## Fixed safety state

Keep these unchanged unless the user explicitly authorizes the specific boundary:

- hosted task execution: **OFF**;
- production prediction: **OFF**;
- keirin prediction DB writes: **OFF**;
- automatic external keirin race-data fetching: **OFF**;
- provider generation/write bindings: **unbound**;
- report delivery / 21:00 live scheduling: **OFF / unconfigured**.

Agent-only checkpoint/activity persistence and queue coordination in staging are authorized and active. `race_predictions` remains at **0 rows** in the last direct staging check.

## Keirin prospective evaluation

- Owner-only dry-run remains the validation path.
- Unknown odds are not invented.
- Probabilities remain uncalibrated for monetary EV / production promotion.
- First eligible new prospective real-race history: 2026-09-24 Ito Onsen 1R, 7 riders, 210 model probabilities, 72 confirmed pre-race trifecta odds, valid pre-result chronology and supervised-training eligibility.
- Real prospective collection remains 1 distinct eligible prediction time; four more distinct times are required to reach the evaluator's five-time technical minimum. Boundary purging can require more. Five is not evidence of accuracy or profitability.

## Shared autonomous-agent milestones

Important merged milestones:

- PR #32–#37: broad goal, `TaskSpec`, durable state, activity ledger, capability/permission model, reconciliation, runtime bridge, read-only provider contracts and reporting contracts.
- PR #40: verified GitHub read-only provider path.
- PR #45–#47: queue planning, interruption safety, task locking and immutable full-TaskSpec fingerprint binding.
- PR #52 / #54: owner-only hosted checkpoint persistence and strict `HostedCheckpointClient`.
- PR #56: owner-only append/read activity persistence and strict `HostedActivityClient`.
- PR #57 (`6600d8174bc52f6dd3937e8f5a4acccd05871261`): crash-safe queue lease/fencing, bounded attempts, strict `HostedQueueClient`, explicit expired-lease reconciliation and PostgreSQL 17 fencing tests.
- PR #58 (`e21dca79a08e21b12979cf886fceaf3c69c33763`): fail-closed `HostedWorkerCoordinator`; provider actions are not invoked.
- PR #59 (`783997d8788810ea405db04e4e72da14ea9a2980`): explicitly gated `HostedReadOnlyWorker` / `HostedLeaseStateStore`; default execution authorization is false.
- PR #60 (`b110f5bf890d6e6dad2dfc64497167177cf7f89b`): credential-isolated `SupabaseEdgeTransport` and activation checklist.
- PR #62 (`5bc2b67576db2a9e24970d55e678ebf2ce0410de`): strict SHA-pinned repository/file/CI observation and same-SHA verification.
- PR #63 (`d1d670d54624754b59634348c6d9d44c120995ee`): closed-by-default hosted repository composition with durable GitHub observation/verification evidence, exact trusted TaskSpec validation, lease fencing around provider reads and non-retry `HostedRunInterrupted` semantics.

## Hosted persistence / queue state

Authorized staging project: `keirin-ai-staging` (`omamgmyyqnawlagbemcm`).

Applied agent migrations include:

- `20260925103650_agent_runtime_checkpoints_activation`
- `20260925110207_agent_runtime_checkpoint_rpc_and_rls_optimization`
- `20260925115914_agent_runtime_activity_event_rpc`
- `20260925122122_agent_runtime_queue_lease`

Verified coordination includes:

- owner-scoped `public.agent_tasks` and `public.agent_task_events`;
- immutable TaskSpec fingerprint and revision CAS;
- append-only activity events;
- not-before time, attempt budget and lease owner/generation/expiry;
- FIFO `agent_claim_next_task(...)` with `FOR UPDATE SKIP LOCKED`;
- fenced `agent_save_leased_checkpoint(...)`;
- `agent_reconcile_expired_lease(...)` that converts ambiguous expired work to blocked instead of silently retrying it;
- no always-on worker.

## Hosted runtime

`supabase/functions/agent-runtime-dev` was last read back as:

- version **6 / ACTIVE**;
- `verify_jwt=true`;
- service contract `v6-owner-queue-lease-fencing`;
- checkpoint create/get/list/save;
- activity append/list;
- queue claim/save/reconcile-expired;
- `runtime_task_execution_enabled=false`.

A real user-owner browser/session request through the deployed Edge Function has not been used as proof of live worker execution. Do not mark that path verified until it is actually performed.

## PR #64 recovery/deadline slice

PR #64 prepares the next recovery boundary without activating live execution.

Implemented on branch `agent-recovery-deadline-v1-20260926`:

- `HostedQueueClient.inspect(spec)` reads the exact durable checkpoint/queue row through `checkpoint_get` without claim/save/requeue.
- `HostedRecoveryInspector` reads checkpoint/fence identity plus append-only activity evidence and performs **no mutation**.
- Recovery distinguishes:
  - truly unstarted queued work;
  - active running lease (`do not touch`);
  - expired running work with verified evidence;
  - expired running work with observation only;
  - expired running work without provider evidence;
  - completed work with/without verification evidence;
  - blocked/failed work requiring explicit reconciliation.
- Current-generation evidence must match TaskSpec fingerprint, lease generation and checkpoint revision constraints; future-generation or malformed evidence fails closed.
- Only an expired running lease is marked structurally eligible for the existing explicit reconcile-to-blocked RPC. Inspection itself never calls that RPC and never treats reconciliation as a retry signal.
- `hard_run_deadline()` adds a POSIX wall-clock timer around an explicitly authorized hosted repository run. Live execution fails closed if the hard timer cannot be provided or an existing process timer would be overwritten. Cooperative lease checks and per-request socket timeouts remain additional guards.
- The default authorization gate remains zero-I/O and false before queue claim.
- `tools/prepare_hosted_recovery.py` constructs the recovery inspector without network I/O; actual reads start only when `inspect(spec)` is called.

Validation on the corrected PR #64 head before this status update:

- read-only recovery classification tests: passed;
- recovery factory zero-I/O construction: passed;
- hard-deadline tests: passed;
- existing hosted repository composition, SHA bridge, queue/activity/checkpoint, worker, transport, Web/ML and Deno contract tests: passed in the regression workflow;
- all four PR workflow families reached success on head `19158b1fa80628d80df09cd1aa69e382db6b88a7` before this documentation-only update.

The first PR #64 regression attempt failed only because the new factory test patched an obsolete transport symbol (`urlopen`). The factory was changed to accept an injected requester and the test now verifies zero calls; the corrected run passed. This was a test defect, not a hosted persistence or production failure.

## Current agent state

The project now has:

- generic task/runtime core;
- immutable task identity and explicit permissions;
- durable owner-only checkpoint/activity storage;
- crash-safe queue/fencing and bounded attempts;
- strict hosted clients and credential-isolated Edge transport;
- SHA-pinned repository/CI observation;
- closed-by-default hosted repository composition;
- durable observation/verification evidence;
- read-only interruption recovery inspection;
- prepared hard run deadline enforcement.

It is still **not** an always-on self-contained autonomous agent. No live scheduler/worker service is active and live execution authorization remains false.

## Next action

After PR #64 is merged:

1. prepare a **read-only recovery decision helper** that can propose (not automatically execute) the exact reconciliation action for an expired running lease;
2. add a single-run host activation manifest/checklist binding the exact repository/CI task, owner Edge transport and GitHub read-only bridge while keeping `execution_authorized=false` by default;
3. before any live run, require a separate explicit authorization for hosted read-only execution;
4. perform one bounded single-run validation only after that authorization, then stop and inspect evidence before considering recurrence;
5. keep scheduler/always-on execution, provider generation, prediction writes, race-data auto-fetch and report delivery as separate later authorization/configuration boundaries.

No race screenshots, owner token or credential resend is needed for the next code-only step.

## 21:00 report requirement

The product requirement remains daily 21:00 Asia/Tokyo reporting of daily sales, monthly sales and activity (executed work, results, failures/incomplete work, next actions).

Sales source, accounting rules and delivery destination remain unresolved. Missing sales values must never be shown as zero. Live report delivery/scheduling remains disabled.

## Constraints

Do not commit private race histories, prediction snapshots, model artifacts, credentials, private file identifiers or personal data. Prefer current `main`, current CI, deployed function metadata and direct staging checks over older handoff notes.
