# Dynamic configuration with independent restricted recovery

Prepared 2026-10-03 (Asia/Tokyo). Disposable CI only; no live installer.

PR #181 merged at `1dd5666d779d82793b63d4a838b023ce1247d7ed` after all
five final-head workflows and fourteen regression jobs passed. Its routed
PMTU evidence stays accepted. The previous watchdog used static addresses;
passing separate DHCP/RA jobs did not establish that dynamic configuration
survives that watchdog's policy replacement.

The new mandatory job composes two separate fixed cases: installed networkd
DHCPv4 and installed networkd IPv6 RA/SLAAC/ND. The existing isolated protocol
and watchdog jobs stay intact. DHCPv6's pinned patched build and routed PMTU
are **not yet composed** with this recovery worker. Installed Ubuntu DHCPv6
remains unqualified; no earlier failure is reclassified as a success.

## Policy and supervision

Each case creates sender/peer namespaces and a veth pair, with no outside
link. Only the peer has fixed synthetic addresses. The sender acquires its
address and route dynamically; it has no permanent neighbor entries. The
existing protocol fixture provides the exact maintenance rules in both
inet and netdev, including default denial and bounded control allowances.
The temporary qualification profile adds only outgoing TCP/443 and its
responses to one fixed fixture endpoint in both layers.

Both expected rule shapes are compiled before networkd or application
listeners exist. The real lifecycle begins in restricted maintenance. A
separate systemd service, parent PID 1, enters that test's network namespace.
It verifies the anchor, loads expected shapes into memory and publishes
readiness atomically with a monotonic deadline, PID and process start time.
The controller checks a pidfd, start time and namespace under a cooperating
flock, applies qualification in one nft transaction, then dies by SIGKILL.
The observing parent never performs the successful recovery operation.

At its deadline the worker checks **both** owned table shapes. Expected
qualification becomes exact restricted maintenance using one nft transaction
covering both tables. Existing maintenance is a no-op. Drift in either table
stops without replacement. nft handles and anonymous counter packet/byte
measurements are excluded from comparison; rule order, verdicts, matches,
limits, named-counter identities and other policy properties are retained.
Real control traffic changes those measurements throughout the test.

The fixed worker windows are 5 or 22 seconds. Units have Restart=no,
RuntimeMaxSec=35, TimeoutStopSec=2 and KillMode=control-group. Existing networkd
isolation supplies a private mount namespace, private /run, read-only fixture
configuration and a fresh read-only sysfs; it does not control the CI host's
network. RPC lines, events, process waits, commands and the 5-minute CI job
are bounded. Only unique owned units/directories and fixed private links and
tables are removed; final state must be loopback-only and an empty ruleset.

## Required measured cases

| Case | Required evidence |
| --- | --- |
| Dynamic anchor | Real DHCP lease/address/default route or usable SLAAC address/RA route, with existing and new administration connections; qualification is denied |
| Controller death after apply | SIGKILL exit code, candidate table readback and real established qualification exchange |
| Controls while controller is dead | Actual acknowledged DHCP Renew under candidate; or recurring RA beyond one original lifetime, plus fresh ND resolution, under candidate |
| Independent restore | PID 1 worker result, both tables restored, old and new qualification flows denied, old and new administration preserved, unrelated table unchanged |
| DHCP after restore | Actual acknowledged Renew then unanswered primary Renew and broadcast Rebind accepted by the approved alternate, lease-file server readback, link-counter evidence and wrong-source DHCP frame rejection |
| IPv6 after restore | RA refresh beyond a full lifetime, dynamic ND rediscovery, three invalid RA variants rejected, then stopping RA removes the default route/off-link access without opening qualification |
| Worker death before apply | Actual worker SIGKILL, MainPID becomes zero, controller refuses stale readiness and performs no qualification mutation |
| Controller death before apply | Worker sees maintenance and does not replace it |
| Either-table drift | Separate actual inet and netdev unexpected rules cause fail-stop, with changed shapes left untouched; observing fixture resets only for its own next test |
| Cleanup | Units stopped, MainPID zero, peer reaped, owned files/links/rules removed |

Local guards are not kernel proof. Changed-head CI and all five final-head
workflows must succeed before integration; run/job IDs and actual results
are recorded in the PR and handoff after execution.

## Limits and next work

pidfd/readiness checks narrow the pre-apply failure window; they do not prove
the worker cannot die immediately after its last check or after apply. A
cooperating flock is not an nft generation compare-and-swap against another
root writer. These synthetic files are not authenticated persistent recovery
manifests. No reboot/power-loss recovery, first maintenance installation or
recovery from an incorrect shared administration allowlist is established.
Fail-stop on drift may leave qualification active; it is not claimed to be
successful revocation. That case requires a separate operational design.

DHCP address renumbering, lease expiry in this composition, DHCPv6 and PMTU
composition, full DNS/time protocols and lifecycle, multi-source live
administration, unknown provider changes and live deployment remain outside
this slice. TCP echo is transport evidence, not SSH authentication. Control
header allowlists do not authenticate a DHCP server or router. Existing
isolated expiry/DAD/error tests remain useful within their original scope.

Next compose the separately qualified DHCPv6 build and routed PMTU with
recovery, then resolve DNS/time and the first-install recovery design. No
repeated phone observation, AWS/SSH change, credentials or live activation.
H2a and every runtime/provider/credential/prediction/DB-write/data-fetch/
scheduler/report gate remain OFF.
