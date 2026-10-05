# Kernel qualification lease — unactivated synthetic implementation

## Restricted rescue composition (2026-10-05)

The explicit `rescue-lease` profile reuses the fixed DHCPv4 guard tuple while
retaining the distinct rescue policy. Both host0 and rescue0 identity bind the
prepared receipt and worker. A guarded alias must never omit rescue0 from the
context; local tests require rescue-only index/MAC drift to stop recovery.

A new mandatory job runs available and broken static rescue paths in separate
private namespaces. With primary administration, real DHCP and DNS deliberately
denied after controller death, the original eight-second guard must revoke old
and new TCP/443 while candidate rules and the same 22-second worker remain.
The available TCP/22 rescue path must survive expiry; bringing rescue0 down must
remain an unavailable path despite subsequent successful table restoration.
The same worker restores maintenance without guard renewal. Actual DHCP ACK,
fresh upstream A/AAAA and primary administration must return in the same private
daemons, while wrong rescue source/port remains denied and guard handles survive
through the final verdict. Owned cleanup removes all guards and private resources.
The original unguarded controls remain mandatory; regression now has 26 jobs.
Exact final-head and main-push receipts belong in the PR, not inferred from local
tests. BLOCKED/RESCUE_PATH_UNAVAILABLE cannot be promoted by table shape alone.

This is a same-kernel synthetic second veth and TCP echo, not an authenticated
out-of-band SSH channel. Restart/boot/suspend evidence invalidation, privileged
guard tampering, arbitrary endpoint changes and first live installation remain
open. The next safe slice examines evidence invalidation in isolation without
rebooting/suspending a live host. All activation gates remain OFF.

## Real chrony composition (2026-10-05)

The existing prepared `time-lease` boundary now has a mandatory real chrony
client case for each family in a distinct private namespace. The original
unguarded fifteen-record job stays mandatory. Eight-second kernel expiry must
deny old/new qualification while candidate rules and the same 22-second worker
remain. After expiry, both approved sources must provide two fresh good samples
within five seconds, with primary selection and existing/new management intact.
The same capability-free client continues through late maintenance restoration,
silent and wrong-origin failover, actual rejection, approved return and denial
of unapproved sources/transports. Guard handles stay unchanged until teardown.

This new continuity check does not relax the existing four-good-sample fault
preparation, completed burst, interleaved/kernel RX/TX requirements or the
3/5/12/35/20-second sample/preparation/failover/return bounds. No old samples,
one-peer-only progress or fallback to an unguarded run can pass the guarded case.
One new CI job brings regression to 25 mandatory jobs. Exact final-head and main
receipts belong in the PR. Local tests alone do not prove kernel behavior.

Clients and servers retain nobody, zero capabilities, NoNewPrivs and `-x -U`;
the host clock is never changed. Same-clock synthetic sources do not qualify
external UTC accuracy, NTS, real credentials or a live host. Restricted rescue
under the guard, arbitrary endpoint changes, reboot/suspend, privileged guard
tampering and first live installation remain open. All activation gates stay OFF.

## DHCPv6 composition (2026-10-05)

The explicit `dhcp6-lease` profile uses the same fixed IPv6 qualification tuple
as `ra6`, but retains the distinct DHCPv6 maintenance/candidate policy. Shared
preparation, worker readiness and both controller checks require the original
bound eight-second guard receipt. Restoration never replaces the guard tables.

The existing DHCPv6 CI job keeps the unpatched timer-defect control, pinned
patched lifecycle and unguarded recovery mandatory, then adds a guarded run in
a fresh private namespace using the same hash-verified client build. After
controller SIGKILL, old/new qualification must expire while candidate tables
and the same 22-second worker still remain. A new Renew after observed expiry
must refresh actual address lifetime and both-layer DHCPv6 counters before
worker restoration, with existing/new administration still working. The worker
must then restore maintenance without rearming. Wrong-source packet rejection,
another Renew, alternate-DUID Rebind and real address expiry with the RA route
remaining all continue under unchanged guard handles. Teardown removes both
guards and the original owned resources; the namespace must be empty.

