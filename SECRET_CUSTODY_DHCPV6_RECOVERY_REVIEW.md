# Patched DHCPv6 through independent restricted recovery

Prepared 2026-10-04 (Asia/Tokyo). Isolated CI only; no live installer.

PR #182 merged at `a8cb390df54b1c183623cfee31d7c905eef8dc39`; all five final-head workflows succeeded. Its DHCPv4 and RA/ND recovery evidence remains accepted. This slice extends the same PID 1 worker with one fixed `dhcp6` profile, preserving the already-tested two-table transaction, ownership comparison, readiness, deadlines and cleanup.

The target remains the hash-verified, minimal patched CI networkd build from PR #180. The installed Ubuntu DHCPv6 client is still unqualified. The workflow retains both the unpatched typed-timer-defect negative control and the standalone full patched lifecycle. It then runs this composition in fresh private network/mount/runtime namespaces using the same verified build. No installed binary is replaced; existing final cleanup removes only owned builds and verifies the installed SHA-256.

The helper compiles exact maintenance and qualification table shapes before the real client starts. Qualification adds only one outgoing synthetic TCP/443 tuple and its responses to both inet and netdev. Initial DHCPv6 acquisition, RA routing and distinct T1/T2 validation are unchanged. After the controller applies qualification and dies by SIGKILL, the real client must perform a newly observed Renew, refresh its actual address lifetime and increment both layers' DHCP counters. Qualification remains usable until the independent worker's deadline.

The PID 1 worker restores both tables in one nft transaction. Existing and new qualification flows must fail, while existing and new administration transports survive. A wrong-source DHCPv6 frame must be visible at ETH_P_ALL but denied before a protocol-specific packet socket, with the netdev denial counter incremented. This is header-filter evidence, not DHCP authentication.

The peer event list is then cleared without restarting the client or server. The original mandatory lifecycle now requires a fresh post-restoration Renew, unanswered primary Renew, Rebind to the approved alternate DUID, a subsequent Renew naming that alternate, real address-lifetime refresh and eventual address expiry while RA routing remains. After expiry, the restored table shapes must still match maintenance and qualification stays denied. Existing cleanup must remove units/processes/links/tables and owned files.

## Validation boundary

Two new guard tests plus six shared recovery and nine DHCPv6 tests pass locally (17 total). Kernel/systemd composition and all five final-head workflows must pass before integration. Actual run IDs, observations and any failure diagnosis will be recorded in the PR and handoff; local tests alone do not qualify the composition.

## Limits and next step

The profile does not change the client's implementation or qualify an installed/vendor-supported DHCPv6 remedy. This multicast-only synthetic server does not advertise Server Unicast. Exact rules do not authenticate providers. Renumbering, unknown providers, non-cooperating root writers, worker death after its last readiness check, reboot and incorrect shared allowlists remain outside this fixture. The inherited drift behavior is fail-stop and can leave qualification active; it is not successful revocation.

Next compose routed IPv4/IPv6 PMTU with independent recovery. DNS/time lifecycle and a first maintenance-installation recovery design remain unresolved. No phone, AWS, SSH, live host or credential operation. H2a and all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates stay OFF.
