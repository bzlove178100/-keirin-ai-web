# General agent capability contracts

Updated: 2026-09-25.

This document maps the broad autonomous-agent goal into explicit capability names. It is a contract and activation boundary, not proof that any provider is connected.

## Declared capabilities

- `research.read_public_sources` — public-source research, read access.
- `text.generate` — text generation/transformation, execute access.
- `image.generate` — image generation/editing, execute access.
- `video.generate` — video generation, execute access.
- `code.generate` — code generation/transformation, execute access. This does not apply repository writes by itself.
- `learning.evaluate` — model/task evaluation, execute access.
- `report.generate` — activity/sales report generation from already-available inputs, execute access.

Report delivery remains a separate `report.deliver` write capability.

## Default state

All broad capabilities are disabled/unbound by default. Declaring a capability does not grant provider authorization, connect credentials, enable scheduling, execute a task, persist state, or perform network access.

Hosted runtime diagnostics must continue to distinguish `declared`, `bound`, `authorization_state`, `authorized`, `verified`, and `last_error`.

## Activation rules

Before a capability becomes live:

1. identify the concrete provider/host;
2. define required permissions and the smallest access class (`read`, `execute`, or `write`);
3. keep provider credentials out of task definitions and the public repository;
4. verify the provider binding independently;
5. add targeted regression coverage;
6. preserve existing keirin safety boundaries unless separately authorized.

`research.read_public_sources` must not be interpreted as permission to enable automatic keirin race-data fetching while that feature remains OFF.

`report.generate` must not be interpreted as report delivery. Delivery destination and scheduling are separate concerns.

## Current safety boundary

This capability-contract change does not:

- enable hosted task persistence;
- enable development database writes for keirin prediction flows;
- enable production prediction;
- enable automatic keirin race-data fetching;
- connect text/image/video model providers;
- connect a sales source or report destination;
- enable the 21:00 report schedule.
