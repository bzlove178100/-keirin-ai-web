# Work status

Updated: 2026-09-26 (Asia/Tokyo).

## Product direction

`AI_AGENT_REQUIREMENTS.md` is authoritative. The target is a broad autonomous AI agent for research, text/image/video/code generation, learning/evaluation, task execution, recovery and reporting. Keirin AI is the first major execution target, not the only scope.

## Fixed safety state

Keep these unchanged unless the user explicitly authorizes the specific boundary:

- hosted task execution: **OFF**;
- production prediction: **OFF**;
- keirin prediction DB writes: **OFF**;
- automatic external keirin race-data fetching: **OFF**;
- provider generation/write bindings: **unbound**;
- report delivery / live 21:00 scheduling: **OFF / unconfigured**.

Agent-only checkpoint/activity persistence and queue coordination in staging are authorized and active. `race_predictions` remained **0 rows** at the last direct staging check.

## Keirin prospective evaluation

- Owner-only dry-run remains the validation path.
- Unknown odds are not invented.
- Probabilities remain uncalibrated for monetary EV / production promotion.
- First eligible new prospective history: 2026-09-24 Ito Onsen 1R, 7 riders, all 210 model probabilities, 72 confirmed pre-race trifecta odds, valid chronology and supervised-training eligibility.
- Real prospective collection remains 1 distinct eligible prediction time. Four more distinct times are required to reach the evaluator's five-time technical minimum; boundary purging can require more. Five is not evidence of accuracy or profitability.

## Shared autonomous-agent milestones

Key merged milestones:

- PR #32–#37: broad goal, `TaskSpec`, durable state, activity ledger, permission model, reconciliation, runtime bridge, provider-neutral read-only adapters and report contracts.
- PR #40: verified GitHub read-only provider path.
- PR #45–#47: queue planning, interruption safety, locking and immutable TaskSpec fingerprint binding.
- PR #52 / #54: owner-only hosted checkpoint persistence and strict `HostedCheckpointClient`.
- PR #56: owner-only append/read activity persistence and strict `HostedActivityClient`.
- PR #57 (`6600d8174bc52f6dd3937e8f5a4acccd05871261`): crash-safe queue lease/fencing, bounded attempts, strict `HostedQueueClient`, explicit expired-lease reconciliation and PostgreSQL 17 fencing tests.
- PR #58 (`e21dca79a08e21b12979cf886fceaf3c69c33763`): fail-closed `HostedWorkerCoordinator` with no provider execution.
- PR #59 (`783997d8788810ea405db04e4e72da14ea9a2980`): explicitly gated `HostedReadOnlyWorker` / `HostedLeaseStateStore`; execution denied by default before queue claim.
- PR #60 (`b110f5bf890d6e6dad2dfc64497167177cf7f89b`): credential-isolated `SupabaseEdgeTransport` and activation checklist.
- PR #62 (`5bc2b67576db2a9e24970d55e678ebf2ce0410de`): SHA-pinned repository/file/CI observation and same-SHA verification.
- PR #63 (`d1d670d54624754b59634348c6d9d44c120995ee`): closed-by-default hosted repository composition, durable observation/verification evidence, trusted TaskSpec scope, lease fencing around provider reads and non-retry `HostedRunInterrupted` semantics.
- PR #64 (`71babd01734554bb7aae00295dabbbd1ec292399`): read-only interruption recovery inspection and hard wall-clock deadline enforcement. Recovery reads durable checkpoint/fence + activity evidence without claim/save/requeue; expired running work is never treated as safe replay. All four PR workflow families passed before merge after one test-only patch-target correction.

## Hosted staging/runtime state

Authorized staging project: `keirin-ai-staging` (`omamgmyyqnawlagbemcm`).

Applied agent migrations include checkpoint activation, RLS/CAS optimization, append-only activity events and queue lease/fencing. Current coordination includes owner-scoped `agent_tasks` / `agent_task_events`, immutable TaskSpec identity, revision CAS, FIFO `FOR UPDATE SKIP LOCKED` claim, attempt budget, lease owner/generation/expiry, fenced saves and explicit expired-lease reconcile-to-blocked. No always-on worker is active.

