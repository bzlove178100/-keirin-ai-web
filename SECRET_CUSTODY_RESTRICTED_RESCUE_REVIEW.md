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
qualification TCP/443 remains available in the candidate only. Dedicated
inet/netdev counters deny real DHCP client output and distinguish its hook path. The separate rescue profile keeps
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
are unchanged. Six rescue, seven chrony, six recovery, five DHCP DNS and four
composition tests pass locally (28 total), plus git diff --check. Corrected kernel
acceptance passed as recorded below; all five final-head workflows and twenty
regression jobs are required before integration.

## Initial failures and changed conditions

Initial rescue head `18ad1e1ea9edf9c7c5d7a0e4b20ffe03e707e944`, regression `37189213031`, job `111397692130`, failed before daemon startup at 17:32:04 JST: the unrelated sentinel table omitted a separator after its nested chain. The emitted nft error identifies the closing table brace. Add the same chain separator used by the existing dynamic fixture; policy shape/isolation/client deadlines and all fifteen acceptance requirements remain unchanged. No rescue acceptance record passed on that initial head.

The initial runtime smoke `37189213111`, job `111397691920`, separately reported verification_failed:github.verify_ci at 17:31:49 JST. It reads latest completed main CI, not this PR's kernel test. Direct Actions GET (the commit helper only lists pull-request events) revealed post-merge main regression `37188611863` on `dfbb572a7f101b3f979951b085bc93395444393f` failed time job `111395857615`. At 17:21:40 JST its origin-prime preparation exceeded twelve seconds after successful IPv4 silent-primary failover/return. The primary was selected, both sources had reach 255/poll 0; primary cumulative RX/valid/good were 31/31/20, alternate 39/39/39. The preparation baseline and per-packet rejection reason were not retained, so the precise cause is unproven. Earlier PR #191 final CI and this PR's unchanged time job `111397692121` both passed. The prior PR acceptance statement remains correct; its later main push run did not pass.

One targeted diagnostic rerun of that failed main time job is authorized by the existing CI workflow scope and has been requested on a newly provisioned runner, with code/assertions/deadlines unchanged. Hypothesis: runner-dependent scheduling/sample acceptance may affect fresh-phase preparation. New information: whether the failure reproduces and the actual fresh-phase/client/server counters in the second run. Success requires all fifteen existing records including all four fresh preparations; a pass does not establish a root-cause fix. If it fails again, stop identical reruns and inspect the retained diagnostics. Do not weaken main verification or bypass the final CI gate. The historical preparation reliability limitation stays recorded regardless of that result.

The single diagnostic rerun (main regression `37188611863`, attempt 2, time job `111398307405`) passed all fifteen records at 17:37:07 JST without code/deadline changes. Fresh good-sample deltas (primary, alternate) were IPv4 silent (4,4), IPv4 origin (4,5), IPv6 silent (4,4), IPv6 origin (4,4), with actual poll 0 throughout. This is successful reproduction on another run, not a root-cause fix or a reliability guarantee. The failed attempt remains evidence. The changed fixture now retains the preparation baseline and bounded last ntpdata snapshots on failure, while preserving the original exception, four-good-sample gate and all time limits. One diagnostic regression test passes; seven chrony plus nineteen rescue/reused tests pass locally (26 total). Future recurrence must use these diagnostics rather than repeated identical reruns. Chrony preparation reliability remains an explicit follow-up alongside recovery identity/worker-loss tests.

