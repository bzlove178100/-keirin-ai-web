# First bounded live read-only integration trial — 2026-09-26

This record is evidence of the first explicitly authorized, single-run, read-only repository/CI integration trial. It is deliberately narrower than an always-on autonomous-agent claim.

## Authorized scope

- Task: `keirin-readonly-status-check`
- Task fingerprint: `sha256-v1:f9af0209ae2545d096d9c04cf4cfe5d434b90407bfc6aaa73ca0c6445d749403`
- Repository: `bzlove178100/-keirin-ai-web`
- Actions: `github.read_main`, `github.verify_ci`
- Access: read only
- Maximum tasks: 1
- Scheduler / recurrence: disabled
- GitHub writes during the task: none
- Production prediction: OFF
- Keirin prediction DB writes: OFF
- Automatic external keirin data fetch: OFF
- Provider generation/write bindings: unbound
- Report delivery: OFF / unconfigured

## Durable task result

Staging task `keirin-readonly-status-check` was created and claimed once by worker identity `chatgpt-single-run-20260926`.

Final durable state:

- status: `completed`
- revision: `6`
- attempt_count: `1`
- max_attempts: `1`
- lease_generation: `1`
- lease_owner: cleared
- lease_expires_at: cleared
- completed step: `read-current-state`
- last_error: null
- blocked_reason: null

The append-only activity ledger contains the claim, task/step start, checkpoint/fence saves, GitHub observation, GitHub verification, step completion, lease release and task completion events.

## Pinned GitHub observation

Observed `main` SHA:

`826e59163280f1f461f58f9c8a8a5a5dc6bbc34d`

Required files were read at that exact commit:

- `AI_AGENT_REQUIREMENTS.md` — blob `55aee582794dee98be821812f39121e73d3efa18`, 6393 bytes
- `AGENTS.md` — blob `be0b87cdd8c5cc562d68469d72af17c08989158e`, 5959 bytes
- `WORK_STATUS.md` — blob `f38da208c8ee3337020af47aa955db35e31e13f6`, 8893 bytes

The final `main` re-read still matched the observed SHA.

## Same-commit CI verification

All four required `main` push workflows were `completed / success` for the same SHA:

- regression — workflow `365001481`, run `36212528769`
- collection progress UI regression — workflow `365889130`, run `36212528579`
- agent checkpoint PostgreSQL contract — workflow `366817234`, run `36212528834`
- agent runtime read-only smoke — workflow `365961402`, run `36212528642`

The durable `github_verification` event records `verified=true` and the same observed/current SHA.

## Safety recheck

After the run, `race_predictions` remained at `0` rows. The deployed `agent-runtime-dev` was still version 6 / ACTIVE / `verify_jwt=true`, and its contract still reported `runtime_task_execution_enabled=false`; prediction DB writes, production prediction and external automatic fetch remained disabled.

## Important execution-path limitation

This trial used the connected ChatGPT GitHub and Supabase control surfaces to orchestrate the live provider reads and the real staging checkpoint/activity/lease RPC state machine. It did **not** prove that the deployed `agent-runtime-dev` independently executed the worker from an owner browser/session, and it did not prove an always-on autonomous host.

Therefore this trial verifies:

- real GitHub read-only provider access;
- same-SHA file + CI verification;
- real durable staging queue/checkpoint/activity persistence;
- one bounded claim / completion / lease release;
- post-run evidence inspection with no re-execution.

It does not verify:

- autonomous background scheduling;
- independent long-lived host/session execution;
- browser-owner-JWT to worker execution;
- generation-provider execution;
- report delivery;
- production prediction or prediction DB writes.

## Next engineering boundary

Prepare a standalone one-shot host entrypoint that loads the closed activation manifest, requires runtime-only credentials and an explicit one-run authorization signal, invokes the already-tested `HostedRepositoryStatusWorker`, then performs read-only recovery inspection before exiting. Keep scheduler and recurrence disabled. A later live host trial must still be separately bounded and must not be treated as permission for recurring execution.
