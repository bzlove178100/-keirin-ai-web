# Jarvis core: bounded decision loop, live AI still unqualified

## Latest continuation: existing CLI found, authentication required

Workspace trust was enabled after the owner's explicit action-time approval.
The existing development environment has Claude Code **2.1.296**. Both ordinary
and safe-mode CLI authentication checks report `loggedIn=false`,
`authMethod=none`, `apiProvider=firstParty`, `subscriptionType=null`.
No credential contents were opened, installed, copied or registered. No model
inference was attempted. Exact private connection details remain in the private
handoff. Authentication must be completed through the official subscription
login by the owner; do not request a secret in chat.

`agent_core/claude_decision_provider.py` now supplies the previously missing
subprocess transport. `tools/jarvis_claude_document_task.py` defaults to a
read-only version/authentication preflight. Its explicit execution mode connects
the same DecisionLoop to the existing CLI; it does not replay scripted answers.
The older no-provider CLI keeps its original behavior.

The profile requires the inspected CLI version, first-party `claude.ai` login,
a recognized Pro/Max subscription, and completed runtime/cost reviews. It
refuses API-key, generic OAuth-token, unknown plan and third-party routes.
No installer, login automation or fallback provider is included. Before setting
the review flags, verify that existing subscription allowance is available,
usage-credit/extra-usage charging is disabled, and managed policies cannot add
hooks, commands, tools, credentials or alternate endpoints. These flags record
operator review, not automatic proof of entitlement or a billing guarantee.

Each decision runs with safe mode, restricted mode, no user/project settings,
no built-in tools, denied MCP tools, empty strict MCP config, no session
persistence, no browser integration and one agentic turn. The host uses a clean
temporary working directory and a small environment allowlist; keys, gateway
overrides, proxies and Node injection settings are not inherited. Managed policy
still applies, so this is not an OS sandbox. The real home remains unchanged for
official CLI authentication; the adapter never reads credential files itself.
OAuth-incompatible bare mode and permission bypass are not used.

The transport caps input/output and elapsed process time, terminates/reaps its
process group, redacts errors and never retries automatically. Jarvis validates
every returned decision and alone executes the fixed document operations. Only
numeric usage and allowlisted model identifiers enter provider receipts, never
session IDs or raw error metadata. These receipts are local to an invocation;
they are not a durable billing ledger. `inference_attempts` counts CLI inference
launches, not confirmed provider requests; the loop's `model_calls` counts model
callable attempts, which can fail preflight without inference. A timeout cannot
prove that a remote request was unbilled. Parent-process death, long-running
hosting and durable usage reconciliation remain unqualified.

Validation: **11 new fake-CLI process tests passed**, including full feedback
through real files, duplicate refusal, metadata-only default, absent auth,
wrong credential/plan, review gates, version drift, empty argv preservation,
environment isolation, redaction, malformed output, timeout, bounded stdout and
host rejection of an out-of-scope action. The existing **25 decision-loop tests
passed again** after connecting the transport. This is not real Claude output.
Live execution/quality/usage and stages 2–6 remain incomplete; count stays 1/6.

Read-only command (does not install, authenticate or infer):

```sh
python -m tools.jarvis_claude_document_task --claude /absolute/path/to/claude
```

After authentication and both reviews, the host may add `--execute`,
`--runtime-reviewed`, `--subscription-only-reviewed`, `--source`, `--output`,
`--state-dir`, and a new `--task-id`. Use the nonsecret fixture first. Do not
set the review flags merely to get past the guard. Use the prior review/resume
procedure for an uncertain or blocked task; never silently reset it.

The previous head `343d45b4f94442d40c769d494e5769e64a730b07` finished with four
successful workflows and two failures. Regression job `120517843579` failed
because the pinned Ubuntu `systemd_255.4-1ubuntu8.17.debian.tar.xz` download
returned HTTP 404; the read-only smoke correctly refused that failed sibling
workflow. The main `regression` job itself passed. This is not full-CI success.
The existing Ubuntu fixture/workflow is unchanged and was not blindly rerun.
The latest candidate's CI must be inspected separately in PR #269.

