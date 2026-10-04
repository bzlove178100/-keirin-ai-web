# Recovery readiness context and worker-loss boundary — CI only

Prepared: 2026-10-04 (Asia/Tokyo). No live installer or activation.

## Problem and change

PR #192 proved restricted rescue from wrong shared primary allowances and a
blocked outcome for a broken separate path. It did not bind recovery readiness
to a boot/interface identity, or exercise worker death immediately around the
controller's last readiness check. PID/start/netns checks alone do not make
process liveness and an nft transaction atomic.

The shared dynamic CI worker now binds an unpredictable per-attempt ID, fixed
profile, boot ID, network namespace, and each required interface's name, ifindex,
MAC and veth kind. All profiles require host0; rescue also requires rescue0.
The expected context is loaded into worker memory before readiness publication.
The controller compares the ready binding to its expected attempt/context and
checks actual context and worker pidfd/start/netns. After table-shape comparison,
it repeats readiness immediately before the nft transaction. The worker checks
context before publication and at its deadline, and immediately before restoring
both tables. Changed/missing/unreadable context stops without replacement and
publishes STOP_RECOVERY_CONTEXT_CHANGED at the deadline.

Dynamic addresses, routes, leases, MTU and administrative link up/down are not
interface identity. In particular, PR #192's broken rescue link still permits
shape restoration but must fail its independent transport verifier. Every
existing protocol/composition job remains mandatory. Windows remain 5/22 seconds,
RuntimeMaxSec 35, and no existing assertion or deadline is relaxed.

## Five mandatory real cases, fifteen records

Each case has three records: restricted baseline with live old/new administration
and a matching ready context; its fault/positive result; complete owned cleanup.
Each runs in a separate bounded process/network namespace with a static synthetic
peer, so DHCP timing and listener reuse do not obscure the identity/process fault.

| Case | Required measured result |
| --- | --- |
| Stable context | Real PID 1 worker restores both tables after controller SIGKILL, denies old/new qualification and retains old/new administration |
| Same-name replacement | Rename original host0 and create a new host0 with the same MAC but a different ifindex; controller refuses apply and worker stops at deadline without overwriting either current table |
| MAC changes after apply | Real MAC change with unchanged candidate rules; worker refuses replacement, and actual old/new qualification remains active. Report BLOCKED/RECOVERY_CONTEXT_CHANGED |
| Worker dies after first check | Pause a CI controller after successful preflight, SIGKILL the worker and observe MainPID zero/process absence, then resume; the final readiness check rejects apply and restricted maintenance remains |
| Worker dies after final check | Pause after the last successful check, SIGKILL the worker and observe absence, then resume; candidate applies and controller dies. Beyond the worker's original deadline, no result/restoration exists and actual old/new qualification remains active. Require BLOCKED/WORKER_LOST_RECOVERY_UNVERIFIED |

The two scheduling barriers exist only in the new explicit CI child via a
temporary wrapper. The ordinary controller and worker have no barrier environment
hook. This reproduces a possible scheduling order, not its real-world frequency.
The last case is evidence of an unresolved recovery gap, deliberately required
to block; it is not a successful restoration test. The observing parent destroys
only its owned test resources afterward, never claiming that as recovery.
BLOCKED flags are authorization/qualification flags, not claims that no earlier
candidate mutation occurred. An unrelated table must remain unchanged.

## Validation and integration gate

Eight new negative/contract tests, six shared recovery, six rescue and seven
chrony tests pass locally (27 total). Tests reject stale/legacy attempt bindings,
changed boot/netns/index/MAC/kind, missing/unreadable context, nonfinite deadlines,
and final-check failure before mutation. Actual reboot and PID reuse are not
performed. A twenty-first mandatory regression job requires all fifteen records.
Code-head real CI acceptance passed below; all five final-head workflows and twenty-one
regression jobs are required before merge. Exact results and merge receipt belong
in the PR and subsequent handoff.

## Observed code-head evidence

Code head `cf623fd4fc106eaa0640ba2a3180734aa07dea75` (tree `10341d9f5eea121e4e08e1d61136ccaf6ef2f73e`), regression `37191566578`, context job `111404653037`, passed all fifteen records on its first execution, with `SYNTHETIC_RECOVERY_CONTEXT_OK_LAST_CHECK_GAP_UNQUALIFIED` at 2026-10-04 18:15:59 JST. The real same-name/same-MAC replacement changed ifindex 3 to 5 and was refused without table overwrite. Stable context restored/revoked old/new qualification and preserved administration. Post-apply MAC drift stopped restoration while actual qualification remained active. Worker loss after the first check was rejected before apply; loss after the final check allowed candidate installation/controller SIGKILL, then showed no recovery result after the original deadline plus one second and still-working old/new qualification. Both unsafe outcomes were explicitly BLOCKED with all authorization flags false. Each case cleaned up the worker/controller/peer, private files, links and owned tables, preserving the unrelated table until fixture teardown. Kernel `6.17.0-1022-azure`; no code-head retry or deadline relaxation.

The changed shared helper also passed the existing restricted rescue job on this code head; other protocol jobs were still completing when this evidence was recorded. All five workflows and twenty-one regression jobs on the final documentation head remain the integration gate. Exact final results and merge receipt belong in PR #193. This evidence demonstrates the last-check gap; it does not repair it or qualify first live installation.

## Remaining boundary and next step

This is a point-in-time identity comparison, not cryptographic device identity,
an immutable kernel interface generation, or a transaction across process liveness
and nft state. Arbitrary root writers, same-index/MAC reuse, drift after the last
comparison, actual reboot/persistence and authenticated live recovery remain
unqualified. Fail-stop after identity drift can leave qualification active, as
the real negative control requires. No additional worker or controller-driven
repair is silently introduced.

Next design a separately enforced lifetime for qualification, or an independent
recovery mechanism that remains effective after worker/controller loss, and test
that exact combined failure before considering first live installation. Do not
substitute repeated readiness checks for that lifetime guarantee. Historical
chrony rejection causes remain unproven; use retained baseline/ntpdata diagnostics
if they recur, without identical retry loops or deadline relaxation.

No phone/AWS/SSH/live-host/credential operation. Accepted phone evidence remains
accepted. H2a and every runtime/provider/credential/prediction/DB-write/data-fetch/
scheduler/report gate remain OFF.
