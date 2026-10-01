# Secret-custody host hardening review

Reviewed: 2026-09-30 (Asia/Tokyo)
Status: **declarative review; only the separately specified H2a identity/files scope has live authorization**

Progress update: 2026-10-02 01:18 JST. H1 and H2a succeeded; H2b passed at 00:46 JST (IMG_8926, PR #168) and H2c synthetic memory verification passed at 01:16 JST (IMG_8927, PR #169). The continuation proceeds to [H2d synthetic process-failure verification](SECRET_CUSTODY_HOST_H2D_REVIEW.md); its live result is pending. Persistent H2a installation stays unchanged. Full H2-H7 qualification remains pending; this document grants no additional mutation scope or real credential/runtime use.

This review turns the selected Amazon Lightsail Tokyo 1 GB candidate into a staged host-qualification plan without provisioning AWS resources or enabling any agent runtime.

## Boundary

The separately authorized first paid candidate remains **untrusted / no-secret**. It may not receive:

- a custody database password;
- a Vault secret or provider credential;
- a custody-project service key;
- a production task payload;
- provider OAuth material;
- a live hosted worker activation.

It earns trust only after the local-host, network, TLS, restart and resource gates below pass with synthetic/no-secret inputs.

## H0 — immutable identity and billing guard

Before any instance is created, re-check the current Lightsail Tokyo Micro 1 GB price and availability. Create exactly one candidate, attach one static IPv4, and record the resource identifiers privately.

Fail if the selected bundle, region, static-IP semantics, or price differs materially from the reviewed candidate. Do not silently select a larger or more expensive bundle.

## H1 — local host preflight

`review/lightsail_host_preflight.sh` is intentionally read-only and offline. It does not install packages, edit files, change the firewall, contact AWS/Supabase/GitHub, inspect secret stores, or print environment-variable values.

Required local shape before hardening work continues:

- Linux kernel;
- systemd available;
- cgroup v2 mounted;
- the existing script's reviewed 1 GB-class floor of at least 900000 kB usable MemTotal (not a claim of 1 GiB usable RAM or workload headroom);
- no active swap before secret-host qualification;
- `nft` available before any egress policy can be qualified;
- `systemctl`, `ss`, `ip`, `findmnt` and `stat` available;
- no unexpected listener bound to a non-loopback wildcard address;
- core-dump policy can be disabled for the eventual service.

The script emits only non-secret host facts. Missing tooling is a blocker, not a reason to weaken the contract.

## H2 — administrator and filesystem boundary

The bounded [H2a identity/files implementation](SECRET_CUSTODY_HOST_H2A_REVIEW.md) has explicit apply/verify/rollback guards. The user authorized its exact scope; corrected installation and verification now succeeded. The failed first attempt was recovered, and must not be retried. It installs only an inactive placeholder. H2b proved the measured basic controls; H2c proved its bounded synthetic ephemeral-storage/descriptor checks. H2d now prepares service-parent and launcher failure tests under that transient profile. Broader sandbox, network, capacity and recovery qualification remains incomplete.

The later mutating hardening package must be reviewed separately before execution. It should:

- create a dedicated non-login service identity for the secret-host process;
- keep AWS/SSH/bootstrap administration separate from the runtime identity;
- prevent the runtime identity from using `sudo`, Docker/container-daemon control, package management, kernel interfaces or cloud metadata credentials;
- use root-owned configuration with no group/world write access;
- use a read-only application/code location at runtime;
- provide only a bounded private runtime directory and tmpfs-style ephemeral secret handoff;
- disable core dumps for the service and keep `NoNewPrivileges=yes`;
- use `ProtectSystem=strict`, `ProtectHome=yes`, private temporary space and the narrowest compatible systemd sandboxing;
- set explicit memory/PID/CPU limits rather than relying on host-wide free capacity.

Do not add a swap file to make the 1 GB bundle pass. If memory is insufficient without weakening the security boundary, reject the 1 GB candidate and qualify the next reviewed size.

## H3 — inbound boundary

The Lightsail platform firewall and host firewall must both be reviewed.

Target state:

- no public HTTP/HTTPS listener;
- no public agent/runtime listener;
- SSH only during bounded administration from an approved source, then reduced or removed where a reviewed recovery path permits;
- IPv4 and IPv6 treated independently;
- no wildcard application listener on the host;
- host-local management endpoints bind loopback only.

A default cloud image's convenience rules are not accepted as the final state.

## H4 — outbound boundary

Lightsail's platform firewall does not supply the required outbound restriction, so the host must enforce it locally.

The final nftables policy must be generated only after the exact runtime destinations are known. It must be **default deny**, not a broad internet allow rule.

The intended sequence is:

1. bootstrap/update phase with a separately bounded temporary destination set;
2. freeze package/runtime provenance;
3. resolve and record the exact reviewed runtime endpoint/address lifecycle;
4. install the runtime egress policy atomically with a rollback path;
5. prove an approved destination works;
6. prove an unapproved documentation-only destination is rejected;
7. prove policy survives reboot;
8. only then allow the host static IPv4 into the custody database network restriction.

DNS-based destination drift must not silently widen egress. If a required service cannot be represented safely with stable addresses or a separately reviewed proxy boundary, stop and redesign rather than allowing unrestricted outbound traffic.

## H5 — TLS/database boundary

Before C2 DDL or any password exists, the host must prove the transport path using no-secret/synthetic qualification material where possible:

- expected database/pooler hostname only;
- TLS `verify-full`;
- reviewed CA path/pin lifecycle;
- wrong hostname rejected;
- wrong CA rejected;
- plaintext rejected;
- bounded connect/statement/lock/process deadlines;
- no automatic write replay;
- direct-login identity and primary/read-write state checks.

Actual custody-login creation and password delivery remain separate later boundaries.

## H6 — resource and recovery qualification

The 1 GB candidate must pass evidence-based capacity checks rather than merely booting:

- no kernel OOM kill during the exact hardened process composition;
- no sustained memory pressure that threatens supervision/recovery;
- cgroup memory/PID/CPU limits effective;
- process tree terminates on parent/controller failure;
- service does not resurrect stale work after restart;
- machine reboot preserves intended firewall/static-IP/service-disabled state;
- unexpected reboot before runtime activation leaves the system fail closed;
- logs contain no secret-bearing environment, connection string, SQL bind value or raw credential exception.

Failure caused by resource pressure rejects the bundle; safeguards are not relaxed to preserve the USD 7 target.

## H7 — activation gate

Passing host hardening still does not authorize secret use. Before C2/C3, all of the following must also be true:

- Data API confirmed disabled on the custody project;
- Postgres SSL enforcement confirmed enabled;
- network restrictions contain only the verified hardened-host egress CIDR set;
- C2 DDL receives separate explicit authorization and passes its fresh database preflight;
- rollback remains valid with zero bindings/secrets;
- synthetic C3 material is clearly non-production.

Real provider credentials remain a later C4 boundary with a separate availability/cost decision.

## Read-only preflight package

The repository includes `review/lightsail_host_preflight.sh` only to make H1 repeatable. It is deliberately incapable of applying firewall or OS changes.

Local-file invocation (the completed run used the equivalent hash-checked in-memory loader):

```text
sudo -n /bin/sh review/lightsail_host_preflight.sh
```

The script must fail if it cannot prove the expected local shape. Its output may be copied into private qualification evidence after review, but public repository evidence should contain only a sanitized pass/fail summary.

## Non-authorization

This review does not authorize AWS provisioning or charges, static-IP allocation, SSH/IAM creation, package installation, firewall mutation, Supabase management-plane changes, C2 DDL, database passwords, Vault/binding creation, provider refresh/write, hosted task execution, scheduler/recurrence, report delivery, production prediction, prediction DB writes, or external race-data fetching.
