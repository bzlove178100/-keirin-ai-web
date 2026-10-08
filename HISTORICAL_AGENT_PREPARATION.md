# Shared-agent historical preparation

`python -m agent_core.historical_preparation` connects the existing historical
preparation function to the shared `AgentRunner`, local task state, verification
and activity ledger. It is a one-shot offline diagnostic, not a worker, scheduler
or model-training command. It does not depend on note or a provider reply.

Supply an existing `historical-review-records-v1` document, a separate review
array and explicit chronological boundaries. Empty reviews are valid diagnostic
input: a completed job can have zero eligible races. Never invent reviews or
timestamps to pass the checks. Record hashes must match the current record bytes
under the existing canonical JSON digest; any evidence edit needs updated hashes
and a new final-record review.

```sh
python -m agent_core.historical_preparation \
  /private/records.json /private/reviews.json \
  --run-dir /private/preparation-run \
  --validation-start 2025-01-01T00:00:00+09:00 \
  --test-start 2026-01-01T00:00:00+09:00
```

These dates illustrate diagnostic boundaries only; this command does not adopt
an evaluation period. The caller must choose private storage outside this public
project and protect it from other writers. The launcher binds paths, whole-file
hashes and boundaries into a persisted task definition. It exposes no arbitrary
path arguments to runner actions and no train/fetch/DB/publish action.

The run directory contains `task.json`, `preparation.json` and `state/`. Report
creation refuses replacement of different existing bytes, including an interrupted
partial write. Verification rereads inputs and the saved output. A completed
resume checks the report again and does not rerun the action. Changed inputs,
reviews or boundaries require a new run directory. An interrupted attempt keeps
the shared runner's explicit reconciliation requirement; this launcher never
marks it resolved merely because an output file exists.

The CLI prints counts, hashes and task outcome, not record contents. Its task and
preparation artifacts still contain private paths/data and must stay outside git.
Local artifact readback does not prove durable remote saving or a device download;
the receipt deliberately leaves `durable_storage_verified` false. Archive the
private artifacts and record durable-save receipts separately.

## Observed application, 2026-10-08

The previously converted 208 private records were processed once through this
launcher with empty reviews. Preparation completed, all 208 remained excluded,
and train/validation/test counts were 0/0/0. A second invocation executed no steps
and verified the same output hash. No new races, source approvals or real model
training resulted. Synthetic tests cover a valid 2/1/1 partition, changed input,
changed reviews/boundaries, tampered output, interruption and conflicting output.

Before real learning: verify source-use and historical-time evidence, review exact
final records, secure continuous data coverage and choose an untouched evaluation
period. Hosted operation and BLOCKED_SUSPEND_EXPIRY_GAP are unaffected.
