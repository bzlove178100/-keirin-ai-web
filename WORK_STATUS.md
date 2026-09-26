# Work status

Updated: 2026-09-26 (Asia/Tokyo).

## Product direction

`AI_AGENT_REQUIREMENTS.md` is the authoritative shared goal. The target is a broad autonomous AI agent for research, text/image/video/code generation, learning/evaluation, task execution, recovery and reporting. Keirin AI remains the first major execution target, not the only product scope.

## Keirin AI / prospective evaluation

Verified current state:

- Production prediction: **OFF**.
- Keirin development prediction DB writes: **OFF**.
- Automatic external keirin race-data fetching: **OFF**.
- Owner-only dry-run remains the validation path.
- Unknown odds are not invented.
- Probabilities remain uncalibrated for monetary EV / production promotion.
- First new prospective real-race history is 2026-09-24 Ito Onsen 1R: 7 riders, 210 model probabilities, 72 confirmed pre-race trifecta odds, valid pre-result chronology and supervised-training eligibility.
- Real prospective collection remains 1 eligible distinct prediction time. Four more distinct eligible times are required to reach the evaluator's five-time technical minimum; boundary purging can require more. Five is not evidence of accuracy or profitability.
- Two older history variants without `training_input` are not eligible for the current paired evaluation.

## Shared autonomous-agent foundation

Key merged milestones:

- PR #32: broad autonomous-agent goal made authoritative.
- PR #33: `TaskSpec`, durable task-state model, activity ledger, allowed-action gates, idempotency keys, verification hooks and artifact lifecycle separation.
- PR #35: explicit reconciliation, capability/permission metadata, orchestration preflight, read-only GitHub adapter contract and Asia/Tokyo reporting contracts. Missing revenue stays `unknown/unavailable`, never silently zero.
- PR #37: credential-free runtime binding manifests, provider-neutral bridge, read-only Supabase/file adapter contracts, CLI/runtime utilities and report-delivery separation.
- PR #40: verified live GitHub read-only provider path using ephemeral GitHub Actions credentials.
- PR #45–#47: queue planning, interruption safety, local task locking and immutable full-TaskSpec fingerprint binding.
- PR #52: authorized owner-only hosted checkpoint persistence in staging.
- PR #54: strict provider-neutral `HostedCheckpointClient`.
- PR #56 (`94c98cb10cc7324dbcd16dae1cdb9f35ef7c4e45`): owner-only append/read activity persistence and strict `HostedActivityClient`.
- PR #57 (`6600d8174bc52f6dd3937e8f5a4acccd05871261`): crash-safe queue lease/fencing, bounded attempts, strict `HostedQueueClient`, explicit expired-lease reconciliation and PostgreSQL 17 fencing tests.
- PR #58 (`e21dca79a08e21b12979cf886fceaf3c69c33763`): fail-closed `HostedWorkerCoordinator`; queue claims can be preflighted and durably released as blocked without invoking provider actions.
- PR #59 (`783997d8788810ea405db04e4e72da14ea9a2980`, merged; all four PR workflows passed) prepares an explicitly gated `HostedReadOnlyWorker` and `HostedLeaseStateStore`. The default is execution denied before queue claim. When enabled only in an explicitly authorized host, all task actions/verifiers must be registered `read` capabilities and every AgentRunner state transition is persisted through queue revision-CAS/fencing. CI tests use fake/injected actions only; this is preparation, not live activation.

- PR #60 (`b110f5bf890d6e6dad2dfc64497167177cf7f89b`) merged credential-isolated `SupabaseEdgeTransport`, package exports, the activation checklist, and transport regression CI. HTTP errors cannot override failure status; redirects are rejected; credential echoes and unsafe error propagation are blocked; ambiguous POSTs are not automatically retried.

## 2026-09-26 verified handoff checkpoint

- Read current GitHub main, PR #59, the existing transport branch and its full diff before editing. Starting main matched `783997d8788810ea405db04e4e72da14ea9a2980`; the transport branch was four commits ahead with no divergence and no existing PR.
- PR #60 head `65c69cc28237c3d40cc8e5e1cac41d9070f73589`: all four PR workflows passed. Regression run `36209262808` explicitly executed and passed the new transport test step. The other successful runs were `36209262849` (UI), `36209262788` (PostgreSQL), and `36209262848` (read-only smoke).
- Local checks: transport 11 tests, queue 7, activity 6, checkpoint 7, read-only worker 5, web/safety regression and diff whitespace validation all passed.
- GitHub main was read back at PR #60 merge `b110f5bf890d6e6dad2dfc64497167177cf7f89b`. This is the verified code baseline for this documentation update, not a claim that future main commits have the same SHA.
- Supabase `agent-runtime-dev` was independently read back at version 6 / ACTIVE / `verify_jwt=true`; deployed source retains `v6-owner-queue-lease-fencing`, agent-only persistence/queue ON and execution/prediction/auto-fetch OFF. Direct SQL confirmed `race_predictions=0`.
- No Supabase deployment/migration, live hosted queue execution, credential provisioning, GitHub permission change or report scheduling was performed.
- `HOSTED_READONLY_BINDING_DESIGN.md` now specifies the concrete composition, exact task/repository boundary, missing SHA-pinned CI verification, lease timing and injected integration acceptance tests. This is reviewed design preparation, not an implemented or live-tested binding.