Reference checked against installed help and official docs:
https://code.claude.com/docs/en/cli-reference
https://code.claude.com/docs/en/headless
https://code.claude.com/docs/en/env-vars
https://code.claude.com/docs/en/costs

The sections below record the initial implementation before this continuation;
their unbound-provider/unlocated-runtime statements are superseded above.

## Source and boundary

Inspected on 2026-10-24 JST. The connected account lists one accessible
repository, `bzlove178100/-keirin-ai-web`. The common-agent source is actually
present in `agent_core/`; `AI_AGENT_REQUIREMENTS.md` explicitly defines its
general purpose. Base main: `d069ab9b6adcf9585954a5bae7be7df0546e473c`.
This identifies the source inspected, not every possible private installation.
Work branch: `work/jarvis-core-20261024`. No main merge or deployment here.

Open #250/#257/#266/#267 were checked. None changes the new decision/document
modules. #266/#267 also prepend WORK_STATUS/WORK_RESUME; preserve their entries
when integrating. Their racing application, models and runtime remain separate.
The existing regression workflow is unchanged; the new dedicated test workflow
uses scripted decisions, local files and read-only GitHub permissions only.

## Five-point inventory

| Item | Verified here | Limit |
| --- | --- | --- |
| Source | `agent_core/`, base main above, isolated branch | No claim that AWS has this revision |
| Entry/execution | `AgentOrchestrator.run` previously executes fixed TaskSpec steps; new `DecisionLoop.run` / `run_document_task` accepts successive decisions | Local process only; no daemon started; AWS/Lightsail/Codespaces live status unknown |
| Model/authentication | New host-injected model callable; `None` blocks before any model call | Work PATH has no claude/codex/omniroute CLI; named provider key/OAuth environment settings absent; remote credential state unknown |
| Real tools | Fixed-source file read, fixed-output atomic write, section/source verification via existing ToolRegistry and AgentRunner | Only the selected private files; no shell, network, customer send, publish, payment or database capability |
| Persistence | Existing FileStateStore: parent `states/`, `activity.jsonl`; child `decision_steps/states/` and its ledger | Host chooses private directory outside repo; scratch is not a permanent service; no new queue, lease, server or distributed store |

The old hosted paths still exist in `agent_core/hosted_worker.py`,
`hosted_readonly_worker.py`, `single_run_host.py` and related host tools. They
were not activated. Existing authentication/hosting histories are not evidence
of their current runtime health. No credential values were read or recorded.

## Actual change

`DecisionLoop` adds the missing feedback path: instruction and host-selected
capabilities -> one model decision -> permission/schema checks -> existing
AgentRunner child task -> persisted observation -> next model decision.
Finish is accepted only after a host-selected read-only verifier returns the
literal boolean true and required tool actions have completed. A model cannot
declare itself verified, widen scope, supply a verifier or change a saved goal.

The parent stores a decision before executing it. If the child completed but
the parent checkpoint was interrupted, restart uses the child's saved result
without repeating the tool. Unknown side effects or interrupted model calls
block for explicit review. Clean pauses resume with previous observations.
Terminal duplicates do not call the model. Same write decisions are refused.
Maximum decisions, bounded JSON/context, safe error codes and an operator-stop
callback limit a run. They are not provider-token/cost limits or hard process
deadlines; an eventual provider host must enforce those separately.

`DocumentTools` reuses the registry and performs real filesystem operations.
Model arguments contain no paths. Only a host-selected UTF-8 source and output
are allowed. Nonregular files, symlinks, hard links, changed input and oversized
documents are refused. Output uses a private temporary file and atomic rename.
The caller must supply a trusted private directory and authorized nonsecret
source. This is not an OS sandbox against hostile concurrent local processes.

Verification checks source identity and nonempty required Markdown sections.
It does **not** prove factual accuracy, usefulness or quality of a summary.
Model/provider and tool implementation bindings are host responsibilities;
change the declared binding/input version under a new reviewed task ID.

## Test receipt

- **25 new tests passed**: scripted model decisions + real local file tools.
  Includes output feedback, failed completion followed by repair, preexisting
  output refusal, duplicate submission, clean pause/new-object restart,
  interruption after child completion, interruption after write effect,
  interrupted model, changed identity/scope, invalid decision, missing model,
  auth/usage/timeout errors, error redaction, stop, limits, duplicate write,
  lock contention, source drift, symlinks, empty sections and reviewed recovery.
