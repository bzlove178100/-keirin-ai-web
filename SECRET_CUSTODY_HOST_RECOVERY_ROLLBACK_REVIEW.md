# Secret-custody host recovery and rollback review

Reviewed: 2026-09-30 (Asia/Tokyo)
Status: **review only — no live recovery, rollback, host mutation, AWS action, database change, or secret operation is authorized**

This review defines the failure-handling boundary for the future secret-custody host before any real credential, C2 binding, or hosted runtime activation exists. It is intentionally limited to repository-side planning and validation.

## Safety objective

A failed host qualification must leave the system in a safer state, not attempt to recover by widening permissions, opening network access, enabling services, or touching unrelated data.

The default response to uncertainty is **fail closed**:

- runtime remains disabled;
- host remains no-secret;
- no provider credential is introduced;
- no Supabase custody DDL is applied;
- no Vault row or binding is created;
- no prediction/race-data state is changed;
- no AWS resource is automatically deleted, resized, rebooted, snapshotted, or replaced;
- no firewall or egress policy is automatically relaxed.

## Recovery classes

### R0 — preflight mismatch

If the live candidate later differs from the reviewed region, bundle, operating-system assumptions, listener state, swap state, cgroup shape, or required tooling, stop before hardening. Record only sanitized facts. Do not compensate by weakening the reviewed contract.

### R1 — hardening verification failure

If a separately authorized hardening run later fails ownership, sandbox, listener, egress, reboot, process-tree, log-redaction, or resource checks, keep the runtime disabled. The host is treated as untrusted and may not receive any database password, Vault material, provider credential, or production task.

### R2 — network/TLS qualification failure

If default-deny egress, approved-destination access, TLS `verify-full`, hostname validation, CA validation, or timeout behavior cannot be proven, stop. Do not widen outbound access or fall back to plaintext/insecure TLS.

### R3 — capacity failure

OOM, sustained memory pressure, or inability to preserve the required sandbox rejects the 1 GB candidate. Security controls are not weakened to preserve the USD 7 target.

### R4 — reboot/recovery failure

If reboot does not preserve the intended disabled-runtime and firewall state, the candidate remains untrusted. No credential or Supabase allowlist change may follow.

## Pre-credential rollback invariants

The declarative plan in `review/secret_custody_host_recovery.plan.json` is valid only while all of these are true:

- no real provider/OAuth credential exists on the custody path;
- no custody database password has been delivered to the host;
- no C2 binding exists;
- hosted runtime/provider execution remains disabled;
- no active secret-host process is using the reviewed runtime identity or files.

Rollback sequencing must preserve isolation. It must not touch the Supabase custody schema, Vault, prediction state, race-data state, or provider account state.

AWS resource destruction is deliberately outside this plan. If a candidate is rejected, destroying the paid host later requires a separate explicit live AWS action after sanitized evidence is preserved.

## Evidence policy

Only sanitized metadata may be retained in repository-visible evidence: pass/fail state, class of failure, reviewed control name, timestamps, software versions, and non-secret resource measurements. Do not commit live IP allowlists, AWS account identifiers, private hostnames, connection strings, environment values, credentials, provider account identifiers, private file identifiers, prediction snapshots, or race histories.

## Offline validator

`review/validate_secret_custody_host_recovery_plan.py` reads only repository JSON. It performs no subprocess call, network access, AWS/Supabase action, filesystem mutation, service control, package operation, firewall mutation, or secret lookup.

It rejects accidental live authorization, enabled runtime/provider/prediction gates, permission to touch protected data domains, automatic destructive AWS recovery, automatic network relaxation, credential-like literals, or world-open CIDRs.

## Exit from this boundary

This recovery review does not authorize the next live step. Live progression still requires, in order:

1. authenticated AWS confirmation of exact Tokyo availability, Ubuntu LTS blueprint, and displayed price;
2. explicit live-provision authorization before creating one instance/static IPv4;
3. read-only/no-secret H1 preflight;
4. review of actual host facts;
5. separate live-hardening authorization before any host mutation;
6. successful no-secret verification before any Supabase network restriction, C2 DDL, or credential exists.

## Non-authorization

This review does not authorize or perform AWS provisioning/deletion/reboot/resize/snapshot, firewall mutation, package installation, user/service creation, Supabase management changes, C2 DDL, database passwords, Vault/binding creation, provider credentials/actions, hosted execution, scheduling, report delivery, production prediction, prediction writes, or external race-data fetching.