All five final-head workflows and all 24 regression jobs are required before
merge; exact CI and independent main-push receipts are kept in the PR. This
qualifies only the pinned patched CI client and fixed synthetic addresses.
Arbitrary renumbering, the installed Ubuntu/live client, guarded chrony/rescue,
reboot/suspend, privileged guard tampering and first live installation remain
outside this proof. All activation gates remain OFF.

## Defect and mechanism

PR #193 demonstrated that process liveness checks and nft installation are not
atomic. If the worker dies after the final check, the controller can install an
unbounded qualification allowance before also dying. Identity fail-stop can
similarly leave existing candidate rules active.

The pure renderer in `review/secret_custody_qualification_lease.py` creates separate
inet and netdev guard tables before worker readiness. Each has a timed service
set with one TCP/443 element and a fixed eight-second lifetime. Exact documentation
source/destination addresses gate both IPv4 and IPv6. Inet additionally binds the
observed interface index; netdev attaches to the fixed fixture interface. Both
directions check the timed membership on every qualification packet. Nonmatching
TCP/443 is dropped; remaining traffic continues to the existing default-deny
maintenance/candidate policy, so the guard cannot independently open a service.

Candidate/restore replaces only its own two tables, never the guards. No timer
starts in the controller and no packet refreshes it. Repeated installation uses
`create table`, which fails on existing ownership without resetting set contents.
The entire initial guard creation is one nft transaction. Its one-minute GC
interval exceeds the eight-second timeout; matching must expire independently of
garbage collection. The read-only observer does no mutation while awaiting expiry.

