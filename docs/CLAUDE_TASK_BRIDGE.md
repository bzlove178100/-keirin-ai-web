# Claude Code GitHub task bridge — opt-in only

Status: **OFF / preparation only** (2026-10-13). This is a GitHub Issue → Claude Code → tests → draft PR handoff proposal. It does **not** connect the ChatGPT conversation directly to Claude; a human still reviews and merges PRs.

## What is prepared

- `.github/workflows/claude-task-bridge.yml` listens **only** for an Issue receiving the `claude-ready` label, **only** when the actor is `bzlove178100` and repository variable `CLAUDE_TASK_BRIDGE_ENABLED` is exactly `true`.
- The variable is absent by default; this workflow must remain disabled until separately approved. No schedules, no automatic deployment, and no existing workflows are modified.
- The workflow accepts **only** `CLAUDE_CODE_OAUTH_TOKEN` (not `ANTHROPIC_API_KEY`), checks that the secret exists before calling Claude, limits turns to 8 and the job to 25 minutes, and creates a reviewable PR rather than merging.
- The Issue template collects a bounded file scope, synthetic test plan, and stop conditions; applying the trigger label is a separate owner action.

## Preconditions before activation — do not complete without explicit owner approval

1. Confirm the official Claude GitHub App is installed for **this repository only** with the required write permissions. The existing Claude web-to-GitHub login is not proof that the Actions GitHub App is installed or can write branches.
2. Decide the authentication and cost boundary. Anthropic documents `CLAUDE_CODE_OAUTH_TOKEN` for Pro/Max accounts, generated with `claude setup-token` in a CLI environment. Availability from an iPhone-only workflow is **not confirmed**. Pro usage limits still apply. Do **not** create an Anthropic API key or a paid API plan by default.
3. Store any OAuth token **only** in repository Actions secret `CLAUDE_CODE_OAUTH_TOKEN`; never paste it in an Issue, public repo, chat or workflow. Confirm the account owner has accepted the security and access implications.
4. After explicit approval, create repository Actions variable `CLAUDE_TASK_BRIDGE_ENABLED=true`. This is the deliberate activation switch; do not flip it as part of this PR.
5. Create one small Issue with the template. Check latest main and open PRs to avoid conflicts. Apply `claude-ready` **manually as owner** to trigger **one** run; observe the Actions log and the PR. Do not rapidly remove/reapply the label.
6. Review exact file changes, regression tests, potential external access and PR CI. No auto-merge. Disable the variable if a run behaves unexpectedly. A successful CI is not a production or licensing approval.

## Invariants and costs

- KEIRIN.JP **HOLD** persists: no official source fetching, alternative endpoints, archive promotion or data training. Other sources require separate documented permission. Production prediction, DB writes, external acquisition, real training, hosted autonomous execution and deployment remain **OFF**.
- Existing `AGENTS.md`, Issue #249, `WORK_STATUS.md` and `WORK_RESUME.md` remain the authoritative safety and handoff context. This integration must not duplicate/replace the agent-runtime or its trusted one-shot entrypoint.
- The current repository is public: GitHub **standard** hosted runners have no runner-minute charge, but storage/limits, Anthropic subscription usage, or a separately selected API option may differ. **No API plan, extra payment, secret or paid resource is activated by this PR.** A prompt and the GitHub workflow are *not* a hardware-enforced network block.
- Prompt injection is possible via public Issue descriptions. Owner-only triggering, strict task scope and human PR review reduce risk but do not eliminate it. Do not put credentials or private race information in Issues.
- ChatGPT can inspect the resulting PR via the GitHub connector **when asked**. Automatically sending new GitHub events to this ChatGPT conversation needs another integration that is not installed.

## Existing blocked work — preserve, do not invent success

Claude reported local-only commit `9fbb95d` on `claude/settle-eval-7-9-riders` from `62f197d`, with 9/9 settlement and 10/10 evaluation tests. Git push and branch creation returned 403; **no remote branch/PR was verified**. Do not assume this commit is on GitHub, discard the original Claude session, or duplicate the change without a recovery check. Keep this recovery separate from the bridge PR.

## References

- https://github.com/anthropics/claude-code-action
- https://github.com/anthropics/claude-code-action/blob/main/docs/setup.md
- https://github.com/anthropics/claude-code-action/blob/main/docs/security.md
- https://github.com/bzlove178100/-keirin-ai-web/issues/249
