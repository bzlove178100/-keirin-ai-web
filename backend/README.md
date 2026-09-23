# History/backtest regression checks

Run with Node.js 24:
```sh
node --test tests/history-backtest.test.mjs
```

Sources retrieved from deployed version 4 of history-builder-dev,
history-pipeline-dev and backtest-engine-dev on 2026-09-23.
Only backtest-engine-dev differs: aggregate full-distribution metrics require
210 distinct triples using cars 1–7 and probability mass within 0.02 of 1.
Partial-input per-race metrics remain diagnostic; full_probability_input identifies eligibility.
Selection ROI still uses settlement odds.

Tests use synthetic data and execute pure validation/calculation functions.
Deno.serve registration is ignored. No auth credentials, network, database,
or deployed HTTP calls are used. These tests do not verify authentication,
CORS, browser integration, or production deployment.

Baseline: 3 passed, 3 failed. Patched: 6 passed.
No Edge Functions have been redeployed by this change.
Actual saved input checked so far is raw race input, not a prediction snapshot.
A matching confirmed settlement is still required for real-race replay.
