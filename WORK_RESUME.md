# Work resume handoff

Updated: 2026-10-01 (Asia/Tokyo)

Use this file when resuming in ChatGPT Work.

## Resume command

If the user says only `続けて` in Work, resume from this exact boundary without redoing prior repository review work.

## Verified repository state

- Repository: `bzlove178100/-keirin-ai-web`
- Current verified `main`: `abee8b76e0538e4442961bdcbb0128297b1298a4`
- PR #146: AWS control-plane observation review merged.
- PR #147: status synchronization merged.
- PR #148: Work resume handoff merged.
- PR #148 exact-head CI passed before merge: collection progress UI regression, keirin-ai regression, and agent checkpoint PostgreSQL contract all succeeded.
- No open pull request was present at the 2026-10-01 resumption check.
- The previously pending final CI completion check is complete; no repository-review work needs to be repeated before AWS observation.

## Fixed safety state

Keep all of these unchanged unless the user separately authorizes the specific live boundary:

- hosted task/provider execution OFF;
- production prediction OFF;
- prediction DB writes OFF;
- automatic external race-data fetching OFF;
- provider generation/write unbound;
- scheduler/recurrence OFF;
- report delivery OFF;
- no real provider/OAuth refresh credential connected;
- no real refresh secret stored in custody;
- no C2 live secret-store DDL applied;
- no paid hardened host provisioned.

## Immediate next action in Work

Use an authenticated AWS console/browser session and perform **observation only**. Do not create or mutate any AWS resource.

Observe and record only sanitized facts required by `SECRET_CUSTODY_AWS_CONTROL_PLANE_OBSERVATION_REVIEW.md` and `review/lightsail_control_plane_observation.template.json`:

1. selected region is exactly `ap-northeast-1`;
2. an Ubuntu LTS Linux/Unix blueprint is available and its exact blueprint identifier;
3. the candidate bundle is available and matches exactly 2 vCPU / 1 GiB RAM / 40 GiB storage / 2 TB transfer;
4. displayed monthly bundle price is at or below USD 7;
5. static IPv4 availability and displayed pricing/conditions;
6. no automatic region or size substitution is required.

Unknown, ambiguous, unavailable, mismatched, or over-budget values are a hard stop.

## Do not do during observation

- do not create/start/stop/reboot/resize/snapshot/clone/delete an instance;
- do not allocate/attach/detach/release a static IP;
- do not create/change SSH keys;
- do not change firewall/network/DNS/load balancer/database/container/storage settings;
- do not change IAM/account/billing/support settings;
- do not change Supabase management settings or run C2 DDL;
- do not create/read/write Vault/provider credentials;
- do not enable hosted execution, prediction writes, race-data fetching, scheduling, or reporting.

## After successful observation

Report the observed sanitized values to the user and stop. Passing observation is **not** creation authorization. Ask for a separate explicit live-provision authorization before creating one Lightsail candidate and one static IPv4.

If authorized later, continue with exactly one candidate, then read-only/no-secret H1 preflight before any host mutation. Any live hardening, Supabase network restriction, Data API/SSL management change, C2 DDL, synthetic C3 credential, or C4 real credential activation remains a separate authorization boundary.
