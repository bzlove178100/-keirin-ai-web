# DNS observation reconciliation and first-install boundary

Prepared 2026-10-04 (Asia/Tokyo). Implemented: a pure, offline comparison of
selected reader facts. Proposed: resolver integration and first-install gates.
No live read, resolver change, firewall generation, installation or recovery.

## Problem and implemented boundary

PR #185 proved fixed dig transport; PR #186 proved fixed chrony source selection.
Neither established how a changing DNS configuration becomes an approved policy.
The accepted live reader observation is complete and must not be repeated merely
to produce another copy of the same evidence. Its source file remains unchanged.

`review/secret_custody_dns_reconciliation.py` consumes two in-memory
`LOCAL_NETWORK_DEPENDENCIES_V1` reports from the existing private reader shape.
It returns only fixed decision/reason codes and false gates. It has no I/O,
command, resolver query, timer, persistence, rule renderer or apply function.
Direct execution refuses. There is no new approval manifest or live adapter.
The tests feed synthetic D-Bus responses through the existing reader parsers;
this tests their composition, not an actual running resolver.

| Outcome | Meaning | Permitted automated action |
| --- | --- | --- |
| OBSERVATIONS_MATCH_REVIEW_ONLY | Selected facts match and the narrow DNS views agree | None; retain as review evidence |
| CHANGE_REVIEW_REQUIRED | Both views agree internally, but an endpoint, origin, interface or port representation changed | None; prepare a separately reviewed change |
| BLOCKED | Missing, malformed, unsupported or internally inconsistent evidence | None; identify the missing evidence, no automatic retry |

All outcomes include `qualification=false`, `mutation=false`,
`apply_allowed=false`, `freshness_verified=false`. No outcome approves an
endpoint, even if both managers report it. Outputs contain no endpoint, interface,
provider, private input hash or raw exception. Inputs are not modified.

The supported comparison is deliberately narrow: nonempty per-link numeric DNSEx
entries on configured/routable networkd links, explicit DHCPv4/DHCPv6 origin and
numeric provider, no fallback servers, and observed port token 0 or 53 with an
empty server-name field. The address/interface indexes must match in both views.
Addresses are canonicalized; order is ignored; duplicates are rejected. Provider,
interface identity and optional networkd port facts remain part of the comparison.
A changed provider with the same resolver is still a change. Disagreement stops
rather than selecting whichever reader is convenient.

The reader's zero-means-default token is preserved, never converted to a firewall
port. Zero versus explicit 53, and absent versus present networkd port, are
conservatively different observations. Even an explicit 53 is not evidence that
DNS-over-TLS is disabled. DNSOverTLS, routing/search domains, NSS selection,
per-link default-route decisions, resolv.conf ownership and effective fallback
behavior are outside this reader's evidence. Legacy DNS fields without DNSEx
metadata, global entries, local stubs, named servers, other ports, fallback,
non-DHCP origins and ambiguous scope require separate review. They are not
necessarily invalid configurations; this comparator cannot qualify them.

## Freshness and real resolver integration: required next evidence

These reports have no trustworthy collection generation, boot identity, process
identity or atomic multi-reader boundary. Replaying one report twice can yield
matching selected facts; this is explicitly not a freshness check. Equal indexes
can be reused, and a changed-then-reverted configuration can be missed. Endpoint
comparison does not check local address/route lifetimes or all unrelated network
facts. No runtime gate may treat this result as readiness.

The next isolated fixture must run a real resolver with its own mount/network
namespaces, configuration, runtime directory and private IPC. It must demonstrate
that the host resolver, host bus, resolv.conf and host services are untouched.
Do not use the host D-Bus to configure the fixture. Record exact binary identity.
The following are acceptance requirements, not current passing tests:

1. Use a private client path through the real resolver, not direct dig to upstream.
   Prove A/AAAA, UDP/TCP fallback, warm-cache hits and TTL expiry with upstream
   request counters and changed answers. A cache hit alone cannot prove egress.
2. Change a synthetic DHCP-supplied resolver; read actual manager/resolver state
   before and after, with bounded monotonic collection intervals and stable
   boot/interface/process identity. Interrupted or inconsistent reads fail closed.
3. Keep firewall ownership/shape unchanged for an unapproved changed endpoint.
   Require bounded lookup failure and exact deny evidence. Do not silently revert
   to public fallback or widen the allowlist from discovered addresses.
4. Test a separately pre-reviewed alternate and withdrawal/expiry under an explicit
   candidate generation; prove old/new traffic restrictions after independent
   restoration. Configuration restoration and firewall restoration are separate
   outcomes. Do not claim service recovery while they point to different peers.
