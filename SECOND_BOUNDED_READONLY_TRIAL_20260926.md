# Second bounded live read-only trial — 2026-09-26

## Authorization and scope

The user explicitly authorized one new bounded live read-only run after the first authorization had already been consumed.

This run remained limited to one fresh trusted run instance, one exact task claim, one worker identity, GitHub read-only observation/CI verification, no recurrence, and no provider write/generation actions.

Keirin safety state remained unchanged:

- production prediction OFF;
- keirin prediction DB writes OFF;
- automatic external race-data fetching OFF;
- report delivery / live 21:00 scheduling OFF;
- scheduler / recurrence OFF.

## Fresh run instance

- task id: `keirin-readonly-status-check.aebc2bc4a1703796`
- spec fingerprint: `sha256-v1:7627cc318cf6f3151dac670260491276316250e18d13fdfadc97736d8065a035`
- worker id: `chatgpt-exact-run-20260926-1309`
- max attempts: `1`
- lease generation: `1`

The fresh checkpoint was created at revision `0`, claimed by exact task id, and completed at revision `3`. Final durable state is `completed`, attempt count is `1/1`, `last_error=null`, `blocked_reason=null`, and the lease owner/expiry are cleared.

## GitHub observation

Observed and final `main` SHA:

`296b28d5955878ce2ed3c36cde9ae2ec1d61e9bb`

Required files were read from that exact SHA:

- `AI_AGENT_REQUIREMENTS.md` blob `55aee582794dee98be821812f39121e73d3efa18`
- `AGENTS.md` blob `be0b87cdd8c5cc562d68469d72af17c08989158e`
- `WORK_STATUS.md` blob `dcb9daa4e161171dabe0480adf70ba0ee6fe543c`

All four required same-SHA push workflows were verified `completed / success`:

- collection progress UI regression — run `36216613733`
- agent checkpoint PostgreSQL contract — run `36216613735`
- keirin-ai regression — run `36216613774`
- agent runtime read-only smoke — run `36216613734`

The final `main` re-read still matched the observed SHA.

## Durable evidence

The staging activity ledger contains the fresh checkpoint creation, exact-task lease claim (`claim_mode=exact_task`), worker/task/step start, pinned GitHub observation, same-SHA GitHub verification, step verification/completion, completed checkpoint, lease release and task completion.

Post-run verification confirmed `race_predictions` remains `0`.

## What this proves

This second trial proves that a fresh unique run-instance can be persisted and consumed exactly once through the exact-task database claim primitive, while preserving lease fencing, bounded attempts, durable evidence and GitHub read-only verification at one pinned commit.

## Important limitation

This run was orchestrated through the connected ChatGPT GitHub and Supabase control surfaces. The exact-task PostgreSQL RPC was exercised directly in staging, but the owner-authenticated HTTP call through deployed `agent-exact-claim-dev` and the standalone Python one-shot host were not independently executed end-to-end in this trial.

Therefore this does **not** yet prove a self-contained external host can perform enqueue → Edge exact claim → Python worker → recovery without ChatGPT orchestration. It also does not prove always-on autonomy, scheduling, recurrence, provider generation/write execution or report delivery.

## Next boundary

The next meaningful integration target is an independently hosted one-shot runner using the existing owner-authenticated Edge transports and runtime-only credentials, still with one task maximum, read-only GitHub permissions and no recurrence. A recurring scheduler or provider writes must remain a separate later authorization boundary.
