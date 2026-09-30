# Secret-custody host hardening package review

Reviewed: 2026-09-30 (Asia/Tokyo)
Status: **review only — no live host mutation, AWS action, secret access, or database change is authorized by this package**

This package prepares the mutating-host hardening boundary without executing it. It exists so the future Lightsail host can be hardened from a reviewed, fail-closed plan after the no-secret H1 preflight has been run and inspected.

## Safety boundary

Nothing in this review may:

- create, stop, reboot, resize, snapshot, or delete an AWS resource;
- change a Lightsail firewall or static IP;
- install or remove packages on a live host;
- create users, groups, services, files, firewall rules, sysctls, or credentials on a live host;
- contact Supabase, AWS, GitHub, or any provider endpoint;
- read or write Vault, provider credentials, database passwords, race data, prediction data, or production data;
- enable hosted task/provider execution, scheduler/recurrence, reporting, production prediction, prediction DB writes, or race-data fetching.

The machine remains **untrusted / no-secret** until a separately authorized live hardening run passes all postconditions.

## Reviewed hardening phases

The plan is represented in `review/secret_custody_host_hardening.plan.json`. It is data, not an executable shell script.

### P0 — identity and preconditions

Require an exact match to the reviewed Lightsail candidate and a completed no-secret H1 preflight. Reject any automatic size upgrade, region substitution, unexpected listener, active swap, missing cgroup v2, or missing required host tooling.

### P1 — runtime identity and filesystem

The future package may create exactly one dedicated non-login service identity. Runtime configuration must be root-owned and not group/world writable. Application code must be read-only to the runtime identity. Secret handoff must use bounded ephemeral memory-backed storage only after the later credential boundary is separately authorized.

No cloud-management credential, AWS access key, Supabase service key, provider credential, or private SSH key may be placed in runtime environment variables.

### P2 — systemd sandbox

The eventual unit must remain disabled until qualification is complete and should enforce, where compatible:

- `NoNewPrivileges=yes`;
- `ProtectSystem=strict`;
- `ProtectHome=yes`;
- private temporary space;
- bounded memory, process, and CPU limits;
- core-dump suppression;
- explicit writable-path allowlist only;
- termination of the complete process tree when supervision fails.

A resource-limit failure rejects the 1 GB candidate; it does not justify weakening the sandbox.

### P3 — inbound network

Target state is no public HTTP/HTTPS/runtime listener. SSH, if temporarily required for bootstrap, must be restricted to a separately approved administrative source and removed or narrowed after a reviewed recovery path exists. IPv4 and IPv6 are qualified independently.

### P4 — outbound network

The operating-system firewall must implement default-deny egress. The final allowlist is generated only after exact required runtime destinations are known. The plan must never contain `0.0.0.0/0` or `::/0` as runtime egress allowances.

Bootstrap/update access and runtime access are separate phases. Broad internet egress is not carried forward into runtime.

### P5 — logging and crash material

The runtime must not emit credentials, connection strings, SQL bind values, secret-bearing environment values, private allowlist addresses, or provider account identifiers. Core dumps remain disabled. Logs are metadata-only and bounded.

### P6 — verification before trust

After a separately authorized hardening application, but still before any real credential exists, require evidence for:

- expected service identity and file ownership;
- sandbox directives effective;
- swap disabled;
- no unexpected wildcard listener;
- default-deny egress effective;
- approved egress succeeds and an unapproved documentation-only destination fails;
- rules persist after reboot;
- no OOM kill or sustained memory pressure under the exact process composition;
- process tree terminates on controller failure;
- logs remain free of secret-bearing material.

Only after those checks may the verified static egress address be considered for the later Supabase network restriction.

## Rollback boundary

Before any real credential or C2 binding exists, rollback must be structural and fail-closed:

1. keep runtime disabled;
2. remove runtime firewall allowances before relaxing any other isolation;
3. remove the reviewed service unit/configuration and dedicated runtime identity only after proving no process is using them;
4. preserve evidence required to diagnose the failed qualification;
5. do not touch the Supabase custody schema, Vault, provider credentials, prediction state, or race-data state.

After any real credential exists, this simple rollback is no longer sufficient; provider revocation, credential rotation, quarantine, backup/retention handling, and incident review become mandatory separate procedures.

## Offline validation

`review/validate_secret_custody_host_hardening_plan.py` validates only repository data. It performs no network call, subprocess execution, filesystem mutation outside reading the plan, package operation, firewall change, or service control action.

The validator fails if the plan becomes live-authorized, contains a world-open CIDR, enables runtime/provider/prediction gates, or embeds credential-like fields.

## Non-authorization

This review does not authorize or perform AWS provisioning, host hardening, firewall mutation, package installation, systemd changes, Supabase management changes, C2 DDL, database passwords, Vault/binding creation, provider credentials/actions, hosted execution, scheduling, report delivery, production prediction, prediction writes, or external race-data fetching.
