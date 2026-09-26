# Work status

Updated: 2026-09-26 (Asia/Tokyo).

## Product direction

`AI_AGENT_REQUIREMENTS.md` is authoritative. The target is a broad autonomous AI agent for research, text/image/video/code generation, learning/evaluation, task execution, recovery and reporting. Keirin AI is the first major execution target, not the only scope.

## Fixed safety state

Unless the user explicitly authorizes a new, specific boundary:

- deployed hosted runtime task execution: **OFF**;
- production prediction: **OFF**;
- keirin prediction DB writes: **OFF**;
- automatic external keirin race-data fetching: **OFF**;
- provider generation/write bindings: **unbound**;
- report delivery / live 21:00 scheduling: **OFF / unconfigured**.

Agent-only checkpoint/activity persistence and queue coordination in staging are authorized and active. After the first bounded read-only integration trial, `race_predictions` was directly rechecked at **0 rows**.

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
- PR #57 (`6600d8174bc52f6dd3937e8f5a4acccd05871261`): crash-safe queue lease/fencing, bounded attempts, strict `HostedQueueClient`, explicit expired-lease reconciliation and PostgreSQL fencing tests.
- PR #58 (`e21dca79a08e21b12979cf886fceaf3c69c33763`): fail-closed `HostedWorkerCoordinator` with no provider execution.
- PR #59 (`783997d8788810ea405db04e4e72da14ea9a2980`): explicitly gated `HostedReadOnlyWorker` / `HostedLeaseStateStore`; execution denied by default before queue claim.
- PR #60 (`b110f5bf890d6e6dad2dfc64497167177cf7f89b`): credential-isolated `SupabaseEdgeTransport` and activation checklist.
- PR #62 (`5bc2b67576db2a9e24970d55e678ebf2ce0410de`): SHA-pinned repository/file/CI observation and same-SHA verification.
- PR #63 (`d1d670d54624754b59634348c6d9d44c120995ee`): closed-by-default hosted repository composition, durable observation/verification evidence, trusted TaskSpec scope, lease fencing around provider reads and non-retry interruption semantics.
- PR #64 (`71babd01734554bb7aae00295dabbbd1ec292399`): read-only interruption recovery inspection and hard wall-clock deadline enforcement.
- PR #65 (`826e59163280f1f461f58f9c8a8a5a5dc6bbc34d`): proposal-only recovery decisions and a committed closed single-run activation manifest. The manifest remains `activation_enabled=false`, one task maximum, no scheduler/recurrence, exact trusted repository/task/actions and read-only GitHub permissions.

## Hosted staging/runtime state

Authorized staging project: `keirin-ai-staging` (`omamgmyyqnawlagbemcm`).

Current durable coordination includes owner-scoped `agent_tasks` / `agent_task_events`, immutable TaskSpec identity, revision CAS, FIFO claim, attempt budget, lease owner/generation/expiry, fenced saves and explicit expired-lease reconcile-to-blocked. No always-on worker is active.

`supabase/functions/agent-runtime-dev` was re-read immediately before the first bounded trial as version **6 / ACTIVE**, `verify_jwt=true`, service `v6-owner-queue-lease-fencing`. Its contract still reported `runtime_task_execution_enabled=false`; production prediction, prediction DB writes and automatic external fetch remained disabled.

## First bounded live read-only integration trial

The user explicitly authorized exactly one live read-only trial. That authorization has been **consumed** and is not permission for another run or recurrence.

Trusted task:

- task id: `keirin-readonly-status-check`;
- fingerprint: `sha256-v1:f9af0209ae2545d096d9c04cf4cfe5d434b90407bfc6aaa73ca0c6445d749403`;
- actions: `github.read_main`, `github.verify_ci` only;
- repository: `bzlove178100/-keirin-ai-web`;
- one worker / one claim / no recurrence.

Durable staging result:

- final status `completed`;
- revision `6`;
- attempt count `1 / 1`;
- lease generation `1`;
- lease owner and expiry cleared on completion;
- completed step `read-current-state`;
- `last_error=null`, `blocked_reason=null`;
- append-only ledger contains claim, task/step start, fenced saves, GitHub observation, GitHub verification, step verification/completion, lease release and task completion.

Pinned GitHub observation:

- observed/final `main`: `826e59163280f1f461f58f9c8a8a5a5dc6bbc34d`;
- `AI_AGENT_REQUIREMENTS.md`: blob `55aee582794dee98be821812f39121e73d3efa18`, 6393 bytes;
- `AGENTS.md`: blob `be0b87cdd8c5cc562d68469d72af17c08989158e`, 5959 bytes;
- `WORK_STATUS.md`: blob `f38da208c8ee3337020af47aa955db35e31e13f6`, 8893 bytes.

Same-SHA `main` push CI was verified `completed / success` for all four required workflows:

- regression: run `36212528769`;
- collection progress UI regression: run `36212528579`;
- PostgreSQL checkpoint contract: run `36212528834`;
- agent runtime read-only smoke: run `36212528642`.

The durable `github_verification` evidence records `verified=true`, and the final main re-read matched the observed SHA. Post-run `race_predictions` remained 0.

### What this trial proves

It proves real GitHub read-only provider access, pinned requirement/status file reads, same-SHA CI verification, real staging queue/checkpoint/activity persistence, one bounded claim/completion/lease release and durable post-run evidence.

### What this trial does not prove

The run was orchestrated through the connected ChatGPT GitHub and Supabase control surfaces. It therefore does **not** prove that deployed `agent-runtime-dev` independently executed the Python worker from an owner browser/session, and it does not prove an always-on autonomous host, scheduler, recurrence, generation-provider execution or report delivery.

The completed trusted task must not be automatically replayed. Its durable state corresponds to `completed_verified_no_reexecution`.

## PR #66 — standalone one-shot host preparation

Branch: `record-live-readonly-trial-20260926`.

This branch records the live trial in `LIVE_READONLY_TRIAL_20260926.md` and prepares a standalone fail-closed one-shot host path without performing another live run.

Current implementation:

- `agent_core/single_run_host.py` contains the provider-neutral one-shot host contract.
- `tools/run_hosted_repository_once.py` is a thin CLI wrapper.
- execution requires both `--execute-once` and runtime-only `KEIRIN_AGENT_SINGLE_RUN_AUTHORIZED=true`;
- runtime credentials are read from environment only and omitted from output;
- the committed closed activation manifest is validated before an authorized worker is constructed;
- exactly one `run_next` call is permitted by the entrypoint;
- after normal completion it performs read-only recovery inspection before exit;
- `HostedRunInterrupted` is a stop signal: inspect durable state and exit, never retry automatically;
- scheduler and recurrence remain absent.

Regression coverage verifies the runtime authorization gate, closed manifest, one-shot construction, secret redaction and interruption-to-inspection behavior.

## Current agent state

The project now has a generic task/runtime core, durable owner-only checkpoint/activity storage, crash-safe queue/fencing, strict hosted clients, credential-isolated Edge transport, SHA-pinned repository/CI observation, durable provider evidence, recovery inspection/proposals, hard deadline enforcement, a closed single-run manifest, one completed bounded integration trial and a standalone one-shot host entrypoint under CI review.

It is still **not** an always-on self-contained autonomous agent. No scheduler/recurrence is active and the deployed Edge runtime still reports task execution OFF.

## Next action / next boundary

1. finish PR #66 CI and merge only after required workflows pass;
2. do **not** perform another live task run under the already-consumed authorization;
3. next design a safe unique run-instance/enqueue contract, because the exact trusted task id is now completed and must not be silently reused;
4. only after that code/test preparation, request a new explicit authorization before another live hosted execution;
5. keep generation providers, recurring scheduler, prediction writes, race-data auto-fetch and report delivery as separate later boundaries.

No race screenshots, owner token or credential resend is needed for the current code-only work.

## 21:00 report requirement

The product requirement remains daily 21:00 Asia/Tokyo reporting of daily sales, monthly sales and activity (executed work, results, failures/incomplete work, next actions). Sales source, accounting rules and delivery destination remain unresolved. Missing sales values must never be shown as zero. Live report delivery/scheduling remains disabled.

## Constraints

Do not commit private race histories, prediction snapshots, model artifacts, credentials, private file identifiers or personal data. Prefer current `main`, current CI, deployed function metadata and direct staging checks over older handoff notes.