## SHA-pinned GitHub binding preparation (2026-09-26)

- Added `tools/agent_github_sha_bridge.py` with `ShaPinnedGitHubReadOnlyBridge`, scoped to this repository and the three existing requirement/status files.
- Resolves main once and fetches all files at that full SHA; validates file type, UTF-8/base64 content, size and Git blob identity.
- Verifies the four reviewed workflow IDs and paths using same-SHA main push runs, bounded complete pagination and latest run/attempt selection. Pending, failed, missing or mismatched evidence cannot pass. Rechecks main and returns `main_changed` instead of mixing commits.
- Verification consumes the action result's serializable observation, including with a fresh bridge instance. The existing AgentRunner wiring was tested with this binding. Persisting that observation for hosted interruption/reconciliation is still pending; this is not claimed as durable evidence storage.
- The strict bridge refuses redirects and sanitizes provider failures/credential echoes. It adds no provider permission or live workflow binding.
- Local validation: 15 strict-bridge tests, 4 legacy GitHub bridge tests, 8 runtime-bridge tests, web/safety regression and diff whitespace checks passed. The new tests are included in regression CI; PR check results are the authoritative merge gate.
- Development-only live public GitHub GET validation also passed: all three files and all four required main push workflows matched `90e42ad4ebe843dd6b6a54017afa3297fa3713fa`; the final main read matched. No owner token, Supabase call or hosted queue execution was used for this check.
- The legacy read-only smoke bridge is deliberately not replaced in this slice: its in-workflow check cannot require its own still-running workflow. Its older CI selection is not used as evidence that the new hosted path has passed. Hosted composition must bind the strict class.
- Deployed runtime source was read back with service v6 and execution/prediction/auto-fetch flags still false. No deployment, migration, queue claim or live hosted execution occurred.

## Hosted repository composition preparation (2026-09-26)

- Reconfirmed main at PR #62 merge `5bc2b67576db2a9e24970d55e678ebf2ce0410de` and its four passing PR workflows before this slice. Deployed runtime source still reports service v6 and execution OFF.
- `tools/agent_hosted_repository_worker.py` now composes SupabaseEdgeTransport, HostedQueueClient, HostedActivityClient, the strict SHA bridge and HostedReadOnlyWorker. Construction and the default run gate perform zero provider/Edge I/O.
- The complete claimed TaskSpec must match the trusted repository template fingerprint. Prior attempts/completed steps are blocked for explicit reconciliation; scope mismatch never invokes GitHub. A local nonblocking lock prevents concurrent reuse of one worker object; database lease/fencing remains the cross-process protection.
- The observation is appended to the existing agent activity ledger before CI verification. Verification evidence (including a negative result) is also appended before task completion. Both carry TaskSpec fingerprint, lease generation and revision. No DB schema change is needed.
- Fenced saves surround GitHub reads and evidence acknowledgement. Current lease budget must exceed 30 seconds, and the run has an elapsed-time guard of 180 seconds. HTTP operations retain the existing 20-second socket timeout. This is a cooperative budget check, **not a hard process wall-clock cancellation guarantee**; an indefinitely slow response is a remaining live-host concern.
- `HostedRunInterrupted` deliberately bypasses the runner's automatic Exception retry loop. An ambiguous save/append stops without a compensating POST or provider replay. The durable attempts/evidence remain available for explicit inspection/reconciliation. The host must not automatically restart this signal.
- Persistence and completion are separate: activity append and queue CAS are not one atomic transaction. Events are evidence tied to a fence, not proof that the final queue transition succeeded. A completed checkpoint with a missing final activity acknowledgement must be inspected, not re-executed.
- Validation: 13 injected full-composition tests passed (including actual Edge transport serialization and real queue/activity clients), plus read-only worker 5, queue client 7, strict SHA bridge 15, runner interruption 5 and web/safety regression. No live hosted task, owner token or real agent-persistence write was used.
- This change does not activate execution, deploy Supabase, alter permissions, schedule reports, or enable prediction writes/production/auto-fetch.

## Hosted persistence and queue state

The user explicitly authorized **AI-agent-only task/activity persistence in staging**. That authorization does not extend to keirin prediction writes, production prediction, automatic race-data fetching, provider writes/generation, hosted task execution or report delivery.

Applied `keirin-ai-staging` migrations:

- `20260925103650_agent_runtime_checkpoints_activation`
- `20260925110207_agent_runtime_checkpoint_rpc_and_rls_optimization`
- `20260925115914_agent_runtime_activity_event_rpc`
- `20260925122122_agent_runtime_queue_lease`

Verified storage/coordination:

