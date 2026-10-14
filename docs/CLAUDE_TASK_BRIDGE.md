# Claude task bridge — OFF / approval required

Revised 2026-10-14 on PR #253. This prepares an Issue → bounded Claude proposal →
validated draft PR handoff. It is not enabled or runtime-qualified. Main merge,
OAuth registration, permission changes and first execution require separate
owner approval. Existing production/data/cloud stops remain unchanged.

## Review findings and correction

The earlier head `61e9a7d` passed three existing CI workflows, but these did not
exercise the bridge. Inspection of the official Action at
`34968b5981d5d170904281aa3df6f3c0d4a28855` found:

- `conclusion`, `branch_name` and `structured_output` are real outputs. However,
  supplying `prompt` selects agent mode, which does not create a task branch by
  itself. No `CLAUDE_BRANCH` was supplied. Asking Claude to commit/push while
  disabling Bash and not enabling file-ops tools could not establish a branch.
- The diff gate ran **after** the proposed push. It could refuse a PR but could
  not prevent an earlier out-of-scope remote write. Its shell glob also accepted
  nested paths and omitted rename-source / truncation handling.
- Mutable action tags and one job holding both model credentials and repository
  write permissions unnecessarily enlarged the review boundary.

The revision uses two separate fresh-runner jobs. `propose` has only GitHub read
permissions, an explicit read-only `github_token` override, and the separately
approved Claude subscription credential. It supplies a bounded source snapshot,
AGENTS and the source HOLD to Claude. All tools are denied with a nonempty `--disallowedTools "*"`; MCP configuration
is empty/strict, hooks are disabled, and project/local settings and automatic
customizations are excluded. Only ephemeral runner user settings are loaded. Claude returns only
structured JSON replacement text. It does not test, push or post messages.

