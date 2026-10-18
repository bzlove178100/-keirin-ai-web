# Owner synthetic acceptance and Web result blocker

2026-10-18 JST. Repository: bzlove178100/-keirin-ai-web only.

## Verified baseline

- main `f4a83f9817ea44d01ffdc7aee0d7163a1e9f0fc3`, tree
  `8a72be11c3c42a3b0bd0b879e6a344c30ead1a82`.
- Main ML39058247364/UI39058247363/DB39058247350/regression39058247374 and
  Pages39058247785 all completed successfully. PR262 is merged; do not remerge.
- PR261 remains Draft at `4be2a8266ad4cfd857b1778a63c8387252c25e84`.
  Open PR250/257 are documentation work. No public head changes or new overlap
  were observed. Nonpublic Work and unpushed sessions remain unverified.
- Owner login succeeded in the agent browser through the secure user-entry
  flow. The page showed role=owner, plan=owner and Web/server/dev owner checks
  successful. No password, token or account identifier is retained here.
  Password reset was unnecessary and was not performed.

## Executed within the existing staged-deployment approval

The corrected package manifest was
`e0b0f8004eec7d954171cdc00b7aff87e962feda79da9764aa1b5d88f44a4553`.
Before deployment, all seven rollback files matched fresh live source bytes;
predict16/history6/backtest5 were ACTIVE, JWT enabled, with no import maps.
The package integrity check also passed. No model retraining was performed.

1. Deployed backtest-engine-dev v6. Its two source files matched the candidate
   exactly after accounting for the source-root prefix removed by retrieval.
   Actual owner Web executed one synthetic two-record request (7/9 riders,
   210/504 probabilities). UI showed two evaluated races, probability mass 1,
   and zero saved records. The UI only accepts this response with saved=false,
   db_write_enabled=false and production_prediction_enabled=false.
2. Deployed history-builder-dev v7. Its two source files also matched exactly.
3. Loaded a generated nine-rider snapshot and entered result 9-8-7. Existing
   Web rejected it before the API request: validOutcomeCombo restricted cars
   to 1..7. Therefore live nine-rider history acceptance did NOT succeed.
   No predict deployment or PR261 merge followed this failure.
4. Restored history then backtest from the exact observed originals.
   Current versions are history-builder-dev **v8** and backtest-engine-dev
   **v7**, both ACTIVE/JWT=true. Files match the pre-deployment originals byte
   for byte. The higher version numbers are rollback deployments, not the
   accepted seven-/nine-rider candidate. predict-engine-dev remains v16.

The same synthetic fixtures exercise prospective chronology structurally.
The Web's displayed prospective count and ROI are fixture results, not real
race observations, model accuracy, profitability or production readiness.
No external race data, real-data training or prediction database write occurred.

## Narrow correction in this candidate

- Validate result car numbers against the existing validated seven-/nine-rider
  roster at submission, dataset import and fallback collection counting.
- Keep seven-car interpretation only for the existing legacy record path with
  no training_input. Malformed present rosters do not fall back.
- Reject duplicate, out-of-roster, zero, ten and noncanonical leading-zero
  combinations. No authentication, transport, API, permission or OFF flag changes.
- Extend the existing Web capture test to drive the actual submission function
  through a synthetic safe response, then verify returned-history handling,
  import and fallback counts for outcomes containing 8/9. Invalid inputs never
  reach the stubbed transport. All inputs/responses are code-generated.
- The new test fails on the previous main and passes with this correction.
  Existing capture/cutoff/probability/7-9 import checks also pass locally.
  CI status and exact candidate head are recorded in the PR, not assumed here.

This isolated branch is based on the current main tree, not the owner-panel
branch. PR261 is unchanged; its separate panel hunks must be composed and checked
after this fix. Shared WORK documents and Jarvis files were not edited.

## Reproduction and next approval boundary

Use `tests/test_prospective_tools.cjs` snapshot(0, 'SYNTHETIC_GENERATED', n)
for n=7/9, set venue='SYNTHETIC' and race_number=n, and replace the fixture
prediction with buildFullPredictionWithWeights(snapshot.race_data). The browser
core buildHistory uses outcome n-(n-1)-(n-2), settlementOdds=42 and
resultTimestamp='2026-09-24T00:40:00Z'. This is generated test data only.
Fixture timestamps are historical; do not represent them as live predictions.

The original approval order was backend acceptance before PR261/Pages. Publishing
this newly discovered existing-Web fix FIRST changes that order and is not
treated as covered by the earlier approval. Prepare and verify this Draft PR,
then request approval for this narrow merge/Pages correction before retrying.

After approval and successful Pages verification, recapture the three live
functions and regenerate a new package: the old manifest's observed versions
are stale after rollback. Reuse the unchanged synthetic owner bundle. Compare
remote heads and exact sources immediately before saving/deploying. Repeat only
the acceptance steps invalidated by rollback and the newly fixed Web path.

Resume backtest -> history -> predict with live owner synthetic verification at
each step; rollback in reverse on failure. PR261/Pages remains conditional on
backend success. The unchanged history-pipeline-dev v6 was read only to confirm
its routing and generic combination validation; it was not deployed or called
by the rejected Web submission. Runtime nine-rider history remains unverified.

KEIRIN.JP HOLD; external real acquisition, real-data training, prediction DB
writes and production predictions remain OFF. No source inquiry, billing,
authorization change, Claude-original recovery or unrelated project work.