- `public.agent_tasks` and `public.agent_task_events` are owner-scoped through RLS.
- Checkpoint create/save uses immutable TaskSpec identity plus revision CAS.
- Activity events are append-only for the owner path.
- Queue metadata tracks not-before time, attempt budget, lease owner/generation/expiry.
- `agent_claim_next_task(...)` uses atomic FIFO `FOR UPDATE SKIP LOCKED`.
- `agent_save_leased_checkpoint(...)` rejects stale revision/worker/generation and expired leases.
- `agent_reconcile_expired_lease(...)` blocks ambiguous expired work instead of silently retrying/requeueing it.
- Staging exposes all six queue metadata columns and all three queue RPCs.
- `race_predictions` remains at **0 rows**.
- No always-on worker is active.

Security advisor findings remain existing/unrelated items: `race_predictions` has RLS with no policy, and leaked-password protection is disabled. The performance advisor still reports the pre-existing `user_profiles_select_own` auth init-plan warning. Newly created queue indexes may appear unused before worker load; that is not evidence they should be removed.

## Hosted runtime

`supabase/functions/agent-runtime-dev` is owner-only and uses `verify_jwt=true`.

Current deployed/read-back state:

- Edge Function: **version 6 / ACTIVE**.
- Service contract: `v6-owner-queue-lease-fencing`.
- Checkpoint modes: create/get/list/save.
- Activity modes: append/list.
- Queue modes: claim/save/reconcile-expired.
- Queue RPC responses are read back from durable state before success is returned.
- Queue responses still report `executed:false`.

Safety state remains:

- agent checkpoint/activity persistence: **ON, agent-only**;
- queue coordination: **ON, agent-only**;
- hosted task execution: **OFF**;
- production prediction: **OFF**;
- keirin prediction DB writes: **OFF**;
- automatic external keirin race-data fetching: **OFF**;
- external provider generation/write bindings: **unbound**;
- report delivery: **OFF / unconfigured**.

A real browser-owner-JWT request through the deployed Edge Function has not yet been performed in this chat. Do not mark that specific browser-to-Edge path verified until it is actually tested.

## Validation

CI covers shared agent safety/recovery, immutable task identity, orchestration/reporting, queue planning, hosted checkpoint/activity/queue clients, migration safety, PostgreSQL 17 queue fencing/crash cases, runtime bridge/delivery, live GitHub read-only host behavior, Web/prospective/ML regression, Phase32/training-input contracts and hosted runtime type/contract checks.

PR #58 added tests proving the coordinator never executes provider actions and fails closed on missing/forbidden capabilities or persistence failures.

PR #59 adds tests proving:

- hosted read-only execution is denied **before queue claim** unless explicitly authorized by the host;
- authorized fake read-only action + verifier can complete through durable fenced state transitions;
- write/execute or missing actions are blocked without invocation;
- a read-only adapter cannot silently report artifact creation/persistent/device/UI writes as success.

## Current agent state

The project has a tested generic task/runtime core, safe resume/reconciliation, durable owner-only checkpoint/activity storage, crash-safe queue lease/fencing, strict hosted persistence clients, deployed v6 coordination runtime, a verified GitHub read-only provider path, a fail-closed worker coordinator and broad provider-neutral capability contracts.

It is still **not** an always-on self-contained autonomous agent. `agent-runtime-dev` does not execute tasks, and no scheduler/worker service is active.

Remaining major boundaries:

1. prepare read-only recovery inspection and hard deadline enforcement for the tested, unactivated hosted composition;
2. separately authorize and configure any live hosted task execution before setting an execution host to enabled;
3. test a real authenticated owner browser-to-Edge flow without storing the user's token;
4. connect additional safe read-only Supabase/files/Web provider bindings where host authorization exists;
5. text/image/video/code generation providers remain unbound;
6. sales source, accounting rules and report destination are unresolved;
7. 21:00 report generation/delivery remains unscheduled.

## Next action

The closed-by-default composition is now implemented and tested with injected Edge/GitHub responses. Next add a read-only recovery inspector that compares checkpoint/fence identity and observation/verification events, distinguishing missing acknowledgements, expired running work and completed work without executing or requeueing it. Address hard request/run deadline enforcement before any live host is activated.

Keep live `execution_authorized=False`, the Edge execution flag OFF and all keirin/report safety conditions unchanged. Actual owner-authenticated Edge-to-worker execution remains untested and requires the user's separate authorization plus a configured host/session. No screenshot or token resend is needed for the next code-only step.

## 21:00 report requirement

The product requirement remains daily 21:00 Asia/Tokyo reporting of daily sales, monthly sales and an activity report covering executed work, results, failures/incomplete work and next actions.

Sales source, accounting rules and delivery destination are still unresolved. Missing sales values must not be shown as zero. Report delivery/scheduling stays disabled until those inputs are defined.

## Constraints

Do not commit private race histories, prediction snapshots, model artifacts, credentials, private file identifiers or personal data. Prefer current `main`, current CI, deployed function metadata and direct staging checks over older handoff notes.