`supabase/functions/agent-runtime-dev` was last read back as version **6 / ACTIVE**, `verify_jwt=true`, service `v6-owner-queue-lease-fencing`, with checkpoint create/get/list/save, activity append/list and queue claim/save/reconcile-expired. Its safety contract still reports `runtime_task_execution_enabled=false`.

A real owner-authenticated hosted worker execution has not been used as proof of completion. Do not mark it verified until a separately authorized bounded live run is actually performed.

## PR #65 proposal-only recovery + closed activation manifest

Branch: `agent-recovery-proposal-manifest-v1-20260926`.

Implemented:

- `HostedRecoveryProposal`: a non-mutating recommendation object. `automatic_execution_allowed` is always false.
- `HostedRecoveryInspector.propose(spec)`: performs a stable double read of checkpoint/fence + current evidence. If the durable snapshot changes between reads, it fails closed with `recovery_snapshot_changed`.
- Expired running work can produce an exact `reconcile_expired_to_blocked` proposal containing expected revision, lease generation and a TaskSpec-bound blocked state. The helper **does not call** the reconciliation RPC.
- Active running leases propose `do_not_touch`.
- Completed checkpoints propose `no_reexecution`.
- Blocked/failed/prior-attempt states propose explicit manual reconciliation/review.
- Only truly queued/unstarted work can be labeled `eligible_for_first_execution`, and that still does not authorize execution.
- Added committed manifest `agent_core/examples/hosted_readonly_single_run_activation.json` with `activation_enabled=false`, single-run mode, exactly one task, no scheduler/recurrence, read-only access, exact repository, exact trusted TaskSpec fingerprint, exact `github.read_main` + `github.verify_ci` actions and only `contents:read` / `actions:read` GitHub permissions.
- Manifest validation rejects activation=true, write/execute access, extra actions/permissions, repository/task/fingerprint mismatch, scheduling/recurrence, more than one task or any safety flag being enabled.
- The committed manifest's `live_execution_authorized` property is always false; repository configuration is not accepted as the user's live authorization signal.

Validation before this status update:

- proposal-only recovery tests: passed;
- activation manifest tests: passed;
- full `keirin-ai regression`: passed;
- collection progress UI regression: passed;
- agent runtime read-only smoke: passed;
- PostgreSQL checkpoint contract: passed;
- no live queue claim/reconciliation/execution, Supabase deployment, permission change or scheduler activation was performed.

## Current agent state

The project now has a generic task/runtime core, durable owner-only checkpoint/activity storage, crash-safe queue/fencing, strict hosted clients, credential-isolated Edge transport, SHA-pinned repository/CI observation, durable provider evidence, read-only recovery inspection, proposal-only recovery decisions, hard run deadline preparation and a closed single-run activation manifest.

It is still **not** an always-on self-contained autonomous agent. No live scheduler/worker service is active and live execution authorization remains false.

## Next boundary / next action

After PR #65 is merged, code-only preparation is sufficient for the first bounded repository/CI worker trial. The next meaningful boundary is **actual hosted read-only execution authorization**.

Before crossing it:

1. re-read current main and deployed runtime safety state;
2. ensure the committed activation manifest still validates against the exact trusted TaskSpec;
3. use only one task / one worker / one bounded run, with no recurrence;
4. keep GitHub access read-only and all keirin/report/provider-write safety flags OFF;
5. after the run, stop and inspect durable checkpoint/fence/evidence with `HostedRecoveryInspector` before considering any further execution.

Do not set `execution_authorized=true`, claim a real task, enable a scheduler or perform provider execution until the user explicitly authorizes this separate live read-only boundary.

No race screenshots or credential resend is needed for remaining code/status verification.

## 21:00 report requirement

The product requirement remains daily 21:00 Asia/Tokyo reporting of daily sales, monthly sales and activity (executed work, results, failures/incomplete work, next actions). Sales source, accounting rules and delivery destination remain unresolved. Missing sales values must never be shown as zero. Live report delivery/scheduling remains disabled.

## Constraints

Do not commit private race histories, prediction snapshots, model artifacts, credentials, private file identifiers or personal data. Prefer current `main`, current CI, deployed function metadata and direct staging checks over older handoff notes.
