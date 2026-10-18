# Web prediction acceptance after the result fix

2026-10-18 JST. Scope: bzlove178100/-keirin-ai-web only.

## Published result correction

The user's 12:09 JST approval covered PR263 merge/Pages before the previously
approved staged API acceptance. PR263 merged as
`326cad1defd6c7b60559c5309c8a6d87c214bb94`, tree
`7adc05d2fd1f22af5b7cd2dd90c65f326c0bf6aa`, identical to the verified PR head.
Pages39092651266 succeeded. The existing browser restored the owner session
after reload without entering credentials again. No auth changes occurred.

Main ML39092651821/UI39092651730/DB39092651723 succeeded. Main regression
39092651797 was still running when this note was written; final status belongs
in the PR. Never inherit a previous head's CI conclusion.

## Live synthetic acceptance and reverse rollback

Fresh observations were predict16/history8/backtest7, all ACTIVE/JWT=true.
New deployment manifest SHA256:
`375d7fae2bf55501e85b22cca141b33a73cf80e44ecfa84f5ec3a857a42bd2aa`.
The generator's verify function completed without error; it returns the
manifest, not an integrity_verified field. Candidate and rollback file hashes
matched the previously verified package. Reused the same generated model bundle;
no model retraining or dependency installation was needed.

1. backtest v8: exact candidate readback; actual owner evaluated generated
   7/9-rider records together (210/504 probabilities), two races, zero saves.
2. history v9: exact candidate readback. The published Web accepted 9-8-7 and
   7-6-5, generated each history and completed its evaluation, zero DB saves.
   The visible JSON retained 504/210 probabilities and result timestamp
   `2026-09-24T00:40:00.000Z` respectively.
   Enter **09:40** in this browser's Japanese-local datetime field for that UTC
   instant. The first 00:40 local entry was correctly rejected as pre-prediction
   before any API call; this was a test input timezone error, not a product fix.
3. predict v17: all eight candidate files matched on readback. Actual owner
   seven-rider dry-run displayed nine picks and zero saves. Nine-rider dry-run
   was rejected by the Web safety gate, whose probability validator still
   defaulted to seven cars. This was not successful nine-rider prediction display.
4. Stopped further publication and restored predict -> history -> backtest.
   Current versions are **predict18/history10/backtest9**, all ACTIVE/JWT=true
   and byte-identical to the pre-deployment originals. Version increments are
   rollback deployments, not successful candidate promotion. PR261 is unchanged.

Source retrieval may strip different common path prefixes (including leaving
`predict-engine-dev/index.ts`). The rollback guard initially rejected its path
mapping before deployment; after predict rollback it also rejected the changed
returned root. Inspection confirmed identical source bytes. Prefix mapping was
corrected only for uniquely identified expected paths; no source mismatch was
ignored and no extra deployments were used to resolve these guard errors.

All race inputs were code-generated. Names were added as `SYNTHETIC RIDER n` to
the dry-run fixture, because the training/snapshot fixture intentionally omits
names but the prediction input contract requires them. Historical fixture dates
are structural chronology tests, not real prospective observations. No real-data
accuracy, ROI or commercial readiness follows from these results.

## Narrow follow-up correction and stronger integration test

The remaining production-code change passes the input's validated 7/9-car roster
to fullProbabilityTableValid in runRealDryRun. It preserves all other owner,
safety, no-save and probability requirements. A complete normalized table for
the wrong rider count must fail; merely accepting 504 rows is not sufficient.

`tests/test_web_dry_run.cjs` executes the actual Web functions and renderer plus
the actual predict/history-pipeline/history-builder/backtest handlers. Synthetic
owner responses and in-process routing prohibit network sockets and DB writes.
For both nine and seven riders it verifies prediction display -> eligible
snapshot -> history -> evaluation -> dataset validation, and rejection of the
other roster's complete normalized probability table without a savable snapshot.
The unmodified main fails at nine-rider prediction display. This correction
passes both complete flows. ML CI runs the test with its existing pinned Node24.
Shared WORK documents, Jarvis files and PR261's branch are not edited.

## Next boundary

This new correction is an independent Draft based on main326cad1. PR263 is
already merged; do not remerge it. Publishing this additional correction needs
approval; the user's approval named PR263, not an unspecified future PR.
After exact-head CI and approval, publish this correction, refresh the live
observations/package (versions above supersede the last manifest), and resume
the previously approved backtest -> history -> predict acceptance. Test the
fixed nine-rider prediction display as well as the seven-rider regression.
Only backend success permits PR261 composition/CI/merge/Pages and actual owner
7/9 synthetic model display. Its head remains
`4be2a8266ad4cfd857b1778a63c8387252c25e84`.

Public PRs250/257 remain documentation-only; no new public code overlap was
observed. Nonpublic Work/unpushed sessions are unverified. No recovery claim for
Claude9fbb95d. Reuse PR257 permission evidence; do not restart source research.
KEIRIN.JP HOLD; real acquisition/training, prediction DB writes and production
predictions OFF. No inquiry sending, billing, permission changes or other work.