Corrected grammar head `64a3ae63f9190036bd574cd46e44663dc7eb597c`, regression `37189615299`, rescue job `111398888857`, passed all eight available-path records, including the wrong-shared-fallback control, real DHCP/DNS/admin denial after controller death, independent restoration, actual ACK/fresh answers, usable-rescue verdict and owned cleanup. At 17:40:03 JST the second case failed before daemon startup with EADDRINUSE when reusing the wildcard administration listener. Both cases shared one process/network namespace; the helper's daemon accept threads can outlive socket context closure, but the exact retaining descriptor was not captured. Each case now runs in a separate bounded child process and fresh network namespace, and the parent waits for full process exit before the next case. One new unit guard rejects reuse of the parent namespace. No traffic, lifetime or verdict assertion is weakened; all fifteen records including the broken-link BLOCKED result remain mandatory. Five rescue, six recovery, five DHCP DNS, four composition and seven chrony tests pass locally (27 total). Failure diagnostics now preserve the original chrony exception even if an auxiliary diagnostic read fails; the existing diagnostic test covers both outcomes.

Head `3ff7ced5deaafa790f70c0a24036bacf3a6ce937`, regression `37189773966`, rescue job `111399353028`, again passed all eight available-path records and reached the broken-case baseline. It then timed out waiting only for a netdev DHCP drop. The journal shows real ACK/T1/T2 setup at 17:43:05 JST and bound-to-renewing at 17:43:13; the twelve-second wait ended at 17:43:21 before observing the later-layer count. The candidate also denies normal UDP output at inet, so netdev-only measurement cannot establish absence of DHCP activity. The correction adds a dedicated matching DHCP drop counter at inet as well, requires fresh non-regressing progress in either layer, prints both before/after counts, and still requires no server receipt, a live address, unfinished recovery and separate-path availability. The twelve-second measurement and 22-second recovery windows are unchanged. A new local test rejects unchanged/regressing counts and covers either observed layer.

The same head's time job `111399353040` passed IPv4 fully, then failed IPv6's existing five-second post-restore two-good-sample wait at 17:43:32 JST. That earlier phase had not used the new diagnostic helper, so its exact baseline/rejection cause remains missing. The unchanged three-second post-controller and five-second post-restore predicates now use the same bounded diagnostic wrapper and preserve original sample/selection/reach requirements and failures. No blind rerun or deadline extension is used. Six rescue, seven chrony and fifteen reused tests pass locally (28 total). Corrected-code acceptance is recorded below.

## Corrected acceptance

Corrected code head `14fcf826654b16c6fd311e190203fbcb3c4322d6` (tree `56f40d20f7eff67f30a22785cfb03449b6201d79`), regression `37190000878`, rescue job `111400011794`, passed all fifteen records and `SYNTHETIC_RESTRICTED_RESCUE_OK_NO_LIVE_APPLY` at 2026-10-04 17:47:41 JST. Both AVAILABLE and BROKEN cases measured DHCP drops `{inet: 0, netdev: 0}` to `{inet: 1, netdev: 0}` with no new server receipt: this run directly observed denial at the earlier inet hook. Both cases restored exact restricted shape, revoked old/new qualification, reacquired actual DHCP ACK/fresh DNS/primary administration and cleaned up all owned resources. AVAILABLE verified the separate existing/new/bidirectional path; BROKEN correctly returned BLOCKED/RESCUE_PATH_UNAVAILABLE despite successful shape/primary recovery. All verdict gates remained false. Kernel `6.17.0-1022-azure` and networkd/resolved/dbus hashes match PR #191's recorded binaries.

The same head's time job `111400011614` passed all fifteen records at 17:47:53 JST, with fresh primary/alternate good-sample deltas (4,4) in each of the four IPv4/IPv6 silent/origin preparations and poll 0 throughout. Chronyd/chronyc hashes and version 4.5 match the previous recorded binaries. This validates the changed diagnostic code and original acceptance in this run; it does not establish a fix for the missing historical rejection causes. Four other workflows had passed and the existing DHCPv6 lifecycle job was still running when this targeted evidence was recorded. All five final-documentation-head workflows and twenty regression jobs remain required before merging PR #192; exact final results and merge receipt belong in that PR. No additional identical diagnostic rerun is planned; any recurrence must use the new retained baseline/ntpdata evidence.

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