5. Require controller-death recovery, existing/new administration, namespace/IPC
   isolation and complete cleanup. Cache, routing-domain, provider-origin and
   stale-generation failures must not become approval signals.

Passing this future fixture still would not authenticate DHCP/DNS providers,
prove DNSSEC/NTS, or authorize live endpoint acquisition or installation.

## First restricted installation: concrete stop and recovery decisions

Current fact: the host has no qualified restricted maintenance anchor and no
verified independently usable recovery path. Existing browser SSH is not accepted
as an independent path in the repository's maintenance design. A worker restoring
an identical wrong shared allowance cannot correct that allowance. This PR keeps
first installation blocked and defines the evidence required to reconsider it.

| Stage | Required evidence before advancing | Failure or ambiguous result |
| --- | --- | --- |
| Prepare | Separately reviewed restricted rescue profile and a recovery path demonstrated to work when candidate management, DNS and renewal allowances are deliberately wrong | Do not install; same-session/browser reachability and matching reports are insufficient |
| Own | Exact machine/boot/namespace/interface identities, current policy owners, candidate and rescue digests; exclusive writer protocol with documented limits | Unknown owner, drift or stale identity: no write; record unresolved state |
| Arm | Independent supervisor, bounded monotonic deadline, exact target binding, verified rescue material; controller may die without disarming recovery | No positive readiness: no write; worker death after readiness remains a blocker until qualified |
| Install | One reviewed transaction for all owned tables after fresh identity/shape readback; no blanket established-flow exemption | Transaction failure: inspect unchanged state; lost result: read back, never replay automatically |
| Verify | Exact rules plus fresh existing/new administration, dependency lifecycle, denied traffic and independently reachable recovery | Do not cancel supervisor based on nft exit, old socket survival or cached DNS alone |
| Rescue | Candidate still matches ownership and expected shape; apply the separately reviewed restricted rescue profile and verify traffic/state | Wrong shared allowance or drift is not solved by restoration; preserve no-secret/runtime-OFF state, escalate without opening policy |
| Finish/boot | Durable verified state and bounded interrupted-boot behavior, tested before any persistent installation | No verified boot behavior: no persistent installation; never enable runtime on unknown state |

No rescue may flush protection, restore an unfiltered baseline, open global SSH
or grant unrestricted egress under the current contract. The rescue policy must
be independent in the failure dimension being tested; renaming the maintenance
policy is insufficient. If the existing host cannot meet these prerequisites,
the future proposal must explicitly state the operational change needed and its
cost/access implications. This PR neither chooses nor performs replacement,
snapshot restore, new infrastructure, IAM expansion or a contract exception.

For an initial synthetic acceptance case, corrupt the candidate's administration
and DNS/renewal allowances while keeping an independently designed restricted
rescue path available. Kill the controller, prove that independent recovery can
act, then require exact restricted rescue shape, fresh administration/dependencies
and continued qualification denial. Also break the rescue path itself: this must
report unrecoverable/blocked rather than successful rollback. A private test path
is not evidence that the live host has such a path.

## Verification and remaining scope

Fourteen local comparison tests cover existing-parser composition, both IP
families, reordering/canonicalization, endpoint addition/removal/change, provider
and interface changes, default-port representation, mismatched managers, unknown
or counts-only evidence, fallback/stub/encrypted/named modes, missing origins,
duplicates, bounds, false gates and private-output redaction. They are mandatory
in the existing `custody-network-dependencies` CI job. The existing seventeen
regression jobs and all five final-head workflows remain required; exact run IDs
and merge receipt belong in the PR. No new kernel/resolver integration success
is claimed by these offline tests.

Next implementation: the isolated real-resolver fixture above. First-install
recovery, reboot, non-cooperating root writers and worker death after readiness
remain unqualified. Installed Ubuntu DHCPv6 remains unqualified; only the pinned
patched CI build has its separate lifecycle evidence. H2a and all runtime,
provider, credential, prediction, DB-write, data-fetch, scheduler and report gates
remain OFF. No phone, AWS, SSH, live host or credential action is requested.

## Repository evidence

- [Selected local reader](review/secret_custody_network_dependencies.py) and
  [its parser tests](tests/test_secret_custody_network_dependencies.py).
- [Accepted observations and initial-anchor decision](SECRET_CUSTODY_NETWORK_MAINTENANCE_DESIGN.md).
- [Fixed DNS transport evidence](SECRET_CUSTODY_DNS_RECOVERY_REVIEW.md).
- [Fixed chrony selection evidence](SECRET_CUSTODY_TIME_RECOVERY_REVIEW.md).
- [Independent recovery limits](SECRET_CUSTODY_DYNAMIC_RECOVERY_REVIEW.md).
