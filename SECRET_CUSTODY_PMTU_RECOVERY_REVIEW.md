# Routed PMTU after independent restricted recovery

## Scope and acceptance

CI-only fixed documentation networks, no installer or live profile. Reuse the real sender/router/receiver namespaces and the PID 1 supervised worker. The original standalone PMTU case remains mandatory in `custody-routed-pmtu`; the composition runs in a fresh outer namespace.

1. Compile maintenance/qualification shapes before opening management/bulk connections. Qualification adds only the fixed peer TCP/443 tuple to both inet and netdev. No broad established allowance.
2. Open the management and bulk sockets under maintenance at MTU 1500. Arm the existing worker, apply qualification through a controller which kills itself with SIGKILL, and require actual TCP/443 exchange.
3. Keep exchanging on both original TCP/22 sockets while waiting for PID 1's worker. Require `RESTORE_MAINTENANCE`, exact two-table readback, old/new TCP/443 failure and existing/new management success. The same bulk socket must still have socket/TCP PMTU 1500.
4. Run all original wrong-source, wrong-code, unrelated-flow and out-of-window TCP quote tests after restoration, including link/inet counters and the kernel sequence-rejection counter.
5. Lower the real router's outgoing and receiver link MTU to 1280. Blocking real related PMTU errors must stall the queued 65,536-byte transfer with PMTU still 1500. Admit those errors, then require full delivery on the same socket, socket/TCP PMTU 1280, reduced MSS and unfragmented wire packets at most 1280 with 1280 observed.
6. Recheck restored rule shape (excluding handles/counter measurements only) and old/new qualification denial. Existing namespace/process/link/table cleanup and worker unit/directory cleanup are mandatory.

There are sixteen composition acceptance records (eight per family), in addition to the ten standalone records. These are assertions to run, not success claims until CI evidence is recorded.

## Limits and remaining work

The MTU reduction occurs after restoration. This does not qualify a route change during the nft transaction, simultaneous DHCP/RA/PMTU lifecycles, DNS/time, first maintenance installation, a wrong shared allowlist, reboot, worker death after the last readiness check or non-cooperating root writers. The fixture uses static routes/neighbors. Installed Ubuntu DHCPv6 remains unqualified; only the previously pinned patched CI build has its separately recorded evidence.

H2a and all live/provider/runtime/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF. No phone, AWS, SSH, live host or credential action.

## Evidence

Pending local and CI validation. All five workflows for the exact final head must pass before integration; final run IDs and merge receipt belong in the PR.