Official reference: [nftables element timeouts](https://wiki.nftables.org/wiki-nftables/index.php/Element_timeouts).
This documents timed membership and possible recreation/packet-path refresh;
the implementation deliberately exposes neither as a renewal mechanism.

## Mandatory evidence: four cases, twenty records

Each case runs in a fresh child/network namespace with synthetic static neighbors,
private peer TCP listeners, existing/new administration, owned tables and unrelated
sentinel. No real endpoint, clock adjustment, credentials or host firewall apply.

| Case | Required result |
| --- | --- |
| Normal | Controller SIGKILL; existing PID 1 worker restores maintenance within its unchanged five-second window; guard also expires |
| Worker loss | Hold controller after last successful check, SIGKILL worker and observe process absence, resume candidate apply/controller SIGKILL; active old/new IPv4/IPv6 qualification subsequently expires without any restoring process |
| Delayed apply | Same worker loss, but keep controller held beyond the original lease; late candidate installation never opens qualification |
| Identity drift | Change real host MAC and peer neighbor after candidate apply; worker reports context fail-stop; still-present candidate cannot keep old/new qualification after lease expiry |

All cases require five records: restricted baseline/armed guard; controller death
and chosen fault; dual-family old/new revocation with administration preserved;
rearm rejection and two candidate replays after expiry; complete owned cleanup.
Old sockets send traffic while time passes, so established traffic cannot refresh
the timer. Guard object handles stay constant. The replay controls explicitly
mutate candidate tables only AFTER expiry; they are not reported as recovery.
Worker-loss cases use the existing 22-second worker readiness window, with kernel
expiry eight seconds after the earlier guard creation. Other scenarios retain the
existing five-second recovery window. No existing acceptance is relaxed.

Four pure/isolation tests and eight existing context tests pass locally. Actual
kernel evidence is required from the new twenty-second regression job. All five
applicable workflows must succeed at the final head before integration. Exact
run evidence and merge receipt are retained in the PR.

## Limits and next integration boundary

Expiry is effective transport revocation, not table-shape restoration or proof of
hosted readiness. Fixed TCP echo does not establish authenticated SSH. A broken
management route still needs independently qualified rescue. The existing time
profile supplies fixed dual-family maintenance; this test does not run chronyd
or qualify all DHCP/RA/DNS/rescue dependencies together with the guard.

This renderer has no CLI/apply/renew entry point and is not bound to a live host.
The fixture owns the guard installation independently of candidate/restore. A
real installation must enforce/verify guard ownership and the baseline before
readiness, and must never reload an expired timed set from a saved ruleset. Root
writers can still delete/rearm tables; no protection from arbitrary privilege is
claimed. Interface replacement/reused index, reboot/suspend, persistence and
first live install remain outside this proof. Existing unguarded negative tests
remain necessary controls, not indications that all legacy profiles gained expiry.

Next qualify the guarded installation and ownership path with required dynamic
dependencies before proposing any live apply. All runtime/provider/credential/
prediction/DB/data-fetch/scheduler/report gates remain OFF.

## Initial failure and corrected fixture setup

Head da5c78bb98d1f8f6c5a40a8757d4d33405cdda69, lease job 111457986532: first three cases passed fifteen records; MAC drift then failed administration before expiry. Linux v6.17 NETDEV_CHANGEADDR flushes the host ARP/ND neighbors, including permanent entries. The prior fixture updated only peer mappings. Corrected setup verifies local mappings disappeared, restores the original fixed static peer mappings, and updates the peer for the changed host MAC before measuring lease behavior. This explicit test setup is not claimed as automatic network repair. The real MAC remains changed, so the worker must still fail-stop.

Primary sources: https://github.com/torvalds/linux/blob/v6.17/net/ipv4/arp.c , https://github.com/torvalds/linux/blob/v6.17/net/ipv6/ndisc.c , https://github.com/torvalds/linux/blob/v6.17/net/core/neighbour.c .

## Corrected code acceptance


Corrected code head `1f4f4bd34ec10200fea82b528a5062163c5fdff3` (tree `e9de122079cad46efdaf799012205c8d8d044350`), regression `37210048538`: lease job `111459213686` passed all twenty records at 23:40:13 JST. The MAC-change readback was actually `[]`, confirming local neighbor removal; explicit static transport restoration let the same changed-MAC worker fail-stop while kernel expiry revoked old/new dual-family qualification. Normal restore, combined worker/controller death, delayed post-expiry apply, no-refresh under traffic, refused rearm and candidate replay denial all passed with existing/new administration preserved. Kernel `6.17.0-1022-azure`. No previous failed job was rerun unchanged.

Time job `111459213731` passed all fifteen records at 23:40:42 JST. Every one of four fresh phases measured +4/+4 accepted samples and burst_finished=true. Raw delay-deviation rejections still occurred (e.g. ten primary rejections cumulatively by IPv6 origin preparation), demonstrating accepted acquisition without disabling rejection. This is acceptance of bounded preparation, not proof that shared-runner timing variance is gone. The remaining full regression jobs were still completing when this targeted evidence was recorded; final-head all-five-workflow/22-job acceptance and merge/main receipts belong in PR #195.


## Guarded admission follow-up (PR #196, not merged)

An explicit CI-only `time-lease` profile now requires fixed guard installation before worker readiness. Installation uses create-table semantics, starts an immutable monotonic deadline before the transaction, and seals the full two-table readback retaining object handles. Receipts bind attempt/version/boot/netns/interface identity. Before publishing worker readiness and at both controller admission checks, the guard must still contain its live timed member, match the sealed policy/handles and retain at least two seconds on the original deadline. Only counters and decreasing member expiry are normalized. Maintenance restoration does not depend on a live lease. Legacy `time` and negative controls are unchanged.

This trusts successful fixed installation and assumes no concurrent privileged writer during installation/readback. It is not independent semantic attestation of arbitrary existing tables. Same-handle element recreation by root, post-read privileged edits, reboot/suspend and dynamic profiles remain unqualified; kernel expiry still covers final-check/commit process-loss races only while the guard is intact.

Head `aa73bae115810b392a83fcde50057ff840175d3a`, regression `37248051381`, job `111569789198`: all 35 records passed (original 20, five guarded cases × three) at 2026-10-05 09:36:01 JST. The same head's existing time job `111569789371` failed IPv4 origin-prime with +3 primary accepted samples against required +4 and raw delay-deviation rejections. This blocks merge despite targeted guard acceptance; see WORK_RESUME.md and PR #196. A documentation rerun is not evidence of a timing repair.


## Dynamic guarded profiles (2026-10-05)

The renderer accepts only fixed `time`, `dhcp4` and `ra6` profiles. DHCPv4 uses 192.0.2.10→192.0.2.2; RA uses 2001:db8:6::10→2001:db8:7::2. Each single-family profile keeps separate inet/netdev guard tables, eight-second timed TCP/443 membership and unconditional remaining TCP/443 drop, with no dynamic endpoint adoption or rearming. The guard does not decide DHCP/RA/ARP/ND permissions: the unchanged underlying restricted profile does. Explicit `dhcp4-lease` and `ra6-lease` admission paths require this profile's receipt and snapshot.

The new job observes kernel expiry while a 22-second worker still waits and candidate tables remain, then requires that the same worker restore maintenance despite the expired lease. DHCP renew/rebind, periodic RA route refresh, dynamic ARP/ND, management preservation and legitimate RA route expiry are measured. This extends synthetic composition; it is not a live installer or proof of arbitrary addressing changes. Original unguarded negative controls and static lease jobs remain mandatory. Exact acceptance is recorded in the PR and work records.


Code head `d866cd4d2fc4debab8a96395ea9bea76378231d3`, tree `e3b6e72f3e66fe9101d8843165100cb4dac85adb`, regression `37250237810`, dynamic lease job `111576217409`: all twelve records passed at 10:10:34 JST. IPv4 kernel-expiry denial with ongoing renewal/admin/neighbors was observed at 10:09:10, then the same PID 1 worker restored maintenance at 10:09:24. IPv6 expiry/RA-refresh/admin/ND passed at 10:10:00 and late worker restore at 10:10:08. Post-restore DHCP rebind and IPv6 RA refresh/actual route expiry passed; guard handles were unchanged. Time job `111576217426` passed all fifteen records with actual interleaved/kernel TX evidence at 10:10:02. Existing static guard job also succeeded. Local 3 dynamic-lease + 6 lease + 6 shared + 8 context tests passed (23). Final-head all-five-workflow/23-job acceptance and independent main receipts belong in PR #197: https://github.com/bzlove178100/-keirin-ai-web/pull/197 . No live activation.


## DHCP-delivered DNS composition (2026-10-05)

`dhcp-dns-lease` reuses the fixed `dhcp4` tuple and preserves the original DHCP-DNS base policy. This is a separate admission choice requiring the existing prepared guard receipt, not a change to legacy unguarded negative controls. No DNS server is promoted based on observation. A separate mandatory job runs the real private networkd/resolved/bus lifecycle with an eight-second guard and 22-second restoring worker.

The guarded case requires expiry before restoration while candidate shape and worker identity remain, with old/new TCP/443 denied but fresh approved A/AAAA queries and existing/new management intact. It then observes actual DHCP DNS change, denied unapproved traffic, maintenance restoration after guard expiry, approved DNS return using the same daemons, killed/mixed collector rejection and real DHCP expiry. Guard handles must remain unchanged throughout and both guards are removed by fixture teardown. The legacy case and its exact negative transaction checks remain mandatory. Code head `497cb60c6281d20029bf00ced482b3d2e8ee58c9`, tree `2e9701620623998ef9decf58ee8e48817ceb14ba`, regression `37252034264`, guarded DNS job `111581475013`: all 21 records passed at 10:37:20 JST. Kernel-expiry denial with candidate rules, the same live worker, fresh approved A/AAAA queries and management was observed at 10:36:10; actual DHCP unapproved-DNS delivery remained denied at 10:36:17; PID 1 maintenance restoration after expiry passed at 10:36:23. Same-daemon approved return, killed/mixed collectors, genuine DHCP address/route/DNS withdrawal and unchanged guard handles through full cleanup also passed. The legacy DHCP-DNS, dynamic guard and time jobs succeeded. Local 17 related tests passed. No failed attempt or identical rerun occurred. Final-head all-five-workflow/24-job and independent main receipts belong in PR #198: https://github.com/bzlove178100/-keirin-ai-web/pull/198 .