- **42 existing tests passed**: core 8, interruptions 5, task identity 5,
  orchestration 7, runtime bridge 8, safe errors 6, redaction static 3.
- Existing web/safety regression passed; `git diff --check` passed.
- CLI prerequisite run returned exit **2**, `status=blocked`,
  `reason=model_unavailable`, `model_calls=0`, no output report created.
- No live model call, AI-generated report, cloud worker, automated delivery,
  revenue or full-system acceptance was demonstrated.
- Remote CI receipt belongs in the PR once actually observed; local success
  is not a claim of remote CI completion.

## The same six acceptance stages

| Stage | Status |
| --- | --- |
| 1. Foundation | Confirmed for the identified code and bounded test scope |
| 2. Live AI connection | Not complete; feedback loop implemented, authorized provider unbound |
| 3. Real tools | Partial: real file operations pass with scripted model; live AI return path untested |
| 4. Continued operation | Partial local persistence/restart; no chat-independent host verified |
| 5. End-to-end live acceptance | Not complete |
| 6. Stable operations acceptance | Not complete |

**1 of 6 stages confirmed, 5 not complete.** This count is not a completion
percentage or time estimate. The lazy sales system's 99 tests are excluded.

## Run and resume

From the repository root, with an existing private output directory:

```sh
python tests/test_agent_decision_loop.py
python -m tools.jarvis_document_task \
  --source agent_core/examples/document_source.txt \
  --output /tmp/jarvis-report.md \
  --state-dir /tmp/jarvis-private-state \
  --task-id jarvis-prerequisite-check
```

The second command intentionally has no provider and returns blocked/exit 2.
It is a prerequisite check, not an AI demo. Do not repeatedly rerun it expecting
authentication to appear. There is no synthetic-model fallback in that command.

An authorized host must call `run_document_task(..., model=callable,
model_binding="reviewed-provider-profile")`. The callable receives a JSON
request containing the instruction, permitted tools, observations and decision
protocol, and returns exactly one tool/finish/stop object. The host must bind
actual authenticated inference, not replay this test's answers. No CLI/API
provider transport is implemented by the callable interface itself.

`DecisionLoop.resume_after_review` is an explicit host operation. Inspect the
parent blocked reason first. For a tool interruption, inspect its child and
use existing `FileStateStore.reconcile_blocked_step` only after establishing
whether the effect occurred. Then resume the parent with the exact expected
reason and a nonsecret review note. For an interrupted model call, first resolve
its external status/usage, then explicitly set `model_call_resolved=True`.
Limits/duplicate-write blocks require a new reviewed task; do not reset counters.

## First remaining dependency

Locate the already-owned Claude Code/Codespaces (or other authorized inference)
execution environment and verify its current entitlement, authentication,
isolation and usage limits. This Work did not install a CLI or introduce a paid
API. Issue #254 records OAuth registration approval on 2026-10-15, but issuance
and registration were still incomplete then; do not ask for that same approval
again, and do not treat that dated observation as a current secret inventory.

Issue #254 also records an earlier automatic-review rejection of CLI installation
and an OAuth/bare compatibility concern. No installation or workaround was
attempted here. Official documentation checked again on 2026-10-24 confirms bare
mode excludes OAuth; the CLI reference describes safe mode as retaining normal
authentication while disabling customizations. This does not verify the pinned
Action/CLI combination. Preserve the disabled bridge until that runtime is
qualified; do not simply remove isolation or add an API-key fallback.

Sources:
- https://github.com/bzlove178100/-keirin-ai-web/issues/254
- https://code.claude.com/docs/en/authentication
- https://code.claude.com/docs/en/cli-reference
- https://code.claude.com/docs/en/headless

After a qualified existing provider is bound, run one nonsecret fixture through
the actual model without feeding each step manually. Record model identity,
tool/result receipts, verifier outcome, any manual intervention and measured
usage. Only then assess stages 2/3/5. Host persistence/stop/restart and repeated
operation remain separate stages. No new paid resources, scheduled jobs, cloud
changes, public deployment, source acquisition or production activation occurred.
