# Work status

Updated: 2026-09-25 UTC.

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

Relevant merged work includes offline LightGBM inference/evaluation, strict prospective capture and chronology, private history bundling, readiness UI and the unified strict chronological split protocol (through PR #31).

## Shared autonomous-agent foundation

### Runtime core and recovery

Merged and verified:

- PR #32: broad autonomous-agent goal made authoritative.
- PR #33: machine-readable `TaskSpec`, private task state, activity ledger, allowed-action gates, idempotency keys, verification hooks and artifact lifecycle separation.
- PR #35: explicit reconciliation, capability/permission metadata, orchestration preflight, read-only GitHub adapter contract and Asia/Tokyo reporting contracts. Missing revenue remains `unknown/unavailable`, never silently zero.
- PR #37: credential-free runtime binding manifests, provider-neutral runtime bridge, read-only Supabase/file adapter contracts, CLI/runtime utilities, report-delivery separation and disabled-by-default 21:00 scheduling contract.
- PR #40: first live external provider path through a GitHub Actions read-only worker using ephemeral `GITHUB_TOKEN`; repository/CI verification works without screenshots and write capabilities are blocked.
- PR #45: pure owner-scoped queue planner / worker-lifecycle contract. It does not claim tasks or perform hosted I/O.
- PR #46: interruption safety prevents automatic repetition after an attempted-but-incomplete side effect and adds nonblocking local per-task locking.
- PR #47: task state is bound to an immutable fingerprint of the complete TaskSpec so a reused task ID with changed inputs/actions/permissions/retry rules cannot silently resume.
- PR #48 (`b5112df4f60d003daed2eb92706d156bc81aebed`): rollback-only hosted checkpoint v2 preparation with immutable task definition, revision compare-and-swap, owner-role grants, atomic checkpoint/audit writes and PostgreSQL 17 isolation tests. This is validated preparation only; hosted persistence is still not activated.

### Hosted runtime

- `supabase/functions/agent-runtime-dev` is an owner-only hosted shell protected with `verify_jwt=true`.
- PR #43 added capability diagnostics: `declared`, `bound`, `authorization_state`, `authorized`, `verified`, `last_error`.
- PR #49 (`9a591bc3fbe2ff5df60db0d903ccaeec5c3e6c89`) added explicit broad capability contracts for:
  - `research.read_public_sources`
  - `text.generate`
  - `image.generate`
  - `video.generate`
  - `code.generate`
  - `learning.evaluate`
  - `report.generate`
- Those capabilities are declarations only. They remain **unbound**, **unauthorized** and **unverified** in the hosted runtime.
- PR #50 (`455a289c4652e4b95be62261c0f3a3f604b3852a`) aligned hosted v3 messages and added `deno check` for the Edge Function entrypoint before deployment.
- `agent-runtime-dev` was deployed after PR #50 as **version 3**, verified `ACTIVE` with `verify_jwt=true`, and read back from Supabase.
- Hosted v3 still has:
  - task execution: **OFF**
  - hosted persistence: **OFF**
  - provider writes: **OFF / unbound**
  - automatic keirin race-data fetching: **OFF**
  - report delivery: **OFF / unconfigured**

## Validation

CI currently covers:

- shared agent core safety;
- interrupted/competing runner cases;
- immutable task identity;
- orchestration/reporting;
- queue planning;
- runtime bridge/delivery;
- live GitHub read-only host bridge;
- broad capability contracts;
- rollback-only hosted state schema safety;
- Web/prospective/ML regression;
- Phase32/training-input contracts;
- hosted runtime contract tests;
- hosted runtime entrypoint type-checking;
- isolated PostgreSQL 17 checkpoint/RLS/CAS tests.

The current design explicitly separates `created`, `verified`, `persistent_saved`, `device_saved` and `ui_loaded` artifact states and does not treat Work/Chat execution as proof of an independent always-on agent.

## Current agent state

The project now has:

- a tested generic task/runtime core;
- safe resume/reconciliation semantics;
- a queue-planning contract;
- a real Supabase hosted preflight/diagnostic shell;
- a verified live GitHub read-only provider path;
- a validated but unapplied durable checkpoint schema;
- explicit broad capability contracts for research/text/image/video/code/learning/report generation.

It is still **not** an always-on self-contained autonomous agent.

Major remaining gaps:

1. durable hosted task/activity persistence is prepared but intentionally OFF;
2. no hosted queue/lease worker is activated;
3. Supabase/files/Web/model-provider live bindings are not yet broadly connected;
4. text/image/video/code capabilities are declared but provider-unbound;
5. sales source, accounting rules and report destination are unresolved;
6. 21:00 report generation/delivery is not scheduled live.

## Next action / authorization boundary

The next irreversible boundary is **activating AI-agent-only hosted task/activity persistence in the staging Supabase project**.

Do **not** activate it without explicit user authorization. If authorized:

1. convert the reviewed rollback-only checkpoint design into a staging migration;
2. apply it only to agent-specific tables/functions, not keirin prediction tables;
3. run RLS/security/advisor checks;
4. verify owner isolation, compare-and-swap, completed-state protection and rollback/failure behavior;
5. only then connect hosted checkpoint persistence to the runtime;
6. keep production prediction, keirin prediction DB writes and automatic external keirin data fetching OFF unless separately authorized.

Until that authorization is given, continue only reversible/no-persistence work such as capability contracts, read-only bindings, tests, provider adapters and documentation.

## 21:00 report requirement

The product requirement remains daily 21:00 Asia/Tokyo reporting of:

- daily sales;
- monthly sales;
- activity report: work executed, results, failures/incomplete work and next actions.

Sales source, accounting rules and delivery destination are still unresolved. Missing sales values must not be shown as zero. Report delivery/scheduling stays disabled until those inputs are defined.

## Constraints

Do not commit private race histories, prediction snapshots, model artifacts, credentials, private file identifiers or personal data. Prefer current `main`, current CI, deployed function metadata and direct staging checks over older handoff notes.
