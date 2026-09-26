# Work status

Updated: 2026-09-26 (Asia/Tokyo).

## Product direction

`AI_AGENT_REQUIREMENTS.md` is authoritative. The target is a broad autonomous AI agent for research, text/image/video/code generation, learning/evaluation, task execution, recovery and reporting. Keirin AI is the first major execution target, not the only scope.

## Fixed safety state

Unless the user explicitly authorizes a new, specific boundary:

- deployed hosted task/provider execution: **OFF**;
- production prediction: **OFF**;
- keirin prediction DB writes: **OFF**;
- automatic external keirin race-data fetching: **OFF**;
- provider generation/write bindings: **unbound**;
- report delivery / live 21:00 scheduling: **OFF / unconfigured**;
- scheduler / recurrence: **OFF**.

Agent-only checkpoint/activity persistence and queue coordination in staging are authorized and active. Exact-task lease acquisition is deployed, but it does not execute a task. `race_predictions` remains **0 rows**.

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
- PR #57 (`6600d8174bc52f6dd3937e8f5a4acccd05871261`): crash-safe queue lease/fencing, bounded attempts, strict queue client and explicit expired-lease reconciliation.
- PR #58–#60: fail-closed worker coordination, explicit execution gate and credential-isolated Supabase Edge transport.
- PR #62–#64: SHA-pinned GitHub observation/CI verification, durable provider evidence, recovery inspection and hard run deadline.
- PR #65 (`826e59163280f1f461f58f9c8a8a5a5dc6bbc34d`): proposal-only recovery decisions and committed closed single-run activation manifest.
- PR #66 (`a76ea6336251348ea165183c904f3a0069fc4824`): records the first bounded read-only integration trial and adds a fail-closed standalone one-shot host entrypoint.
- PR #67 (`6c7802a62909aeaaf288395c39f041237ab6f6f3`): strict trusted run-instance identity contract; fresh run IDs are separate from the completed template task.
- PR #68 (`6bc7585a941751f96ee5557310b7e3181bdd28bb`): exact-task queue-claim RPC/client preparation so a bounded host does not consume an unrelated FIFO task.
- PR #69 (`c1e1386a9260b47f08506f76d357f13487dbb930`): hosted repository worker can be permanently bound to one exact trusted run instance before any claim.
- PR #70 (`8ed4a5d841494b17d90ca2ced44fc34ba2892884`): one-shot CLI requires a fresh instance token and recovery inspection remains bound to the same exact task identity.
- PR #71 (`3bf8e0aa2a8bc22d510f0469c54e841ef4ffed4c`): separate owner-only exact-claim Edge path and credential-isolated routing; exact claim is queue coordination only, not execution.
- PR #72 (`7eff05fe8c7c26dd4933a67d87f17c8829056af4`): idempotent trusted run-instance enqueue preparation. Repeated enqueue is accepted only while the exact immutable instance remains pristine queued/revision-0/pending; consumed instances fail closed. No claim or execution occurs during enqueue.

## Hosted staging/runtime state

Authorized staging project: `keirin-ai-staging` (`omamgmyyqnawlagbemcm`).

Current durable coordination includes owner-scoped `agent_tasks` / `agent_task_events`, immutable TaskSpec identity, revision CAS, FIFO and exact-task claim primitives, attempt budget, lease owner/generation/expiry, fenced saves and explicit expired-lease reconcile-to-blocked. No always-on worker is active.

Deployed functions relevant to the agent:

- `agent-runtime-dev`: **v6 / ACTIVE / verify_jwt=true**. Its safety contract still reports `runtime_task_execution_enabled=false`.
- `agent-exact-claim-dev`: **v1 / ACTIVE / verify_jwt=true**, service `v1-owner-trusted-run-exact-claim`. It accepts only `queue_claim_task` for fresh trusted run-instance IDs and reports task execution, production prediction, prediction DB writes, external race-data fetch, provider generation and report delivery all disabled.

Staging database verification after applying `agent_runtime_exact_task_claim`:

- `public.agent_claim_task(text,text,integer)` exists;
- `authenticated` can execute it;
- `anon` cannot execute it;
- `race_predictions` count remained `0`.

Post-PR #72 staging readback confirmed:

- trusted fresh run-instance rows (`keirin-readonly-status-check.*`): `0`;
- queued trusted run-instance rows: `0`;
- completed template task `keirin-readonly-status-check`: exactly `1`;
- `race_predictions`: `0`.

The exact-claim function source/metadata was read back successfully. No owner-authenticated live exact claim was performed because no new live run is authorized.

## First bounded live read-only integration trial

The user explicitly authorized exactly one live read-only trial. That authorization has been **consumed** and is not permission for another run or recurrence.

Trusted template task `keirin-readonly-status-check` completed once with revision `6`, attempt count `1/1`, lease generation `1`, cleared lease, no error/blocked reason, durable GitHub observation and verification evidence, and no prediction-table writes.

Observed/final GitHub SHA for that trial was `826e59163280f1f461f58f9c8a8a5a5dc6bbc34d`; all four required same-SHA CI workflows were verified successful. The completed template task must never be automatically replayed and corresponds to `completed_verified_no_reexecution`.

The trial proves real GitHub read-only provider access plus real staging queue/checkpoint/activity persistence. It does **not** prove an always-on autonomous host, scheduler/recurrence, generation-provider execution, report delivery, production prediction or prediction DB writes.

## Trusted run-instance enqueue is prepared, not activated

Merged PR #72 adds:

- `TrustedRunEnqueuer.ensure_queued(spec)` with strict trusted-run validation;
- a confirmed-not-found error distinct from duplicate/CAS conflicts;
- task-id idempotency key and revision-0/pending/pristine verification;
- concurrent identical-create re-read with immutable-spec validation;
- fail-closed rejection of running, blocked, failed or completed instances;
- `tools/enqueue_trusted_run_instance.py`, which persists a checkpoint only and never claims or executes it;
- regression coverage proving no `queue_claim*` operation occurs during enqueue.

PR #72 pull-request CI and all four required `main` push workflows completed successfully. The enqueue CLI has **not** been run against staging, so no new live run instance exists.

## Current agent state

The project now has a generic task/runtime core, durable owner-only checkpoint/activity storage, crash-safe queue/fencing, exact task identity/claim support, a safe unique run-instance enqueue path, strict hosted clients, credential-isolated Edge routing, SHA-pinned GitHub/CI observation, durable provider evidence, recovery inspection/proposals, hard deadline enforcement, a closed single-run manifest, one completed bounded live integration trial and a one-shot host path bound to fresh exact run instances.

It is still **not** an always-on self-contained autonomous agent. No scheduler/recurrence is active, provider generation/write bindings remain unbound, and deployed runtime task execution remains OFF.

## Next boundary requiring a new explicit authorization

The safe code-only path is now complete through **fresh instance identity → enqueue → exact claim → bounded worker → recovery inspection**. The next meaningful validation is a second bounded live read-only run using a fresh unique instance.

That next action would create one new queued trusted run instance and then execute exactly one bounded read-only repository/CI worker against it. It must remain one task / one worker / one claim / no recurrence, with GitHub read-only access and all keirin/report/provider-write safety flags OFF.

Do **not** create, claim or execute that fresh live instance until the user explicitly authorizes this new live-run boundary. The previous live-run authorization was consumed.

No race screenshots, owner token or credential resend is needed for the current state.

## 21:00 report requirement

The product requirement remains daily 21:00 Asia/Tokyo reporting of daily sales, monthly sales and activity (executed work, results, failures/incomplete work, next actions). Sales source, accounting rules and delivery destination remain unresolved. Missing sales values must never be shown as zero. Live report delivery/scheduling remains disabled.

## Constraints

Do not commit private race histories, prediction snapshots, model artifacts, credentials, private file identifiers or personal data. Prefer current `main`, current CI, deployed function metadata and direct staging checks over older handoff notes.