`publish` has no Claude action or OAuth credential. The trusted Python helper from
exact event SHA rechecks the current main, owner Issue/comment, exact allowed
paths, original blobs, no existing task branch and no overlapping open PR. It
accepts 1–4 existing non-executable regular `.py` files directly in `ml/` or
`tests/` (excluding the bridge's test). No new paths, deletions, renames, symlinks,
mode changes, duplicate entries or truncated API results are accepted. Limits:
24 KB per file / 60 KB total. Candidate Python remains inert text and is never
imported or executed in this job. Only after validation are Git blobs/tree/commit
created, followed by the deterministic `claude/task-<issue>` ref and a draft PR.
A final context check precedes ref creation. No ref update, force push or merge
endpoint exists. Human review of the candidate's behavior is still mandatory.

The pinned Action parses empty CLI values as flags and falls back to all settings
sources; therefore the workflow does not rely on `--tools ""` or
`--setting-sources ""`. It uses an explicit wildcard denial, `--bare`,
`--setting-sources user` and disabled hooks.

The whole workflow is serialized; existing task branches stop a repeat request.
A failure after branch creation leaves that branch for inspection. Do not rerun
or delete it automatically: inspect for an existing PR / lost API response first.
A main change requires fresh preparation, not silent rebase. A concurrent main or
Issue change immediately after the final read cannot be atomically prevented by
GitHub's API; review the exact PR head/base and current task before CI or merge.

## Activation sequence (not performed)

1. Review exact final PR #253 diff and required CI. Approve merging only if the
   **disabled preparation** is acceptable. No issue-comment workflow runs until
   it exists on the default branch and its flag is enabled.
2. Confirm the Claude account's subscription entitlement and token issuance with
   `claude setup-token`. Official documentation supports Pro/Max OAuth. An iPhone
   alone does not provide the required CLI; safe access to an existing trusted
   CLI/session and no extra usage charges remain account-specific, unverified.
   Do not create an API key, paid plan, tunnel or new host as a fallback.
3. Separately approve storing `CLAUDE_CODE_OAUTH_TOKEN` as an Actions secret.
   Never paste it in an Issue, repository, report or chat. This revised design
   supplies GitHub's job token explicitly, so it does **not** request the Claude
   GitHub App token or OIDC permissions. No App installation is required by this
   code path; actual authentication remains untested.
4. Confirm Settings → Actions → General allows Actions to create pull requests.
   Any required setting change needs separate owner approval.
5. Separately approve `CLAUDE_TASK_BRIDGE_ENABLED=true` and one synthetic-only
   pilot. Use the updated Issue template: one exact allowed path per line. Check
   unfinished Claude commit `9fbb95d` before choosing settlement/evaluation work.
6. Owner posts exactly `/claude-run` once. Observe authentication, bounded output,
   artifact transfer, fresh publisher, draft PR and refusal behavior. Model/API
   failure is a failure, not completed implementation. Disable on unexpected use.
7. Inspect the draft diff **before approving CI**. Current GitHub.com documentation
   says `GITHUB_TOKEN`-created `pull_request` opened/synchronize/reopened events
   create **approval-required** workflow runs. A writer selects “Approve workflows
   to run”. Other token-generated events remain suppressed. Do not bypass this
   gate with a PAT/App, or count pending/absent checks as successful CI.
8. Record exact head, all applicable CI, reviewed behavior and remaining blockers.
   Merge remains a separate approval; no production activation follows it.

## Validation and residual limits

The offline contract workflow uses synthetic API responses, no model/credentials,
no network and no real race data. It tests positive draft publication and refusal
of stale, overlapping, malformed, duplicate, oversized or unsafe proposals, API
failures and partial-write recovery. This is **not** real Action/OAuth/PR runtime
proof. Existing CI remains independently required at the exact new head.

Pinned Action source makes review reproducible, but its runtime dependencies and
Claude CLI are installed by the Action. CLI isolation flags, structured output,
read-token compatibility and the account's subscription limits require the first
controlled pilot. No network firewall or comprehensive code-safety proof is
claimed. A generated Python file can contain unsafe behavior: human review and
isolated CI approval must precede execution; paths alone cannot prove semantics.
One-day artifact retention is requested; no incremental-cost guarantee is made.
All public artifacts contain only already-public code and candidate code.

KEIRIN.JP HOLD; real source acquisition/training; prediction DB writes;
production prediction; hosted Jarvis execution; cloud operations; outbound
provider messages; deployment; and reporting remain OFF. Existing agent-runtime,
PR #250 and other applications are unchanged. ChatGPT↔Claude direct conversation
and autonomous 21:00 reporting are not implemented by this bridge.

## Unpublished work

The recovery branch `claude/keirin-ai-web-survey-i4e236` still points to main
`62f197d` on this review. Reported local commit `9fbb95d` remains unavailable in
this workspace and unverified on GitHub. Do not reproduce the 7/9-rider changes
from a description or claim its reported tests passed here. Recover the original
Claude session and use only its authorized non-force push path after diagnosing
its 403. This is independent of the bridge revision.

## Primary references (checked 2026-10-14)

- Action inputs/outputs: https://github.com/anthropics/claude-code-action/blob/34968b5981d5d170904281aa3df6f3c0d4a28855/action.yml
- Agent mode: https://github.com/anthropics/claude-code-action/blob/34968b5981d5d170904281aa3df6f3c0d4a28855/src/modes/agent/index.ts
- Mode selection: https://github.com/anthropics/claude-code-action/blob/34968b5981d5d170904281aa3df6f3c0d4a28855/src/modes/detector.ts
- Token override: https://github.com/anthropics/claude-code-action/blob/34968b5981d5d170904281aa3df6f3c0d4a28855/src/github/token.ts
- OAuth/setup: https://code.claude.com/docs/en/github-actions
- Tool isolation: https://code.claude.com/docs/en/cli-reference
- CI approval: https://docs.github.com/en/actions/concepts/security/github_token
- Tasks and stop boundaries: Issues #249 / #254, SOURCE_ACQUISITION_STATUS.md
