# Restricted rescue under wrong shared allowances — CI only

Prepared: 2026-10-04 (Asia/Tokyo).

## Problem and concrete scope

A worker restoring the same incorrect administration/DHCP/DNS allowances cannot
correct that shared error. This slice adds a separately fixed rescue profile and
an actual second veth with fixed documentation addresses and static neighbors.
The link has no DHCP, DNS, ARP or default-route dependency. Only its exact peer
TCP/22 tuples in both directions are allowed, with inet connection-state checks,
netdev source MAC/address/port checks, fragment denial and default-drop chains.
It shares the kernel, namespace and owned tables with the primary link. This is
independence from the tested allowance fault, not a general out-of-band channel.
TCP echo proves transport only, not SSH authentication or a trusted recovery user.

The candidate and ordinary fallback deliberately replace primary approved peer
addresses with incorrect fixed peers. Their primary ARP rules stay unchanged;
qualification TCP/443 remains available in the candidate only. A dedicated
netdev counter denies real DHCP client output. The separate rescue profile keeps
its own fixed correct primary allowances and static-link rules. It is never
constructed from a discovered address or the corrupted candidate/fallback.
No policy flush, global SSH, unrestricted egress, credential or live apply exists.

`test_secret_custody_restricted_rescue.py` and the fixed `rescue` key in the
existing dynamic recovery fixture are CI-only. The controller and worker retain
root/CI/private-network/PID-1 guards, owned private readiness material, pidfd/start
checks, cooperating lock, known shape checks, bounded 22-second deadline and one
nft transaction for both tables. The worker's RESTORE_MAINTENANCE means exact
shape restoration only. A separate verifier requires traffic/dependency evidence
and never equates this string with usable rescue. All verdicts keep qualification,
mutation, apply_allowed and freshness_verified false.

## Mandatory acceptance (fifteen records)

Each of the available and broken-link cases requires seven records:

1. Prove rescue TCP/22, disallowed peer source and port before filtering. Under
   restriction prove exact static rescue access, deny that other source/port and
   qualification, then acquire real DHCP DNS and query the private resolver.
2. Arm independent recovery; kill the applying controller. Require lost existing
   and new primary administration, a new denied DNS transaction/output drop with
   no upstream receipt, and real networkd DHCP output drops with no server receipt.
   The separate static path still works and the worker has not yet restored.
3. After the independent deadline, require exact rescue shape, worker process/unit
   and private-file cleanup, and denial of old/new qualification TCP/443.
4. Require an actual new DHCP ACK, address/route/lease/DNSEx, drained pending DNS
   work, fresh A/AAAA/TCP upstream events, primary administration and unchanged
   daemon identities/unrelated sentinel table.
5. Available rescue must have fresh bidirectional and existing/new peer-to-host
   transport. In the broken case, lower rescue0 after readiness and before the
   deadline: restoration/primary recovery still occur, but the missing rescue path
   must produce BLOCKED/RESCUE_PATH_UNAVAILABLE. No automatic link repair occurs.
6. Private networkd/resolved/bus processes, runtime and cgroup are cleaned up.
7. Both peer processes, links and owned tables are cleaned up.

The available case additionally requires a negative control: candidate and wrong
ordinary fallback each fail primary existing/new administration and distinct A
then AAAA transactions, while the separate path remains available. The observer
explicitly resets the fixture to restricted rescue before arming the independent
worker; that reset is setup, not a claimed automatic recovery. No unfiltered
fallback is used. A cache/coalesced DNS failure does not count as a new transaction.

The dynamic fixtures retain their original mandatory jobs. This slice adds the
twentieth job with a five-minute bound; existing client/daemon/worker deadlines
are unchanged. Four new scope/verdict tests, six recovery, five DHCP DNS and four
composition tests pass locally (19 total), plus git diff --check. Actual kernel
acceptance is pending; all five final-head workflows and twenty regression jobs
are required before integration.

## Unqualified boundaries and next step

The fixture begins from an already tested restricted anchor and cannot authorize
first installation on the live host. No live independent interface/route/source
approval has been established. It does not repair a dead rescue link, survive
kernel/network-namespace/table-wide failure, authenticate DHCP or administration,
exclude non-cooperating root writers, qualify boot/persistence, or survive worker
death after its final readiness check. Source/interface identity drift and loss
of the worker after readiness remain next review/test requirements. Shape checks
and flock are not a kernel compare-and-swap. Broken path is a blocked outcome even
when qualification revocation and primary dependency recovery succeed.

Do not repeat accepted phone evidence or infer a need to create resources. No
phone/AWS/SSH/live host/credential work occurred. H2a and every runtime/provider/
credential/prediction/DB-write/data-fetch/scheduler/report gate remain OFF.

Related repository evidence: [first-install stop decisions](SECRET_CUSTODY_DNS_RECONCILIATION_REVIEW.md),
[independent worker limits](SECRET_CUSTODY_DYNAMIC_RECOVERY_REVIEW.md),
[real DHCP DNS lifecycle](SECRET_CUSTODY_DHCP_DNS_REVIEW.md), and
[the new executable acceptance fixture](tests/test_secret_custody_restricted_rescue.py).
