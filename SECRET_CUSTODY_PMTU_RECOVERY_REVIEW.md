# Routed PMTU after independent restricted recovery

## Scope and acceptance

CI-only fixed documentation networks, no installer or live profile. Reuse the real sender/router/receiver namespaces and the PID 1 supervised worker. The original standalone PMTU case remains mandatory in `custody-routed-pmtu`; the composition runs in a fresh outer namespace.

1. Compile maintenance/qualification shapes before opening management/bulk connections. Qualification adds only the fixed peer TCP/443 tuple to both inet and netdev. No broad established allowance.
2. Open the management and bulk sockets under maintenance at MTU 1500. Arm the existing worker, apply qualification through a controller which kills itself with SIGKILL, and require actual TCP/443 exchange.
3. Keep exchanging on both original TCP/22 sockets while waiting for PID 1's worker. Require `RESTORE_MAINTENANCE`, exact two-table readback, old/new TCP/443 failure and existing/new management success. The same bulk socket must still have socket/TCP PMTU 1500.
4. Run all original wrong-source, wrong-code, unrelated-flow and out-of-window TCP quote tests after restoration, including link/inet counters and the kernel sequence-rejection counter.
5. Lower the real router's outgoing and receiver link MTU to 1280. Blocking real related PMTU errors must stall the queued 65,536-byte transfer with PMTU still 1500. Admit those errors, then require full delivery on the same socket, socket/TCP PMTU 1280, reduced MSS and unfragmented wire packets at most 1280 with 1280 observed.
6. Recheck restored rule shape (excluding handles/counter measurements only) and old/new qualification denial. Existing namespace/process/link/table cleanup and worker unit/directory cleanup are mandatory.

There are sixteen composition acceptance records (eight per family), in addition to the ten standalone records. All passed in the code-head run recorded below.

## Limits and remaining work

The MTU reduction occurs after restoration. This does not qualify a route change during the nft transaction, simultaneous DHCP/RA/PMTU lifecycles, DNS/time, first maintenance installation, a wrong shared allowlist, reboot, worker death after the last readiness check or non-cooperating root writers. The fixture uses static routes/neighbors. Installed Ubuntu DHCPv6 remains unqualified; only the previously pinned patched CI build has its separately recorded evidence.

H2a and all live/provider/runtime/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF. No phone, AWS, SSH, live host or credential action.

## Evidence

Code head `ed5e49640688e2384ae95016a170be795b271dd8` passed all sixteen composition acceptance records in regression run `37162795373`, PMTU job `111319533837`, on kernel `6.17.0-1022-azure`. The ten standalone records also passed. For both families the independently restored bulk socket still reported PMTU 1500; subsequent real router errors quoted 1500-byte packets and announced MTU 1280. Blocking them stalled the transfer, and admitting them delivered all 65,536 bytes on the same socket. IPv4 MSS changed 1448→1228, IPv6 1428→1208, with actual unfragmented wire packet lengths at most 1280 and 1280 observed. Post-restoration forged-error rejection, restored shape, old/new qualification denial, management survival and cleanup passed. The composition ended with `SYNTHETIC_PMTU_INDEPENDENT_RECOVERY_OK_NO_LIVE_APPLY` at 23:46:31 UTC on October 3 (08:46 JST on October 4). Fourteen local tests and `git diff --check` passed. All five code-head workflows succeeded, including all fifteen regression jobs in run `37162795373`. All five workflows for the exact final head must pass before integration; final run IDs and merge receipt belong in the PR.


The first evidence-only head `d56f6fb9c4d21776e94cacafffad3efbb7c81853` passed PMTU again but failed existing H2d job `111320627742` in run `37163162130`. Invalid probe output was correctly rejected as `PROCESS_EVIDENCE_INVALID`; cleanup then replaced that error with `PROCESS_RESET_FAILED`. The log does not contain reset stderr/state, so transient-unit collection between ownership readback and reset is a hypothesis, not a proven diagnosis of that historical run. H2d cleanup now tolerates a nonzero reset only when a new manager readback verifies `LoadState=not-found`; existing directory/cgroup absence checks still run. A retained or unreadable unit still fails. Two local tests cover absent/retained units and remaining cgroups. A real-systemd test forces collection between readback and the actual stale reset, requires its nonzero exit, preserves the original rejection and verifies cleanup. The probe exits nonzero on SIGTERM so the test retains the failed unit until intentional collection. Fourteen H2d local tests pass (28 total with the PMTU/helper checks). Corrected-head CI remains required; no assertion was skipped and no blind rerun was used.
