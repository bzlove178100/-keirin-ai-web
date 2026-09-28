# Host egress review

Updated: 2026-09-28 (Asia/Tokyo)

## Current verified base

PR #114 is merged on main at `7665d7a7fe0c668135cd41217692fb7ee851d970`.
Its post-merge main regression, PostgreSQL/host contract, collection UI regression and
Pages workflows all passed. The synthetic host image is pinned to an approved immutable
manifest, checked as Linux/amd64 by RepoDigest, and launched with the explicit
`/usr/local/bin/python3` entrypoint rather than a shell or upstream moving command.

Production prediction, prediction DB writes, automatic external race-data fetching,
hosted task/provider execution, scheduler/recurrence, provider generation/write and
live report delivery remain disabled.

## Synthetic approved-destination topology

This slice does not contact a real provider, database or public endpoint. It creates one
disposable Docker bridge network with `Internal=true` and bridge IP masquerading disabled.
The client and one synthetic approved TCP endpoint use the already pinned image, non-root
UID/GID, read-only filesystem, dropped capabilities, no-new-privileges, core limit zero,
Docker log driver `none`, and direct Python entrypoints.

Before client traffic starts, the outer observer requires exactly two network members by
full immutable container ID and exact name: the approved endpoint and the client. It also
creates a third unapproved synthetic peer and proves that the membership preflight rejects
the topology before traffic, then removes that peer and re-verifies the exact two-member
set. The approved endpoint IPv4 address is obtained from Docker inspection and injected
as a numeric value; no external DNS discovery is used.

Inside the client, the route table must contain no non-loopback default route. A direct TCP
exchange to the approved endpoint is the positive control. A connection to the
RFC 5737 documentation-only address `192.0.2.1` must fail with a routing-unreachable
error; timeout, refusal, permission error or success does not count as blocking evidence.
The exact network membership is checked again after the client exits. Containers and the
network are removed on completion/failure and residual network presence fails cleanup.

## What this does not qualify

This is an exclusive-segment topology contract, not a general firewall or production
service-mesh policy. It does not prove protection against a privileged Docker/host
administrator attaching another endpoint after preflight, Docker daemon compromise,
host routing/firewall mutation, DNS policy for a network-enabled deployment, IPv6
allowlisting, proxy bypass, real external-provider reachability, or production TLS
composition. A real deployment that shares a network with untrusted peers needs a
separate kernel/network-policy enforcement mechanism and its own fault tests.

No real credentials, real endpoint, migration, provider refresh, task execution or
production activation is introduced by this test.

## Next boundary after this slice

If exact-head Docker CI proves the contract, the remaining adjacent gate is host/platform/
database log custody and secret-redaction behavior, followed by deployment-specific daemon/
host fault and administration-boundary review before any real-backend migration or provider
refresh integration.
