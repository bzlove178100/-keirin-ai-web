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

Agent-only checkpoint/activity persistence and queue coordination in staging are authorized and active. Exact-task lease acquisition is deployed. `race_predictions` remains **0 rows**.

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
- PR #66 (`a76ea6336251348ea165183c904f3a0069fc4824`): first bounded read-only integration trial record plus fail-closed standalone one-shot host entrypoint.
- PR #67 (`6c7802a62909aeaaf288395c39f041237ab6f6f3`): strict trusted run-instance identity contract.
- PR #68 (`6bc7585a941751f96ee5557310b7e3181bdd28bb`): exact-task queue-claim RPC/client preparation.
- PR #69 (`c1e1386a9260b47f08506f76d357f13487dbb930`): hosted repository worker permanently bindable to one exact trusted run instance.
- PR #70 (`8ed4a5d841494b17d90ca2ced44fc34ba2892884`): one-shot CLI requires a fresh instance token and same-instance recovery inspection.
- PR #71 (`3bf8e0aa2a8bc22d510f0469c54e841ef4ffed4c`): separate owner-only exact-claim Edge path and credential-isolated routing.
- PR #72 (`7eff05fe8c7c26dd4933a67d87f17c8829056af4`): idempotent trusted run-instance enqueue preparation; consumed instances fail closed and enqueue never claims or executes.
- PR #73 (`296b28d5955878ce2ed3c36cde9ae2ec1d61e9bb`): records the merged enqueue boundary and staging safety state.

## Hosted staging/runtime state

Authorized staging project: `keirin-ai-staging` (`omamgmyyqnawlagbemcm`).

Durable coordination includes owner-scoped `agent_tasks` / `agent_task_events`, immutable TaskSpec identity, revision CAS, FIFO and exact-task claim primitives, attempt budget, lease owner/generation/expiry, fenced saves and explicit expired-lease reconcile-to-blocked. No always-on worker is active.

Deployed functions relevant to the agent:

- `agent-runtime-dev`: **v6 / ACTIVE / verify_jwt=true**. Its safety contract reports `runtime_task_execution_enabled=false`.
- `agent-exact-claim-dev`: **v1 / ACTIVE / verify_jwt=true**, service `v1-owner-trusted-run-exact-claim`. It accepts only `queue_claim_task` for fresh trusted run-instance IDs and reports task execution, production prediction, prediction DB writes, external race-data fetch, provider generation and report delivery all disabled.

Staging database verification remains:

- `public.agent_claim_task(text,text,integer)` exists;
- `authenticated` can execute it;
- `anon` cannot execute it;
- `race_predictions` count remains `0`.

## First bounded live read-only integration trial

The first explicit authorization was consumed by the original template-task trial. That run completed once, preserved one attempt / one lease generation, verified pinned GitHub files and same-SHA CI, released the lease and left `race_predictions=0`.

It proved real GitHub read-only provider access plus staging queue/checkpoint/activity persistence. It did not prove an always-on autonomous host, scheduler/recurrence, generation-provider execution, report delivery, production prediction or prediction DB writes.

## Second bounded live read-only integration trial

The user explicitly authorized one new bounded live read-only run on 2026-09-26. That authorization is now **consumed** and is not permission for another live run or recurrence.

Fresh trusted run instance:

- task id: `keirin-readonly-status-check.aebc2bc4a1703796`;
- spec fingerprint: `sha256-v1:7627cc318cf6f3151dac670260491276316250e18d13fdfadc97736d8065a035`;
- worker id: `chatgpt-exact-run-20260926-1309`;
- max attempts: `1`;
- lease generation: `1`.

Durable final state:

- status `completed`;
- revision `3`;
- attempt count `1 / 1`;
- completed step `read-current-state`;
- lease owner and expiry cleared;
- `last_error=null`;
- `blocked_reason=null`.

Pinned GitHub observation and verification:

- observed/final `main`: `296b28d5955878ce2ed3c36cde9ae2ec1d61e9bb`;
- `AI_AGENT_REQUIREMENTS.md`: blob `55aee582794dee98be821812f39121e73d3efa18`;
- `AGENTS.md`: blob `be0b87cdd8c5cc562d68469d72af17c08989158e`;
- `WORK_STATUS.md`: blob `dcb9daa4e161171dabe0480adf70ba0ee6fe543c`.

Same-SHA push CI was verified `completed / success` for all four required workflows:

- collection progress UI regression: run `36216613733`;
- agent checkpoint PostgreSQL contract: run `36216613735`;
- keirin-ai regression: run `36216613774`;
- agent runtime read-only smoke: run `36216613734`.

The append-only staging ledger contains checkpoint creation, exact-task lease claim with `claim_mode=exact_task`, worker/task/step start, GitHub observation, GitHub verification, step verification/completion, completed checkpoint, lease release and task completion. Post-run `race_predictions` remained `0`.

Detailed evidence is in `SECOND_BOUNDED_READONLY_TRIAL_20260926.md`.

### What the second trial proves

A fresh unique run-instance can be persisted and consumed exactly once through the exact-task database claim primitive while preserving immutable identity, bounded attempts, lease fencing, durable evidence and pinned read-only GitHub/CI verification.

### What it does not prove

The second run was orchestrated through the connected ChatGPT GitHub and Supabase control surfaces. The exact-task PostgreSQL RPC was exercised directly in staging, but the owner-authenticated HTTP path through deployed `agent-exact-claim-dev` and the standalone Python one-shot host were not independently executed end-to-end.

Therefore it still does **not** prove a self-contained external host can perform enqueue → Edge exact claim → Python worker → recovery without ChatGPT orchestration. It also does not prove always-on autonomy, scheduling, recurrence, provider generation/write execution or report delivery.

## Current agent state

The project now has a generic task/runtime core, durable owner-only checkpoint/activity storage, crash-safe queue/fencing, exact task identity/claim support, a safe unique run-instance enqueue path, strict hosted clients, credential-isolated Edge routing, SHA-pinned GitHub/CI observation, durable provider evidence, recovery inspection/proposals, hard deadline enforcement, a closed single-run manifest, two bounded live read-only integration trials and a one-shot host path bound to fresh exact run instances.

It is still **not** an always-on self-contained autonomous agent. No scheduler/recurrence is active, provider generation/write bindings remain unbound, report delivery is not configured, and deployed runtime task execution remains OFF.

## Next work / next boundary

Code-only work may continue without another live-run authorization. The next implementation target is an independently hosted **manual one-shot runner** that wires the existing enqueue + owner-authenticated Edge exact claim + standalone Python worker + recovery inspection, with no schedule and no recurrence.

A future live execution of that independently hosted runner is a separate boundary and requires a new explicit authorization because the second live-run authorization is consumed.

Generation providers, recurring scheduler, prediction writes, race-data auto-fetch and report delivery remain separate later boundaries.

No race screenshots or owner credential resend is needed for current code-only preparation.

## 21:00 report requirement

The product requirement remains daily 21:00 Asia/Tokyo reporting of daily sales, monthly sales and activity (executed work, results, failures/incomplete work, next actions). Sales source, accounting rules and delivery destination remain unresolved. Missing sales values must never be shown as zero. Live report delivery/scheduling remains disabled.

## Constraints

Do not commit private race histories, prediction snapshots, model artifacts, credentials, private file identifiers or personal data. Prefer current `main`, current CI, deployed function metadata and direct staging checks over older handoff notes.
