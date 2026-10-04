# Kernel qualification lease — unactivated synthetic implementation

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
