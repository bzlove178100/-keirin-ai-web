# DHCPv4 DNS delivery and interrupted observation — CI only

Updated: 2026-10-04 (Asia/Tokyo).

## Boundary

This fixture composes the installed real networkd and resolved in one private
mount/network environment, generated read-only `/etc`, private `/run` and `/var`,
fresh read-only sysfs, and a private D-Bus daemon with no activation directories.
The host resolver configuration is fingerprinted before/after, all child process
namespaces/executables are checked, and unit/cgroup/process/file cleanup is required.
All work uses documentation addresses on a disposable Ubuntu CI runner.

DHCP option 6 carries one fixed DNS address. Networkd has `UseDNS=yes`; resolved
receives its state through the shared private networkd runtime. The fixture never
calls SetLinkDNS. Vendor network profiles and configuration drop-ins are masked.
The container marker needed by Ubuntu networkd exists only in its private runtime.
The synthetic DHCP server records the acknowledged address and its own test epoch;
the epoch is a fixture control value, not a DHCP generation identifier.

Only the primary documentation address is permitted for UDP/TCP DNS. The existing
actual-ARP/DHCP bootstrap rules are retained, unused NTP access is removed, and both
table shapes are compared throughout. A changed DHCP DNS address does not modify
the policy. Private cache flushing is explicit where fresh upstream evidence is
required; this slice does not repeat or expand the previous cache/TTL qualification.

## Required real-kernel acceptance (twelve records)

1. Both DNS peers answer A/AAAA before restrictions; neighbors are then flushed.
2. Real DHCP acquisition/ARP yields the DNS lease and matching resolved DNSEx.
3. Actual networkd Describe reports DHCPv4 and its provider; the existing immutable
   reader parsers and pure comparison accept the selected private observations.
4. Stub A/AAAA, including TCP client transport, generate fresh upstream events.
5. SIGKILL a separate collector after its first manager read: partial exists,
   complete does not; administration and the policy survive.
6. Change DHCP DNS during a paused collection and wait for an actual renewal,
   lease change and DNSEx change. The collector must reject its changed bracket,
   exit unsuccessfully and publish no completed observation.
7. A new completed observation of the changed source requires review; all
   qualification/mutation/apply/freshness flags remain false.
8. The unapproved DNS source fails within the client's fixed deadline, increments
   output drops and receives no packets. Policy and administration remain intact.
9. Actual DHCP renewal returns the approved source. Drain existing private DNS
   transactions with a bounded wait, flush private cache and require fresh changed
   A/AAAA answers. Original daemon identities and administration remain intact.
10. Silent DHCP server causes real expiry: address, default route, lease DNS and
    DNSEx disappear. Empty resolver observations are blocked; fresh query fails
    without reaching either upstream. Expired administration becomes unreachable.
11. Shared private resolver/networkd/bus processes, cgroup and files are removed.
12. Peer, virtual links and both owned rulesets are removed.

The source-return drain uses the bounded behavior established by PR #188; it does
not imply that a configuration update cancels an existing transaction instantly.

## Observation scope

Each collection uses a fresh UUID and a separate process. A complete result is
published by rename only after all reads and checks. A killed collector's partial
file is never consumed as complete. The result binds collector PID, monotonic
start/end (at most four seconds), boot ID, service PID/start time/executable,
network and mount namespaces, cgroup, interface index/name/MAC, private bus inode,
and lease/link file inode/mtime/content hashes. Resolved DNS is read before and
after the networkd read; private file and identity brackets must match.

This detects the tested interruption and renewal. Equal brackets do not establish
an atomic snapshot, authenticated DHCP origin, correctness against arbitrary root
writers, future freshness or a trusted production collector. File reads are not an
atomic transaction with D-Bus. No live reader code is modified or invoked. The
existing comparison's `freshness_verified`, `apply_allowed`, `qualification` and
`mutation` remain false even for a successful collection. No policy is generated
from observations.

## Source review and evidence

Primary upstream v255 source inspected through the GitHub API:

- [resolved-link.c](https://github.com/systemd/systemd/blob/v255/src/resolve/resolved-link.c),
  blob `dd5daddce486f166f2123a46d2ebcca06c89e413`: per-link DNS is read using
  `sd_network_link_get_dns`; no private SetLinkDNS simulation is needed here.
- [networkd-json.c](https://github.com/systemd/systemd/blob/v255/src/network/networkd-json.c),
  blob `eed8d9f7879aa481403b5eaf720f9ebb18077b77`: DNS records contain configuration
  source/provider and omit zero port fields. Runtime tests bind actual installed
  binaries by SHA-256 and record package version/kernel; upstream source alone is
  not evidence of installed behavior.

Five new, six resolver, fourteen comparison and five DHCP tests pass locally
(30 total), plus `git diff --check`.

Code head `7638dcc6000d9921752333caf3f0f6b4293a23c8`, regression `37178001953`, new job `111364577877`, passed all twelve acceptance records and `SYNTHETIC_DHCP_DNS_OBSERVATION_OK_NO_LIVE_APPLY` at 04:48:17 UTC on October 4 (13:48 JST). Installed systemd is `255.4-1ubuntu8.17`, kernel `6.17.0-1022-azure`; networkd SHA-256 `12e65fbae70b7cf17a84299c5323eb0735309c2891d3caea321a4ad2093f8c19`, resolved `5e694042ba4bad6c29584334eeb5b06c6abdab17a84d96718dd286e41bff322d`, dbus-daemon `8c479f1fcddfd6693c736ce541da0955f6752834bdeeef4b928e27f5e974c247`. Real acquisition, origin agreement, stub A/AAAA/TCP, SIGKILL partial rejection, renewal-during-collection rejection, unapproved-source denial without widening, approved return with unchanged daemon identities/admin, expiry withdrawal and full cleanup passed. Four completed collection windows were 24.878015, 23.923450, 24.856132 and 23.621945 milliseconds; three had matching selected facts and the expired observation was blocked as EMPTY_RESOLVER_SET. The separate resolver job `111364577855` also reproduced all eighteen previous acceptance records. Other workflows/jobs were still running when this targeted evidence was recorded; all five final-head workflows and nineteen regression jobs remain the merge gate. No failure/retry occurred in this code-head acceptance.

Exact final-head workflow/job results and merge receipt belong in PR #189.

## Remaining boundary

DHCPv6 DNS, NSS, production observation, simultaneous route/RA/PMTU lifecycle and
combined DHCP DNS changes with controller-death restoration are not qualified.
The earlier eighteen-record resolved recovery fixture remains mandatory. Initial
restricted installation, independent rescue for wrong shared allowances, reboot,
non-cooperating writers and worker death after readiness remain blocked. Installed
Ubuntu DHCPv6 remains unqualified. No phone/AWS/SSH/live host/credential action;
H2a and all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/
report gates remain OFF.
